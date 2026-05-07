import re
import hashlib
from typing import Dict, List, Tuple

class PrivacyScrubber:
    """
    Production-grade Privacy Shield that detects and masks PII.
    Replaces patient names with hash identifiers (e.g., PATIENT_HASH_8805).
    """

    def __init__(self):
        self.logs: List[str] = []
    
    def get_logs(self) -> List[str]:
        logs = list(self.logs)
        self.logs.clear() # Clear after reading
        return logs

    def log(self, message: str):
        self.logs.append(f"[PRIVACY]: {message}")
        print(f"[PRIVACY]: {message}")

    def hash_name(self, name: str) -> str:
        # Create a short 4-digit hex hash for the name
        hash_suffix = hashlib.md5(name.lower().encode()).hexdigest()[:4]
        return f"PATIENT_HASH_{hash_suffix.upper()}"

    def scrub_raw_text(self, text: str) -> str:
        """Aggressively scrubs raw OCR text and records logs."""
        if not text:
            return text
            
        original_text = text
        
        # 1. Mask Names based on common structures or greetings
        name_patterns = [
            (r'(?i)patient\s+name[:\s]+([A-Za-zÀ-ỹ\s]+)(?:\n|\r|$)', "Patient Name: {hash}\n"),
            (r'(?i)dear\s+(mr\.?|ms\.?|mrs\.?|dr\.?|me)\s+([A-Za-zÀ-ỹ\s]+)(?:[\n\r:,])', "Dear {hash}:\n"),
            (r'(?i)nama\s+pesakit[:\s]+([A-Za-zÀ-ỹ\s]+)(?:\n|\r|$)', "Nama Pesakit: {hash}\n")
        ]
        
        for pattern, replacement in name_patterns:
            def replacer(match):
                # The name is usually the last group
                name = match.group(match.lastindex).strip()
                hashed = self.hash_name(name)
                self.log(f"Masking PII for {name} -> {hashed}")
                return replacement.format(hash=hashed)
            text = re.sub(pattern, replacer, text)
            
        # 2. Mask Vietnamese specific name structures (often uppercase words at start of line after specific keywords)
        vietnamese_name_match = re.search(r'(?i)(?:Họ\s+và\s+tên|Tên|Patient|Name)[:\s]+([A-Z][a-zÀ-ỹA-Z\s]+)', text)
        if vietnamese_name_match:
            name = vietnamese_name_match.group(1).strip()
            hashed = self.hash_name(name)
            self.log(f"Masking PII for {name} -> {hashed}")
            text = text.replace(vietnamese_name_match.group(1), hashed)

        # 3. Mask Dates of Birth (DOB)
        dob_patterns = [
            r'(?i)(?:dob|date\s+of\s+birth|ngày\s+sinh)[:\s]*\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}'
        ]
        for pattern in dob_patterns:
            if re.search(pattern, text):
                self.log("Masking exact DOB")
                text = re.sub(pattern, "DOB: [REDACTED_DOB]", text)

        # 4. Generic long numbers (Phones, IDs)
        # We need to make sure we don't redact clinical numbers. Phone numbers typically are 8-15 digits.
        phone_matches = re.finditer(r'(?:\+?\d{1,3}[\s-]?)?\(?\d{3,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', text)
        has_phone = False
        for match in phone_matches:
            val = match.group(0).strip()
            if len(re.sub(r'\D', '', val)) >= 8: # If it has at least 8 digits
                has_phone = True
                text = text.replace(val, '[REDACTED_PHONE]')
        if has_phone:
            self.log("Masking Phone Numbers")

        # 5. Mask Email Addresses
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        if re.search(email_pattern, text):
            self.log("Masking Email Address")
            text = re.sub(email_pattern, '[REDACTED_EMAIL]', text)

        # 6. Fallbacks from original scrub_raw_text
        text = re.sub(r'(?i)ad\s*dress[es]*.*?[\n\r]', '[REDACTED_ADDRESS]\n', text)
        text = re.sub(r'(?i)license\s*number.*?[\n\r]', '[REDACTED_LICENSE]\n', text)
        text = re.sub(r'\d{2}[-/\.]\d{2}[-/\.]\d{4}', '[REDACTED_DATE]', text)

        return text
