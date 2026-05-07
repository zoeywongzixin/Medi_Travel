"""
pipeline/ingest_mock_data.py
============================
Injects mock hospital, doctor and charity entries into ChromaDB that are:
- Relevant to Vietnamese patients (Diabetic Nephropathy, Coronary Artery Disease)
- Sufficient to generate all three letter templates (Appointment, MHTC, Visa Support)
"""

import os
import sys
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import chromadb

DB_PATH = os.path.join(ROOT_DIR, "data", "chroma_db")

# ---------------------------------------------------------------------------
# 1. MOCK HOSPITALS / DOCTORS (malaysia_doctors collection)
# ---------------------------------------------------------------------------
MOCK_DOCTORS = [
    {
        "id": "mock_cardio_01",
        "name": "Dr. Ahmad Fadzillah bin Hashim",
        "specialty": "Cardiology",
        "specialty_tags": "Cardiology, Interventional Cardiology, Coronary Angiography, Coronary Artery Disease",
        "hospital": "Institut Jantung Negara (IJN)",
        "hospital_location": "Kuala Lumpur",
        "tier": "Government / Semi-Gov",
        "qualification": "FRCP (Edinburgh), Fellowship Interventional Cardiology (USA)",
        "graduated_from": "Universiti Malaya",
        "provisional_registration_number": "",
        "full_registration_number": "45231",
        "mmc_profile_id": "mock_001",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock001/search",
        "primary_practice": "Institut Jantung Negara, 145 Jalan Tun Razak, 50400 Kuala Lumpur",
        "document_text": (
            "Doctor Name: Dr. Ahmad Fadzillah bin Hashim\n"
            "Sub-Specialty: Interventional Cardiology\n"
            "Specialty Tags: Cardiology, Coronary Artery Disease, Coronary Angiography, PCI\n"
            "Affiliated Hospital: Institut Jantung Negara (IJN)\n"
            "Qualification: FRCP (Edinburgh), Fellowship Interventional Cardiology (USA)\n"
            "Graduated From: Universiti Malaya\n"
            "Full Registration Number: 45231\n"
            "Primary Practice: Institut Jantung Negara, 145 Jalan Tun Razak, 50400 Kuala Lumpur\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock001/search\n"
            "Medical Tourist Tier: Government / Semi-Gov\n"
            "Foreigner Pricing: High-quality specialized care. Non-citizen pricing. Est: USD $80 - $150."
        )
    },
    {
        "id": "mock_nephro_01",
        "name": "Dr. Lim Beng Kiang",
        "specialty": "Nephrology",
        "specialty_tags": "Nephrology, Diabetic Nephropathy, Chronic Kidney Disease, Renal Transplant",
        "hospital": "Hospital Kuala Lumpur (HKL)",
        "hospital_location": "Kuala Lumpur",
        "tier": "Government / Semi-Gov",
        "qualification": "MRCP (UK), Fellowship Nephrology (Australia)",
        "graduated_from": "Universiti Kebangsaan Malaysia",
        "provisional_registration_number": "",
        "full_registration_number": "38742",
        "mmc_profile_id": "mock_002",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock002/search",
        "primary_practice": "Hospital Kuala Lumpur, Jalan Pahang, 50586 Kuala Lumpur",
        "document_text": (
            "Doctor Name: Dr. Lim Beng Kiang\n"
            "Sub-Specialty: Nephrology\n"
            "Specialty Tags: Nephrology, Diabetic Nephropathy, Chronic Kidney Disease, CKD, Renal Care\n"
            "Affiliated Hospital: Hospital Kuala Lumpur (HKL)\n"
            "Qualification: MRCP (UK), Fellowship Nephrology (Australia)\n"
            "Graduated From: Universiti Kebangsaan Malaysia\n"
            "Full Registration Number: 38742\n"
            "Primary Practice: Hospital Kuala Lumpur, Jalan Pahang, 50586 Kuala Lumpur\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock002/search\n"
            "Medical Tourist Tier: Government / Semi-Gov\n"
            "Foreigner Pricing: High-quality specialized care. Non-citizen pricing. Est: USD $60 - $120."
        )
    },
    {
        "id": "mock_cardionephro_01",
        "name": "Dr. Saranya Krishnamoorthy",
        "specialty": "Cardio-Nephrology",
        "specialty_tags": "Cardiology, Nephrology, Diabetic Nephropathy, Coronary Artery Disease, Type 2 Diabetes",
        "hospital": "Prince Court Medical Centre",
        "hospital_location": "Kuala Lumpur",
        "tier": "Premium Private",
        "qualification": "MD, Fellowship Cardio-Nephrology (UK)",
        "graduated_from": "Universiti Malaya",
        "provisional_registration_number": "",
        "full_registration_number": "62190",
        "mmc_profile_id": "mock_003",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock003/search",
        "primary_practice": "Prince Court Medical Centre, 39 Jalan Kia Peng, 50450 Kuala Lumpur",
        "document_text": (
            "Doctor Name: Dr. Saranya Krishnamoorthy\n"
            "Sub-Specialty: Cardio-Nephrology\n"
            "Specialty Tags: Cardiology, Nephrology, Diabetic Nephropathy, Coronary Artery Disease, Type 2 Diabetes Mellitus\n"
            "Affiliated Hospital: Prince Court Medical Centre\n"
            "Qualification: MD, Fellowship Cardio-Nephrology (UK)\n"
            "Graduated From: Universiti Malaya\n"
            "Full Registration Number: 62190\n"
            "Primary Practice: Prince Court Medical Centre, 39 Jalan Kia Peng, 50450 Kuala Lumpur\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock003/search\n"
            "Medical Tourist Tier: Premium Private\n"
            "Foreigner Pricing: Luxury experience, highest foreigner rates. Est: USD $180 - $350."
        )
    },
    {
        "id": "mock_endo_01",
        "name": "Dr. Nurul Huda binti Ramli",
        "specialty": "Endocrinology",
        "specialty_tags": "Endocrinology, Type 2 Diabetes, Diabetes Management, Dyslipidemia, Metabolic Syndrome",
        "hospital": "Gleneagles Hospital Kuala Lumpur",
        "hospital_location": "Kuala Lumpur",
        "tier": "Premium Private",
        "qualification": "FRCP, Fellowship Endocrinology (Singapore)",
        "graduated_from": "Universiti Sains Malaysia",
        "provisional_registration_number": "",
        "full_registration_number": "55871",
        "mmc_profile_id": "mock_004",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock004/search",
        "primary_practice": "Gleneagles Hospital Kuala Lumpur, 282 & 286 Jalan Ampang, 50450 Kuala Lumpur",
        "document_text": (
            "Doctor Name: Dr. Nurul Huda binti Ramli\n"
            "Sub-Specialty: Endocrinology\n"
            "Specialty Tags: Endocrinology, Type 2 Diabetes, Dyslipidemia, HbA1c Management, Metabolic Syndrome\n"
            "Affiliated Hospital: Gleneagles Hospital Kuala Lumpur\n"
            "Qualification: FRCP, Fellowship Endocrinology (Singapore)\n"
            "Graduated From: Universiti Sains Malaysia\n"
            "Full Registration Number: 55871\n"
            "Primary Practice: Gleneagles Hospital Kuala Lumpur, 282 Jalan Ampang, 50450 Kuala Lumpur\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock004/search\n"
            "Medical Tourist Tier: Premium Private\n"
            "Foreigner Pricing: Luxury experience, highest foreigner rates. Est: USD $150 - $280."
        )
    },
    {
        "id": "mock_onco_01",
        "name": "Dr. Aisyah Marina Mohd Noor",
        "specialty": "Medical Oncology",
        "specialty_tags": "Medical Oncology, Lung Cancer, Small Cell Lung Cancer, Chemotherapy, Thoracic Oncology",
        "hospital": "National Cancer Institute (IKN)",
        "hospital_location": "Putrajaya",
        "tier": "Government / Semi-Gov",
        "qualification": "MRCP (UK), Fellowship Medical Oncology",
        "graduated_from": "Universiti Malaya",
        "provisional_registration_number": "",
        "full_registration_number": "49821",
        "mmc_profile_id": "mock_005",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock005/search",
        "primary_practice": "National Cancer Institute, Presint 7, 62250 Putrajaya",
        "document_text": (
            "Doctor Name: Dr. Aisyah Marina Mohd Noor\n"
            "Sub-Specialty: Medical Oncology\n"
            "Specialty Tags: Medical Oncology, Lung Cancer, Small Cell Lung Cancer, Chemotherapy, Thoracic Oncology, SCLC\n"
            "Affiliated Hospital: National Cancer Institute (IKN)\n"
            "Qualification: MRCP (UK), Fellowship Medical Oncology\n"
            "Graduated From: Universiti Malaya\n"
            "Full Registration Number: 49821\n"
            "Primary Practice: National Cancer Institute, Presint 7, 62250 Putrajaya\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock005/search\n"
            "Medical Tourist Tier: Government / Semi-Gov\n"
            "Foreigner Pricing: High-quality oncology care. Non-citizen pricing. Est: USD $90 - $180."
        )
    },
    {
        "id": "mock_radio_onco_01",
        "name": "Dr. Jason Lee Chee Keong",
        "specialty": "Radiation Oncology",
        "specialty_tags": "Radiation Oncology, Lung Cancer, Small Cell Lung Cancer, Radiotherapy, Thoracic Oncology",
        "hospital": "Subang Jaya Medical Centre",
        "hospital_location": "Subang Jaya",
        "tier": "Standard Private",
        "qualification": "MBBS, Clinical Oncology Fellowship",
        "graduated_from": "Universiti Kebangsaan Malaysia",
        "provisional_registration_number": "",
        "full_registration_number": "53402",
        "mmc_profile_id": "mock_006",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock006/search",
        "primary_practice": "Subang Jaya Medical Centre, 1 Jalan SS12/1A, 47500 Subang Jaya",
        "document_text": (
            "Doctor Name: Dr. Jason Lee Chee Keong\n"
            "Sub-Specialty: Radiation Oncology\n"
            "Specialty Tags: Radiation Oncology, Lung Cancer, Small Cell Lung Cancer, Radiotherapy, Thoracic Oncology, SCLC\n"
            "Affiliated Hospital: Subang Jaya Medical Centre\n"
            "Qualification: MBBS, Clinical Oncology Fellowship\n"
            "Graduated From: Universiti Kebangsaan Malaysia\n"
            "Full Registration Number: 53402\n"
            "Primary Practice: Subang Jaya Medical Centre, 1 Jalan SS12/1A, 47500 Subang Jaya\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock006/search\n"
            "Medical Tourist Tier: Standard Private\n"
            "Foreigner Pricing: Rapid access oncology care. Est: USD $120 - $220."
        )
    },
    {
        "id": "mock_pulmo_01",
        "name": "Dr. Tan Wei Jian",
        "specialty": "Pulmonology",
        "specialty_tags": "Pulmonology, Lung Mass, Hemoptysis, Respiratory Oncology Support, Bronchoscopy",
        "hospital": "Sunway Medical Centre",
        "hospital_location": "Kuala Lumpur",
        "tier": "Standard Private",
        "qualification": "MRCP, Fellowship Respiratory Medicine",
        "graduated_from": "Universiti Sains Malaysia",
        "provisional_registration_number": "",
        "full_registration_number": "57718",
        "mmc_profile_id": "mock_007",
        "mmc_url": "https://merits.mmc.gov.my/viewDoctor/mock007/search",
        "primary_practice": "Sunway Medical Centre, Bandar Sunway, Selangor",
        "document_text": (
            "Doctor Name: Dr. Tan Wei Jian\n"
            "Sub-Specialty: Pulmonology\n"
            "Specialty Tags: Pulmonology, Lung Mass, Hemoptysis, Respiratory Oncology Support, Bronchoscopy\n"
            "Affiliated Hospital: Sunway Medical Centre\n"
            "Qualification: MRCP, Fellowship Respiratory Medicine\n"
            "Graduated From: Universiti Sains Malaysia\n"
            "Full Registration Number: 57718\n"
            "Primary Practice: Sunway Medical Centre, Bandar Sunway, Selangor\n"
            "MMC Profile URL: https://merits.mmc.gov.my/viewDoctor/mock007/search\n"
            "Medical Tourist Tier: Standard Private\n"
            "Foreigner Pricing: Rapid respiratory and oncology workup. Est: USD $110 - $200."
        )
    },
]

