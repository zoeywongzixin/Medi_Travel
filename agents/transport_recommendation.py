from typing import Dict

# 🌏 ASEAN knowledge base
TRANSPORT_RULES = {
    "Thailand": {
        "Stretcher": ("Stretcher Flight", "USD 4000 - 8000"),
        "Wheelchair": ("Assisted Commercial Flight", "USD 500 - 1500"),
        "Ambulatory": ("Commercial Flight", "USD 200 - 600")
    },
    "Indonesia": {
        "Stretcher": ("Air Ambulance", "USD 15000 - 30000"),
        "Wheelchair": ("Assisted Commercial Flight", "USD 800 - 2000"),
        "Ambulatory": ("Commercial Flight", "USD 300 - 800")
    },
    "Singapore": {
        "Stretcher": ("Air Ambulance", "USD 8000 - 15000"),
        "Wheelchair": ("Ground Ambulance", "USD 200 - 600"),
        "Ambulatory": ("Car / Taxi", "USD 50 - 150")
    },
    "Vietnam": {
        "Stretcher": ("Air Ambulance", "USD 12000 - 25000"),
        "Wheelchair": ("Assisted Commercial Flight", "USD 600 - 1800"),
        "Ambulatory": ("Commercial Flight", "USD 300 - 900")
    }
}


def recommend_transport(logistics_output: Dict, country: str) -> Dict:
    """
    Core decision engine
    """

    mobility = logistics_output.get("mobility_level", "Ambulatory")
    escort = logistics_output.get("medical_escort_needed", False)
    equipment = logistics_output.get("required_equipment", [])

    if country not in TRANSPORT_RULES:
        return {"error": "Country not supported"}

    transport, cost = TRANSPORT_RULES[country].get(
        mobility,
        ("Commercial Flight", "USD 300 - 1000")
    )

    # 🧠 Reasoning
    reason = f"Patient requires {mobility} transport."

    if escort:
        reason += " Medical escort required for monitoring."

    if equipment:
        reason += f" Equipment needed: {', '.join(equipment)}."

    return {
        "country": country,
        "recommended_transport": transport,
        "estimated_cost": cost,
        "reason": reason
    }


# 🧪 Test
if __name__ == "__main__":
    sample_logistics = {
        "mobility_level": "Stretcher",
        "required_equipment": ["Oxygen"],
        "medical_escort_needed": True
    }

    result = recommend_transport(sample_logistics, "Thailand")

    import json
    print(json.dumps(result, indent=4))