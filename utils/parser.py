import re
import json
from pydantic import BaseModel, Field
from typing import Optional
from utils.llm import call_gemini

class MedicalRecord(BaseModel):
    condition: str = Field(default="Unknown")
    sub_specialty_inference: str = Field(default="General")
    severity: str = Field(default="Moderate")
    age_group: Optional[str] = Field(default="Unknown")
    urgency: Optional[str] = Field(default="Unknown")
    is_cardio_oncology: bool = Field(default=False)
    raw_summary: Optional[str] = Field(default="")


def _heuristic_sub_specialty(text: str) -> str:
    lowered = (text or "").lower()
    if any(term in lowered for term in ("small cell lung cancer", "lung cancer", "sclc", "ung thư", "un g thu", "phổi", "pho i")):
        if any(term in lowered for term in ("radiotherapy", "xạ trị", "xa tri")):
            return "Radiation Oncology"
        return "Medical Oncology"
    if any(term in lowered for term in ("heart", "coronary", "cardio", "jantung")):
        return "Cardiology"
    if any(term in lowered for term in ("kidney", "renal", "nephro")):
        return "Nephrology"
    return "General Medicine"


def _heuristic_condition(text: str) -> str:
    lowered = (text or "").lower()
    if any(term in lowered for term in ("small cell lung cancer", "sclc")):
        return "Small Cell Lung Cancer"
    if any(term in lowered for term in ("lung cancer", "ung thư", "un g thu", "phổi", "pho i")):
        return "Lung Cancer"
    if any(term in lowered for term in ("coronary artery disease", "cad")):
        return "Coronary Artery Disease"
    if any(term in lowered for term in ("chronic kidney disease", "ckd")):
        return "Chronic Kidney Disease"
    return "General Medicine"


def _heuristic_severity(text: str) -> str:
    lowered = (text or "").lower()
    if any(term in lowered for term in ("critical", "icu", "ventilator")):
        return "Critical"
    if any(term in lowered for term in ("cancer", "ung thư", "un g thu", "hemoptysis", "máu", "mau", "radiotherapy", "xạ trị", "xa tri")):
        return "High"
    return "Moderate"


def _heuristic_medical_record(text: str) -> dict:
    severity = _heuristic_severity(text)
    condition = _heuristic_condition(text)
    return {
        "condition": condition,
        "sub_specialty_inference": _heuristic_sub_specialty(text),
        "severity": severity,
        "age_group": infer_age_group(text),
        "urgency": infer_urgency(text, severity),
        "is_cardio_oncology": "cardio" in (text or "").lower() and condition in {"Lung Cancer", "Small Cell Lung Cancer"},
        "raw_summary": (text or "").strip()[:1000],
    }


def infer_age_group(text: str) -> str:
    if not text:
        return "Unknown"

    age_match = re.search(r"\bage\s*[:\-]?\s*(\d{1,3})\b", text, re.IGNORECASE)
    if not age_match:
        age_match = re.search(r"tu[oô]i\s*[:\-]?\s*(\d{1,3})", text, re.IGNORECASE)
    if age_match:
        age = int(age_match.group(1))
        if age <= 1:
            return "Infant"
        if age < 18:
            return "Child"
        if age >= 60:
            return "Senior"
        return "Adult"

    lowered = text.lower()
    if any(term in lowered for term in ("infant", "neonate", "newborn")):
        return "Infant"
    if any(term in lowered for term in ("child", "children", "pediatric", "paediatric")):
        return "Child"
    if any(term in lowered for term in ("elderly", "geriatric", "senior")):
        return "Senior"
    return "Unknown"


def infer_urgency(text: str, severity: str = "") -> str:
    severity_normalized = (severity or "").strip().title()
    if severity_normalized == "Critical":
        return "Critical"
    if severity_normalized == "High":
        return "Urgent"

    if not text:
        return "Unknown"

    lowered = text.lower()
    critical_terms = (
        "critical",
        "life-threatening",
        "life threatening",
        "immediate life-saving",
        "requires icu",
        "requires ventilator",
        "hemodynamic instability",
    )
    urgent_terms = (
        "urgent",
        "emergency",
        "as soon as possible",
        "requires transfer",
        "needs transfer",
        "refer to malaysia",
        "chemotherapy",
        "radiotherapy",
        "hemoptysis",
        "blood-streaked sputum",
        "coughing blood",
        "rapid weight loss",
        "chest pain",
        "ung thư",
        "un g thu",
        "xạ trị",
        "xa tri",
        "hóa trị",
        "hoa tri",
        "sụt cân",
        "sut can",
        "đờm lẫn máu",
        "dom lan mau",
    )

    if any(term in lowered for term in critical_terms):
        return "Critical"
    if any(term in lowered for term in urgent_terms):
        return "Urgent"
    return "Stable"


