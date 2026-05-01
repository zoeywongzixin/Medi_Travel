from typing import Dict, Tuple

PROCEDURE_HEURISTICS = {
    "knee replacement": {"cost_myr": 33400, "cost_usd": 7500, "stay_days": 5, "type": "Total Knee Replacement"},
    "angiogram": {"cost_myr": 11700, "cost_usd": 2600, "stay_days": 2, "type": "Angiogram (Heart Check)"},
    "heart": {"cost_myr": 11700, "cost_usd": 2600, "stay_days": 2, "type": "Angiogram (Heart Check)"},
    "appendix": {"cost_myr": 20700, "cost_usd": 4700, "stay_days": 3, "type": "Appendix Removal"},
    "gallbladder": {"cost_myr": 21300, "cost_usd": 4800, "stay_days": 3, "type": "Gallbladder Removal"},
    "cataract": {"cost_myr": 8400, "cost_usd": 1900, "stay_days": 0, "type": "Cataract Surgery"},
    "fibroid": {"cost_myr": 24600, "cost_usd": 5500, "stay_days": 4, "type": "Fibroid Removal"},
    "screening": {"cost_myr": 1500, "cost_usd": 300, "stay_days": 0, "type": "Health Screening (VIP)"},
}

def estimate_procedure_details(condition: str) -> Dict:
    """
    Given a medical condition, estimate the procedure cost and stay duration.
    Returns: { "procedure_name": str, "cost_usd": float, "stay_days": int }
    """
    condition_lower = condition.lower()
    for key, data in PROCEDURE_HEURISTICS.items():
        if key in condition_lower:
            return {
                "procedure_name": data["type"],
                "cost_usd": data["cost_usd"],
                "stay_days": data["stay_days"]
            }
    
    # Default fallback
    return {
        "procedure_name": "General Medical Treatment",
        "cost_usd": 5000.0,
        "stay_days": 3
    }

def calculate_total_stay(medical_stay_days: int) -> int:
    """
    Total Stay = Pre-op (1-2 days) + Recovery/Observation (medical_stay_days)
    """
    pre_op = 2
    return pre_op + medical_stay_days
