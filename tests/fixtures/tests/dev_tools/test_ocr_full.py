import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from utils.ocr_engine import extract_raw_text
from utils.translator import translate_medical_text
from utils.parser import get_concise_json

img_path = str(Path(__file__).resolve().parent.parent / "fixtures" / "vietnamese_report.jpg")

print(f"--- Extracting from {img_path} ---")
raw_text = extract_raw_text(img_path)
print(f"Raw Text: {raw_text}")

if "Error" not in raw_text:
    print("\n--- Translating ---")
    english = translate_medical_text(raw_text)
    print(f"English: {english}")

    print("\n--- Parsing ---")
    data = get_concise_json(english)
    print(f"JSON Data: {data}")
