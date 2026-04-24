import json
import os
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHARITIES_FILE = DATA_DIR / "charities.json"

_chroma_client = None
_charity_collection = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client()
    return _chroma_client
emb_fn = embedding_functions.DefaultEmbeddingFunction()

def load_charities() -> List[Dict]:
    if not os.path.exists(CHARITIES_FILE):
        return []
    with open(CHARITIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def initialize_charity_vector_db():
    global _charity_collection
    if _charity_collection is not None:
        return _charity_collection
        
    charities = load_charities()
    if not charities:
        return None
        
    client = get_chroma_client()
    try:
        collection = client.get_collection("charities")
        client.delete_collection("charities")
    except:
        pass
        
    collection = client.create_collection(
        name="charities",
        embedding_function=emb_fn
    )
    
    ids = []
    documents = []
    metadatas = []
    
    for c in charities:
        ids.append(c["id"])
        doc_text = f"Fund: {c['name']}. Targets: {', '.join(c['target_audience'])}. Covers: {', '.join(c['conditions_covered'])}. Description: {c['description']}"
        documents.append(doc_text)
        metadatas.append({
            "name": c["name"],
            "max_coverage_usd": c["max_coverage_usd"]
        })
        
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    _charity_collection = collection
    return collection

def match_charities(medical_data: Dict, origin_country: str) -> List[Dict]:
    """
    Search agent to match patient's profile against available funds using Vector RAG.
    """
    collection = initialize_charity_vector_db()
    if not collection:
        return load_charities()[:2]
        
    condition = medical_data.get("condition", "general medical")
    
    query_text = f"Financial aid for patient from {origin_country} with {condition}."
    
    results = collection.query(
        query_texts=[query_text],
        n_results=2
    )
    
    matched = []
    if results and "metadatas" in results and len(results["metadatas"][0]) > 0:
        for i in range(len(results["ids"][0])):
            matched.append({
                "id": results["ids"][0][i],
                "name": results["metadatas"][0][i]["name"],
                "max_coverage_usd": results["metadatas"][0][i]["max_coverage_usd"]
            })
            
    return matched
