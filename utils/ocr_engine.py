import os
import cv2
import numpy as np
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Fetch paths and CLEAN them (removes quotes and accidental spaces)
TESSERACT_PATH = os.getenv('TESSERACT_PATH', '').strip().replace('"', '')
POPPLER_BIN = os.getenv('POPPLER_PATH', '').strip().replace('"', '')

# Apply Tesseract configuration
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    print("❌ ERROR: TESSERACT_PATH missing from .env")

# --- PATH VALIDATION (Debugging) ---
# This will alert you immediately if the folder doesn't exist
if not os.path.exists(POPPLER_BIN):
    print(f"❌ ERROR: Poppler path is incorrect: {POPPLER_BIN}")

# Configure Tesseract path
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH.strip()
else:
    print("❌ ERROR: TESSERACT_PATH not found in .env file.")

# --- HELPER FUNCTIONS ---

def preprocess_image_data(cv_img):
    """
    Cleans and prepares image data for OCR.
    Uses adaptive thresholding to handle uneven lighting in photos (snaps).
    """
    # Convert to grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Apply Adaptive Thresholding
    # This is better for scanned/snapped documents than simple global thresholding
    distorted = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    return Image.fromarray(distorted)

# --- MAIN EXTRACTION ENGINE ---

def extract_raw_text(file_path):
    """
    Main extraction logic for both Images (.jpg, .png) and PDFs.
    Returns a string of extracted raw text.
    """
    if not os.path.exists(file_path):
        return f"Error: The file path '{file_path}' does not exist."

    try:
        # Handle PDF files
        if file_path.lower().endswith('.pdf'):
            # Convert PDF pages to images
            # Uses POPPLER_BIN fetched from .env
            pages = convert_from_path(file_path, poppler_path=POPPLER_BIN)
            
            full_text = ""
            for i, page in enumerate(pages):
                # Convert PIL page to OpenCV format for cleaning
                open_cv_image = np.array(page)
                processed_page = preprocess_image_data(open_cv_image)
                
                # oem 3 = Default OCR engine, psm 6 = Assume a single uniform block of text
                custom_config = r'--oem 3 --psm 6'
                page_text = pytesseract.image_to_string(processed_page, config=custom_config)
                full_text += f"\n[Page {i+1}]\n{page_text}"
            
            return full_text
            
        # Handle Standard Image files
        else:
            img = cv2.imread(file_path)
            if img is None:
                return "Error: Could not read image file. It may be corrupted or in an unsupported format."
            
            processed_img = preprocess_image_data(img)
            
            # Perform OCR on single image
            custom_config = r'--oem 3 --psm 6'
            return pytesseract.image_to_string(processed_img, config=custom_config)

    except Exception as e:
        return f"OCR Engine Error: {str(e)}"