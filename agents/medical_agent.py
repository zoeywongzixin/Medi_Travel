import os
import re
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

import chromadb

from utils.medical_specialty import build_case_profile, infer_specialties, specialty_groups_for_text
from utils.estimation import estimate_procedure_details, calculate_total_stay

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma_db"
_RRF_K = 60

# ---------------------------------------------------------------------------
# Refactored Helpers
# ---------------------------------------------------------------------------

def _extract_query_tokens(profile: Dict) -> Set[str]:
    raw = " ".join([
        profile.get("condition", ""),
        profile.get("sub_specialty", ""),
        profile.get("summary", ""),
        " ".join(profile.get("specialties", [])),
    ])
    tokens = re.split(r"[^a-z0-9]+", raw.lower())
    stopwords = {"the", "and", "for", "with", "of", "in", "to", "a", "an", "is", "or"}
    return {t for t in tokens if len(t) > 2 and t not in stopwords}

def _keyword_score(doc_text: str, query_tokens: Set[str]) -> int:
    haystack = doc_text.lower()
    return sum(1 for token in query_tokens if token in haystack)

def _hard_group_gate(candidates: List[Dict], required_groups: Set[str]) -> List[Dict]:
    if not required_groups:
        return candidates
    filtered = [
        c for c in candidates
        if specialty_groups_for_text(
            c.get("specialty", ""),
            c.get("specialty_tags", ""),
            c.get("rag_summary", ""),
        ) & required_groups
    ]
    return filtered if filtered else candidates


def _infer_hospital_location(hospital_name: str) -> str:
    hospital = (hospital_name or "").lower()
    if "penang" in hospital or "adventist" in hospital:
        return "Penang, Malaysia"
    if "johor" in hospital:
        return "Johor Bahru, Malaysia"
    if "malacca" in hospital or "melaka" in hospital:
        return "Malacca, Malaysia"
    if "sabah" in hospital:
        return "Kota Kinabalu, Malaysia"
    return "Kuala Lumpur, Malaysia"


def _grant_metadata(hospital_name: str, tier: str) -> Dict:
    hospital = (hospital_name or "").lower()
    if "penang adventist" in hospital:
        return {"Grant Availability": "High", "grant_cap_usd": 450}
    if "sunway" in hospital:
        return {"Grant Availability": "Medium", "grant_cap_usd": 320}
    if "gleneagles" in hospital:
        return {"Grant Availability": "Low", "grant_cap_usd": 180}

    if tier == "Government / Semi-Gov":
        return {"Grant Availability": "High", "grant_cap_usd": 500}
    if tier == "Standard Private":
        return {"Grant Availability": "Medium", "grant_cap_usd": 275}
    return {"Grant Availability": "Low", "grant_cap_usd": 150}


def _build_candidate(doc_id: str, meta: Dict, doc_text: str, semantic_rank: int = None) -> Dict:
    grant_meta = _grant_metadata(meta.get("hospital"), meta.get("tier"))
    candidate = {
        "id": doc_id,
        "name": meta.get("name"),
        "hospital": meta.get("hospital"),
        "specialty": meta.get("specialty"),
        "specialty_tags": meta.get("specialty_tags"),
        "tier": meta.get("tier"),
        "full_registration_number": meta.get("full_registration_number"),
        "mmc_url": meta.get("mmc_url"),
        "rag_summary": doc_text,
        "hospital_location": _infer_hospital_location(meta.get("hospital")),
        "grant_availability": grant_meta["Grant Availability"],
        "hospital_metadata": grant_meta,
    }
    if semantic_rank is not None:
        candidate["semantic_rank"] = semantic_rank
    return candidate

