import re
from typing import Dict, Iterable, List, Set


SPECIALTY_KEYWORDS = [
    ("Radiation Oncology", ("radiation oncology", "radioterapi", "radiotherapy")),
    (
        "Medical Oncology",
        ("medical oncology", "clinical oncology", "oncology", "onkologi", "kanser", "cancer"),
    ),
    ("Hematology", ("hematology", "haematology", "hematologi", "lymphoma", "leukemia", "myeloma")),
    ("Thoracic Surgery", ("thoracic surgery", "toraks", "lung surgery", "chest surgery")),
    ("Pulmonology", ("pulmonology", "pulmonary", "respiratory", "paru paru", "lung", "chest physician")),
    ("Cardio-Oncology", ("cardio oncology", "cardio-oncology")),
    ("Interventional Cardiology", ("interventional cardiology",)),
    ("Cardiothoracic Surgery", ("cardiothoracic", "cardio thoracic", "cardiothoracic surgery")),
    ("Cardiology", ("cardiology", "kardiologi", "jantung", "heart failure", "coronary")),
    ("General Surgery", ("surgery", "surgeon", "pembedahan")),
]

ONCOLOGY_SPECIALTIES = {
    "Radiation Oncology",
    "Medical Oncology",
    "Hematology",
    "Thoracic Surgery",
    "Pulmonology",
    "Cardio-Oncology",
}

CARDIOLOGY_SPECIALTIES = {
    "Cardio-Oncology",
    "Interventional Cardiology",
    "Cardiothoracic Surgery",
    "Cardiology",
}


def normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def infer_specialties(*texts: str) -> List[str]:
    haystack = normalize_text(" ".join(text for text in texts if text))
    matches: List[str] = []
    for specialty, keywords in SPECIALTY_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            matches.append(specialty)
    return matches or ["General Medicine"]


def specialty_groups_for_specialties(specialties: Iterable[str]) -> Set[str]:
    groups: Set[str] = set()
    for specialty in specialties:
        if specialty in ONCOLOGY_SPECIALTIES:
            groups.add("oncology")
        if specialty in CARDIOLOGY_SPECIALTIES:
            groups.add("cardiology")
    return groups


def specialty_groups_for_text(*texts: str) -> Set[str]:
    return specialty_groups_for_specialties(infer_specialties(*texts))


def build_case_profile(medical_data: Dict) -> Dict:
    condition = medical_data.get("condition", "")
    sub_specialty = medical_data.get("sub_specialty_inference", "")
    summary = medical_data.get("raw_summary", "")
    combined = normalize_text(" ".join([condition, sub_specialty, summary]))

    specialties = infer_specialties(condition, sub_specialty, summary)
    groups = specialty_groups_for_specialties(specialties)

    if "cancer" in combined or "tumor" in combined or "tumour" in combined or "metast" in combined:
        groups.add("oncology")
    if "cardio" in combined or "heart" in combined or "jantung" in combined:
        groups.add("cardiology")

    return {
        "condition": condition,
        "sub_specialty": sub_specialty,
        "summary": summary,
        "combined_text": combined,
        "specialties": specialties,
        "groups": groups,
        "lung_focus": "lung" in combined or "pulmo" in combined or "thorac" in combined,
        "cardio_oncology": bool(medical_data.get("is_cardio_oncology")),
    }
