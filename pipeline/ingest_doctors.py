import os
import re
import sys
from typing import Dict, Iterable, List, Optional

import chromadb
import requests
from bs4 import BeautifulSoup

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.medical_specialty import infer_specialties

MMC_BASE_URL = "https://merits.mmc.gov.my"
MMC_SEARCH_URL = f"{MMC_BASE_URL}/search/registeredDoctor"
DEFAULT_TIMEOUT = 20
DEFAULT_MAX_PAGES = int(os.getenv("MMC_MAX_PAGES_PER_QUERY", "2"))
DEFAULT_MAX_DOCTORS_PER_QUERY = int(os.getenv("MMC_MAX_DOCTORS_PER_QUERY", "15"))
DEFAULT_SEARCH_TERMS = [
    "ONKOLOGI",
    "KANSER",
    "RADIOTERAPI",
    "THORACIC",
    "RESPIRATORY",
    "KARDIOLOGI",
    "CARDIOLOGY",
]


def fetch_html(session: requests.Session, url: str, params: Optional[Dict] = None) -> str:
    response = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_search_results(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#viewDoktor tbody tr")
    doctors: List[Dict] = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        link = row.find("a", onclick=True)
        if not link:
            continue

        match = re.search(r"'(https://merits\.mmc\.gov\.my/viewDoctor/\d+/search)'", link["onclick"])
        if not match:
            continue

        doctors.append(
            {
                "name": cells[1].get_text(" ", strip=True),
                "graduated_from": cells[2].get_text(" ", strip=True),
                "detail_url": match.group(1),
            }
        )

    return doctors


def extract_labeled_fields(soup: BeautifulSoup) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for row in soup.select("div.form-group.row"):
        label = row.find("label")
        value = row.find("div", class_="col-sm-6")
        if not label or not value:
            continue
        key = re.sub(r"\s+", " ", label.get_text(" ", strip=True)).strip().lower()
        fields[key] = value.get_text(" ", strip=True)
    return fields


def parse_practice_rows(soup: BeautifulSoup) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for row in soup.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) != 5:
            continue
        rows.append(
            {
                "apc_year": cells[1].get_text(" ", strip=True),
                "apc_number": cells[2].get_text(" ", strip=True),
                "principle": cells[3].get_text("\n", strip=True),
                "others": cells[4].get_text("\n", strip=True),
            }
        )
    return rows


def infer_hospital_name(practice_rows: Iterable[Dict[str, str]]) -> str:
    hospital_keywords = (
        "hospital",
        "medical centre",
        "medical center",
        "centre",
        "center",
        "institut",
        "institute",
        "klinik",
        "pusat perubatan",
        "jantung",
        "kanser",
    )

    for row in practice_rows:
        principle = row.get("principle", "")
        first_line = principle.splitlines()[0].strip() if principle else ""
        if not first_line:
            continue

        segments = [segment.strip(" ,") for segment in first_line.split(",") if segment.strip(" ,")]
        for segment in reversed(segments):
            lowered = segment.lower()
            if any(keyword in lowered for keyword in hospital_keywords):
                return segment
        if segments:
            return segments[-1]

    return "Unknown Hospital"


def infer_tier(hospital: str, practice_text: str) -> str:
    haystack = f"{hospital} {practice_text}".lower()

    if any(token in haystack for token in ("prince court", "gleneagles")):
        return "Premium Private"
    if any(
        token in haystack
        for token in (
            "institut kanser negara",
            "universiti",
            "kementerian kesihatan",
            "institut jantung negara",
            "hospital kuala lumpur",
        )
    ):
        return "Government / Semi-Gov"
    if any(token in haystack for token in ("medical centre", "specialist hospital", "hospital", "centre", "center")):
        return "Standard Private"
    return "Government / Semi-Gov"


def build_doctor_profile(seed: Dict, detail_html: str) -> Dict:
    soup = BeautifulSoup(detail_html, "html.parser")
    fields = extract_labeled_fields(soup)
    practice_rows = parse_practice_rows(soup)
    practice_text = "\n".join(
        "\n".join(filter(None, [row.get("principle", ""), row.get("others", "")]))
        for row in practice_rows
    ).strip()

    specialties = infer_specialties(practice_text, seed.get("matched_query", ""), seed.get("name", ""))
    hospital = infer_hospital_name(practice_rows)
    mmc_profile_id_match = re.search(r"/viewDoctor/(\d+)/search", seed["detail_url"])
    mmc_profile_id = mmc_profile_id_match.group(1) if mmc_profile_id_match else ""

    return {
        "name": fields.get("full name", seed.get("name", "Unknown Doctor")),
        "graduated_from": fields.get("graduated of", seed.get("graduated_from", "Unknown")),
        "qualification": fields.get("qualification", "Unknown"),
        "provisional_registration_number": fields.get("provisional registration number", ""),
        "date_of_provisional_registration": fields.get("date of provisional registration", ""),
        "full_registration_number": fields.get("full registration number", ""),
        "date_of_full_registration": fields.get("date of full registration", ""),
        "specialty": specialties[0],
        "specialty_tags": ", ".join(specialties),
        "hospital": hospital,
        "tier": infer_tier(hospital, practice_text),
        "primary_practice": practice_rows[0]["principle"] if practice_rows else "",
        "practice_locations": practice_text,
        "apc_year": practice_rows[0]["apc_year"] if practice_rows else "",
        "apc_number": practice_rows[0]["apc_number"] if practice_rows else "",
        "mmc_profile_id": mmc_profile_id,
        "mmc_url": seed["detail_url"],
        "source_query": seed.get("matched_query", ""),
    }


