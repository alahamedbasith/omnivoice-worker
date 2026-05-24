# ─────────────────────────────────────────────────────────────────────────────
# RunPod Serverless Worker — OmniVoice Voice Clone
# ─────────────────────────────────────────────────────────────────────────────
# Base image: official RunPod PyTorch image with CUDA 12.1
# → GPU drivers, torch, torchaudio already baked in; no reinstall needed.
FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

# Set working directory inside the container
WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# ffmpeg  → needed by torchaudio / soundfile for audio format handling
# git     → needed to pip-install OmniVoice directly from GitHub
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first so Docker layer-caches the pip install step.
# Re-running `docker build` after only changing handler.py won't reinstall deps.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY handler.py voice_service.py ./

# ── Runtime env defaults ──────────────────────────────────────────────────────
# OMNIVOICE_MODEL_DIR : where the model lives (overridden by RunPod volume mount)
ENV OMNIVOICE_MODEL_DIR=/runpod-volume/omnivoice_model

# ── Start command ─────────────────────────────────────────────────────────────
# RunPod serverless expects the container to call runpod.serverless.start()
# The -u flag disables Python output buffering so logs appear immediately.
CMD ["python", "-u", "handler.py"]