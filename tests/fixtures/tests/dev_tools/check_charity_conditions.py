import chromadb
import os
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CHROMA_DB_PATH = str(ROOT_DIR / "data" / "chroma_db")

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_collection(name="charities")
results = collection.get()

conditions_count = {}
for meta in results['metadatas']:
    conds = json.loads(meta.get('conditions_covered', '[]'))
    for c in conds:
        conditions_count[c] = conditions_count.get(c, 0) + 1

print("--- Conditions in 'charities' collection ---")
for cond, count in sorted(conditions_count.items(), key=lambda x: -x[1]):
    print(f"{cond}: {count}")

print(f"\nTotal records: {len(results['ids'])}")
