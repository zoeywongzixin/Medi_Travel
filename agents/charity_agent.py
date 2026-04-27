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
  3. Regional ASEAN funds
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


# ---------------------------------------------------------------------------
# ChromaDB connection
# ---------------------------------------------------------------------------

def _get_collection() -> Optional[chromadb.Collection]:
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
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
    Match patient profile to charity funds using two-stage Vector RAG
    with country-priority post-ranking.

    Args:
        medical_data:   dict with at least {'condition': str}
        origin_country: patient's home country e.g. 'Laos', 'Vietnam'
        top_n:          max results to return

    Returns:
        List of matched fund dicts, country-specific ranked first.
    """
    collection = _get_collection()
    if collection is None or collection.count() == 0:
        return []

    condition = medical_data.get("condition", "general medical")
    return _two_stage_query(collection, condition, origin_country, top_n)


def get_funds_for_country(country: str) -> List[Dict]:
    """Return all charities that explicitly target a specific country."""
    collection = _get_collection()
    if collection is None or collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[f"Medical financial assistance fund for {country} patients"],
        n_results=min(20, collection.count()),
    )
    funds = []
    if results and results.get("ids"):
        for i, cid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            target_list = _parse_list(meta.get("target_countries", "[]"))
            origin = (meta.get("origin_country") or "").lower()
            if country.lower() in [t.lower() for t in target_list] or origin == country.lower():
                funds.append({
                    "id": cid,
                    "name": meta.get("name", ""),
                    "organization": meta.get("organization", ""),
                    "source": meta.get("source", ""),
                    "origin_country": meta.get("origin_country", ""),
                    "target_countries": target_list,
                    "conditions_covered": _parse_list(meta.get("conditions_covered", "[]")),
                    "max_coverage_usd": int(meta.get("max_coverage_usd", 0)),
                    "url": meta.get("url", ""),
                })
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
        charities.append({
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
        })
    return charities


def collection_count() -> int:
    c = _get_collection()
    return c.count() if c else 0


# ---------------------------------------------------------------------------
# Internal: two-stage RAG + priority ranking
# ---------------------------------------------------------------------------

def _two_stage_query(
    collection: chromadb.Collection,
    condition: str,
    origin_country: str,
    top_n: int,
) -> List[Dict]:
    n_results = min(top_n + 5, collection.count())

    # Stage 1: country-specific query
    r1 = collection.query(
        query_texts=[f"Fund for {origin_country} patients with {condition}"],
        n_results=n_results,
    )
    # Stage 2: regional / theme query
    r2 = collection.query(
        query_texts=[f"ASEAN medical financial aid {condition} treatment"],
        n_results=n_results,
    )

    seen: set = set()
    candidates: List[Dict] = []
    for results in (r1, r2):
        if not results or not results.get("ids"):
            continue
        for i, cid in enumerate(results["ids"][0]):
            if cid in seen:
                continue
            seen.add(cid)
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            candidates.append({
                "id": cid,
                "name": meta.get("name", "Unknown Fund"),
                "organization": meta.get("organization", ""),
                "source": meta.get("source", ""),
                "origin_country": meta.get("origin_country", ""),
                "target_countries": _parse_list(meta.get("target_countries", "[]")),
                "target_audience": _parse_list(meta.get("target_audience", "[]")),
                "conditions_covered": _parse_list(meta.get("conditions_covered", "[]")),
                "max_coverage_usd": int(meta.get("max_coverage_usd", 0)),
                "url": meta.get("url", ""),
            })

    candidates.sort(key=lambda c: _priority(c, origin_country, condition), reverse=True)
    return candidates[:top_n]


def _priority(c: Dict, origin_country: str, condition: str) -> int:
    score = 0
    country_lc = origin_country.lower()
    origin_lc = (c.get("origin_country") or "").lower()
    target_lc = [t.lower() for t in c.get("target_countries", [])]
    audience_lc = [t.lower() for t in c.get("target_audience", [])]
    cond_lc = [t.lower() for t in c.get("conditions_covered", [])]
    cond_query_lc = condition.lower()

    if origin_lc == country_lc:
        score += 100          # Fund originated from patient's own country
    if country_lc in target_lc:
        score += 50           # Fund explicitly targets this country
    if "asean" in audience_lc:
        score += 10           # Broad ASEAN coverage

    # Condition relevance
    if any(kw in cond_query_lc for kw in cond_lc) or any(cond_query_lc in t for t in cond_lc):
        score += 20

    return score


def _parse_list(value) -> List[str]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [value] if value else []
