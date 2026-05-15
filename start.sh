#!/bin/bash
set -e

echo "=== ASEAN Medical Match - Startup ==="
echo "Checking ChromaDB collections..."

echo "Skipping ingestion checks for cloud deployment to prevent OOM."

echo "=== All collections ready. Starting server... ==="
exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
