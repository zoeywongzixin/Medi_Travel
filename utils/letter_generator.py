from fpdf import FPDF
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

LETTER_SKELETONS = {
    "appointment_conf": "Surat Pengesahan Rawatan\n\nDengan ini disahkan bahawa pesakit sedang menerima rawatan di {hospital_name} di bawah seliaan {specialist_name}.",
    "visa_support": (
        "OFFICIAL MEDICAL INVITATION\n"
        "Reference: {appointment_id}\n"
        "Date: {current_date}\n\n"
        "TO: THE DIRECTOR GENERAL OF IMMIGRATION, MALAYSIA\n\n"
        "RE: MEDICAL VISA SUPPORT FOR {patient_name} (Passport: {patient_passport})\n\n"
        "This is to certify that the above-named patient is under the care of {hospital_name} "
        "for {medical_condition}. The patient is scheduled for {treatment_type} "
        "under the supervision of {specialist_name}.\n\n"
        "PROPOSED ITINERARY:\n"
        "- Tentative Admission: {start_date}\n"
        "- Estimated Duration: {duration}\n"
        "- Designated Escort: {escort_name} (Passport: {escort_passport})\n\n"
        "As an MHTC-registered facility, we confirm that the patient has completed the "
        "necessary clinical pre-screening. We kindly request your assistance in granting "
        "entry for medical purposes as per the provided Borang IM.47.\n\n"
        "Issued by,\n"
        "{specialist_name}\n"
        "{hospital_name}, Malaysia"
    ),
    "urgent_appeal": "Surat Rayuan Urusan Perubatan\n\nKami memohon pertimbangan segera bagi urusan perubatan pesakit ini, dengan sokongan Borang IM.47.",
    "mhtc_visa_support": "MALAYSIA HEALTHCARE TRAVEL COUNCIL (MHTC)\nCompliance Liaison Office\n\nOFFICIAL VISA SUPPORT LETTER\n\nTo: The Director of Immigration / Visa Department\nRe: Medical Travel Authorization for {patient_name}\n\nThis letter serves as official confirmation and support for the medical travel of {patient_name} (Passport: {patient_passport}).\n\nThe patient is scheduled for {treatment_type} at {hospital_name} under the clinical supervision of {specialist_name} (MMC Registration No: ____________).\n\nAs per MHTC healthcare travel standards, this case is officially supported under the medical tourism facilitation framework. We kindly request the processing of the necessary medical visa/entry permits, with specific reference to Borang IM.47 (Medical Treatment Support).\n\nAccompanying Escort Details:\nName: {escort_name}\nPassport: {escort_passport}\n\nIssued by,\nMHTC Compliance Liaison Officer\nKuala Lumpur, Malaysia"
}

VISA_TEMPLATE_KEYS = {"visa_support", "mhtc_visa_support"}
UNICODE_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/calibri.ttf"),
)


def _clean_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _find_unicode_font() -> Optional[Path]:
    for candidate in UNICODE_FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _default_letter_date() -> str:
    return datetime.now().strftime("%d %B %Y").lstrip("0")


def _normalize_age_group(medical_data: Optional[Dict[str, Any]], user_data: Dict[str, Any]) -> str:
    raw_value = ""
    if medical_data:
        raw_value = medical_data.get("age_group", "")
    if not raw_value:
        raw_value = user_data.get("age_group", "")

    normalized = str(raw_value).strip().title()
    if normalized in {"Infant", "Child", "Adult", "Senior"}:
        return normalized
    return "Unknown"


def _normalize_diagnosis(medical_data: Optional[Dict[str, Any]], user_data: Dict[str, Any]) -> str:
    if medical_data and medical_data.get("condition"):
        return _clean_text(medical_data["condition"], "Clinical condition under review")
    return _clean_text(user_data.get("medical_condition"), "Clinical condition under review")


def _normalize_urgency_status(medical_data: Optional[Dict[str, Any]]) -> str:
    severity = ""
    urgency = ""
    if medical_data:
        severity = str(medical_data.get("severity", "")).strip().title()
        urgency = str(medical_data.get("urgency", "")).strip().title()

    if severity == "Critical" or urgency == "Critical":
        return "Critical"
    if severity == "High" or urgency in {"Urgent", "High", "Emergency"}:
        return "Urgent"
    if urgency == "Stable":
        return "Stable"
    if severity in {"Low", "Moderate"}:
        return "Stable"
    return "Stable"


def _format_hospital_line(package_data: Optional[Dict[str, Any]], user_data: Dict[str, Any]) -> str:
    hospital = (package_data or {}).get("hospital") or {}
    hospital_name = _clean_text(
        hospital.get("hospital") or hospital.get("name") or user_data.get("hospital_name"),
        "Hospital to be confirmed in Malaysia",
    )
    specialist_name = _clean_text(
        hospital.get("name") if hospital.get("hospital") else user_data.get("specialist_name"),
        "",
    )
    specialty = _clean_text(hospital.get("specialty"), "")

    if specialist_name and specialty:
        return f"{hospital_name}. Receiving specialist reference: {specialist_name}, {specialty}."
    if specialist_name:
        return f"{hospital_name}. Receiving specialist reference: {specialist_name}."
    return hospital_name


