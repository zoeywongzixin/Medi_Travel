import json
import os
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
import ollama

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HOSPITALS_FILE = DATA_DIR / "hospitals.json"

# Initialize ChromaDB lazily to prevent Uvicorn worker deadlocks
_chroma_client = None
_hospital_collection = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client()
    return _chroma_client
emb_fn = embedding_functions.DefaultEmbeddingFunction()

def load_hospitals() -> List[Dict]:
    if not os.path.exists(HOSPITALS_FILE):
        return []
    with open(HOSPITALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def initialize_hospital_vector_db():
    global _hospital_collection
    if _hospital_collection is not None:
        return _hospital_collection
        
    hospitals = load_hospitals()
    if not hospitals:
        return None
        
    client = get_chroma_client()
    try:
        collection = client.get_collection("hospitals")
        client.delete_collection("hospitals")
    except:
        pass
        
    collection = client.create_collection(
        name="hospitals",
        embedding_function=emb_fn
    )
    
    # Prepare data for insertion
    ids = []
    documents = []
    metadatas = []
    
    for h in hospitals:
        ids.append(h["id"])
        # Document text to embed (combination of specialties and description)
        doc_text = f"Hospital: {h['name']}. Specialties: {', '.join(h['specialties'])}. Description: {h['description']}"
        documents.append(doc_text)
        metadatas.append({
            "name": h["name"],
            "city": h["city"],
            "base_consultation_fee": h["base_consultation_fee"],
            "description": h["description"],
            "specialties": ", ".join(h["specialties"])
        })
        
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    _hospital_collection = collection
    return collection

def match_hospitals(medical_data: Dict) -> List[Dict]:
    """
    Match the patient's condition to suitable Malaysian hospitals using Vector RAG.
    """
    collection = initialize_hospital_vector_db()
    if not collection:
        return load_hospitals()[:3]
        
    condition = medical_data.get("condition", "general checkup")
    severity = medical_data.get("severity", "moderate")
    
    query_text = f"Patient needs treatment for: {condition}. Severity: {severity}."
    
    results = collection.query(
        query_texts=[query_text],
        n_results=3
    )
    
    matched = []
    if results and "metadatas" in results and len(results["metadatas"][0]) > 0:
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            
            matched.append({
                "id": results["ids"][0][i],
                "name": meta["name"],
                "city": meta["city"],
                "base_consultation_fee": meta["base_consultation_fee"],
                "description": meta["description"],
                "specialties": meta["specialties"]
            })
            
    return matched
