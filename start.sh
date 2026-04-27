#!/bin/bash
set -e

echo "=== ASEAN Medical Match - Startup ==="
echo "Checking ChromaDB collections..."

# Run doctor ingestion if collection is missing or empty
python -c "
import chromadb, sys
client = chromadb.PersistentClient(path='/app/data/chroma_db')
try:
    col = client.get_collection('malaysia_doctors')
    count = col.count()
    print(f'  malaysia_doctors: {count} records')
    if count == 0:
        raise Exception('empty')
    sys.exit(0)
except Exception as e:
    print(f'  malaysia_doctors missing/empty ({e}), ingesting...')
    sys.exit(1)
" && echo "  Doctors OK" || python pipeline/ingest_doctors.py

# Run charity ingestion if collection is missing or empty
python -c "
import chromadb, sys
client = chromadb.PersistentClient(path='/app/data/chroma_db')
try:
    col = client.get_collection('charities')
    count = col.count()
    print(f'  charities: {count} records')
    if count == 0:
        raise Exception('empty')
    sys.exit(0)
except Exception as e:
    print(f'  charities missing/empty ({e}), ingesting...')
    sys.exit(1)
" && echo "  Charities OK" || python pipeline/ingest_charities.py

echo "=== All collections ready. Starting server... ==="
exec uvicorn app:app --host 0.0.0.0 --port 8000
