import ollama

def translate_medical_text(raw_text):
    """Translate medical text to clear English. NO JSON."""
    
    system_prompt = (
        "You are a professional medical translator.\n"
        "Translate the following medical report into clear, accurate English.\n"
        "Do NOT summarize.\n"
        "Do NOT return JSON.\n"
        "Return ONLY translated English text."
    )
    
    response = ollama.chat(
        model='llama3.2:3b',   # ⬅️ upgrade from 1B → 3B
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': raw_text}
        ],
        options={'temperature': 0}
    )
    
    return response['message']['content']