def merge_doctor_records(existing: Optional[Dict], incoming: Dict) -> Dict:
    if not existing:
        return incoming

    existing_tags = {tag.strip() for tag in existing.get("specialty_tags", "").split(",") if tag.strip()}
    incoming_tags = {tag.strip() for tag in incoming.get("specialty_tags", "").split(",") if tag.strip()}
    merged_tags = sorted(existing_tags | incoming_tags)

    merged = dict(existing)
    merged["specialty_tags"] = ", ".join(merged_tags)
    merged["specialty"] = merged_tags[0] if merged_tags else existing.get("specialty", "General Medicine")

    for key in (
        "provisional_registration_number",
        "date_of_provisional_registration",
        "full_registration_number",
        "date_of_full_registration",
        "primary_practice",
        "practice_locations",
        "apc_year",
        "apc_number",
    ):
        if not merged.get(key) and incoming.get(key):
            merged[key] = incoming[key]

    return merged


def scrape_mmc_doctors(
    search_terms: Optional[List[str]] = None,
    max_pages_per_query: int = DEFAULT_MAX_PAGES,
    max_doctors_per_query: int = DEFAULT_MAX_DOCTORS_PER_QUERY,
) -> List[Dict]:
    print("Fetching live doctor data from MMC MeRITS...")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
    )

    deduped: Dict[str, Dict] = {}
    for term in search_terms or DEFAULT_SEARCH_TERMS:
        collected = 0
        for page in range(1, max_pages_per_query + 1):
            html = fetch_html(session, MMC_SEARCH_URL, params={"place-of-practice": term, "page": page})
            results = parse_search_results(html)
            if not results:
                break

            for result in results:
                if collected >= max_doctors_per_query:
                    break
                result["matched_query"] = term
                detail_html = fetch_html(session, result["detail_url"])
                profile = build_doctor_profile(result, detail_html)
                unique_key = (
                    profile.get("full_registration_number")
                    or profile.get("provisional_registration_number")
                    or profile["mmc_profile_id"]
                )
                deduped[unique_key] = merge_doctor_records(deduped.get(unique_key), profile)
                collected += 1

            if collected >= max_doctors_per_query:
                break

        print(f"MMC query '{term}' captured {collected} doctor profiles.")

    doctors = list(deduped.values())
    print(f"Prepared {len(doctors)} unique MMC doctor profiles.")
    return doctors


def scrape_real_doctors() -> List[Dict]:
    return scrape_mmc_doctors()


def build_vector_document(doc_data: Dict) -> str:
    if doc_data["tier"] == "Premium Private":
        pricing = "Luxury experience, highest foreigner rates. Est: USD $150 - $300."
    elif doc_data["tier"] == "Standard Private":
        pricing = "Fast service, standard foreigner rates. Est: USD $80 - $150."
    else:
        pricing = "High-quality specialized care. Non-citizen pricing is usually not subsidized. Est: USD $50 - $100."

    return (
        f"Doctor Name: {doc_data['name']}\n"
        f"Sub-Specialty: {doc_data['specialty']}\n"
        f"Specialty Tags: {doc_data.get('specialty_tags', doc_data['specialty'])}\n"
        f"Affiliated Hospital: {doc_data['hospital']}\n"
        f"Qualification: {doc_data.get('qualification', 'Unknown')}\n"
        f"Graduated From: {doc_data.get('graduated_from', 'Unknown')}\n"
        f"Provisional Registration Number: {doc_data.get('provisional_registration_number') or 'N/A'}\n"
        f"Full Registration Number: {doc_data.get('full_registration_number') or 'N/A'}\n"
        f"Primary Practice: {doc_data.get('primary_practice') or 'N/A'}\n"
        f"MMC Profile URL: {doc_data.get('mmc_url') or 'N/A'}\n"
        f"Medical Tourist Tier: {doc_data['tier']}\n"
        f"Foreigner Pricing: {pricing}"
    )


def ingest_to_chroma(doctors: List[Dict]) -> None:
    print("Connecting to ChromaDB...")

    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
    os.makedirs(db_path, exist_ok=True)

    client = chromadb.PersistentClient(path=db_path)
    try:
        client.delete_collection(name="malaysia_doctors")
    except Exception:
        pass
    collection = client.get_or_create_collection(name="malaysia_doctors")

    documents: List[str] = []
    metadatas: List[Dict] = []
    ids: List[str] = []

    for idx, doctor in enumerate(doctors):
        documents.append(build_vector_document(doctor))
        metadatas.append(
            {
                "name": doctor["name"],
                "hospital": doctor["hospital"],
                "specialty": doctor["specialty"],
                "specialty_tags": doctor.get("specialty_tags", doctor["specialty"]),
                "tier": doctor["tier"],
                "provisional_registration_number": doctor.get("provisional_registration_number") or "",
                "full_registration_number": doctor.get("full_registration_number") or "",
                "mmc_profile_id": doctor.get("mmc_profile_id") or "",
                "mmc_url": doctor.get("mmc_url") or "",
                "primary_practice": doctor.get("primary_practice") or "",
            }
        )
        ids.append(f"mmc_doc_{idx}")

    print(f"Inserting {len(documents)} doctor profiles into ChromaDB...")
    collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    print("Ingestion complete. The doctor registry is refreshed.")


if __name__ == "__main__":
    doctors_list = scrape_real_doctors()
    ingest_to_chroma(doctors_list)
