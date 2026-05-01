from typing import Dict, List
import os
import ollama
from agents.medical_agent import match_hospitals, generate_clinical_summary
from agents.flight_agent import get_flight_options
from agents.charity_agent import match_charities
from agents.logistics_agent import get_transport_requirements
from utils.date_calculator import calculate_travel_dates

def _get_flight_price_estimate(logistics_data: Dict) -> float:
    """Extract rough flight price from logistics data for gap calculation."""
    options = logistics_data.get("options", [])
    if not options:
        return 500.0 # Default fallback
    
    price_str = options[0].get("price", "500")
    try:
        # Extract numbers
        import re
        numbers = re.findall(r'\d+', str(price_str))
        if numbers:
            return float("".join(numbers))
    except Exception:
        pass
    return 500.0

def orchestrate_packages(medical_data: Dict, origin_country: str, budget_usd: float, currency: str, preferred_month: str) -> List[Dict]:
    """
    Combines layers 1, 2, and 3 to create holistic medical travel packages.
    Generates 3 distinct packages: Elite, Optimized (Budget), and Proximity.
    """
    from utils.currency import convert_usd_to
    import copy
    print(f"\n--- 🚀 Starting Lead Orchestrator for {origin_country} ---")
    
    # ---------------------------------------------------------
    # PHASE 1: Parallel Agent Delegation
    # ---------------------------------------------------------
    
    # Clinical Agent
    print("[Orchestrator] Clinical Agent: Estimating duration and generating summary...")
    clinical_summary = generate_clinical_summary(medical_data)
    hospitals = match_hospitals(medical_data)
    
    if not hospitals:
        return []

    # Logistics Agent
    print("[Orchestrator] Logistics Agent: Calculating dates and transport...")
    travel_dates = calculate_travel_dates(preferred_month, clinical_summary["total_stay_days"])
    transport_reqs = get_transport_requirements(medical_data, origin=origin_country, destination="Malaysia")
    logistics = get_flight_options(transport_reqs, origin_country)
    
    # Financial Agent
    print("[Orchestrator] Financial Agent: Comparing budget and identifying charities...")
    flight_estimate = _get_flight_price_estimate(logistics)
    total_estimated_cost = clinical_summary["estimated_cost_usd"] + flight_estimate
    
    charities = match_charities(
        medical_data, 
        origin_country, 
        budget_usd=budget_usd, 
        estimated_cost_usd=total_estimated_cost
    )

    # ---------------------------------------------------------
    # PHASE 2: Output Generation (The 3 Packages)
    # ---------------------------------------------------------
    print(f"[Orchestrator] Generating packages with currency: {currency}")
    print(f"[Orchestrator] Base clinical cost: ${clinical_summary['estimated_cost_usd']}")
    packages = []
    
    # Package 1: The Elite
    # Best-in-class hospital (index 0), most direct logistics
    elite_hospital = hospitals[0] if len(hospitals) > 0 else None
    if elite_hospital:
        elite_summary = copy.deepcopy(clinical_summary)
        base_cost = elite_summary["estimated_cost_usd"]
        elite_cost_usd = base_cost * 1.5
        elite_cost_local = convert_usd_to(elite_cost_usd, currency)
        elite_summary["estimated_cost_usd"] = elite_cost_usd
        elite_summary["estimated_cost_local"] = elite_cost_local
        elite_summary["estimated_cost_formatted"] = f"${elite_cost_usd:,.0f} USD ({currency} {elite_cost_local:,.0f})"
        print(f"  - Elite cost: {elite_summary['estimated_cost_formatted']}")
        
        packages.append({
            "package_id": "PKG_ELITE",
            "package_type": "The Elite",
            "package_reasoning": "Best-in-class hospital matched with the most direct logistics for premium care.",
            "specialist": elite_hospital,
            "flight_logistics": logistics,
            "travel_dates": travel_dates,
            "clinical_summary": elite_summary,
            "charity": None
        })

    # Package 2: The Optimized (Budget)
    # Solid hospital + Charity Subsidy
    budget_hospital = hospitals[1] if len(hospitals) > 1 else elite_hospital
    if budget_hospital:
        opt_summary = copy.deepcopy(clinical_summary)
        base_cost = opt_summary["estimated_cost_usd"]
        opt_cost_usd = base_cost * 1.0
        opt_cost_local = convert_usd_to(opt_cost_usd, currency)
        opt_summary["estimated_cost_usd"] = opt_cost_usd
        opt_summary["estimated_cost_local"] = opt_cost_local
        opt_summary["estimated_cost_formatted"] = f"${opt_cost_usd:,.0f} USD ({currency} {opt_cost_local:,.0f})"
        
        packages.append({
            "package_id": "PKG_OPTIMIZED",
            "package_type": "The Optimized",
            "package_reasoning": "A solid hospital choice paired with a specific identified Charity Subsidy to stay under budget.",
            "specialist": budget_hospital,
            "flight_logistics": logistics,
            "travel_dates": travel_dates,
            "clinical_summary": opt_summary,
            "charity": charities[0] if charities else None
        })

    # Package 3: The Proximity
    # Most logistically convenient (could use third hospital or specific logistics logic)
    proximity_hospital = hospitals[2] if len(hospitals) > 2 else budget_hospital
    if proximity_hospital:
        prox_summary = copy.deepcopy(clinical_summary)
        base_cost = prox_summary["estimated_cost_usd"]
        prox_cost_usd = base_cost * 1.15
        prox_cost_local = convert_usd_to(prox_cost_usd, currency)
        prox_summary["estimated_cost_usd"] = prox_cost_usd
        prox_summary["estimated_cost_local"] = prox_cost_local
        prox_summary["estimated_cost_formatted"] = f"${prox_cost_usd:,.0f} USD ({currency} {prox_cost_local:,.0f})"
        
        packages.append({
            "package_id": "PKG_PROXIMITY",
            "package_type": "The Proximity",
            "package_reasoning": "The most logistically convenient option optimized for ease of travel and access.",
            "specialist": proximity_hospital,
            "flight_logistics": logistics,
            "travel_dates": travel_dates,
            "clinical_summary": prox_summary,
            "charity": None
        })

    print("--- ✅ Orchestration Complete ---\n")
    return packages

