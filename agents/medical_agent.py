import os
from pathlib import Path
from typing import Dict, List

import chromadb

from utils.medical_specialty import build_case_profile, infer_specialties, specialty_groups_for_text

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma_db"


def rank_doctor_matches(medical_data: Dict, candidates: List[Dict], limit: int = 3) -> List[Dict]:
    profile = build_case_profile(medical_data)
    ranked: List[Dict] = []

    for index, candidate in enumerate(candidates):
        candidate_text = " ".join(
            [
                candidate.get("specialty", ""),
                candidate.get("specialty_tags", ""),
                candidate.get("hospital", ""),
                candidate.get("rag_summary", ""),
                candidate.get("primary_practice", ""),
            ]
        )
        candidate_specialties = infer_specialties(candidate_text)
        candidate_groups = specialty_groups_for_text(candidate_text)

        score = max(0, 8 - index)
        if candidate.get("mmc_url"):
            score += 2
        if candidate.get("provisional_registration_number") or candidate.get("full_registration_number"):
            score += 2

        group_overlap = profile["groups"] & candidate_groups
        if group_overlap:
            score += 12 * len(group_overlap)
        elif profile["groups"]:
            score -= 10

        if profile["lung_focus"] and any(
            specialty in candidate_specialties
            for specialty in ("Medical Oncology", "Radiation Oncology", "Thoracic Surgery", "Pulmonology")
        ):
            score += 8

        if "oncology" in profile["groups"] and "cardiology" in candidate_groups and not profile["cardio_oncology"]:
            score -= 20

        ranked_candidate = dict(candidate)
        ranked_candidate["match_score"] = score
        ranked.append(ranked_candidate)

    ranked.sort(key=lambda item: item["match_score"], reverse=True)
    return ranked[:limit]


def match_hospitals(medical_data: Dict) -> List[Dict]:
    """
    Match the patient's condition to specific specialists using the doctor RAG.
    """
    if not os.path.exists(DB_PATH):
        print("Warning: ChromaDB not found. Please run 'python pipeline/ingest_doctors.py' first.")
        return []

    client = chromadb.PersistentClient(path=str(DB_PATH))

    try:
        collection = client.get_collection(name="malaysia_doctors")
    except Exception:
        print("Warning: 'malaysia_doctors' collection not found.")
        return []

    profile = build_case_profile(medical_data)
    condition = profile["condition"] or "General Medicine"
    sub_specialty = profile["sub_specialty"] or condition

    query_text = (
        f"Specialist for {condition}. "
        f"Needed department: {sub_specialty}. "
        f"Relevant specialties: {', '.join(profile['specialties'])}. "
        f"Clinical summary: {profile['summary']}."
    )

    results = collection.query(query_texts=[query_text], n_results=12)

    candidates: List[Dict] = []
    if results and results.get("metadatas"):
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            doc_text = results["documents"][0][i]
            candidates.append(
                {
                    "id": results["ids"][0][i],
                    "name": meta.get("name"),
                    "hospital": meta.get("hospital"),
                    "specialty": meta.get("specialty"),
                    "specialty_tags": meta.get("specialty_tags", meta.get("specialty")),
                    "tier": meta.get("tier"),
                    "provisional_registration_number": meta.get("provisional_registration_number"),
                    "full_registration_number": meta.get("full_registration_number"),
                    "mmc_profile_id": meta.get("mmc_profile_id"),
                    "mmc_url": meta.get("mmc_url"),
                    "primary_practice": meta.get("primary_practice"),
                    "rag_summary": doc_text,
                }
            )

    return rank_doctor_matches(medical_data, candidates)
