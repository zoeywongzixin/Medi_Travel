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
    "mhtc_visa_support": "MALAYSIA HEALTHCARE TRAVEL COUNCIL (MHTC)\nCompliance Liaison Office\n\nOFFICIAL VISA SUPPORT LETTER\n\nTo: The Director of Immigration / Visa Department\nRe: Medical Travel Authorization for {patient_name}\n\nThis letter serves as official confirmation and support for the medical travel of {patient_name} (Passport: {patient_passport}).\n\nThe patient is scheduled for {treatment_type} at {hospital_name} under the clinical supervision of {specialist_name} (MMC Registration No: ____________).\n\nAs per MHTC healthcare travel standards, this case is officially supported under the medical tourism facilitation framework. We kindly request the processing of the necessary medical visa/entry permits, with specific reference to Borang IM.47 (Medical Treatment Support).\n\nAccompanying Escort Details:\nName: {escort_name}\nPassport: {escort_passport}\n\nIssued by,\nMHTC Compliance Liaison Officer\nKuala Lumpur, Malaysia",
    "official_referral": (
        "OFFICIAL CLINICAL REFERRAL LETTER\n"
        "Date: {current_date}\n\n"
        "To: {specialist_name}, {hospital_name}, Malaysia\n\n"
        "Dear Dr. {specialist_name},\n\n"
        "Re: Referral for Medical Assessment and Management\n"
        "Patient: {patient_name} (Passport: {patient_passport})\n\n"
        "I am writing to formally refer the above-named patient for further specialist assessment "
        "and management at your esteemed facility.\n\n"
        "Clinical Summary:\n"
        "{clinical_summary}\n\n"
        "The estimated duration of stay is expected to be around {total_stay_days} days to accommodate "
        "pre-operative assessment, the procedure, and an adequate recovery observation window.\n\n"
        "Kindly arrange for the necessary admission protocols upon their arrival.\n\n"
        "Sincerely,\n"
        "Referring Medical Officer\n"
        "Malaysia Medical Match Platform"
    ),
    "smart_itinerary": (
        "SMART MEDICAL TRAVEL ITINERARY\n"
        "Patient: {patient_name}\n"
        "Destination: {hospital_name}, Malaysia\n\n"
        "TRAVEL DATES (Calculated based on clinical estimation):\n"
        "- Arrival Date: {arrival_date}\n"
        "- Departure Date: {departure_date}\n"
        "- Total Estimated Stay: {total_stay_days} days\n\n"
        "FLIGHT LOGISTICS:\n"
        "{flight_details}\n\n"
        "HOSPITAL APPOINTMENT:\n"
        "Please proceed directly to {hospital_name} on your arrival date for clinical registration "
        "with {specialist_name}.\n\n"
        "Note: This itinerary has been algorithmically generated based on your preferred travel month and "
        "the specific clinical requirements of your diagnosis."
    ),
    "charity_memo": (
        "OFFICIAL FINANCIAL ASSISTANCE MEMO\n"
        "Date: {current_date}\n\n"
        "Subject: Potential Financial Subsidy Eligibility\n\n"
        "Based on the financial assessment comparing the estimated treatment and travel costs "
        "against the declared budget, the patient {patient_name} has been identified as a candidate "
        "for financial assistance.\n\n"
        "MATCHED CHARITY/SUBSIDY PROVIDER:\n"
        "{charity_details}\n\n"
        "NEXT STEPS:\n"
        "The patient or authorized representative is advised to contact the foundation directly "
        "or through the hospital's international patient center to formalize the subsidy application "
        "prior to the scheduled treatment.\n\n"
        "Issued by,\n"
        "Financial Liaison\n"
        "Malaysia Medical Match Platform"
    )
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
    pkg = package_data or {}
    charity = pkg.get("charity") or pkg.get("selected_charity")
    
    # Also check inside grant_analysis if passed from some flows
    if not charity and "grant_analysis" in pkg:
        charity = pkg["grant_analysis"].get("selected_charity")
        
    if not charity:
        return "No financial aid / charity fund is allocated to this package."

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
    template_str: str,
    user_data: Optional[Dict[str, Any]] = None,
    medical_data: Optional[Dict[str, Any]] = None,
    package_data: Optional[Dict[str, Any]] = None,
) -> str:
    user_data = user_data or {}
    medical_data = medical_data or {}
    package_data = package_data or {}

    # Enrich user_data with clinical and itinerary details for the template
    enrich_user_data_with_package(user_data, medical_data, package_data)
    
    current_date = user_data.get("current_date")
    age_group = user_data.get("age_group")
    diagnosis = user_data.get("medical_condition")
    urgency_status = _normalize_urgency_status(medical_data)
    hospital_line = user_data.get("hospital_details", "")
    flight_line = user_data.get("flight_details", "")
    charity_line = user_data.get("charity_details", "")

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
    
    # If template_str looks like a key, use the skeleton, otherwise use the string directly
    final_template = LETTER_SKELETONS.get(template_str, template_str)
    
    # If the template contains placeholders like {diagnosis}, {charity_details}, etc.
    # we fill it using our enriched user_data
    return fill_template(final_template, user_data)

def enrich_user_data_with_package(user_data: Dict[str, Any], medical_data: Dict[str, Any], package_data: Dict[str, Any]):
    """Populates user_data with printable strings derived from medical and package data."""
    current_date = _clean_text(
        user_data.get("current_date"),
        _default_letter_date(),
    )
    user_data["current_date"] = current_date
    user_data["age_group"] = _normalize_age_group(medical_data, user_data)
    user_data["medical_condition"] = _normalize_diagnosis(medical_data, user_data)
    user_data["diagnosis"] = user_data["medical_condition"]
    user_data["urgency_status"] = _normalize_urgency_status(medical_data)
    
    # Format lines for templates that use {hospital_details}, {flight_details}, etc.
    user_data["hospital_details"] = _format_hospital_line(package_data, user_data)
    user_data["flight_details"] = _format_flight_line(package_data, user_data)
    user_data["charity_details"] = _format_charity_line(package_data)
    
    # Map to common template keys
    user_data["hospital_name"] = _clean_text(((package_data or {}).get("specialist") or {}).get("hospital"), "Selected Hospital")
    user_data["specialist_name"] = _clean_text(((package_data or {}).get("specialist") or {}).get("name"), "Selected Specialist")
    
    if package_data and "clinical_summary" in package_data:
        cs = package_data["clinical_summary"]
        user_data["clinical_summary"] = cs.get("professional_summary", "")
        user_data["total_stay_days"] = cs.get("total_stay_days", "")
        
    if package_data and "travel_dates" in package_data:
        td = package_data["travel_dates"]
        user_data["arrival_date"] = td.get("arrival_date", "")
        user_data["departure_date"] = td.get("departure_date", "")
    
    # Default fallbacks for patient info if not provided
    user_data["patient_name"] = _clean_text(user_data.get("patient_name"), "___________________________")
    user_data["patient_passport"] = _clean_text(user_data.get("patient_passport"), "_______________________")
    user_data["escort_name"] = _clean_text(user_data.get("escort_name"), "_________________________")
    user_data["escort_passport"] = _clean_text(user_data.get("escort_passport"), "_______________________")

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
