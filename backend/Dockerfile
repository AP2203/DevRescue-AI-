# Production Dockerfile for DevRescue AI Backend
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies needed for git diffs and native wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose default HTTP port
EXPOSE 8000

# Run uvicorn server with 1 worker to ensure in-memory state consistency
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