def _format_flight_line(package_data: Optional[Dict[str, Any]], user_data: Dict[str, Any]) -> str:
    flight = (package_data or {}).get("flight") or {}
    if not flight:
        proposed_date = _clean_text(user_data.get("start_date"), "date to be confirmed")
        return f"Flight arrangement pending final booking. Proposed travel timing: {proposed_date}."

    carrier = flight.get("airline") or flight.get("provider") or "Selected carrier"
    flight_type = flight.get("type") or "Medical travel flight"
    price = flight.get("price")
    departure = flight.get("departure")
    arrival = flight.get("arrival")

    details = [f"{carrier} ({flight_type})"]
    if departure:
        details.append(f"departure {departure}")
    if arrival:
        details.append(f"arrival {arrival}")
    if price:
        details.append(f"estimated fare {price}")
    return ", ".join(details) + "."


def _format_charity_line(package_data: Optional[Dict[str, Any]]) -> str:
    charity = (package_data or {}).get("charity") or {}
    if not charity:
        return "No charity selected at the time of issuance."

    name = _clean_text(charity.get("name"), "Selected charity")
    organization = _clean_text(charity.get("organization"), "")
    coverage = charity.get("max_coverage_usd")

    line = name
    if organization:
        line += f", administered by {organization}"
    if coverage:
        line += f", with listed support coverage up to USD {coverage}"
    return line + "."


def build_visa_support_content(
    user_data: Optional[Dict[str, Any]] = None,
    medical_data: Optional[Dict[str, Any]] = None,
    package_data: Optional[Dict[str, Any]] = None,
) -> str:
    user_data = user_data or {}
    medical_data = medical_data or {}
    package_data = package_data or {}

    current_date = _clean_text(
        user_data.get("current_date"),
        _default_letter_date(),
    )
    age_group = _normalize_age_group(medical_data, user_data)
    diagnosis = _normalize_diagnosis(medical_data, user_data)
    urgency_status = _normalize_urgency_status(medical_data)
    hospital_line = _format_hospital_line(package_data, user_data)
    flight_line = _format_flight_line(package_data, user_data)
    charity_line = _format_charity_line(package_data)

    is_critical = urgency_status == "Critical"
    title = "MEDICAL APPEAL LETTER" if is_critical else "MEDICAL TRAVEL SUPPORT LETTER"
    subject = (
        "Medical Appeal for Cross-Border Treatment Facilitation"
        if is_critical else
        "Medical Travel Support for Cross-Border Treatment"
    )
    purpose_line = (
        "This letter is issued as a medical appeal for urgent cross-border treatment support"
        if is_critical else
        "This letter is issued in support of the above patient for planned medical travel"
    )
    request_line = (
        "Given the critical clinical status, we respectfully request immediate consideration of visa and entry facilitation under Borang IM.47."
        if is_critical else
        "In line with MHTC medical travel standards, we respectfully request consideration of the necessary visa or entry facilitation under Borang IM.47."
    )

    content = "\n".join([
        "MALAYSIA HEALTHCARE TRAVEL COUNCIL (MHTC)",
        title,
        "Reference: Borang IM.47 Medical Treatment Support",
        f"Date: {current_date}",
        "",
        "To:",
        "The Director of Immigration / Visa Department",
        "Malaysia",
        "",
        f"Subject: {subject}",
        "",
        "Clinical Extraction Summary",
        f"Age Group: {age_group}",
        f"Diagnosis: {diagnosis}",
        f"Urgency Status: {urgency_status}",
        "",
        "PATIENT NAME: ___________________________",
        "",
        "PASSPORT NUMBER: _______________________",
        "",
        "CAREGIVER NAME: _________________________",
        "",
        f"{purpose_line} to Malaysia in accordance with Malaysia Healthcare Travel Council (MHTC) standards and the supporting requirements of Borang IM.47.",
        "",
        "Based on the medical chart reviewed in this case, the patient requires specialist assessment and coordinated treatment planning in Malaysia. This document is prepared for administrative support only and intentionally uses placeholders for all personal identifiers.",
        "",
        "Formal Itinerary",
        "1. Selected Hospital",
        hospital_line,
        "",
        "2. Selected Flight",
        flight_line,
        "",
        "3. Selected Charity",
        charity_line,
        "",
        "Upon arrival in Malaysia, the patient is expected to proceed to the selected treatment center for specialist review, admission coordination, and onward management as clinically indicated.",
        "",
        request_line,
        "We further request permission for one caregiver to accompany the patient for travel support, hospital registration, and continuity of care.",
        "",
        "Issued in support of medical travel coordination to Malaysia.",
        "",
        "Sincerely,",
        "",
        "MHTC Liaison / Medical Travel Coordination Desk",
        "Malaysia Medical Match Platform",
    ])
    return content

def fill_template(template_str: str, user_data: dict) -> str:
    """
    Fills the template with user data.
    Sensitive patient data stays local to comply with healthcare privacy standards.
    """
    try:
        return template_str.format(**user_data)
    except KeyError as e:
        # Fallback to literal template if keys are missing
        return template_str
    except Exception as e:
        return f"Error filling template: {str(e)}"

def generate_pdf(content: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    unicode_font = _find_unicode_font()

    if unicode_font is not None:
        pdf.add_font("UnicodeSans", "", str(unicode_font))
        pdf.set_font("UnicodeSans", size=12)
    else:
        pdf.set_font("helvetica", size=12)
    
    # Ensure the content is a string and use the 'txt' parameter
    pdf.multi_cell(0, 10, txt=str(content))
    
    # fpdf2 returns a bytearray here; FastAPI Response expects bytes.
    return bytes(pdf.output())
