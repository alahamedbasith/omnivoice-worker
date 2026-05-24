"""
VoiceService — OmniVoice voice-clone inference wrapper
=======================================================
Differences from the original (Gradio) version:
  • No Gradio imports.
  • Model loads from RUNPOD_VOLUME_PATH env var so it works
    both locally and on the RunPod network volume.
  • Output files go to /tmp (ephemeral; handler deletes them after use).
  • load_asr=False  →  ASR weights never loaded  →  saves ~1-2 GB VRAM/RAM.
"""

import os
import uuid
import torch
import soundfile as sf
import logging
from huggingface_hub import snapshot_download
from omnivoice import OmniVoice
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Where the model lives ─────────────────────────────────────────────────────
# RunPod mounts your network volume at /runpod-volume by default.
# Override by setting OMNIVOICE_MODEL_DIR env var during local testing.
DEFAULT_MODEL_DIR = os.environ.get(
    "OMNIVOICE_MODEL_DIR",
    "/runpod-volume/omnivoice_model"   # path on the RunPod network volume
)


class VoiceService:
    """Singleton wrapper around the OmniVoice voice-clone model."""

    _instance = None

    @classmethod
    def get_instance(cls) -> "VoiceService":
        """Load the model exactly once; reuse for all subsequent jobs."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR):
        self.model_dir  = model_dir
        self.output_dir = "/tmp/omnivoice_outputs"
        os.makedirs(self.output_dir, exist_ok=True)

        # ── Device / dtype ──────────────────────────────────────────────────
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype  = torch.float16 if self.device == "cuda" else torch.float32
        logger.info(f"[VoiceService] device={self.device}  dtype={self.dtype}")

        # ── Download model if not already cached on the volume ──────────────
        # This runs on the FIRST cold start only.
        # Subsequent workers on the same volume find the model already there
        # and skip straight to loading.
        #
        # REAL repo file list (k2-fsa/OmniVoice, verified May 2026):
        #   model.safetensors                   2.45 GB  ← voice clone backbone (REQUIRED)
        #   audio_tokenizer/model.safetensors   ~0.8 GB  ← audio codec (REQUIRED)
        #   audio_tokenizer/config.json         tiny     ← codec config (REQUIRED)
        #   audio_tokenizer/preprocessor_config.json tiny (REQUIRED)
        #   config.json                         tiny     ← model config (REQUIRED)
        #   chat_template.jinja                 tiny     ← tokenizer template (REQUIRED)
        #   tokenizer.json                      tiny     ← text tokenizer (REQUIRED)
        #   tokenizer_config.json               tiny     ← tokenizer config (REQUIRED)
        #   README.md                           tiny     ← docs only (NOT needed)
        #   .gitattributes                      tiny     ← git metadata (NOT needed)
        #   audio_tokenizer/README.md           tiny     ← docs only (NOT needed)
        #   audio_tokenizer/.gitattributes      tiny     ← git metadata (NOT needed)
        #
        # Total download with allow_patterns: ~3.27 GB
        # Whisper ASR weights are downloaded SEPARATELY by omnivoice library
        # at runtime — load_asr=False below prevents that entirely.
        #
        # We use allow_patterns (whitelist) instead of ignore_patterns (blacklist).
        # Whitelist = only download exactly what we list. Nothing extra ever sneaks in.
        if not os.path.isdir(self.model_dir) or not os.listdir(self.model_dir):
            logger.info(
                "[VoiceService] Model not found on volume — downloading from "
                "HuggingFace (k2-fsa/OmniVoice). Total size ~3.27 GB. "
                "Takes ~5-8 min on first cold start."
            )
            snapshot_download(
                repo_id="k2-fsa/OmniVoice",
                local_dir=self.model_dir,
                # WHITELIST: download ONLY these files — nothing else
                allow_patterns=[
                    "model.safetensors",                        # main voice clone model
                    "config.json",                              # model architecture config
                    "chat_template.jinja",                      # tokenizer template
                    "tokenizer.json",                           # text tokenizer vocab
                    "tokenizer_config.json",                    # tokenizer settings
                    "audio_tokenizer/model.safetensors",        # audio codec weights
                    "audio_tokenizer/config.json",              # audio codec config
                    "audio_tokenizer/preprocessor_config.json", # audio preprocessor config
                ],
            )
            logger.info("[VoiceService] Download complete!")
        else:
            logger.info(f"[VoiceService] Model found at {self.model_dir} — skipping download.")

        # ── Load model into VRAM ─────────────────────────────────────────────
        logger.info("[VoiceService] Loading OmniVoice into memory...")
        try:
            self.model = OmniVoice.from_pretrained(
                self.model_dir,
                device_map=self.device,
                dtype=self.dtype,
                load_asr=False,        # ASR not needed  → saves ~1-2 GB
            )
            self.sampling_rate = self.model.sampling_rate
            logger.info(f"[VoiceService] Model ready! sampling_rate={self.sampling_rate}")
        except Exception as e:
            logger.error(f"[VoiceService] Failed to load model: {e}")
            raise

    # ─────────────────────────────────────────────────────────────────────────
    def clone(
        self,
        text:                 str,
        ref_audio:            str,
        ref_text:             str,
        speed:                Optional[float] = 1.0,
        denoise:              Optional[bool]  = True,
        guidance_scale:       Optional[float] = 2.0,
        num_step:             Optional[int]   = 32,
        duration:             Optional[float] = None,
        t_shift:              Optional[float] = 0.1,
        position_temperature: Optional[float] = 5.0,
        class_temperature:    Optional[float] = 0.0,
        layer_penalty_factor: Optional[float] = 5.0,
    ) -> str:
        """
        Run voice-clone inference.

        Parameters
        ----------
        text        : Text the synthesised voice should speak.
        ref_audio   : Path to the reference audio file (WAV/MP3, ≥3 s recommended).
        ref_text    : Transcript of ref_audio (required; ASR is disabled).
        speed       : Playback speed multiplier (0.5 – 2.0).
        denoise     : Apply denoising to the reference audio before use.
        guidance_scale : CFG guidance scale (higher → closer to ref voice).
        num_step    : Diffusion steps (more = better quality, slower).
        duration    : Force output duration in seconds (None = auto from speed).
        t_shift     : Time-step shift for the diffusion scheduler.
        position_temperature : Controls positional diversity.
        class_temperature    : Controls class diversity.
        layer_penalty_factor : Penalises repetitive layers in output.

        Returns
        -------
        str : Absolute path to the output WAV file in /tmp.
        """
        if not ref_text or not ref_text.strip():
            raise ValueError("ref_text is required (ASR is disabled).")

        logger.info(f"[clone] target='{text[:60]}...'  ref_audio={ref_audio}")

        # Build kwargs — only pass params that are not None so the model
        # can apply its own defaults for anything we don't override.
        kwargs: dict = {
            "text":      text,
            "ref_audio": ref_audio,
            "ref_text":  ref_text.strip(),
        }
        if speed                is not None: kwargs["speed"]                = speed
        if denoise              is not None: kwargs["denoise"]              = denoise
        if guidance_scale       is not None: kwargs["guidance_scale"]       = guidance_scale
        if num_step             is not None: kwargs["num_step"]             = num_step
        if duration             is not None and duration > 0:
                                             kwargs["duration"]             = duration
        if t_shift              is not None: kwargs["t_shift"]              = t_shift
        if position_temperature is not None: kwargs["position_temperature"] = position_temperature
        if class_temperature    is not None: kwargs["class_temperature"]    = class_temperature
        if layer_penalty_factor is not None: kwargs["layer_penalty_factor"] = layer_penalty_factor

        try:
            with torch.no_grad():
                audio_output = self.model.generate(**kwargs)

            # ── Convert tensor → numpy → write WAV ──────────────────────────
            waveform = audio_output[0]
            if isinstance(waveform, torch.Tensor):
                waveform = waveform.cpu().numpy()

            out_path = os.path.join(
                self.output_dir, f"clone_{uuid.uuid4().hex[:8]}.wav"
            )
            sf.write(out_path, waveform, self.sampling_rate)
            logger.info(f"[clone] Saved → {out_path}")
            return out_path

        except Exception as e:
            logger.error(f"[clone] Inference error: {e}")
            raise