"""
RunPod Serverless Handler for OmniVoice Voice Cloning
======================================================
This is the entry point RunPod calls for every inference job.
Flow: RunPod sends JSON → handler() runs → returns JSON with base64 audio.
"""

import runpod
import base64
import os
import tempfile

from voice_service import VoiceService

# ── Model loads ONCE when the worker container wakes up ──────────────────────
# RunPod keeps warm workers alive between jobs (configurable).
# This means the model is already in GPU VRAM for subsequent requests.
print("[handler] Warming up OmniVoice model... (first cold start may take ~10 min)")
vs = VoiceService.get_instance()
print("[handler] Worker ready to accept jobs.")


def handler(job: dict) -> dict:
    """
    Called by RunPod for every inference request.

    Expected input (job["input"]):
    {
        "ref_audio":   "<base64-encoded WAV/MP3>",   # REQUIRED
        "ref_text":    "What the speaker says",       # REQUIRED
        "target_text": "What you want them to say",   # REQUIRED

        # --- Optional tuning knobs ---
        "speed":                1.0,   # 0.5 – 2.0
        "denoise":              true,
        "num_step":             32,    # 8 – 64
        "guidance_scale":       2.0,   # 0.0 – 5.0
        "duration":             null,  # seconds, null = auto
        "t_shift":              0.1,
        "position_temperature": 5.0,
        "class_temperature":    0.0,
        "layer_penalty_factor": 5.0
    }

    Returns:
    {
        "audio_base64": "<base64-encoded WAV>",
        "format": "wav",
        "message": "Voice cloning successful"
    }
    OR on error:
    {
        "error": "<description>"
    }
    """
    job_input = job.get("input", {})

    # ── 1. Validate required fields ──────────────────────────────────────────
    ref_audio_b64 = job_input.get("ref_audio")
    ref_text      = job_input.get("ref_text", "").strip()
    target_text   = job_input.get("target_text", "").strip()

    if not ref_audio_b64:
        return {"error": "ref_audio (base64-encoded audio) is required."}
    if not ref_text:
        return {"error": "ref_text is required (ASR is disabled; type what the speaker says)."}
    if not target_text:
        return {"error": "target_text is required."}

    # ── 2. Decode reference audio to a temp file ─────────────────────────────
    # RunPod workers are ephemeral containers; /tmp is safe for short-lived files.
    ref_audio_path = None
    try:
        audio_bytes = base64.b64decode(ref_audio_b64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="/tmp") as f:
            f.write(audio_bytes)
            ref_audio_path = f.name
    except Exception as e:
        return {"error": f"Failed to decode ref_audio: {e}"}

    # ── 3. Read optional parameters (fall back to model defaults) ────────────
    speed                = job_input.get("speed",                1.0)
    denoise              = job_input.get("denoise",              True)
    num_step             = job_input.get("num_step",             32)
    guidance_scale       = job_input.get("guidance_scale",       2.0)
    duration             = job_input.get("duration",             None)   # None = auto
    t_shift              = job_input.get("t_shift",              0.1)
    position_temperature = job_input.get("position_temperature", 5.0)
    class_temperature    = job_input.get("class_temperature",    0.0)
    layer_penalty_factor = job_input.get("layer_penalty_factor", 5.0)

    # ── 4. Run voice cloning ─────────────────────────────────────────────────
    output_path = None
    try:
        output_path = vs.clone(
            text=target_text,
            ref_audio=ref_audio_path,
            ref_text=ref_text,
            speed=speed,
            denoise=denoise,
            num_step=num_step,
            guidance_scale=guidance_scale,
            duration=duration,
            t_shift=t_shift,
            position_temperature=position_temperature,
            class_temperature=class_temperature,
            layer_penalty_factor=layer_penalty_factor,
        )

        # ── 5. Encode output WAV as base64 and return ─────────────────────────
        with open(output_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        return {
            "audio_base64": audio_b64,
            "format": "wav",
            "message": "Voice cloning successful",
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        # Always clean up temp files regardless of success/failure
        if ref_audio_path and os.path.exists(ref_audio_path):
            os.unlink(ref_audio_path)
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)


# ── RunPod entry point ───────────────────────────────────────────────────────
runpod.serverless.start({"handler": handler})