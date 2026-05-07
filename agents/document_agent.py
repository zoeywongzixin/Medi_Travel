import os
import json
from pathlib import Path
from typing import Dict
from utils.llm import call_gemini

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "visa"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "generated_docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_visa_document(user_data: Dict, package_data: Dict, origin_country: str) -> str:
    """
    Generates a fillable Word document using Gemini to naturally draft the letter
    in the requested language based on the template guidelines.
    """
    template_path = TEMPLATES_DIR / f"{origin_country.lower()}.md"
    if not os.path.exists(template_path):
        template_path = TEMPLATES_DIR / "default.md"

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    except FileNotFoundError:
        template_content = "Medical Visa Invitation Letter\n[ENTER PATIENT NAME]\n[ENTER HOSPITAL NAME], [ENTER CITY]\n"

    specialist = package_data.get("specialist") or package_data.get("hospital") or {}
    hospital_name = specialist.get("hospital") or specialist.get("name") or "Unknown Hospital"
    city = package_data.get("flight", {}).get("destination_city") or "Unknown City"

    system_prompt = (
        "You are a professional administrative assistant for a Malaysian hospital. "
        "Your task is to draft a Medical Visa Invitation Letter. "
        "Use the provided template as a strict guideline for structure and language. "
        "Replace placeholders like [ENTER HOSPITAL NAME] and [ENTER CITY] with the provided real data. "
        "Leave user-specific placeholders (like [ENTER PATIENT NAME] or [ENTER PASSPORT NUMBER]) exactly as they are. "
        "Do not include any external markdown formatting in your final output, just raw text. "
        f"Ensure the language matches the intended language of the template ({origin_country} or English)."
    )

    user_prompt = (
        f"Hospital Data to inject:\n"
        f"Hospital Name: {hospital_name}\n"
        f"City: {city}\n\n"
        f"Template:\n{template_content}"
    )

    try:
        res = call_gemini(system_prompt, user_prompt, model_name="gemini-1.5-flash")
        final_text = res.get("text", "").strip()
    except Exception as e:
        print(f"Document Agent: Gemini generation failed, using basic replace: {e}")
        final_text = template_content.replace("[ENTER HOSPITAL NAME]", hospital_name).replace("[ENTER CITY]", city)

    # Save as plain text (docx dependency removed to avoid heavy dependency)
    filename = f"visa_application_{origin_country.lower()}.txt"
    output_path = OUTPUT_DIR / filename
    with open(str(output_path), "w", encoding="utf-8") as fout:
        fout.write(final_text)

    return str(output_path)
