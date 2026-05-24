"""
test_endpoint.py — Example client for the OmniVoice RunPod Serverless Endpoint
===============================================================================
Run this from your laptop / server AFTER you deploy the RunPod endpoint.

Usage:
    pip install requests
    python test_endpoint.py

What it does:
    1. Reads a reference WAV file from disk.
    2. Encodes it as base64.
    3. Sends a POST request to your RunPod endpoint.
    4. Decodes the returned base64 audio.
    5. Saves the output WAV to disk.
"""

import base64
import json
import time
import requests

# ─────────────────────────────────────────────────────────────────────────────
# ← FILL THESE IN
# ─────────────────────────────────────────────────────────────────────────────
RUNPOD_API_KEY    = "YOUR_RUNPOD_API_KEY"       # RunPod dashboard → Settings → API Keys
ENDPOINT_ID       = "YOUR_ENDPOINT_ID"           # RunPod dashboard → Serverless → your endpoint
REF_AUDIO_PATH    = "reference.wav"              # Path to your reference voice audio (≥3s)
REF_TEXT          = "Hello, this is my reference audio."   # What the speaker says
TARGET_TEXT       = "Welcome to our application. How can I help you today?"
OUTPUT_PATH       = "output_cloned.wav"
# ─────────────────────────────────────────────────────────────────────────────

RUNPOD_BASE_URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}"

HEADERS = {
    "Authorization": f"Bearer {RUNPOD_API_KEY}",
    "Content-Type": "application/json",
}


def encode_audio_file(path: str) -> str:
    """Read an audio file from disk and return it as a base64 string."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def decode_audio_to_file(b64_string: str, out_path: str) -> None:
    """Decode a base64 audio string and save it to disk."""
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64_string))


def run_sync(payload: dict) -> dict:
    """
    POST to /runsync — waits up to 90s for the result inline.
    Best for short jobs (<90s). Use run_async() for longer ones.
    """
    resp = requests.post(
        f"{RUNPOD_BASE_URL}/runsync",
        headers=HEADERS,
        json={"input": payload},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def run_async(payload: dict, poll_interval: float = 3.0) -> dict:
    """
    POST to /run (async) then poll /status/<id> until complete.
    Use this for jobs that may take >90 seconds.
    """
    # Submit job
    resp = requests.post(
        f"{RUNPOD_BASE_URL}/run",
        headers=HEADERS,
        json={"input": payload},
        timeout=30,
    )
    resp.raise_for_status()
    job_id = resp.json()["id"]
    print(f"  Job submitted: {job_id}")

    # Poll until done
    while True:
        time.sleep(poll_interval)
        status_resp = requests.get(
            f"{RUNPOD_BASE_URL}/status/{job_id}",
            headers=HEADERS,
            timeout=30,
        )
        status_resp.raise_for_status()
        data = status_resp.json()
        status = data.get("status")
        print(f"  Status: {status}")

        if status == "COMPLETED":
            return data
        elif status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Job {job_id} ended with status: {status}\n{data}")


def main():
    print("=== OmniVoice RunPod Endpoint Test ===\n")

    # ── 1. Prepare payload ────────────────────────────────────────────────────
    print(f"Reading reference audio: {REF_AUDIO_PATH}")
    ref_audio_b64 = encode_audio_file(REF_AUDIO_PATH)

    payload = {
        "ref_audio":   ref_audio_b64,
        "ref_text":    REF_TEXT,
        "target_text": TARGET_TEXT,

        # Optional — remove any you don't want to override
        "speed":                1.0,
        "denoise":              True,
        "num_step":             32,
        "guidance_scale":       2.0,
        "t_shift":              0.1,
        "position_temperature": 5.0,
        "class_temperature":    0.0,
        "layer_penalty_factor": 5.0,
        # "duration": null  ← omit to let the model decide length automatically
    }

    # ── 2. Call the endpoint ──────────────────────────────────────────────────
    print("Sending request to RunPod endpoint...")
    start = time.time()

    # Use runsync for quick jobs; switch to run_async if you get timeout errors
    result = run_sync(payload)
    # result = run_async(payload)   # ← uncomment for async polling

    elapsed = time.time() - start
    print(f"Response received in {elapsed:.1f}s\n")

    # ── 3. Handle response ────────────────────────────────────────────────────
    output = result.get("output", {})

    if "error" in output:
        print(f"ERROR from endpoint: {output['error']}")
        return

    audio_b64 = output.get("audio_base64")
    if not audio_b64:
        print("Unexpected response structure:")
        print(json.dumps(result, indent=2))
        return

    # ── 4. Save output audio ──────────────────────────────────────────────────
    decode_audio_to_file(audio_b64, OUTPUT_PATH)
    print(f"✓ Cloned audio saved to: {OUTPUT_PATH}")
    print(f"  Message: {output.get('message', '')}")


if __name__ == "__main__":
    main()