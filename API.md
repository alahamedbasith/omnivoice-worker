# OmniVoice API Documentation

Voice-cloning service backed by a RunPod serverless endpoint (HiggsAudio / OmniVoice).

- **RunPod endpoint**: `g2r3qa341vtyyd`
- **Base URL**: `https://api.runpod.ai/v2/{ENDPOINT_ID}`
- **Auth**: `Authorization: Bearer <RUNPOD_API_KEY>` (server-side only)

---

## 1. RunPod Serverless API (call directly)

All requests are `POST {BASE_URL}/runsync` or `{BASE_URL}/run` with header
`Content-Type: application/json` and body `{"input": {...}}`.

### Common input fields

| Field          | Type    | Required | Default | Notes                                  |
|----------------|---------|----------|---------|----------------------------------------|
| `ref_audio`    | string  | yes      | —       | Base64-encoded reference WAV (≥3s)     |
| `ref_text`     | string  | yes      | —       | Transcript of the reference audio      |
| `target_text`  | string  | yes      | —       | Text to synthesize in the cloned voice |
| `speed`        | float   | no       | 1.0     | Playback speed                         |
| `denoise`      | bool    | no       | true    | Denoise reference audio                |
| `num_step`     | int     | no       | 32      | Diffusion steps                        |
| `guidance_scale` | float | no       | 2.0     | Classifier-free guidance               |
| `t_shift`      | float   | no       | 0.1     | Timestep shift                         |
| `position_temperature` | float | no  | 5.0     | Sampling temperature (position)        |
| `class_temperature`    | float | no  | 0.0     | Sampling temperature (class)           |
| `layer_penalty_factor` | float | no | 5.0    | Layer penalty                          |

### Response (`output`)

```json
{
  "output": {
    "audio_base64": "<base64 WAV>",
    "format": "wav",
    "message": "Voice cloning successful"
  },
  "status": "COMPLETED",
  "delayTime": 25897,
  "executionTime": 4199
}
```

On error: `{ "output": { "error": "..." } }`.

---

### A. Synchronous — `POST /runsync`

Blocks until done (hard limit ~90s). Best for short jobs.

```bash
curl -s -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":{"ref_audio":"'"$REF_B64"'","ref_text":"...","target_text":"..."}}'
```

### B. Asynchronous — `POST /run` + `GET /status/{id}`  ⭐ recommended for production

Submit returns a `job_id` immediately; poll until `COMPLETED`.

```bash
# 1. Submit
JOB_ID=$(curl -s -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":{"ref_audio":"'"$REF_B64"'","ref_text":"...","target_text":"..."}}' \
  | jq -r .id)

# 2. Poll
while true; do
  STATUS=$(curl -s "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/status/$JOB_ID" \
    -H "Authorization: Bearer $RUNPOD_API_KEY" | jq -r .status)
  [ "$STATUS" = "COMPLETED" ] && break
  [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ] && { echo failed; break; }
  sleep 3
done

# 3. Fetch result
curl -s "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/status/$JOB_ID" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" | jq -r .output.audio_base64 | base64 -d > out.wav
```

Job status values: `IN_QUEUE` → `IN_PROGRESS` → `COMPLETED` | `FAILED` | `CANCELLED`.

---

## 2. FastAPI Backend (`app.py`) — proxy in front of RunPod

Runs locally: `uvicorn app:app --reload --port 8000`.
Reads `RUNPOD_API_KEY` / `RUNPOD_ENDPOINT_ID` from `.env`.

> The API key stays server-side. The browser only talks to your backend.

### `POST /clone-voice`
Multipart form. Returns the cloned audio as a downloadable **WAV**.

| Field           | Type    | Required | Notes                                  |
|-----------------|---------|----------|----------------------------------------|
| `target_text`   | string  | yes      | Text to synthesize                     |
| `ref_text`      | string  | no       | Defaults to a placeholder              |
| `ref_audio`     | file    | no       | Upload to override default voice       |
| `speed`         | float   | no       | 1.0                                    |
| `num_step`      | int     | no       | 32                                     |
| `guidance_scale`| float   | no       | 2.0                                    |
| `denoise`       | bool    | no       | true                                   |

```bash
curl -X POST "http://localhost:8000/clone-voice" \
  -F "target_text=வணக்கம், இது ஒரு சோதனை." \
  -F "ref_text=Welcome back to this another part of the video." \
  --output cloned.wav
```

### `POST /clone-voice/base64`
Same inputs; returns `{ "audio_base64": "..." }` for frontend playback.

### `GET /default-ref-base64`
Returns the bundled default reference voice as base64 (used by direct-RunPod clients).

---

## 3. Reusable Python Client (`omnivoice_client.py`)

Drop into any backend. Uses `.env` via `python-dotenv`.

```python
from omnivoice_client import OmnivoiceClient

client = OmnivoiceClient()  # reads RUNPOD_ENDPOINT_ID + RUNPOD_API_KEY from env

# Sync (runsync, auto-falls back to async polling on timeout)
audio: bytes = client.clone(
    ref_audio="basith-enhanced-v2.wav",   # path | bytes | base64
    ref_text="Welcome back to this another part of the video.",
    target_text="Your text here.",
)

# Async (await-able, for FastAPI/Starlette)
audio: bytes = await client.clone_async(ref_audio=..., target_text=...)
```

---

## 4. Environment (`.env`)

```dotenv
RUNPOD_API_KEY=your_runpod_api_key_here
RUNPOD_ENDPOINT_ID=your_endpoint_id_here
```

`.env` is gitignored — never committed. See `.env.example`.

---

## 5. Production notes

- Use **`/run` + `/status`** (or webhooks) instead of `/runsync` for jobs >90s.
- Keep `RUNPOD_API_KEY` server-side only.
- Set **Min Workers = 1** on the endpoint to avoid ~80s cold starts (costs more).
- Store output audio in blob storage; return a URL, not raw base64.
- Validate input (text length, audio size/type) and add rate limits + concurrency caps.
- Very short `target_text` can return an empty WAV — require a minimum length.
