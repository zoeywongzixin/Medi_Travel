import os
import chromadb
import ollama
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CHROMA_DB_PATH = str(ROOT_DIR / "data" / "chroma_db")

print("--- Checking ChromaDB Collections ---")
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

for col_name in ["malaysia_doctors", "charities"]:
    try:
        col = client.get_collection(name=col_name)
        print(f"Collection '{col_name}': {col.count()} records")
    except Exception as e:
        print(f"Collection '{col_name}': Error or Missing - {e}")

print("\n--- Testing Ollama Connection ---")
# Try localhost first as we are on Windows
hosts = ["http://localhost:11434", "http://host.docker.internal:11434"]
for host in hosts:
    try:
        print(f"Trying Ollama at {host}...")
        c = ollama.Client(host=host)
        response = c.list()
        # In some versions it's a dict, in others an object
        models = getattr(response, 'models', response.get('models', []))
        print(f"Success! Models found: {[getattr(m, 'model', m.get('model', 'unknown')) for m in models]}")
        break
    except Exception as e:
        print(f"Failed at {host}: {e}")