def rank_doctor_matches(medical_data: Dict, candidates: List[Dict], limit: int = 5) -> List[Dict]:
    profile = build_case_profile(medical_data)
    severity = profile.get("severity", "Unknown")
    urgency = profile.get("urgency", "Unknown")
    age_group = profile.get("age_group", "Unknown")
    ranked: List[Dict] = []

    for index, candidate in enumerate(candidates):
        candidate_text = " ".join([
            candidate.get("specialty", ""),
            candidate.get("specialty_tags", ""),
            candidate.get("hospital", ""),
            candidate.get("rag_summary", ""),
        ])
        candidate_groups = specialty_groups_for_text(candidate_text)

        score = max(0, 8 - index)
        if candidate.get("mmc_url"): score += 2
        
        group_overlap = profile["groups"] & candidate_groups
        if group_overlap:
            score += 12 * len(group_overlap)
        elif profile["groups"]:
            score -= 10

        ranked_candidate = dict(candidate)
        ranked_candidate["match_score"] = score
        ranked.append(ranked_candidate)

    ranked.sort(key=lambda item: item["match_score"], reverse=True)
    return ranked[:limit]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_hospitals(medical_data: Dict, retrieval_mode: str = "default", top_n: int = 3) -> List[Dict]:
    profile = build_case_profile(medical_data)
    condition = profile["condition"] or "General Medicine"
    
    print(f"  [MedicalAgent] Searching for specialists for: {condition}...")
    
    os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "False"
    client = chromadb.PersistentClient(path=str(DB_PATH))

    try:
        collection = client.get_collection(name="malaysia_doctors")
    except Exception:
        print("  [!] Warning: 'malaysia_doctors' collection not found.")
        return get_mock_hospitals()[:top_n]

    # Stage 1a: Semantic Search
    print("  [MedicalAgent] Stage 1a: Running Semantic Search...")
    query_text = f"Specialist for {condition}. {profile['summary']}"
    sem_results = collection.query(query_texts=[query_text], n_results=50)
    
    if not sem_results or not sem_results.get("ids"):
        return get_mock_hospitals()

    all_ids = sem_results["ids"][0]
    all_docs = sem_results["documents"][0]
    all_metas = sem_results["metadatas"][0]

    # Stage 1b: Local Keyword Search
    print(f"  [MedicalAgent] Stage 1b: Running Keyword Search on {len(all_ids)} candidates...")
    query_tokens = _extract_query_tokens(profile)
    keyword_ranked = []
    for doc_id, doc_text in zip(all_ids, all_docs):
        score = _keyword_score(doc_text, query_tokens)
        if score > 0:
            keyword_ranked.append((doc_id, score))
    keyword_ranked.sort(key=lambda x: x[1], reverse=True)

    # Stage 1c: Fusing results
    print("  [MedicalAgent] Stage 1c: Fusing results...")
    semantic_ids = all_ids[:20]
    rrf_scores = {}
    for rank, doc_id in enumerate(semantic_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
    for rank, (doc_id, _) in enumerate(keyword_ranked[:20]):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    fused_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    id_to_data = {doc_id: {"meta": m, "doc": d} for doc_id, m, d in zip(all_ids, all_metas, all_docs)}

    if retrieval_mode == "semantic_raw":
        raw_hits: List[Dict] = []
        for rank, doc_id in enumerate(all_ids[:top_n], start=1):
            data = id_to_data.get(doc_id)
            if not data:
                continue
            raw_hits.append(_build_candidate(doc_id, data["meta"], data["doc"], semantic_rank=rank))
        return raw_hits or get_mock_hospitals()[:top_n]

    candidates = []
    for doc_id in fused_ids:
        data = id_to_data.get(doc_id)
        if not data: continue
        meta, doc_text = data["meta"], data["doc"]
        candidates.append(_build_candidate(doc_id, meta, doc_text))

    # -----------------------------------------------------------------------
    # Stage 2 & 3: Filtering and Scoring
    # -----------------------------------------------------------------------
    print("  [MedicalAgent] Stage 2: Applying Hard Specialty Gate...")
    
    # DELETE OR COMMENT OUT THE LINE BELOW:
    # from agents.medical_agent import _hard_group_gate, rank_doctor_matches 
    
    candidates = _hard_group_gate(candidates, profile["groups"])

    print("  [MedicalAgent] Stage 3: Running Metadata-Enriched Scoring...")
    top5 = rank_doctor_matches(medical_data, candidates, limit=5)
    if not top5:
        print("  [MedicalAgent] No ranked candidates remained after filtering. Falling back to mock hospitals.")
        return get_mock_hospitals(medical_data)[:top_n]

    # Stage 4: LLM Rerank
    print("  [MedicalAgent] Stage 4: Initiating LLM Rerank (Ollama)...")
    try:
        from agents.rerank_agent import llm_rerank
        reranked = llm_rerank(top5, medical_data)[:top_n]
        return reranked or get_mock_hospitals(medical_data)[:top_n]
    except Exception as exc:
        print(f"  [!] LLM rerank failed: {exc}")
        return top5[:top_n]

def get_mock_hospitals(medical_data: Dict = None):
    text = " ".join(
        [
            (medical_data or {}).get("condition", ""),
            (medical_data or {}).get("sub_specialty_inference", ""),
            (medical_data or {}).get("raw_summary", ""),
        ]
    ).lower()

    if any(term in text for term in ("lung", "oncology", "cancer", "tumor", "tumour", "sclc", "radiotherapy", "chemotherapy")):
        return [
            {
                'name': 'Dr. Aisyah Marina Mohd Noor',
                'hospital': 'National Cancer Institute (IKN)',
                'specialty': 'Medical Oncology',
                'specialty_tags': 'Medical Oncology, Lung Cancer, Small Cell Lung Cancer, Thoracic Oncology',
                'tier': 'Government / Semi-Gov',
                'hospital_location': 'Putrajaya, Malaysia',
                'grant_availability': 'High',
                'hospital_metadata': {'Grant Availability': 'High', 'grant_cap_usd': 500},
            },
            {
                'name': 'Dr. Jason Lee Chee Keong',
                'hospital': 'Subang Jaya Medical Centre',
                'specialty': 'Radiation Oncology',
                'specialty_tags': 'Radiation Oncology, Lung Cancer, Small Cell Lung Cancer, Radiotherapy',
                'tier': 'Standard Private',
                'hospital_location': 'Kuala Lumpur, Malaysia',
                'grant_availability': 'Medium',
                'hospital_metadata': {'Grant Availability': 'Medium', 'grant_cap_usd': 320},
            },
            {
                'name': 'Dr. Tan Wei Jian',
                'hospital': 'Sunway Medical Centre',
                'specialty': 'Pulmonology',
                'specialty_tags': 'Pulmonology, Lung Mass, Hemoptysis, Respiratory Oncology Support',
                'tier': 'Standard Private',
                'hospital_location': 'Kuala Lumpur, Malaysia',
                'grant_availability': 'Medium',
                'hospital_metadata': {'Grant Availability': 'Medium', 'grant_cap_usd': 320},
            }
        ]

    return [
        {
            'name': 'Dr. Mock Elite',
            'hospital': 'Gleneagles Kuala Lumpur',
            'specialty': 'Orthopedics',
            'specialty_tags': 'Knee Replacement',
            'tier': 'Premium Private',
            'hospital_location': 'Kuala Lumpur, Malaysia',
            'grant_availability': 'Low',
            'hospital_metadata': {'Grant Availability': 'Low', 'grant_cap_usd': 180},
        },
        {
            'name': 'Dr. Mock Optimized',
            'hospital': 'Sunway Medical Centre',
            'specialty': 'Orthopedics',
            'specialty_tags': 'Knee Replacement',
            'tier': 'Standard Private',
            'hospital_location': 'Kuala Lumpur, Malaysia',
            'grant_availability': 'Medium',
            'hospital_metadata': {'Grant Availability': 'Medium', 'grant_cap_usd': 320},
        },
        {
            'name': 'Dr. Mock Proximity',
            'hospital': 'Penang Adventist Hospital',
            'specialty': 'Orthopedics',
            'specialty_tags': 'Knee Replacement',
            'tier': 'Standard Private',
            'hospital_location': 'Penang, Malaysia',
            'grant_availability': 'High',
            'hospital_metadata': {'Grant Availability': 'High', 'grant_cap_usd': 450},
        }
    ]

def generate_clinical_summary(medical_data: Dict) -> Dict:
    """
    Analyzes the medical chart data to provide a clinical summary and estimated stay.
    """
    profile = build_case_profile(medical_data)
    condition = profile.get("condition") or "General Medicine"
    
    estimation = estimate_procedure_details(condition)
    total_stay = calculate_total_stay(estimation["stay_days"])
    
    summary = (
        f"PATIENT CLINICAL SUMMARY:\n"
        f"Diagnosis: {condition}\n"
        f"Severity: {profile.get('severity', 'Unknown')}\n"
        f"Urgency: {profile.get('urgency', 'Unknown')}\n"
        f"Background: {profile.get('summary', 'No background provided.')}\n"
        f"\n"
        f"ANTICIPATED PROCEDURE: {estimation['procedure_name']}\n"
        f"ESTIMATED STAY DURATION: {total_stay} days (Includes 2 days pre-op, {estimation['stay_days']} days recovery)."
    )
    
    return {
        "diagnosis": condition,
        "procedure": estimation["procedure_name"],
        "estimated_cost_usd": estimation["cost_usd"],
        "total_stay_days": total_stay,
        "professional_summary": summary
    }
