import os
import re
import time
from pathlib import Path
from typing import Dict, List, Set, Tuple

import chromadb

from utils.medical_specialty import build_case_profile, infer_specialties, specialty_groups_for_text

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

def match_hospitals(medical_data: Dict) -> List[Dict]:
    profile = build_case_profile(medical_data)
    condition = profile["condition"] or "General Medicine"
    
    print(f"  [MedicalAgent] Searching for specialists for: {condition}...")
    
    os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "False"
    client = chromadb.PersistentClient(path=str(DB_PATH))

    try:
        collection = client.get_collection(name="malaysia_doctors")
    except Exception:
        print("  [!] Warning: 'malaysia_doctors' collection not found.")
        return []

    # Stage 1a: Semantic Search
    print("  [MedicalAgent] Stage 1a: Running Semantic Search...")
    query_text = f"Specialist for {condition}. {profile['summary']}"
    sem_results = collection.query(query_texts=[query_text], n_results=50)
    
    if not sem_results or not sem_results.get("ids"):
        return []

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
    candidates = []
    for doc_id in fused_ids:
        data = id_to_data.get(doc_id)
        if not data: continue
        meta, doc_text = data["meta"], data["doc"]
        candidates.append({
            "id": doc_id, "name": meta.get("name"), "hospital": meta.get("hospital"),
            "specialty": meta.get("specialty"), "specialty_tags": meta.get("specialty_tags"),
            "tier": meta.get("tier"), "full_registration_number": meta.get("full_registration_number"),
            "mmc_url": meta.get("mmc_url"), "rag_summary": doc_text,
        })

    # -----------------------------------------------------------------------
    # Stage 2 & 3: Filtering and Scoring
    # -----------------------------------------------------------------------
    print("  [MedicalAgent] Stage 2: Applying Hard Specialty Gate...")
    
    # DELETE OR COMMENT OUT THE LINE BELOW:
    # from agents.medical_agent import _hard_group_gate, rank_doctor_matches 
    
    candidates = _hard_group_gate(candidates, profile["groups"])

    print("  [MedicalAgent] Stage 3: Running Metadata-Enriched Scoring...")
    top5 = rank_doctor_matches(medical_data, candidates, limit=5)

    # Stage 4: LLM Rerank
    print("  [MedicalAgent] Stage 4: Initiating LLM Rerank (Ollama)...")
    try:
        from agents.rerank_agent import llm_rerank
        return llm_rerank(top5, medical_data)
    except Exception as exc:
        print(f"  [!] LLM rerank failed: {exc}")
        return top5[:3]