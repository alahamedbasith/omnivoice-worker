"""
omnivoice_client.py — drop-in RunPod client for your app's BACKEND
=================================================================
Call RunPod's API directly from your app. Keep RUNPOD_API_KEY in your app's
environment / secrets — never ship it to the browser.

Usage
-----
    from omnivoice_client import OmnivoiceClient

    client = OmnivoiceClient(endpoint_id="g2r3qa341vtyyd")

    # ref_audio can be: file path (str), raw bytes, or already-base64 string
    audio_bytes = client.clone(
        ref_audio="basith-enhanced-v2.wav",
        ref_text="Welcome back to this another part of the video.",
        target_text="கத்தார் பாலைவன எல்லைக்குப் பக்கத்தில்...",
    )

    # async
    audio_bytes = await client.clone_async(ref_audio=..., target_text=...)
"""

import asyncio
import base64
import os
from typing import Optional, Union

import httpx


class OmnivoiceClient:
    def __init__(
        self,
        endpoint_id: str = None,
        api_key: str = None,
        sync_timeout: int = 90,
        poll_interval: float = 3.0,
    ):
        self.endpoint_id = endpoint_id or os.environ["RUNPOD_ENDPOINT_ID"]
        self.api_key = api_key or os.environ.get("RUNPOD_API_KEY", "YOUR_RUNPOD_API_KEY")
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.sync_timeout = sync_timeout
        self.poll_interval = poll_interval

    # ── input helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _to_base64(ref_audio: Union[str, bytes, str]) -> str:
        if isinstance(ref_audio, str) and len(ref_audio) < 10_000 and "\n" not in ref_audio \
           and os.path.isfile(ref_audio):
            with open(ref_audio, "rb") as f:
                return base64.b64encode(f.read()).decode()
        if isinstance(ref_audio, str):
            # assume already base64
            return ref_audio
        return base64.b64encode(ref_audio).decode()

    def _payload(self, ref_audio, ref_text, target_text, **opts) -> dict:
        return {
            "input": {
                "ref_audio": self._to_base64(ref_audio),
                "ref_text": ref_text,
                "target_text": target_text,
                **opts,
            }
        }

    # ── sync ────────────────────────────────────────────────────────────────────
    def clone(self, ref_audio, ref_text: str, target_text: str,
              speed: float = 1.0, denoise: bool = True, num_step: int = 32,
              guidance_scale: float = 2.0) -> bytes:
        payload = self._payload(ref_audio, ref_text, target_text,
                                speed=speed, denoise=denoise,
                                num_step=num_step, guidance_scale=guidance_scale)
        try:
            return self._runsync(payload)
        except httpx.ReadTimeout:
            return self._run_async(payload)

    def _runsync(self, payload: dict) -> bytes:
        with httpx.Client(timeout=self.sync_timeout + 30) as c:
            r = c.post(f"{self.base_url}/runsync", headers=self.headers, json=payload)
            r.raise_for_status()
            return self._extract(r.json())

    # ── async (polling) ──────────────────────────────────────────────────────────
    def _run_async(self, payload: dict) -> bytes:
        with httpx.Client(timeout=30) as c:
            sub = c.post(f"{self.base_url}/run", headers=self.headers, json=payload)
            sub.raise_for_status()
            job_id = sub.json()["id"]
            while True:
                s = c.get(f"{self.base_url}/status/{job_id}", headers=self.headers)
                s.raise_for_status()
                data = s.json()
                if data["status"] == "COMPLETED":
                    return self._extract(data)
                if data["status"] in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"RunPod job {data['status']}: {data}")
                import time; time.sleep(self.poll_interval)

    @staticmethod
    def _extract(result: dict) -> bytes:
        out = result.get("output", {})
        if "error" in out:
            raise RuntimeError(f"RunPod error: {out['error']}")
        b64 = out.get("audio_base64")
        if not b64:
            raise RuntimeError(f"Unexpected response: {result}")
        return base64.b64decode(b64)

    # ── async/await variant ──────────────────────────────────────────────────────
    async def clone_async(self, ref_audio, ref_text: str, target_text: str,
                          speed: float = 1.0, denoise: bool = True, num_step: int = 32,
                          guidance_scale: float = 2.0) -> bytes:
        payload = self._payload(ref_audio, ref_text, target_text,
                                speed=speed, denoise=denoise,
                                num_step=num_step, guidance_scale=guidance_scale)
        try:
            return await self._runsync_async(payload)
        except httpx.ReadTimeout:
            return await self._run_async_async(payload)

    async def _runsync_async(self, payload: dict) -> bytes:
        async with httpx.AsyncClient(timeout=self.sync_timeout + 30) as c:
            r = await c.post(f"{self.base_url}/runsync", headers=self.headers, json=payload)
            r.raise_for_status()
            return self._extract(r.json())

    async def _run_async_async(self, payload: dict) -> bytes:
        async with httpx.AsyncClient(timeout=30) as c:
            sub = await c.post(f"{self.base_url}/run", headers=self.headers, json=payload)
            sub.raise_for_status()
            job_id = sub.json()["id"]
            while True:
                await asyncio.sleep(self.poll_interval)
                s = await c.get(f"{self.base_url}/status/{job_id}", headers=self.headers)
                s.raise_for_status()
                data = s.json()
                if data["status"] == "COMPLETED":
                    return self._extract(data)
                if data["status"] in ("FAILED", "CANCELLED"):
                    raise RuntimeError(f"RunPod job {data['status']}: {data}")
