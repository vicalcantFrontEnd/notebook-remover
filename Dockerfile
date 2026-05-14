# ---- Build stage: install Python deps ----
FROM python:3.11-slim AS base

# System deps: FFmpeg + OpenCV native libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    # Needed for LibreOffice (PPTX processing, optional)
    # libreoffice \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements-full.txt .
RUN pip install --no-cache-dir -r requirements-full.txt

# Copy application source
COPY backend/ ./backend/
COPY watermark_remover.py .

# Create runtime directories
RUN mkdir -p temp/uploads temp/outputs data credentials

# Run as non-root
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
