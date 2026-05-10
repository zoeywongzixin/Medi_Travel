import os
import chromadb
from chromadb.config import Settings

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")

def seed_doctors():
    print(f"Connecting to ChromaDB at {DB_PATH}")
    os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "False"
    client = chromadb.PersistentClient(path=str(DB_PATH))
    
    # We use get_or_create_collection to add more docs
    collection = client.get_or_create_collection(name="malaysia_doctors")
    
    # Let's add some seeded doctors with telegram_handles
    doctors = [
        {
            "id": "doc_100",
            "name": "Dr. Aisyah Marina Mohd Noor",
            "hospital": "National Cancer Institute (IKN)",
            "specialty": "Medical Oncology",
            "specialty_tags": "Medical Oncology, Lung Cancer, Small Cell Lung Cancer, Thoracic Oncology",
            "tier": "Government / Semi-Gov",
            "telegram_handle": "t.me/draisyah_marina"
        },
        {
            "id": "doc_101",
            "name": "Dr. Jason Lee Chee Keong",
            "hospital": "Subang Jaya Medical Centre",
            "specialty": "Radiation Oncology",
            "specialty_tags": "Radiation Oncology, Lung Cancer, Small Cell Lung Cancer, Radiotherapy",
            "tier": "Standard Private",
            "telegram_handle": "t.me/drjason_lee"
        },
        {
            "id": "doc_102",
            "name": "Dr. Siti Nurhaliza",
            "hospital": "Gleneagles Kuala Lumpur",
            "specialty": "Thoracic Oncology",
            "specialty_tags": "Thoracic Oncology, Lung Mass",
            "tier": "Premium Private",
            "telegram_handle": "t.me/drsiti_nurhaliza"
        },
        {
            "id": "doc_103",
            "name": "Dr. Mock Elite",
            "hospital": "Gleneagles Kuala Lumpur",
            "specialty": "Orthopedics",
            "specialty_tags": "Knee Replacement, Orthopedic Surgery",
            "tier": "Premium Private",
            "telegram_handle": "t.me/drmock_elite"
        },
        {
            "id": "doc_104",
            "name": "Dr. Aminah Binti Osman",
            "hospital": "Hospital Kuala Lumpur",
            "specialty": "Cardiology",
            "specialty_tags": "Cardiology, Heart Bypass, ECG",
            "tier": "Government / Semi-Gov",
            "telegram_handle": "t.me/draminah_cardio"
        }
    ]
    
    documents = []
    metadatas = []
    ids = []
    
    for doc in doctors:
        ids.append(doc["id"])
        metadatas.append({
            "name": doc["name"],
            "hospital": doc["hospital"],
            "specialty": doc["specialty"],
            "specialty_tags": doc["specialty_tags"],
            "tier": doc["tier"],
            "telegram_handle": doc["telegram_handle"]
        })
        # The document text is what semantic search uses
        documents.append(f"{doc['specialty']} Specialist. Focuses on {doc['specialty_tags']}. Working at {doc['hospital']}.")

    print(f"Upserting {len(ids)} doctor profiles...")
    collection.upsert(
        ids=ids,
        metadatas=metadatas,
        documents=documents
    )
    
    print("Seed complete!")

if __name__ == "__main__":
    seed_doctors()