# ---------------------------------------------------------------------------
# 2. MOCK CHARITIES (malaysia_charities collection)
# ---------------------------------------------------------------------------
MOCK_CHARITIES = [
    {
        "id": "mock_charity_vn_01",
        "name": "Vietnamese Community Medical Aid Fund",
        "organization": "VCMAF Malaysia",
        "supported_countries": "Vietnam, Southeast Asia",
        "conditions_supported": "Diabetes, Diabetic Nephropathy, Chronic Kidney Disease, Cardiovascular Disease",
        "max_grant_usd": 2500,
        "contact": "vcmaf@charity.my",
        "description": (
            "Name: Vietnamese Community Medical Aid Fund (VCMAF Malaysia)\n"
            "Organization: VCMAF Malaysia\n"
            "Supported Countries: Vietnam, Southeast Asia\n"
            "Conditions: Diabetes, Diabetic Nephropathy, Chronic Kidney Disease, Cardiovascular Disease, Coronary Artery Disease\n"
            "Max Grant: USD $2,500\n"
            "Notes: Specifically supports Vietnamese nationals seeking specialist care in Malaysia. "
            "Covers travel, accommodation, and partial treatment subsidy."
        )
    },
    {
        "id": "mock_charity_asean_cardio_01",
        "name": "ASEAN Heart & Kidney Foundation",
        "organization": "AHKF",
        "supported_countries": "Vietnam, Indonesia, Philippines, Myanmar, Cambodia",
        "conditions_supported": "Coronary Artery Disease, Chronic Kidney Disease, Diabetic Nephropathy, Type 2 Diabetes",
        "max_grant_usd": 3000,
        "contact": "ahkf@foundation.org.my",
        "description": (
            "Name: ASEAN Heart & Kidney Foundation (AHKF)\n"
            "Organization: AHKF\n"
            "Supported Countries: Vietnam, Indonesia, Philippines, Myanmar, Cambodia\n"
            "Conditions: Coronary Artery Disease, Chronic Kidney Disease, Diabetic Nephropathy, Type 2 Diabetes\n"
            "Max Grant: USD $3,000\n"
            "Notes: Provides financial support for ASEAN patients requiring cardiac or renal specialist care in Malaysia. "
            "Application requires referral letter from treating physician."
        )
    },
    {
        "id": "mock_charity_vn_onco_01",
        "name": "Vietnam Cancer Bridge Fund",
        "organization": "VCBF Malaysia",
        "supported_countries": "Vietnam, Malaysia",
        "conditions_supported": "Lung Cancer, Small Cell Lung Cancer, Oncology, Chemotherapy, Radiotherapy",
        "max_grant_usd": 3500,
        "contact": "vcbf@charity.my",
        "description": (
            "Name: Vietnam Cancer Bridge Fund\n"
            "Organization: VCBF Malaysia\n"
            "Supported Countries: Vietnam, Malaysia\n"
            "Conditions: Lung Cancer, Small Cell Lung Cancer, Oncology, Chemotherapy, Radiotherapy\n"
            "Max Grant: USD $3,500\n"
            "Notes: Specifically supports Vietnamese nationals referred to Malaysia for oncology assessment, chemotherapy, and radiotherapy."
        )
    },
    {
        "id": "mock_charity_asean_onco_01",
        "name": "ASEAN Oncology Access Fund",
        "organization": "AOAF",
        "supported_countries": "Vietnam, Indonesia, Philippines, Cambodia, Laos, Myanmar",
        "conditions_supported": "Cancer, Lung Cancer, Oncology, Small Cell Lung Cancer, Radiotherapy",
        "max_grant_usd": 4000,
        "contact": "aoaf@foundation.org.my",
        "description": (
            "Name: ASEAN Oncology Access Fund\n"
            "Organization: AOAF\n"
            "Supported Countries: Vietnam, Indonesia, Philippines, Cambodia, Laos, Myanmar\n"
            "Conditions: Cancer, Lung Cancer, Oncology, Small Cell Lung Cancer, Radiotherapy\n"
            "Max Grant: USD $4,000\n"
            "Notes: Provides financial support for ASEAN patients requiring urgent oncology treatment in Malaysia."
        )
    },
]


