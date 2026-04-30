# Use Python 3.11 Slim as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (Tesseract, Poppler)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libglib2.0-0 \
    build-essential \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create persistent data directories
RUN mkdir -p /app/data/chroma_db /app/reports

# Make startup script executable
RUN chmod +x /app/start.sh

# Expose the FastAPI port
EXPOSE 8000

# Use startup script so collections are always ready
CMD ["/bin/bash", "/app/start.sh"]