def get_concise_json(english_text):
    """Uses Gemini 3.0 Flash to structure translated text into a valid JSON."""
    content = ""

    system_prompt = (
        "You are a strict medical data extractor for a medical tourism app. "
        "Analyze the text and return ONLY a flat JSON object.\n"
        "Rules for keys:\n"
        "1. 'condition': The specific disease or symptom (e.g. Lung Cancer, Heart Failure).\n"
        "2. 'sub_specialty_inference': The most relevant department or sub-specialty. "
        "Use precise labels when possible, such as Medical Oncology, Radiation Oncology, Thoracic Surgery, "
        "Pulmonology, Cardiology, Cardiothoracic Surgery, Orthopedics, Pediatrics, or General Medicine.\n"
        "3. 'severity': Low, Moderate, High, or Critical.\n"
        "4. 'age_group': Infant, Child, Adult, Senior, or Unknown.\n"
        "5. 'urgency': Stable, Urgent, Critical, or Unknown.\n"
        "6. 'is_cardio_oncology': Set to true only if the text clearly mentions both cancer or tumor disease and a meaningful heart-related complication.\n"
        "7. If a value is missing, use 'Unknown'.\n"
        "Return ONLY the JSON."
    )

    try:
        if not english_text or len(english_text.strip()) < 5:
            raise ValueError("English text is empty or too short for AI processing.")

        import os
        res = call_gemini(system_prompt, f"Extract info from this text: {english_text}", model_name=os.getenv("GEMINI_PARSER_MODEL", "gemini-2.5-flash"))
        content = res.get("text", "").strip()

        # Extract JSON block
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        clean_json = json_match.group(0) if json_match else content

        temp_data = json.loads(clean_json)

        # Self-correction: normalise booleans and inferred fields
        val = temp_data.get("is_cardio_oncology")
        temp_data["is_cardio_oncology"] = str(val).lower() in ("true", "1", "yes")
        temp_data["age_group"] = temp_data.get("age_group") or infer_age_group(english_text)
        temp_data["urgency"] = temp_data.get("urgency") or infer_urgency(
            english_text, temp_data.get("severity", "")
        )

        validated = MedicalRecord.model_validate(temp_data).model_dump()

        if validated.get("age_group") in ("Unknown", "", None):
            validated["age_group"] = infer_age_group(english_text)
        if validated.get("urgency") in ("Unknown", "", None):
            validated["urgency"] = infer_urgency(english_text, validated.get("severity", ""))

        return validated

    except Exception as e:
        print(f"\n--- [PARSER ERROR LOG] ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        if content:
            print(f"Raw AI Content: {content[:100]}...")
        print(f"---------------------------\n")

        fallback = _heuristic_medical_record(english_text or "")
        fallback["raw_summary"] = fallback.get("raw_summary") or f"Failed: {str(e)}"
        return fallback


def scrub_pii(data):
    """Privacy layer to remove sensitive dates and phone numbers."""
    for key, value in data.items():
        if isinstance(value, str):
            value = re.sub(r'\d{2}/\d{2}/\d{4}', '[REDACTED_DATE]', value)
            value = re.sub(r'\+?\d{10,12}', '[REDACTED_PHONE]', value)
            data[key] = value
    return data


def scrub_raw_text(text: str) -> str:
    """Aggressively scrubs raw OCR text to prevent AI safety filters from triggering."""
    if not text:
        return text

    text = re.sub(r'(?i)ad\s*dress[es]*.*?[\n\r]', '[REDACTED_ADDRESS]\n', text)
    text = re.sub(r'(?i)license\s*number.*?[\n\r]', '[REDACTED_LICENSE]\n', text)
    text = re.sub(r'(?i)dear\s+(mr|ms|mrs|dr|me).*?[\n\r:]', 'Dear [REDACTED_NAME]:\n', text)
    text = re.sub(r'\+?\d{8,15}', '[REDACTED_NUMBER]', text)
    text = re.sub(r'\d{2}[-/\.]\d{2}[-/\.]\d{4}', '[REDACTED_DATE]', text)

    return text
