import ollama

def translate_medical_text(raw_text):
    """Translate medical text to clear English. NO JSON."""
    
    system_prompt = (
        "You are a medical translator. "
        "Translate the provided OCR text into clear, readable English. "
        "Fix any obvious OCR typos (like 'Lurigs' to 'Lungs'). "
        "Return ONLY the translated English text, and nothing else. No introductions or apologies."
    )
    
    return _call_ollama(system_prompt, raw_text)

def translate_template_text(template_str, target_language):
    """Translate a medical template to target language, keeping placeholders."""
    system_prompt = (
        f"Translate this medical template to {target_language}. "
        "Keep {{placeholders}} exactly as they are. "
        "Return ONLY the translated string."
    )
    return _call_ollama(system_prompt, template_str)


def translate_text(text, target_language):
    """Translate general display text to the chosen language."""
    system_prompt = (
        f"Translate the provided text to {target_language}. "
        "Preserve medical terms, hospital names, charity names, codes, acronyms, and numbers when appropriate. "
        "Return ONLY the translated text."
    )
    return _call_ollama(system_prompt, text)


def translate_document_text(document_str, target_language):
    """
    Translate a formal document while preserving placeholder lines exactly.
    This keeps fill-in-the-blank PII scaffolding safe for later PDF generation.
    """
    protected_lines = []
    protected_text = document_str

    for index, line in enumerate(document_str.splitlines()):
        if "____" in line:
            token = f"[[PLACEHOLDER_{index}]]"
            protected_lines.append((token, line))
            protected_text = protected_text.replace(line, token, 1)

    system_prompt = (
        f"Translate the provided formal medical travel document to {target_language}. "
        "Preserve placeholder tokens like [[PLACEHOLDER_0]] exactly as they are. "
        "Preserve hospital names, charity names, acronyms, reference codes, and numbers when appropriate. "
        "Return ONLY the translated document."
    )
    translated = _call_ollama(system_prompt, protected_text)

    for token, original_line in protected_lines:
        translated = translated.replace(token, original_line)
    return translated

def _call_ollama(system_prompt, user_content):
    response = ollama.chat(
        model='llama3.2:3b',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content}
        ],
        options={'temperature': 0}
    )
    
    # Handle both old (dict) and new (object) Ollama response formats
    if hasattr(response, 'message'):
        return response.message.content
    return response['message']['content']
