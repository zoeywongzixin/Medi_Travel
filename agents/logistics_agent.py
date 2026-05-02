import json
import re

import ollama

from utils.schemas import LogisticsRequirements

MODEL_NAME = 'llama3.2:3b'

COUNTRY_HUBS = {
    "brunei": "Bandar Seri Begawan",
    "cambodia": "Phnom Penh",
    "indonesia": "Jakarta",
    "laos": "Vientiane",
    "malaysia": "Kuala Lumpur",
    "myanmar": "Yangon",
    "philippines": "Manila",
    "singapore": "Singapore",
    "thailand": "Bangkok",
    "timor-leste": "Dili",
    "vietnam": "Ho Chi Minh City",
}

HOSPITAL_CITY_HINTS = {
    "kuala lumpur": "Kuala Lumpur",
    "ampang": "Kuala Lumpur",
    "subang": "Kuala Lumpur",
    "selangor": "Kuala Lumpur",
    "sunway": "Kuala Lumpur",
    "gleneagles kuala lumpur": "Kuala Lumpur",
    "penang": "Penang",
    "adventist": "Penang",
    "johor": "Johor Bahru",
    "malacca": "Malacca",
    "melaka": "Malacca",
    "sabah": "Kota Kinabalu",
    "sarawak": "Kuching",
}

ROUTE_ESTIMATES = {
    ("Jakarta", "Kuala Lumpur"): {"cost_usd": 135.0, "duration_hours": 2.2},
    ("Jakarta", "Penang"): {"cost_usd": 165.0, "duration_hours": 2.8},
    ("Manila", "Bangkok"): {"cost_usd": 185.0, "duration_hours": 3.4},
    ("Manila", "Kuala Lumpur"): {"cost_usd": 175.0, "duration_hours": 3.7},
    ("Bangkok", "Kuala Lumpur"): {"cost_usd": 115.0, "duration_hours": 2.1},
    ("Bangkok", "Penang"): {"cost_usd": 105.0, "duration_hours": 1.8},
    ("Singapore", "Kuala Lumpur"): {"cost_usd": 70.0, "duration_hours": 1.1},
    ("Ho Chi Minh City", "Kuala Lumpur"): {"cost_usd": 145.0, "duration_hours": 2.0},
    ("Vientiane", "Kuala Lumpur"): {"cost_usd": 190.0, "duration_hours": 3.0},
    ("Phnom Penh", "Kuala Lumpur"): {"cost_usd": 150.0, "duration_hours": 2.1},
    ("Yangon", "Kuala Lumpur"): {"cost_usd": 155.0, "duration_hours": 2.6},
    ("Bandar Seri Begawan", "Kuala Lumpur"): {"cost_usd": 120.0, "duration_hours": 2.4},
    ("Dili", "Kuala Lumpur"): {"cost_usd": 260.0, "duration_hours": 4.7},
}


def resolve_user_origin_city(user_origin: str) -> str:
    """Accept a country or city-like string and normalize it to an ASEAN hub city."""
    if not user_origin:
        return "Jakarta"

    cleaned = re.sub(r"\s+", " ", str(user_origin)).strip()
    lowered = cleaned.lower()
    if lowered in COUNTRY_HUBS:
        return COUNTRY_HUBS[lowered]

    for country, city in COUNTRY_HUBS.items():
        if country in lowered or city.lower() in lowered:
            return city

    return cleaned.title()


def infer_hospital_city(hospital_location: str) -> str:
    text = (hospital_location or "").strip()
    lowered = text.lower()
    for hint, city in HOSPITAL_CITY_HINTS.items():
        if hint in lowered:
            return city
    return "Kuala Lumpur"


def simulate_route_lookup(hospital_location: str, user_origin: str) -> dict:
    """
    Deterministically simulate an ASEAN route lookup between the user's origin city
    and the matched hospital city.
    """
    origin_city = resolve_user_origin_city(user_origin)
    destination_city = infer_hospital_city(hospital_location)
    route = ROUTE_ESTIMATES.get((origin_city, destination_city))

    if route is None:
        # Light heuristic fallback for uncovered pairs while staying deterministic.
        regional_multiplier = 1.0 if destination_city == "Kuala Lumpur" else 1.15
        base_cost = 140.0 if origin_city != destination_city else 40.0
        duration = 1.2 if origin_city == destination_city else 2.6
        route = {
            "cost_usd": round(base_cost * regional_multiplier, 2),
            "duration_hours": round(duration * regional_multiplier, 1),
        }

    return {
        "origin_city": origin_city,
        "destination_city": destination_city,
        "route": f"{origin_city} to {destination_city}",
        "travel_mode": "Commercial Flight",
        "travel_cost_usd": route["cost_usd"],
        "travel_duration_hours": route["duration_hours"],
        "lookup_type": "simulated_asean_route",
    }

def get_transport_requirements(medical_json, origin="Bangkok", destination="Malaysia"):
    """
    Analyze medical condition and return structured logistics requirements.
    """

    if medical_json.get("condition") == "Extraction Error":
        return LogisticsRequirements(
            mobility_level="Unknown",
            required_equipment=[],
            medical_escort_needed=False,
            search_query=""
        ).dict()

    system_prompt = f"""
        You are a Medical Logistics Expert for ASEAN travel.

        Patient is traveling from {origin} to {destination}.

        You MUST return a JSON object with EXACT keys:
        - mobility_level (Ambulatory, Wheelchair, Stretcher)
        - required_equipment (list of strings)
        - medical_escort_needed (true/false)
        - search_query (string)

        Rules:
        1. If condition includes "metastatic", "bone", or severe trauma → Stretcher
        2. If patient needs monitoring → escort = true
        3. Equipment examples: Oxygen, IV Drip, Monitor

        search_query format:
        "[mobility_level] medical transport {origin} to {destination} with [equipment]"
        """

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            format='json',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': json.dumps(medical_json)}
            ],
            options={'temperature': 0}
        )

        data = json.loads(response['message']['content'])

        # ✅ Enforce schema (VERY IMPORTANT)
        validated = LogisticsRequirements(**data)

        return validated.dict()

    except Exception as e:
        print(f"Logistics Agent Error: {e}")

        return LogisticsRequirements(
            mobility_level="Unknown",
            required_equipment=[],
            medical_escort_needed=False,
            search_query="medical transport ASEAN"
        ).dict()
