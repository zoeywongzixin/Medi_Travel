import re
import json
import ollama
from pydantic import BaseModel, Field
from typing import Optional

class MedicalRecord(BaseModel):
    condition: str = Field(default="Unknown")
    sub_specialty_inference: str = Field(default="General")
    severity: str = Field(default="Moderate")
    age_group: Optional[str] = Field(default="Unknown")
    urgency: Optional[str] = Field(default="Unknown")
    is_cardio_oncology: bool = Field(default=False)
    raw_summary: Optional[str] = Field(default="")


def infer_age_group(text: str) -> str:
    if not text:
        return "Unknown"

    age_match = re.search(r"\bage\s*[:\-]?\s*(\d{1,3})\b", text, re.IGNORECASE)
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
    )

    if any(term in lowered for term in critical_terms):
        return "Critical"
    if any(term in lowered for term in urgent_terms):
        return "Urgent"
    return "Stable"

def get_concise_json(english_text):
    """Uses Llama 3.2 to structure the translated text into a valid JSON."""
    MODEL_NAME = 'llama3.2:3b' 
    content = "" # Initialize empty so the except block doesn't crash

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
        # Check if we even have text to send
        if not english_text or len(english_text.strip()) < 5:
            raise ValueError("English text is empty or too short for AI processing.")

        response = ollama.chat(
            model=MODEL_NAME,
            format='json', 
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f"Extract info from this text: {english_text}"}
            ],
            options={'temperature': 0}
        )
        
        # Handle both old (dict) and new (object) Ollama response formats
        if hasattr(response, 'message'):
            content = response.message.content.strip()
        else:
            content = response['message']['content'].strip()
        
        # --- FIX: REGEX EXTRACTION ---
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        clean_json = json_match.group(0) if json_match else content
            
        # 2. Convert string to a Python Dictionary
        temp_data = json.loads(clean_json)
        
        # 3. SELF-CORRECTION: Handle the Boolean bug
        val = temp_data.get("is_cardio_oncology")
        temp_data["is_cardio_oncology"] = str(val).lower() in ("true", "1", "yes")
        temp_data["age_group"] = temp_data.get("age_group") or infer_age_group(english_text)
        temp_data["urgency"] = temp_data.get("urgency") or infer_urgency(
            english_text,
            temp_data.get("severity", ""),
        )

        # 4. Final Validation with Pydantic
        # Ensure MedicalRecord is imported/defined above this function
        validated = MedicalRecord.model_validate(temp_data).model_dump()

        if validated.get("age_group") in ("Unknown", "", None):
            validated["age_group"] = infer_age_group(english_text)
        if validated.get("urgency") in ("Unknown", "", None):
            validated["urgency"] = infer_urgency(english_text, validated.get("severity", ""))

        return validated

    except Exception as e:
        print(f"\n--- ❌ PARSER ERROR LOG ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        if content:
            print(f"Raw AI Content: {content[:100]}...")
        print(f"---------------------------\n")
        
        # Return a dictionary that matches your Pydantic schema so the pipeline can continue
        return {
            "condition": "Extraction Error",
            "sub_specialty_inference": "General",
            "severity": "Unknown",
            "age_group": "Unknown",
            "urgency": "Unknown",
            "is_cardio_oncology": False,
            "raw_summary": f"Failed: {str(e)}"
        }
    
def scrub_pii(data):
    """Privacy layer to remove sensitive dates and phone numbers."""
    for key, value in data.items():
        if isinstance(value, str):
            # Mask common patterns (Dates and Phone numbers)
            value = re.sub(r'\d{2}/\d{2}/\d{4}', '[REDACTED_DATE]', value)
            value = re.sub(r'\+?\d{10,12}', '[REDACTED_PHONE]', value)
            data[key] = value
    return data

def scrub_raw_text(text: str) -> str:
    """Aggressively scrubs raw OCR text to prevent AI safety filters from triggering."""
    if not text:
        return text
        
    # Mask variations of addresses
    text = re.sub(r'(?i)ad\s*dress[es]*.*?[\n\r]', '[REDACTED_ADDRESS]\n', text)
    
    # Mask License Numbers
    text = re.sub(r'(?i)license\s*number.*?[\n\r]', '[REDACTED_LICENSE]\n', text)
    
    # Mask patient greetings
    text = re.sub(r'(?i)dear\s+(mr|ms|mrs|dr|me).*?[\n\r:]', 'Dear [REDACTED_NAME]:\n', text)
    
    # Generic long numbers (Phones, IDs)
    text = re.sub(r'\+?\d{8,15}', '[REDACTED_NUMBER]', text)
    
    # Dates
    text = re.sub(r'\d{2}[-/\.]\d{2}[-/\.]\d{4}', '[REDACTED_DATE]', text)
    
    return text
