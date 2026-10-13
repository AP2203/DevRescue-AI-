# ---- Vision3D AI backend ----
# Multi-stage build so heavy AI deps stay optional at runtime.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for Pillow, OpenCV, trimesh, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Core API image
FROM base AS api
RUN pip install -r requirements.txt
COPY app ./app
COPY .env.example ./.env.example
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Full AI image (installs torch/diffusers). Use for GPU deployments.
FROM base AS ai
RUN pip install -r requirements-ai.txt
RUN pip install -r requirements.txt
COPY app ./app
COPY .env.example ./.env.example
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]