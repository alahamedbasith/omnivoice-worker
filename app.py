"""
app.py — FastAPI integration for the OmniVoice RunPod Serverless Endpoint
========================================================================
Exposes a /clone-voice endpoint that proxies to RunPod.

Endpoints
---------
POST /clone-voice        → returns the cloned audio (WAV) as a downloadable file
POST /clone-voice/base64 → returns the cloned audio as base64 JSON (for frontend playback)

Reference voice
---------------
By default it uses the bundled `basith-enhanced-v2.wav`. Send a multipart
`ref_audio` file to override it per-request.

Run
---
    pip install fastapi uvicorn httpx python-multipart
    uvicorn app:app --reload
"""

import asyncio
import base64
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

# ── Config ──────────────────────────────────────────────────────────────────────
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "YOUR_RUNPOD_API_KEY")
ENDPOINT_ID    = os.environ.get("RUNPOD_ENDPOINT_ID", "g2r3qa341vtyyd")
BASE_URL      = f"https://api.runpod.ai/v2/{ENDPOINT_ID}"
HEADERS       = {
    "Authorization": f"Bearer {RUNPOD_API_KEY}",
    "Content-Type": "application/json",
}
DEFAULT_REF_AUDIO = os.path.join(os.path.dirname(__file__), "basith-enhanced-v2.wav")

# Jobs longer than this (seconds) are sent async + polled instead of runsync.
SYNC_TIMEOUT = 90

app = FastAPI(title="OmniVoice API")


def _encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _build_payload(
    ref_audio_b64: str,
    ref_text: str,
    target_text: str,
    speed: float,
    denoise: bool,
    num_step: int,
    guidance_scale: float,
) -> dict:
    return {
        "ref_audio":   ref_audio_b64,
        "ref_text":    ref_text,
        "target_text": target_text,
        "speed":       speed,
        "denoise":     denoise,
        "num_step":    num_step,
        "guidance_scale": guidance_scale,
    }


async def _call_runsync(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=SYNC_TIMEOUT + 30) as client:
        resp = await client.post(f"{BASE_URL}/runsync", headers=HEADERS, json={"input": payload})
        resp.raise_for_status()
        return resp.json()


async def _call_run_async(payload: dict) -> dict:
    """Submit async job and poll /status until COMPLETED."""
    async with httpx.AsyncClient(timeout=30) as client:
        submit = await client.post(f"{BASE_URL}/run", headers=HEADERS, json={"input": payload})
        submit.raise_for_status()
        job_id = submit.json()["id"]

        while True:
            status = await client.get(f"{BASE_URL}/status/{job_id}", headers=HEADERS)
            status.raise_for_status()
            data = status.json()
            state = data.get("status")
            if state == "COMPLETED":
                return data
            if state in ("FAILED", "CANCELLED"):
                raise HTTPException(status_code=502, detail=f"RunPod job {state}: {data}")
            await asyncio.sleep(3)


async def _clone_voice(ref_audio: bytes, ref_text: str, target_text: str, **opts) -> bytes:
    payload = _build_payload(_encode_bytes(ref_audio), ref_text, target_text, **opts)

    try:
        result = await _call_runsync(payload)
    except httpx.ReadTimeout:
        # Fall back to async polling when the sync call exceeds the time limit.
        result = await _call_run_async(payload)

    output = result.get("output", {})
    if "error" in output:
        raise HTTPException(status_code=502, detail=output["error"])

    audio_b64 = output.get("audio_base64")
    if not audio_b64:
        raise HTTPException(status_code=502, detail=f"Unexpected response: {result}")
    return base64.b64decode(audio_b64)


@app.post("/clone-voice")
async def clone_voice(
    target_text: str = Form(...),
    ref_text: str = Form("Welcome back to this another part of the video."),
    ref_audio: Optional[UploadFile] = File(None),
    speed: float = Form(1.0),
    denoise: bool = Form(True),
    num_step: int = Form(32),
    guidance_scale: float = Form(2.0),
):
    if ref_audio is not None:
        ref_bytes = await ref_audio.read()
    else:
        with open(DEFAULT_REF_AUDIO, "rb") as f:
            ref_bytes = f.read()

    audio = await _clone_voice(
        ref_bytes, ref_text, target_text,
        speed=speed, denoise=denoise, num_step=num_step, guidance_scale=guidance_scale,
    )
    return Response(content=audio, media_type="audio/wav")


@app.get("/default-ref-base64")
async def default_ref_base64():
    """Return the bundled default reference voice as base64 (for direct-RunPod clients)."""
    with open(DEFAULT_REF_AUDIO, "rb") as f:
        return {"audio_base64": _encode_bytes(f.read())}


@app.post("/clone-voice/base64")
async def clone_voice_base64(
    target_text: str = Form(...),
    ref_text: str = Form("Welcome back to this another part of the video."),
    ref_audio: Optional[UploadFile] = File(None),
    speed: float = Form(1.0),
    denoise: bool = Form(True),
    num_step: int = Form(32),
    guidance_scale: float = Form(2.0),
):
    if ref_audio is not None:
        ref_bytes = await ref_audio.read()
    else:
        with open(DEFAULT_REF_AUDIO, "rb") as f:
            ref_bytes = f.read()

    audio = await _clone_voice(
        ref_bytes, ref_text, target_text,
        speed=speed, denoise=denoise, num_step=num_step, guidance_scale=guidance_scale,
    )
    return {"audio_base64": base64.b64encode(audio).decode("utf-8")}
