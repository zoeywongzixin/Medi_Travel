import os
import chromadb

db_path = os.path.join("c:\\Documents\\Jasmine\\ai_medical_matching", "data", "chroma_db")
client = chromadb.PersistentClient(path=db_path)
try:
    collection = client.get_collection(name="malaysia_doctors")
    results = collection.get()
    print(f"Count: {len(results['ids'])}")
    if results['metadatas']:
        print(f"Sample: {results['metadatas'][0]}")
except Exception as e:
    print(f"Error: {e}")
