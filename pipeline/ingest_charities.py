"""
Charity Ingestion Pipeline
==========================
Scrapes charity/fund data from external sources ONCE and ingests into
persistent ChromaDB RAG. At query time, the charity_agent reads directly
from ChromaDB — no network calls, no re-scraping.

Sources (in priority order):
  1. GlobalGiving REST API  — requires GLOBALGIVING_API_KEY in .env (free)
     Endpoint: /country/{ISO} filtered to health themes for all ASEAN nations
  2. IATI XML feed          — zero auth, daily updated from GlobalGiving
     URL: https://globalgiving.org/iati/activities.xml

Run once to populate, or re-run periodically to refresh:
  python pipeline/ingest_charities.py
  python pipeline/ingest_charities.py --source globalgiving
  python pipeline/ingest_charities.py --source iati
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
import requests
import urllib3
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DB_PATH = str(DATA_DIR / "chroma_db")

GLOBALGIVING_API_KEY = os.getenv("GLOBALGIVING_API_KEY", "")
GLOBALGIVING_BASE = "https://api.globalgiving.org/api/public/projectservice"
GLOBALGIVING_MAX_PAGES = 5  # max pages per country (10 results/page)
IATI_ACTIVITIES_URL = "https://globalgiving.org/iati/activities.xml"
DEFAULT_TIMEOUT = 20

# ASEAN countries — ISO 3166-1 alpha-2 mapped to display name
ASEAN_COUNTRIES: Dict[str, str] = {
    "LA": "Laos",
    "VN": "Vietnam",
    "KH": "Cambodia",
    "MM": "Myanmar",
    "TH": "Thailand",
    "ID": "Indonesia",
    "PH": "Philippines",
    "MY": "Malaysia",
    "SG": "Singapore",
    "BN": "Brunei",
    "TL": "Timor-Leste",
}

# GlobalGiving theme IDs covering health
HEALTH_THEME_IDS = {8, 2, 14}  # Physical Health, Children, Women & Girls

# IATI DAC sector codes for health (120–129)
HEALTH_DAC_RANGE = range(120, 130)
HEALTH_KEYWORDS = {"health", "medical", "hospital", "disease", "cancer", "cardiac", "surgery"}


# ---------------------------------------------------------------------------
# Source 1: GlobalGiving REST API
# ---------------------------------------------------------------------------

def _gg_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "ASEANMedicalMatchBot/1.0"})
    return s


def _gg_text(el, tag: str) -> str:
    """Get text from a child XML element, or empty string."""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_gg_xml_project(proj_el, country_name: str) -> Optional[Dict]:
    """Parse a single <project> element from GlobalGiving XML."""
    theme_name = _gg_text(proj_el, "themeName").lower()
    title = _gg_text(proj_el, "title")
    summary = _gg_text(proj_el, "summary")
    is_health = any(kw in theme_name for kw in HEALTH_KEYWORDS) or \
                any(kw in (title + " " + summary).lower() for kw in HEALTH_KEYWORDS)
    if not is_health:
        return None

    proj_id = _gg_text(proj_el, "id")
    goal = _safe_float(_gg_text(proj_el, "goal"))
    remaining = _safe_float(_gg_text(proj_el, "remaining") or _gg_text(proj_el, "remainingFunding"))
    org_el = proj_el.find("organization")
    org_name = _gg_text(org_el, "name") if org_el is not None else "Unknown Org"
    link = _gg_text(proj_el, "projectLink")
    text = f"{title} {summary}"
    return {
        "id": f"gg_{proj_id}",
        "name": title or "Unnamed Project",
        "source": "GlobalGiving",
        "url": link,
        "organization": org_name,
        "description": summary,
        "conditions_covered": _infer_conditions(text),
        "target_countries": [country_name],
        "origin_country": country_name,
        "target_audience": [country_name, "ASEAN"],
        "max_coverage_usd": int(min(remaining, 5000)) if remaining > 0 else int(min(goal, 5000)),
        "theme": theme_name.title() or "Physical Health",
        "active": _gg_text(proj_el, "active").lower() == "true",
    }


def _fetch_gg_country(session: requests.Session, iso: str, country_name: str) -> List[Dict]:
    if not GLOBALGIVING_API_KEY:
        return []
    # Correct URL: /countries/{ISO}/projects/active  (paginated, XML)
    base_url = f"{GLOBALGIVING_BASE}/countries/{iso}/projects/active"
    projects = []
    next_id = None
    for page in range(GLOBALGIVING_MAX_PAGES):
        params: Dict = {"api_key": GLOBALGIVING_API_KEY}
        if next_id:
            params["nextProjectId"] = next_id
        try:
            resp = session.get(base_url, params=params, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 404:
                break  # No projects for this country
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as exc:
            print(f"  [GlobalGiving] {country_name} page {page+1}: {exc}")
            break

        for proj_el in root.findall("project"):
            entry = _parse_gg_xml_project(proj_el, country_name)
            if entry:
                projects.append(entry)

        # Pagination
        has_next = root.findtext("hasNext", "false").lower() == "true"
        next_id = root.findtext("nextProjectId")
        if not has_next or not next_id:
            break

    print(f"  [GlobalGiving] {country_name}: {len(projects)} health projects")
    return projects


def _safe_float(val) -> float:
    try:
        return float(str(val).strip())
    except (TypeError, ValueError):
        return 0.0


def fetch_globalgiving() -> List[Dict]:
    if not GLOBALGIVING_API_KEY:
        print("[GlobalGiving] No API key found in .env — skipping.")
        return []
    print("\n[GlobalGiving] Fetching ASEAN health projects...")
    session = _gg_session()
    results: List[Dict] = []
    for iso, name in ASEAN_COUNTRIES.items():
        results.extend(_fetch_gg_country(session, iso, name))
    print(f"[GlobalGiving] Total: {len(results)} projects")
    return results


# ---------------------------------------------------------------------------
# Source 2: IATI XML Feed
# ---------------------------------------------------------------------------

def _iati_text(el, xpath: str) -> str:
    """Namespace-agnostic text extraction for IATI XML."""
    # Try without namespace first, then strip namespace prefix
    child = el.find(xpath)
    if child is not None and child.text:
        return child.text.strip()
    # Some IATI feeds use narrative as direct child text
    parts = xpath.split("/")
    curr = el
    for part in parts:
        found = None
        for c in curr:
            local = c.tag.split("}")[-1] if "}" in c.tag else c.tag
            if local == part:
                found = c
                break
        if found is None:
            return ""
        curr = found
    return (curr.text or "").strip()


def fetch_iati() -> List[Dict]:
    print("\n[IATI] Fetching GlobalGiving IATI XML (no API key)...")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        resp = requests.get(IATI_ACTIVITIES_URL, timeout=90, stream=True, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as exc:
        print(f"[IATI] Failed: {exc}")
        return []

    asean_iso = set(ASEAN_COUNTRIES)
    asean_names_lower = {n.lower() for n in ASEAN_COUNTRIES.values()}
    projects: List[Dict] = []

    def local(el) -> str:
        return el.tag.split("}")[-1] if "}" in el.tag else el.tag

    def find_local(parent, tag: str):
        for c in parent:
            if local(c) == tag:
                return c
        return None

    def find_all_local(parent, tag: str):
        return [c for c in parent if local(c) == tag]

    activities = find_all_local(root, "iati-activity") or root.findall("iati-activity")

    for activity in activities:
        # Recipient country
        recipient = find_local(activity, "recipient-country")
        if recipient is None:
            continue
        iso = (recipient.get("code") or "").upper().strip()
        r_name = (recipient.get("name") or "").strip()
        if iso not in asean_iso and r_name.lower() not in asean_names_lower:
            continue
        country_name = ASEAN_COUNTRIES.get(iso) or r_name or iso

        # Sector check
        sector = find_local(activity, "sector")
        sector_code = _safe_int((sector.get("code") or 0) if sector is not None else 0)
        sector_text = ((sector.get("name") or "").lower() if sector is not None else "")
        is_health = sector_code in HEALTH_DAC_RANGE or any(kw in sector_text for kw in HEALTH_KEYWORDS)

        # Title / description text
        title_el = find_local(activity, "title")
        title = ""
        if title_el is not None:
            narr = find_local(title_el, "narrative")
            title = (narr.text or title_el.text or "").strip() if narr is not None else (title_el.text or "").strip()
        desc_el = find_local(activity, "description")
        desc = ""
        if desc_el is not None:
            narr = find_local(desc_el, "narrative")
            desc = (narr.text or desc_el.text or "").strip() if narr is not None else (desc_el.text or "").strip()

        # Check health via text if sector didn't match
        text = f"{title} {desc}"
        if not is_health:
            is_health = any(kw in text.lower() for kw in HEALTH_KEYWORDS)
        if not is_health:
            continue

        budget_el = find_local(activity, "budget")
        budget_val_el = find_local(budget_el, "value") if budget_el is not None else None
        budget = _safe_int(budget_val_el.text) if budget_val_el is not None else 0

        org_el = find_local(activity, "reporting-org")
        org = ""
        if org_el is not None:
            narr = find_local(org_el, "narrative")
            org = (narr.text or org_el.text or "").strip() if narr is not None else (org_el.text or "").strip()
        org = org or "Unknown Org"

        id_el = find_local(activity, "iati-identifier")
        proj_id = (id_el.text or f"idx_{len(projects)}").strip().replace("/", "_") if id_el is not None else f"idx_{len(projects)}"

        projects.append({
            "id": f"iati_{proj_id}",
            "name": title or "IATI Health Activity",
            "source": "IATI / GlobalGiving",
            "url": f"https://globalgiving.org/iati/activities.xml",
            "organization": org,
            "description": desc,
            "conditions_covered": _infer_conditions(text),
            "target_countries": [country_name],
            "origin_country": country_name,
            "target_audience": [country_name, "ASEAN"],
            "max_coverage_usd": min(budget, 10000) if budget > 0 else 2000,
            "theme": "Physical Health",
            "active": True,
        })

    print(f"[IATI] Found {len(projects)} ASEAN health activities")
    return projects


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONDITION_MAP: Dict[str, List[str]] = {
    "cardiology": ["heart", "cardiac", "cardio", "cardiovascular", "cardiothoracic"],
    "oncology": ["cancer", "oncol", "tumor", "tumour", "chemotherapy", "radiotherapy"],
}
SUPPORTED_CHARITY_CONDITIONS = {"cardiology", "oncology"}


def _infer_conditions(text: str) -> List[str]:
    t = text.lower()
    matched = [c for c, kws in CONDITION_MAP.items() if any(kw in t for kw in kws)]
    return [condition for condition in matched if condition in SUPPORTED_CHARITY_CONDITIONS]


def _safe_int(val) -> int:
    try:
        return int(float(str(val)))
    except (TypeError, ValueError):
        return 0


def _code_to_name(code: str) -> Optional[str]:
    return ASEAN_COUNTRIES.get(code.upper())


def deduplicate(records: List[Dict]) -> List[Dict]:
    seen: Dict[str, Dict] = {}
    for r in records:
        key = r["id"]
        if key not in seen:
            seen[key] = r
        else:
            # Merge target_countries
            merged = list(set(seen[key]["target_countries"] + r["target_countries"]))
            seen[key]["target_countries"] = merged
    return list(seen.values())


# ---------------------------------------------------------------------------
# ChromaDB ingest
# ---------------------------------------------------------------------------

def _build_document(c: Dict) -> str:
    conditions = ", ".join(c.get("conditions_covered") or ["General Medical"])
    countries = ", ".join(c.get("target_countries") or ["ASEAN"])
    audience = ", ".join(c.get("target_audience") or ["ASEAN"])
    return (
        f"Fund Name: {c['name']}\n"
        f"Organization: {c.get('organization', 'Unknown')}\n"
        f"Source: {c.get('source', '')}\n"
        f"Origin Country (fund based in): {c.get('origin_country', 'International')}\n"
        f"Beneficiary Countries (patients from): {countries}\n"
        f"Target Audience: {audience}\n"
        f"Medical Conditions Covered: {conditions}\n"
        f"Theme: {c.get('theme', 'Physical Health')}\n"
        f"Max Coverage (USD): {c.get('max_coverage_usd', 0)}\n"
        f"Description: {c.get('description', '')}\n"
        f"Apply / More Info: {c.get('url', 'N/A')}"
    )


def ingest_to_chroma(charities: List[Dict]) -> None:
    charities = [
        charity
        for charity in charities
        if any(condition in SUPPORTED_CHARITY_CONDITIONS for condition in charity.get("conditions_covered", []))
    ]
    print(f"\n[ChromaDB] Ingesting {len(charities)} charities into persistent RAG...")
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    emb_fn = embedding_functions.DefaultEmbeddingFunction()

    try:
        client.delete_collection("charities")
        print("[ChromaDB] Dropped old 'charities' collection.")
    except Exception:
        pass

    collection = client.create_collection(name="charities", embedding_function=emb_fn)

    ids, documents, metadatas = [], [], []
    for c in charities:
        ids.append(c["id"])
        documents.append(_build_document(c))
        metadatas.append({
            "name": c["name"],
            "organization": c.get("organization", ""),
            "source": c.get("source", ""),
            "origin_country": c.get("origin_country", ""),
            "target_countries": json.dumps(c.get("target_countries", [])),
            "target_audience": json.dumps(c.get("target_audience", [])),
            "conditions_covered": json.dumps(c.get("conditions_covered", [])),
            "max_coverage_usd": int(c.get("max_coverage_usd", 0)),
            "url": c.get("url", ""),
            "active": str(c.get("active", True)),
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"[ChromaDB] Ingested {len(ids)} charities into 'charities' collection.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(source: str = "all") -> None:
    all_charities: List[Dict] = []

    if source in ("globalgiving", "all"):
        all_charities.extend(fetch_globalgiving())

    if source in ("iati", "all"):
        all_charities.extend(fetch_iati())

    if not all_charities:
        print("\n[Warning] No charity data fetched. Check API key and network.")
        print("  Add GLOBALGIVING_API_KEY to .env and ensure network access.")
        return

    all_charities = deduplicate(all_charities)
    print(f"\n[Total] {len(all_charities)} unique charity records after dedup.")
    ingest_to_chroma(all_charities)
    print(f"\nCharity ingestion complete.")
    print(f"   ChromaDB: {CHROMA_DB_PATH} / charities collection")
    print(f"   Records : {len(all_charities)}")
    print(f"   Usage   : charity_agent.py queries ChromaDB directly at runtime.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest charity data into ChromaDB RAG")
    parser.add_argument(
        "--source",
        choices=["all", "globalgiving", "iati"],
        default="all",
        help="Data source (default: all)",
    )
    main(source=parser.parse_args().source)
