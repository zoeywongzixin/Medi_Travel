import ollama

def translate_medical_text(raw_text):
    """Translate medical text to clear English. NO JSON."""
    
    system_prompt = (
        "You are a medical translator. "
        "Translate the provided OCR text into clear, readable English. "
        "Fix any obvious OCR typos (like 'Lurigs' to 'Lungs'). "
        "Return ONLY the translated English text, and nothing else. No introductions or apologies."
    )
    
    response = ollama.chat(
        model='llama3.2:3b',   # ⬅️ upgrade from 1B → 3B
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': raw_text}
        ],
        options={'temperature': 0}
    )
    
    # Handle both old (dict) and new (object) Ollama response formats
    if hasattr(response, 'message'):
        return response.message.content
    return response['message']['content']
