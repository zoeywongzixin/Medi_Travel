import asyncio
from agents.orchestrator import orchestrate_packages

# Dummy medical data
medical_data = {
    "condition": "Total Knee Replacement",
    "severity": "Moderate",
    "urgency": "Stable",
    "summary": "Patient requires knee replacement surgery due to severe osteoarthritis."
}

def run_test():
    packages = orchestrate_packages(
        medical_data=medical_data,
        origin_country="Indonesia",
        budget_usd=3000,
        preferred_month="August 2026"
    )
    
    print("\n\nTEST RESULTS:")
    print("Number of packages:", len(packages))
    for p in packages:
        print(f"[{p['package_type']}] - {p['specialist']['hospital']}")
        print(f"  Reasoning: {p['package_reasoning']}")
        print(f"  Dates: {p['travel_dates']}")
        print(f"  Cost Est: ${p['clinical_summary']['estimated_cost_usd']}")

if __name__ == "__main__":
    run_test()
