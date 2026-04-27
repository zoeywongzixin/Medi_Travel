"""
Medical Agent
=============
Matches a patient's medical profile to the most suitable registered specialists
using a three-stage pipeline:

  Stage 1  — Hybrid Search (Semantic + Keyword via Reciprocal Rank Fusion)
               ChromaDB vector search  +  token-overlap keyword scan → top-20
  Stage 2  — Hard Specialty-Group Gate
               Drop candidates with zero group overlap; relax if no survivors.
  Stage 3  — Metadata-Enriched Scoring → Top-5
               Severity / urgency / age-group bonuses applied on top of the
               existing specialty-group scoring; top-5 selected for LLM rerank.
  Stage 4  — LLM Rerank (rerank_agent)
               Ollama judge compares the 5 pre-vetted doctors and returns top-3.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import chromadb

from utils.medical_specialty import build_case_profile, infer_specialties, specialty_groups_for_text

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma_db"

# RRF constant — higher k dampens the advantage of very top-ranked items
_RRF_K = 60


# ---------------------------------------------------------------------------
# Helpers — Keyword Search leg
# ---------------------------------------------------------------------------

def _extract_query_tokens(profile: Dict) -> Set[str]:
    """Build a set of lower-case tokens from the patient profile for keyword matching."""
    raw = " ".join([
        profile.get("condition", ""),
        profile.get("sub_specialty", ""),
        profile.get("summary", ""),
        " ".join(profile.get("specialties", [])),
    ])
    tokens = re.split(r"[^a-z0-9]+", raw.lower())
    # Remove very short/stop tokens
    stopwords = {"the", "and", "for", "with", "of", "in", "to", "a", "an", "is", "or"}
    return {t for t in tokens if len(t) > 2 and t not in stopwords}


def _keyword_score(doc_text: str, query_tokens: Set[str]) -> int:
    """Count how many query tokens appear in the document text."""
    haystack = doc_text.lower()
    return sum(1 for token in query_tokens if token in haystack)


def _keyword_search(
    all_ids: List[str],
    all_docs: List[str],
    all_metas: List[Dict],
    query_tokens: Set[str],
    n_results: int = 20,
) -> List[Tuple[str, int]]:
    """
    Score every DB document by token overlap and return the top-n (id, score) pairs
    sorted descending.
    """
    scored: List[Tuple[str, int]] = []
    for doc_id, doc_text in zip(all_ids, all_docs):
        score = _keyword_score(doc_text, query_tokens)
        if score > 0:
            scored.append((doc_id, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:n_results]


# ---------------------------------------------------------------------------
# Helpers — Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    semantic_ids: List[str],
    keyword_ranked: List[Tuple[str, int]],
) -> List[str]:
    """
    Merge two ranked lists with RRF: score = Σ 1/(k + rank).
    Returns a de-duplicated list of IDs sorted by fused score descending.
    """
    rrf_scores: Dict[str, float] = {}

    for rank, doc_id in enumerate(semantic_ids):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    for rank, (doc_id, _) in enumerate(keyword_ranked):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    return sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)


# ---------------------------------------------------------------------------
# Helpers — Hard Specialty-Group Gate
# ---------------------------------------------------------------------------

def _hard_group_gate(candidates: List[Dict], required_groups: Set[str]) -> List[Dict]:
    """
    Drop candidates whose specialty group has zero overlap with the patient's
    required groups.  Falls back to the full list if no candidates survive
    (e.g. rare / multi-specialty cases).
    """
    if not required_groups:
        return candidates  # no group constraint — pass all through

    filtered = [
        c for c in candidates
        if specialty_groups_for_text(
            c.get("specialty", ""),
            c.get("specialty_tags", ""),
            c.get("rag_summary", ""),
        ) & required_groups
    ]
    return filtered if filtered else candidates  # relax if empty


# ---------------------------------------------------------------------------
# Scoring — Metadata-Enriched Ranker
# ---------------------------------------------------------------------------

def rank_doctor_matches(medical_data: Dict, candidates: List[Dict], limit: int = 5) -> List[Dict]:
    """
    Score and rank candidates using specialty-group overlap + metadata enrichment.
    Returns the top `limit` (default 5) candidates for the LLM rerank step.
    """
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
            candidate.get("primary_practice", ""),
        ])
        candidate_specialties = infer_specialties(candidate_text)
        candidate_groups = specialty_groups_for_text(candidate_text)

        # --- Base score: position decay (later in RRF list = lower base) ---
        score = max(0, 8 - index)

        # --- Registration & verification bonuses ---
        if candidate.get("mmc_url"):
            score += 2
        if candidate.get("provisional_registration_number") or candidate.get("full_registration_number"):
            score += 2

        # --- Specialty group overlap (primary signal) ---
        group_overlap = profile["groups"] & candidate_groups
        if group_overlap:
            score += 12 * len(group_overlap)
        elif profile["groups"]:
            score -= 10  # wrong specialty group

        # --- Sub-specialty refinements ---
        if profile["lung_focus"] and any(
            sp in candidate_specialties
            for sp in ("Medical Oncology", "Radiation Oncology", "Thoracic Surgery", "Pulmonology")
        ):
            score += 8

        if "oncology" in profile["groups"] and "cardiology" in candidate_groups and not profile["cardio_oncology"]:
            score -= 20  # cardiologist for an oncology-only patient

        # --- Metadata enrichment bonuses ---

        # Severity: critical cases benefit from established specialist centres
        if severity == "Critical":
            tier = candidate.get("tier", "")
            if tier in ("Government / Semi-Gov",):
                # IKN / IJN / HKL handle the most complex cases
                score += 5
            if candidate.get("full_registration_number"):
                score += 3  # senior, fully registered doctor for critical cases

        # Urgency: prefer fully registered (senior) doctors for high-urgency
        if urgency in ("High", "Critical"):
            if candidate.get("full_registration_number"):
                score += 3

        # Paediatric patients → boost paediatric-tagged specialists
        if "paediatr" in age_group.lower() or "pediatr" in age_group.lower():
            if "paediatr" in candidate_text.lower() or "pediatr" in candidate_text.lower():
                score += 10

        ranked_candidate = dict(candidate)
        ranked_candidate["match_score"] = score
        ranked.append(ranked_candidate)

    ranked.sort(key=lambda item: item["match_score"], reverse=True)
    return ranked[:limit]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_hospitals(medical_data: Dict) -> List[Dict]:
    """
    Match the patient's condition to specific specialists using a 4-stage pipeline:
      1. Hybrid Search (semantic + keyword → RRF) → top-20 candidates
      2. Hard specialty-group gate                → drop wrong-group candidates
      3. Metadata-enriched scoring               → top-5
      4. LLM rerank (rerank_agent)               → final top-3
    """
    profile = build_case_profile(medical_data)
    condition = profile["condition"] or "General Medicine"
    sub_specialty = profile["sub_specialty"] or condition
    
    print(f"  [MedicalAgent] Searching for specialists for: {condition}...")
    
    print("  [MedicalAgent] Initializing ChromaDB Client...")
    # Silence telemetry via env var before creating client
    os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "False"
    client = chromadb.PersistentClient(path=str(DB_PATH))

    try:
        collection = client.get_collection(name="malaysia_doctors")
    except Exception:
        print("  [!] Warning: 'malaysia_doctors' collection not found.")
        return []

    query_text = (
        f"Specialist for {condition}. "
        f"Needed department: {sub_specialty}. "
        f"Relevant specialties: {', '.join(profile['specialties'])}. "
        f"Clinical summary: {profile['summary']}."
    )

    # -----------------------------------------------------------------------
    # Stage 1: Hybrid Search
    # -----------------------------------------------------------------------
    print("  [MedicalAgent] Stage 1a: Running Semantic Search...")
    sem_results = collection.query(query_texts=[query_text], n_results=15)
    semantic_ids: List[str] = sem_results["ids"][0] if sem_results and sem_results.get("ids") else []

    print("  [MedicalAgent] Stage 1b: Running Keyword Search (loading all docs)...")
    all_data = collection.get()
    all_ids: List[str] = all_data.get("ids", [])
    all_docs: List[str] = all_data.get("documents", []) or []
    all_metas: List[Dict] = all_data.get("metadatas", []) or []

    query_tokens = _extract_query_tokens(profile)
    keyword_ranked = _keyword_search(all_ids, all_docs, all_metas, query_tokens, n_results=20)

    print("  [MedicalAgent] Stage 1c: Fusing results (RRF)...")
    fused_ids = _reciprocal_rank_fusion(semantic_ids, keyword_ranked)[:20]

    # Build a lookup from id → (meta, doc) for fast access
    id_to_meta: Dict[str, Dict] = {doc_id: meta for doc_id, meta in zip(all_ids, all_metas)}
    id_to_doc: Dict[str, str] = {doc_id: doc for doc_id, doc in zip(all_ids, all_docs)}

    # Assemble candidate dicts from the fused ranking
    candidates: List[Dict] = []
    for doc_id in fused_ids:
        if doc_id not in id_to_meta:
            continue
        meta = id_to_meta[doc_id]
        doc_text = id_to_doc.get(doc_id, "")
        candidates.append({
            "id": doc_id,
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
        })

    # -----------------------------------------------------------------------
    # Stage 2: Hard specialty-group gate
    # -----------------------------------------------------------------------
    print("  [MedicalAgent] Stage 2: Applying Hard Specialty Gate...")
    candidates = _hard_group_gate(candidates, profile["groups"])

    # -----------------------------------------------------------------------
    # Stage 3: Metadata-enriched scoring → top-5
    # -----------------------------------------------------------------------
    print("  [MedicalAgent] Stage 3: Running Metadata-Enriched Scoring...")
    top5 = rank_doctor_matches(medical_data, candidates, limit=5)

    # -----------------------------------------------------------------------
    # Stage 4: LLM rerank → final top-3
    # -----------------------------------------------------------------------
    print("  [MedicalAgent] Stage 4: Initiating LLM Rerank...")
    try:
        from agents.rerank_agent import llm_rerank
        return llm_rerank(top5, medical_data)
    except Exception as exc:
        print(f"  [!] LLM rerank unavailable, using scored order: {exc}")
        return top5[:3]