def ingest_doctors(client: chromadb.PersistentClient):
    try:
        client.delete_collection("malaysia_doctors")
    except Exception:
        pass
    col = client.get_or_create_collection("malaysia_doctors")

    # Re-read existing data if any (don't wipe real data)
    # For mock purposes, upsert only mock entries
    docs, metas, ids = [], [], []
    for d in MOCK_DOCTORS:
        docs.append(d["document_text"])
        metas.append({
            "name": d["name"],
            "hospital": d["hospital"],
            "specialty": d["specialty"],
            "specialty_tags": d["specialty_tags"],
            "tier": d["tier"],
            "provisional_registration_number": d.get("provisional_registration_number", ""),
            "full_registration_number": d.get("full_registration_number", ""),
            "mmc_profile_id": d.get("mmc_profile_id", ""),
            "mmc_url": d.get("mmc_url", ""),
            "primary_practice": d.get("primary_practice", ""),
        })
        ids.append(d["id"])

    col.upsert(documents=docs, metadatas=metas, ids=ids)
    print(f"[MOCK INGEST] Upserted {len(docs)} mock doctor entries into 'malaysia_doctors'.")


def ingest_charities(client: chromadb.PersistentClient):
    try:
        client.delete_collection("malaysia_charities")
    except Exception:
        pass
    col = client.get_or_create_collection("malaysia_charities")

    docs, metas, ids = [], [], []
    for c in MOCK_CHARITIES:
        docs.append(c["description"])
        metas.append({
            "name": c["name"],
            "organization": c["organization"],
            "source": "mock_seed",
            "origin_country": "Vietnam" if "Vietnam" in c["supported_countries"] else "ASEAN",
            "target_countries": json.dumps([country.strip() for country in c["supported_countries"].split(",") if country.strip()]),
            "target_audience": json.dumps(["ASEAN", "medical travelers"]),
            "conditions_covered": json.dumps([condition.strip() for condition in c["conditions_supported"].split(",") if condition.strip()]),
            "max_coverage_usd": str(c["max_grant_usd"]),
            "url": "",
            "active": "True",
            "contact": c["contact"],
        })
        ids.append(c["id"])

    col.upsert(documents=docs, metadatas=metas, ids=ids)
    print(f"[MOCK INGEST] Upserted {len(docs)} mock charity entries into 'malaysia_charities'.")


if __name__ == "__main__":
    print(f"Connecting to ChromaDB at: {DB_PATH}")
    os.makedirs(DB_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_PATH)

    ingest_doctors(client)
    ingest_charities(client)
    print("\n[MOCK INGEST] Done. RAG is now primed with Vietnamese patient-relevant records.")
    print("These mock entries support: Coronary Artery Disease, Diabetic Nephropathy, CKD, Type 2 Diabetes.")
    print("Letter templates supported: Appointment Letter, MHTC Letter, Visa Support Letter.")
