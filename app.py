from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import os
from pathlib import Path
from pydantic import BaseModel, Field
import shutil
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import utilities
from utils.ocr_engine import extract_raw_text
from utils.translator import (
    translate_document_text,
    translate_medical_text,
    translate_template_text,
    translate_text,
)
from utils.parser import get_concise_json
from utils.privacy import PrivacyScrubber
from utils.letter_generator import (
    GUIDANCE_TEMPLATE_KEYS,
    LETTER_SKELETONS,
    VISA_TEMPLATE_KEYS,
    build_visa_support_content,
    fill_template,
    generate_pdf,
)
from fastapi.responses import Response

# Import agents
from agents.logistics_agent import get_transport_requirements
from agents.orchestrator import orchestrate_packages, generate_single_package
from agents.medical_agent import match_hospitals
from agents.flight_agent import get_flight_options
from agents.charity_agent import match_charities
from utils.llm import check_for_clinical_gaps, normalize_medical_data_for_clarification
from utils.db import log_match, get_few_shot_feedback, get_db, User, Selection
from utils.transparency import (
    charity_match_transparency,
    extract_transparency,
    flight_match_transparency,
    hospital_match_transparency,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from fastapi import Depends
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
from typing import Optional, List
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Malaysia Medical Match API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class MatchRequest(BaseModel):
    medical_data: Dict[str, Any]
    origin_country: str = Field(default="Indonesia", description="Where the patient is flying from")
    user_origin: Optional[str] = Field(default=None, description="Optional user-origin city override")
    budget_local: float = Field(default=5000.0, description="Patient's maximum budget in local currency")
    currency: str = Field(default="USD", description="Currency of the budget")
    preferred_month: str = Field(default="Next Month", description="User's preferred month for travel")
    preferred_language: str = Field(default="English", description="Target language for outputs")
    user_priority_preference: str = Field(default="balanced", description="How to rank accessible packages")
    manual_override: bool = Field(default=False, description="Bypass accessibility reranking and preserve raw semantic hits")
    session_id: Optional[str] = Field(default=None, description="Session ID for memory and regeneration")
    rejected_hospitals: Optional[List[str]] = Field(default_factory=list, description="Hospital names already rejected by user")

class LayerRequest(BaseModel):
    medical_data: Dict[str, Any]
    origin_country: str = Field(default="Indonesia", description="Where the patient is flying from")
    language: Optional[str] = "en"


def _build_agent_response(packages: list, manual_override: bool) -> Dict[str, Any]:
    top_package = packages[0] if packages else None
    return {
        "retriever_source": "chromadb",
        "manual_override": manual_override,
        "total_accessibility_score": (top_package or {}).get("total_accessibility_score", 0),
        "structured_itinerary": (top_package or {}).get("structured_itinerary"),
        "antigravity_state": (top_package or {}).get("antigravity_state"),
    }

class CombinePackageRequest(BaseModel):
    hospital: Dict[str, Any]
    logistics_data: Dict[str, Any]
    flight: Optional[Dict[str, Any]] = None
    charity: Optional[Dict[str, Any]] = None
    origin_country: str = Field(default="Indonesia")
    budget_usd: int = Field(default=5000)

class UserCreate(BaseModel):
    username: str
    password: str

class SaveSelectionRequest(BaseModel):
    doctor_id: str
    charity_id: str

@app.post("/api/v1/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = pwd_context.hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@app.post("/api/v1/login")
async def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"access_token": db_user.username, "token_type": "bearer"}

@app.post("/api/v1/save-selection")
async def save_selection(req: SaveSelectionRequest, username: str, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    selection = Selection(user_id=db_user.id, doctor_id=req.doctor_id, charity_id=req.charity_id)
    db.add(selection)
    db.commit()
    return {"message": "Selection saved"}

@app.get("/")
def root():
    return {"status": "ok", "message": "Multi-layer Agent Backend is running."}

@app.get("/tester", response_class=HTMLResponse)
async def get_tester():
    """Serves the interactive pipeline tester UI directly from the backend."""
    try:
        tester_path = Path(__file__).resolve().parent / "frontend" / "pipeline_tester.html"
        with open(tester_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tester UI file not found")

@app.post("/api/v1/extract")
async def extract_chart(file: UploadFile = File(...)):
    """
    Step 1: Upload a medical chart (Image/PDF). Extracts text, translates, and parses to JSON.
    """
    file_location = f"temp_{file.filename}"
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
            
        # 1. OCR Extraction
        raw_text = extract_raw_text(file_location)
        if "Error" in raw_text:
            raise HTTPException(status_code=400, detail=raw_text)
            
        # Scrub sensitive info BEFORE sending to the LLM
        scrubber = PrivacyScrubber()
        safe_raw_text = scrubber.scrub_raw_text(raw_text)
        privacy_logs = scrubber.get_logs()
            
        # 2. Translation
        english_text = translate_medical_text(safe_raw_text)
        
        # 3. Parsing
        structured_data = get_concise_json(english_text)
        
        return {
            "medical_data": structured_data,
            "privacy_logs": privacy_logs,
            "decision_transparency": extract_transparency(len(privacy_logs or [])),
            "debug": {
                "raw_text_original": raw_text,
                "raw_text_scrubbed": safe_raw_text,
                "translated_text": english_text
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

@app.post("/api/v1/match-packages")
async def match_packages(request: MatchRequest):
    """
    Step 2: Takes the extracted medical data and orchestrates layers 1, 2, and 3.
    Supports memory (rejected_hospitals) and Few-Shot feedback injection.
    """
    medical_data = normalize_medical_data_for_clarification(request.medical_data)
    origin = request.origin_country
    preferred_month = request.preferred_month
    language = request.preferred_language
    session_id = request.session_id or str(uuid.uuid4())

    # Step 2a: Agentic Clarification Loop - check for clinical gaps first
    clarification = check_for_clinical_gaps(medical_data)
    if clarification:
        return {
            "clarification_required": True,
            "session_id": session_id,
            "missing_detail": clarification.get("missing_detail_description"),
            "clarification_question": clarification.get("clarification_question"),
            "agent_thinking_step": "Checking for Clinical Gaps...",
        }

    # Step 2b: Few-Shot Feedback Loop - inject prior corrections into context
    condition = medical_data.get("condition", "")
    prior_feedback = get_few_shot_feedback(condition)
    if prior_feedback:
        feedback_notes = "; ".join([f'Previously corrected: {f["feedback"]}' for f in prior_feedback])
        medical_data["_prior_corrections"] = feedback_notes
        print(f"[FEW-SHOT]: Injecting {len(prior_feedback)} prior corrections for condition '{condition}'")

    # Convert local budget to USD for internal logic
    from utils.currency import convert_to_usd
    budget_usd = convert_to_usd(request.budget_local, request.currency)

    # Orchestrate packages (Hospital, Flight, Charity) - skip rejected hospitals
    packages = orchestrate_packages(
        medical_data=medical_data,
        origin_country=origin,
        budget_usd=budget_usd,
        currency=request.currency,
        preferred_month=preferred_month,
        user_origin=request.user_origin,
        user_priority_preference=request.user_priority_preference,
        manual_override=request.manual_override,
        rejected_hospitals=request.rejected_hospitals or [],
    )
    logistics_data = packages[0]["flight_logistics"] if packages else get_transport_requirements(medical_data, origin=origin, destination="Malaysia")

    # Step 2c: Human-in-the-Loop - log match, flag High Urgency as pending
    urgency = medical_data.get("urgency", "Stable")
    db_status = "pending" if urgency in ("Urgent", "Critical") else "approved"
    if packages:
        top = packages[0]
        hospital_name = (top.get("specialist") or {}).get("hospital", "Unknown")
        flight_name = (top.get("flight") or {}).get("airline", "Unknown")
        charity_name = ((top.get("charity") or {}).get("name", "None"))
        log_match(session_id, db_status, condition, hospital_name, flight_name, charity_name, urgency)

    # Translate outputs if necessary
    if language.lower() not in ["english", "en"]:
        for p in packages:
            p["package_type"] = translate_text(p["package_type"], language)
            p["package_reasoning"] = translate_text(p["package_reasoning"], language)
            if "structured_itinerary" in p and "summary" in p["structured_itinerary"]:
                p["structured_itinerary"]["summary"] = translate_text(p["structured_itinerary"]["summary"], language)
            if "clinical_summary" in p and "professional_summary" in p["clinical_summary"]:
                p["clinical_summary"]["professional_summary"] = translate_text(p["clinical_summary"]["professional_summary"], language)

    return {
        "session_id": session_id,
        "match_status": db_status,
        "agent_response": _build_agent_response(packages, request.manual_override),
        "logistics": logistics_data,
        "recommended_packages": packages
    }

@app.post("/api/v1/match-hospitals")
async def api_match_hospitals(request: LayerRequest):
    """Returns top 3 hospitals for the given medical data."""
    from agents.medical_agent import match_hospitals
    hospitals = match_hospitals(request.medical_data)
    
    condition = request.medical_data.get("condition", "your condition")
    from utils.translator import generate_friendly_reasoning
    for h in hospitals:
        h["reasoning"] = generate_friendly_reasoning("hospital/doctor", h, condition, request.language or "en")
        
    return {
        "hospitals": hospitals,
        "decision_transparency": hospital_match_transparency(request.medical_data),
    }

@app.post("/api/v1/match-flights")
async def api_match_flights(request: LayerRequest):
    from agents.flight_agent import get_flight_options
    from agents.logistics_agent import get_transport_requirements
    logistics_data = get_transport_requirements(request.medical_data, origin=request.origin_country, destination="Malaysia")
    logistics = get_flight_options(logistics_data, request.origin_country)
    
    condition = request.medical_data.get("condition", "your condition")
    from utils.translator import generate_friendly_reasoning
    for f in logistics.get("options", []):
        f["reasoning"] = generate_friendly_reasoning("flight", f, condition, request.language or "en")
        
    return {
        "logistics_data": logistics_data,
        "flight_options": logistics,
        "decision_transparency": flight_match_transparency(
            request.origin_country, logistics_data, logistics
        ),
    }

@app.post("/api/v1/match-charities")
async def api_match_charities(request: LayerRequest):
    """Returns top 3 charities based on medical data and origin."""
    from agents.charity_agent import match_charities
    charities = match_charities(request.medical_data, request.origin_country)
    
    condition = request.medical_data.get("condition", "your condition")
    from utils.translator import generate_friendly_reasoning
    
    import os
    from tavily import TavilyClient
    tavily_key = os.getenv("TAVILY_API_KEY")
    client = TavilyClient(api_key=tavily_key) if tavily_key else None
    
    for c in charities:
        c["reasoning"] = generate_friendly_reasoning("charity", c, condition, request.language or "en")
        if client:
            try:
                res = client.search(f'"{c["name"]}" official website', search_depth="basic", max_results=1)
                if res.get("results"):
                    c["website"] = res["results"][0]["url"]
                else:
                    c["website"] = "#"
            except:
                c["website"] = "#"
        else:
            c["website"] = "#"
        
    if not charities:
        charities = [{
            "id": "fallback_charity",
            "name": "Global Medical Aid",
            "organization": "Generic NGO",
            "max_coverage_usd": 1000,
            "website": "https://www.who.int",
            "reasoning": "This fallback option is provided because no specific charities were found in the database for your condition."
        }]
        
    return {
        "charities": charities,
        "decision_transparency": charity_match_transparency(
            request.origin_country, condition
        ),
    }

class TranslateTemplateRequest(BaseModel):
    template_key: str
    target_language: str

@app.post("/api/v1/translate-template")
async def translate_template(request: TranslateTemplateRequest):
    """
    Translates the skeleton only using Ollama.
    Sensitive patient data stays local to comply with healthcare privacy standards.
    """
    if request.template_key not in LETTER_SKELETONS:
        raise HTTPException(status_code=404, detail="Template not found")
    
    skeleton = LETTER_SKELETONS[request.template_key]
    translated = translate_template_text(skeleton, request.target_language)
    
    return {"translated_template": translated}


class TranslateTextRequest(BaseModel):
    text: str
    target_language: str


@app.post("/api/v1/translate-text")
async def api_translate_text(request: TranslateTextRequest):
    """Translates arbitrary display text to the requested language."""
    if not request.text.strip():
        return {"translated_text": ""}
    translated = translate_text(request.text, request.target_language)
    return {"translated_text": translated}

class TranslateBatchRequest(BaseModel):
    texts: Dict[str, str]
    target_language: str

@app.post("/api/v1/translate-batch")
async def api_translate_batch(request: TranslateBatchRequest):
    """Translates a dictionary of strings to the requested language."""
    if request.target_language.lower() in ["en", "english"]:
        return {"translated_texts": request.texts}
    
    import json
    from utils.llm import call_gemini
    
    prompt = f"Translate the following UI labels and button texts to {request.target_language}. Keep the exact same keys. Return ONLY valid JSON.\n\n{json.dumps(request.texts, ensure_ascii=False)}"
    
    # Try Ollama first
    import requests
    try:
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        res = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": f"You are a translator helping with administrative UI localization. Return ONLY valid JSON.\n\n{prompt}",
                "stream": False
            },
            timeout=15
        )
        if res.status_code == 200:
            response_text = res.json().get("response", "").strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            translated_dict = json.loads(response_text)
            return {"translated_texts": translated_dict}
    except Exception as e:
        print(f"Ollama batch translation failed: {e}")
        
    # Fallback to Gemini
    try:
        res = call_gemini("You are a translator helping with administrative UI localization. Return ONLY valid JSON.", prompt, model_name="gemini-1.5-flash")
        response_text = res.get("text", "").strip()
        
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        translated_dict = json.loads(response_text)
        
        # Fallback for missing keys
        for k, v in request.texts.items():
            if k not in translated_dict:
                translated_dict[k] = v
                
        return {"translated_texts": translated_dict}
    except Exception as e:
        print(f"Batch translation error: {e}")
        # Fallback to individual
        from utils.translator import translate_text
        translated_dict = {}
        for k, v in request.texts.items():
            try:
                translated_dict[k] = translate_text(v, request.target_language)
            except:
                translated_dict[k] = v
        return {"translated_texts": translated_dict}


class DoctorProfileRequest(BaseModel):
    doctor_name: str
    hospital_name: str

@app.post("/api/v1/doctor-profile")
async def api_doctor_profile(request: DoctorProfileRequest):
    """Searches for the doctor's official profile page using Tavily."""
    import os
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return {"profile_url": None, "error": "Tavily API key missing"}
        
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        query = f'"{request.doctor_name}" "{request.hospital_name}" doctor profile site:com OR site:my OR site:sg OR site:id'
        response = client.search(query, search_depth="basic", max_results=3)
        results = response.get("results", [])
        if results:
            # Return the first URL
            return {"profile_url": results[0]["url"]}
        return {"profile_url": None}
    except Exception as e:
        print(f"Doctor profile search error: {e}")
        return {"profile_url": None, "error": str(e)}

@app.post("/api/v1/combine-package")
async def api_combine_package(request: CombinePackageRequest):
    """Generates the final package reasoning based on user selections."""
    package = generate_single_package(
        hospital=request.hospital,
        logistics_data=request.logistics_data,
        flight=request.flight,
        charity=request.charity,
        origin_country=request.origin_country,
        budget_usd=request.budget_usd
    )
    return {"package": package}
    
class GenerateLetterRequest(BaseModel):
    template_key: str
    user_data: Dict[str, Any] = Field(default_factory=dict)
    medical_data: Optional[Dict[str, Any]] = None
    package_data: Optional[Dict[str, Any]] = None
    target_language: Optional[str] = None

@app.post("/api/v1/preview-letter")
async def api_preview_letter(request: GenerateLetterRequest):
    """Returns the HTML string for the requested letter."""
    if request.template_key not in LETTER_SKELETONS:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template = LETTER_SKELETONS[request.template_key]
    try:
        if request.template_key in VISA_TEMPLATE_KEYS or request.template_key in GUIDANCE_TEMPLATE_KEYS:
            content = build_visa_support_content(
                template_str=request.template_key,
                user_data=request.user_data,
                medical_data=request.medical_data,
                package_data=request.package_data,
            )
        else:
            from utils.letter_generator import enrich_user_data_with_package
            enrich_user_data_with_package(request.user_data, request.medical_data or {}, request.package_data or {})
            content = fill_template(template, request.user_data)

        if request.target_language and request.target_language.lower() not in {"english", "en"}:
            content = translate_document_text(content, request.target_language)

        return {"html": content}
    except Exception as e:
        print(f"CRITICAL PDF PREVIEW ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF Preview failed: {str(e)}")

@app.post("/api/v1/generate-letter")
async def api_generate_letter(request: GenerateLetterRequest):
    """Generates a PDF letter based on a template and user data."""
    if request.template_key not in LETTER_SKELETONS:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template = LETTER_SKELETONS[request.template_key]
    try:
        if request.template_key in VISA_TEMPLATE_KEYS or request.template_key in GUIDANCE_TEMPLATE_KEYS:
            content = build_visa_support_content(
                template_str=request.template_key,
                user_data=request.user_data,
                medical_data=request.medical_data,
                package_data=request.package_data,
            )
        else:
            from utils.letter_generator import enrich_user_data_with_package
            enrich_user_data_with_package(request.user_data, request.medical_data or {}, request.package_data or {})
            content = fill_template(template, request.user_data)

        if request.target_language and request.target_language.lower() not in {"english", "en"}:
            content = translate_document_text(content, request.target_language)

        print(f"DEBUG: Content to be PDFed: {content}")
        pdf_bytes = generate_pdf(content)
        
        filename = f"{request.template_key}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"CRITICAL PDF ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF Generation failed: {str(e)}")

@app.post("/api/v1/full-pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    origin_country: str = Form("Indonesia"),
    user_origin: Optional[str] = Form(None),
    budget_usd: int = Form(5000),
    currency: str = Form("USD"),
    preferred_month: str = Form("Next Month"),
    preferred_language: str = Form("English"),
    user_priority_preference: str = Form("balanced"),
    manual_override: bool = Form(False),
):
    """
    Step 3: All-in-One. Upload the chart, enter your country and budget, and instantly get packages.
    (This simulates exactly what the App Frontend will do in one click).
    """
    file_location = f"temp_full_{file.filename}"
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
            
        # Extract
        raw_text = extract_raw_text(file_location)
        if "Error" in raw_text:
            raise HTTPException(status_code=400, detail=raw_text)
            
        scrubber = PrivacyScrubber()
        safe_raw_text = scrubber.scrub_raw_text(raw_text)
        privacy_logs = scrubber.get_logs()
        english_text = translate_medical_text(safe_raw_text)
        medical_data = get_concise_json(english_text)
        
        # Match
        packages = orchestrate_packages(
            medical_data=medical_data,
            origin_country=origin_country,
            budget_usd=budget_usd,
            currency=currency,
            preferred_month=preferred_month,
            user_origin=user_origin,
            user_priority_preference=user_priority_preference,
            manual_override=manual_override,
        )
        logistics_data = packages[0]["flight_logistics"] if packages else get_transport_requirements(medical_data, origin=origin_country, destination="Malaysia")
        
        if preferred_language.lower() not in ["english", "en"]:
            for p in packages:
                p["package_reasoning"] = translate_text(p["package_reasoning"], preferred_language)
                if "structured_itinerary" in p and "summary" in p["structured_itinerary"]:
                    p["structured_itinerary"]["summary"] = translate_text(p["structured_itinerary"]["summary"], preferred_language)
                if "clinical_summary" in p and "professional_summary" in p["clinical_summary"]:
                    p["clinical_summary"]["professional_summary"] = translate_text(p["clinical_summary"]["professional_summary"], preferred_language)
        
        return {
            "agent_response": _build_agent_response(packages, manual_override),
            "extracted_medical_data": medical_data,
            "privacy_logs": privacy_logs,
            "logistics": logistics_data,
            "recommended_packages": packages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
