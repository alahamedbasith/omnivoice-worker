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
import os
import time
import requests

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# ← FILL THESE IN
# ─────────────────────────────────────────────────────────────────────────────
RUNPOD_API_KEY    = os.environ.get("RUNPOD_API_KEY", "YOUR_RUNPOD_API_KEY")       # RunPod dashboard → Settings → API Keys
ENDPOINT_ID       = os.environ.get("RUNPOD_ENDPOINT_ID", "YOUR_ENDPOINT_ID")       # RunPod dashboard → Serverless → your endpoint
REF_AUDIO_PATH    = "D:\\saas-mvp\\runpod_omnivoice\\basith-enhanced-v2.wav"              # Path to your reference voice audio (≥3s)
REF_TEXT          = "Welcome back to this another part of the video. இந்த videoவுல என்ன பார்க்கப் போறோம்னா, எப்படி machine learning learn பண்றது அப்படிங்கிறதை நம்ம பார்க்கப் போறோம். இதுவரை நம்ம channelல subscribe பண்ணலைன்னா subscribe பண்ணிக்கோங்க. கூடவே அந்த bell பட்டனை click பண்ணிக்கோங்க."   # What the speaker says
TARGET_TEXT       = """

கத்தார் பாலைவன எல்லைக்குப் பக்கத்தில் இருக்கும் ஒரு சிறிய ஊரில், “ரஹ்மான் எலக்ட்ரானிக்ஸ்” என்று ஒரு பழைய கடை இருந்தது. அந்த கடையை நடத்தி வந்தவன் ஃபைசல்.

பழைய ரேடியோ, கடிகாரம், டிவி — எது பழுதாக இருந்தாலும் அவன் சரி செய்து விடுவான். ஆனால் ஊர்ல இருந்தவர்களுக்கு தெரியாத ஒரு ரகசியம் இருந்தது.

ஒவ்வொரு இரவும் சரியாக 2:17 மணிக்கு, கடையில் மேல் அலமாரியில் இருந்த ஒரு பழைய ரேடியோ தானாகவே ஒளிந்து எரிந்து ஒலி கொடுக்கும்.

அதில் பாடல் வராது.

ஒரே ஒரு குரல் மட்டும்.

> “நாளைக்கு அந்த ரயில் வரக்கூடாது…”

முதலில் ஃபைசல் அதை கவனிக்கவில்லை. “சர்க்யூட் பிரச்சனை இருக்கும்” என்று நினைத்தான். ஆனா அந்த குரல் தினமும் வந்தது.

ஒரு நாள் மாலை, வெள்ளை தாடியுடன் வயதான ஒருவன் கடைக்குள் வந்தான். கையில் பழைய கை கடிகாரம்.

“இதை சரி பண்ண முடியுமா?” என்று கேட்டான்.

ஃபைசல் கடிகாரத்தைத் திறந்தான்.

உள்ளே சிறிய எழுத்தில் ஒரு வரி:

> “நாளைக்கு அந்த ரயில் வரக்கூடாது…”

அவனுடைய உடம்பு முழுக்க சில்லென்று போனது.

“இந்த ஊர்ல ரயில் பாதை கூட இல்லையே…” என்றான்.

அந்த வயதானவன் மெதுவாக சிரித்தான்.

> “நாளைக்கு இருக்கும்.”

அந்த இரவு ஃபைசலுக்கு தூக்கம் வரவில்லை.

அதிகாலை அவன் ஊருக்கு வெளியே இருந்த பழைய ரயில் நிலையத்துக்கு போனான். நாற்பது வருடங்களாக மணலில் புதைந்திருந்த நிலையம் அது.

ஆனால் அந்த நாள்…

ரயில் பாதைகள் புதுசாக இருந்தது.

மணல் இல்லாமல் சுத்தமாக.

யாரோ நேற்று தான் பயன்படுத்திய மாதிரி.

மாலை சூரியன் மறையும் நேரம்.

தொலைவில் ஒரு ரயில் ஹார்ன்.

முழு ஊரும் பயந்து வெளியே வந்தது.

பாலைவன மணல் புயலை கிழித்துக்கொண்டு ஒரு கருப்பு ரயில் வந்தது.

ஜன்னல்களில் ஒளி இல்லை.

டிரைவர் இல்லை.

பெயர் இல்லை.

அது மெதுவாக நிலையத்தில் நின்றது.

கதவுகள் திறந்தது.

உள்ளே யாரும் இல்லை.

ஒரு இளைஞன் தைரியமாக உள்ளே ஏறினான்.

சில விநாடிகள் அமைதி.

பிறகு அவன் அலறிய சத்தம்.

அந்த நேரம் கதவுகள் தானாக மூடிக்கொண்டது.

ரயில் வேகமாக மணல் புயலுக்குள் மறைந்தது.

அவன் திரும்பி வரவே இல்லை.

நிலைய தரையில் மட்டும் ஒரு பழைய கை கடிகாரம் கிடந்தது.

அதன் ஊசிகள் நின்றிருந்த நேரம்:

2:17 AM.


"""

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