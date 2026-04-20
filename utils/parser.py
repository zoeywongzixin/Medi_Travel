import re
import json
import ollama
from pydantic import BaseModel, Field

class MedicalRecord(BaseModel):
    condition: str = Field(description="The primary medical diagnosis or condition")
    severity: str = Field(description="Low, Moderate, High, or Critical")
    age_group: str = Field(description="Infant, Child, Adult, or Senior")
    urgency: str = Field(description="How fast they need a doctor: Low, Medium, High")
    is_cardio_oncology: bool = Field(description="True if the case relates to Heart or Cancer")
    raw_summary: str = Field(description="A 1-sentence summary of the extracted text")

def get_concise_json(english_text):
    """Uses Llama 3.2 to structure the translated text into a valid JSON."""
    MODEL_NAME = 'llama3.2:3b' 
    content = "" # Initialize empty so the except block doesn't crash

    system_prompt = (
        "You are a strict medical data extractor. Return ONLY a flat JSON object. "
        "Rules for keys:\n"
        "1. 'condition', 'severity', 'age_group', 'urgency', 'raw_summary': Use 'Unknown' if missing.\n"
        "2. 'is_cardio_oncology': This MUST be a boolean (true or false). "
        "Set to true ONLY if the text mentions cancer, tumors, heart issues, or cardiology. Otherwise, set to false.\n"
        "3. Return ONLY the JSON."
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