def generate_single_package(hospital: Dict, logistics_data: Dict, flight: Dict, charity: Dict, origin_country: str, budget_usd: int, travel_dates: dict, clinical_summary: dict) -> Dict:
    """
    Generates a single personalized package from user-selected components.
    """
    charity_text = f"Charities: {charity['name']}" if charity else "No specific charities"
    transport_method = logistics_data.get('recommendation', 'Flight')
    flight_details = f"{flight.get('airline', 'Flight')} - {flight.get('price', 'Unknown price')}" if flight else "No flight selected"
    
    prompt = (
        f"Context: Travel coordination for an international visitor to Malaysia.\n"
        f"Destination: {hospital.get('hospital', 'Unknown Hospital')}. Origin: {origin_country}. Budget: ${budget_usd} USD.\n"
        f"Specialist: {hospital.get('name')} ({hospital.get('specialty')})\n"
        f"Transport: {transport_method}. Selected Flight: {flight_details}\n"
        f"- {charity_text}\n\n"
        f"Write two sentences for a travel brochure highlighting why this coordination of hospital reputation and logistics is a great value option."
    )
    
    try:
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        client = ollama.Client(host=ollama_host)
        response = client.chat(
            model='llama3.2:3b',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.2, 'num_ctx': 800}
        )
        package_reasoning = response.message.content.strip()
    except Exception as e:
        print(f"  [!] Package reasoning failed: {e}")
        package_reasoning = "This package combines top medical care, suitable logistics, and available financial aid."
        
    return {
        "package_id": "PKG_CUSTOM",
        "package_reasoning": package_reasoning,
        "specialist": hospital,
        "flight_logistics": logistics_data,
        "selected_flight": flight,
        "recommended_charity": charity,
        "travel_dates": travel_dates,
        "clinical_summary": clinical_summary
    }
