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
        "4. 'is_cardio_oncology': Set to true only if the text clearly mentions both cancer or tumor disease and a meaningful heart-related complication.\n"
        "5. If a value is missing, use 'Unknown'.\n"
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

        # 4. Final Validation with Pydantic
        # Ensure MedicalRecord is imported/defined above this function
        return MedicalRecord.model_validate(temp_data).model_dump()

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
