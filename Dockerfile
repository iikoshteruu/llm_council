# syntax=docker/dockerfile:1

FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_RUN_PORT=5000

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy source
COPY . /app

# Ensure a persistent results dir lives at /data and is referenced by ./results
RUN mkdir -p /data && \
    rm -rf /app/results && \
    ln -s /data /app/results

# Minimal Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Default command: run the web UI
CMD ["python3", "webapp.py"]
