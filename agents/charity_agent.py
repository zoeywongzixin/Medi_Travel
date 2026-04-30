"""
Charity Agent
=============
Queries the persistent ChromaDB 'charities' collection that was populated
by pipeline/ingest_charities.py.

At runtime NO network calls are made — data was fetched once at ingest time
and lives in the local vector database.

Country-Priority RAG Logic:
  1. Funds where origin_country == patient's country  (highest priority)
  2. Funds where target_countries includes the patient's country
  3. Regional ASEAN funds (specific groupings like CLMV)
  4. General international funds
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

ROOT_DIR = Path(__file__).resolve().parent.parent
CHROMA_DB_PATH = str(ROOT_DIR / "data" / "chroma_db")

_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None
SUPPORTED_CHARITY_AREAS = ("cardiology", "oncology")
CONDITION_KEYWORDS = {
    "cardiology": ("heart", "cardio", "cardiac", "cardiovascular", "coronary", "jantung"),
    "oncology": ("cancer", "oncology", "tumor", "tumour", "chemotherapy", "radiotherapy", "kanser"),
}

# ASEAN Regional Groupings
ASEAN_GROUPS = {
    "clmv": {"cambodia", "laos", "myanmar", "vietnam"},
    "bimp-eaga": {"brunei", "indonesia", "malaysia", "philippines"},
    "imes": {"indonesia", "malaysia", "singapore"},
}


# ---------------------------------------------------------------------------
# ChromaDB connection
# ---------------------------------------------------------------------------

def _get_collection() -> Optional[chromadb.Collection]:
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import os
        os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "False"
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        emb_fn = embedding_functions.DefaultEmbeddingFunction()
        _collection = _client.get_collection(name="charities", embedding_function=emb_fn)
        return _collection
    except Exception as exc:
        print(f"[CharityAgent] ChromaDB unavailable: {exc}")
        print("[CharityAgent] Run: python pipeline/ingest_charities.py")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_charities(medical_data: Dict, origin_country: str, top_n: int = 3) -> List[Dict]:
    """
    Match patient profile to charity funds using a two-stage pipeline:
      Stage 1: Semantic vector query against ChromaDB charities collection
               → narrows to the most contextually relevant funds.
      Stage 2: Metadata priority ranking with severity/urgency enrichment
               → country-specific and well-funded results ranked first.

    Args:
        medical_data:   dict with at least {'condition': str}.
                        May also contain 'severity', 'urgency' for enriched ranking.
        origin_country: patient's home country e.g. 'Laos', 'Vietnam'
        top_n:          max results to return

    Returns:
        List of matched fund dicts, country-specific ranked first.
    """
    condition = medical_data.get("condition", "general medical")
    allowed_area = _condition_area_for_query(condition)
    if allowed_area is None:
        return []

    # ---------------------------------------------------------------------------
    # Stage 1: Semantic pre-query — actually use the vector DB
    # ---------------------------------------------------------------------------
    collection = _get_collection()
    semantic_ids: set = set()
    if collection is not None and collection.count() > 0:
        severity = medical_data.get("severity", "")
        urgency = medical_data.get("urgency", "")
        query_text = (
            f"Financial aid fund for {condition} patients from {origin_country}. "
            f"Severity: {severity}. Urgency: {urgency}. "
            f"Medical area: {allowed_area}. ASEAN medical tourism support."
        )
        try:
            n_query = min(15, collection.count())
            sem_results = collection.query(query_texts=[query_text], n_results=n_query)
            if sem_results and sem_results.get("ids"):
                semantic_ids = set(sem_results["ids"][0])
        except Exception as exc:
            print(f"[CharityAgent] Semantic query failed, falling back to full scan: {exc}")

    # ---------------------------------------------------------------------------
    # Stage 2: Metadata priority ranking
    # ---------------------------------------------------------------------------
    funds = get_all_charities()
    if not funds:
        return []

    # Prefer semantically matched funds — boost their priority score
    return _rank_supported_funds(funds, condition, origin_country, top_n, allowed_area,
                                  semantic_ids=semantic_ids, medical_data=medical_data)


def get_funds_for_country(country: str) -> List[Dict]:
    """Return all charities that explicitly target a specific country."""
    funds = []
    for fund in get_all_charities():
        target_list = fund.get("target_countries", [])
        origin = (fund.get("origin_country") or "").lower()
        if country.lower() in [t.lower() for t in target_list] or origin == country.lower():
            funds.append(fund)
    return funds


def get_all_charities() -> List[Dict]:
    """Return all charities in the collection (for dashboard use)."""
    collection = _get_collection()
    if collection is None or collection.count() == 0:
        return []
    results = collection.get()
    charities = []
    for i, cid in enumerate(results["ids"]):
        meta = results["metadatas"][i] if results.get("metadatas") else {}
        charity = {
            "id": cid,
            "name": meta.get("name", ""),
            "organization": meta.get("organization", ""),
            "source": meta.get("source", ""),
            "origin_country": meta.get("origin_country", ""),
            "target_countries": _parse_list(meta.get("target_countries", "[]")),
            "target_audience": _parse_list(meta.get("target_audience", "[]")),
            "conditions_covered": _parse_list(meta.get("conditions_covered", "[]")),
            "max_coverage_usd": int(meta.get("max_coverage_usd", 0)),
            "url": meta.get("url", ""),
            "active": meta.get("active", "True") == "True",
        }
        if _fund_supported(charity):
            charities.append(charity)
    return charities


def collection_count() -> int:
    c = _get_collection()
    return c.count() if c else 0


# ---------------------------------------------------------------------------
# Internal: two-stage RAG + priority ranking
# ---------------------------------------------------------------------------

def _rank_supported_funds(
    funds: List[Dict],
    condition: str,
    origin_country: str,
    top_n: int,
    allowed_area: str,
    semantic_ids: set = None,
    medical_data: Dict = None,
) -> List[Dict]:
    candidates = [fund for fund in funds if _fund_matches_area(fund, allowed_area)]
    candidates.sort(
        key=lambda c: _priority(
            c, origin_country, condition, allowed_area,
            semantic_ids=semantic_ids or set(),
            medical_data=medical_data or {},
        ),
        reverse=True,
    )
    return candidates[:top_n]


def _priority(
    c: Dict,
    origin_country: str,
    condition: str,
    allowed_area: str,
    semantic_ids: set = None,
    medical_data: Dict = None,
) -> int:
    score = 0
    country_lc = origin_country.lower()
    origin_lc = (c.get("origin_country") or "").lower()
    target_lc = [t.lower() for t in c.get("target_countries", [])]
    audience_lc = [t.lower() for t in c.get("target_audience", [])]
    cond_lc = _normalized_condition_areas(c.get("conditions_covered", []))
    cond_query_lc = condition.lower()

    # --- Country priority ---
    if origin_lc == country_lc:
        score += 100          # Fund originated from patient's own country
    if country_lc in target_lc:
        score += 50           # Fund explicitly targets this country
        
    # --- Regional ASEAN logic ---
    if "asean" in audience_lc:
        score += 10           # Broad ASEAN coverage
        
    for group_name, countries in ASEAN_GROUPS.items():
        if country_lc in countries:
            if group_name in audience_lc or group_name in target_lc:
                score += 25   # Specific ASEAN sub-regional match (e.g., CLMV)

    # --- Condition relevance ---
    if allowed_area in cond_lc:
        score += 30           # Heavy boost for primary specialty match
    if any(keyword in cond_query_lc for keyword in CONDITION_KEYWORDS.get(allowed_area, ())):
        score += 15

    # --- Semantic match bonus ---
    if semantic_ids and c.get("id") in semantic_ids:
        score += 25           # ChromaDB ranked this fund as contextually relevant

    # --- Metadata enrichment bonuses ---
    md = medical_data or {}
    severity = (md.get("severity") or "").strip().title()
    urgency = (md.get("urgency") or "").strip().title()
    max_coverage = c.get("max_coverage_usd", 0)

    # Active funds with real coverage are worth more for urgent cases
    if urgency in ("High", "Critical") and c.get("active"):
        score += 20

    # Critical patients need funds that actually have money
    if severity == "Critical" and max_coverage == 0:
        score -= 30           # Penalise zero-coverage funds for critical cases

    # Reward funds whose coverage is meaningful (>= $500 USD)
    if max_coverage >= 500:
        score += 10
    if max_coverage >= 2000:
        score += 5            # Extra bump for well-funded grants

    return score


def _parse_list(value) -> List[str]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [value] if value else []


def _condition_area_for_query(condition: str) -> Optional[str]:
    text = (condition or "").lower()
    matched = [area for area, keywords in CONDITION_KEYWORDS.items() if any(keyword in text for keyword in keywords)]
    if not matched:
        return None
    if "oncology" in matched:
        return "oncology"
    if "cardiology" in matched:
        return "cardiology"
    return None


def _normalized_condition_areas(conditions: List[str]) -> List[str]:
    normalized: List[str] = []
    for condition in conditions:
        area = _condition_area_for_query(condition)
        if area and area not in normalized:
            normalized.append(area)
    return normalized


def _fund_matches_area(fund: Dict, allowed_area: str) -> bool:
    return allowed_area in _normalized_condition_areas(fund.get("conditions_covered", []))


def _fund_supported(fund: Dict) -> bool:
    return any(area in SUPPORTED_CHARITY_AREAS for area in _normalized_condition_areas(fund.get("conditions_covered", [])))
