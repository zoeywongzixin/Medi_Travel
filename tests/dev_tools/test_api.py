import requests
import json
import time

url = "http://localhost:8000/api/v1/match-packages"
payload = {
    "medical_data": {
        "condition": "Cardiology heart surgery",
        "severity": "High",
        "urgency": "Urgent",
        "summary": "Patient needs tertiary cardiac intervention."
    },
    "origin_country": "Indonesia",
    "budget_local": 5000,
    "currency": "USD",
    "preferred_month": "August 2026",
    "preferred_language": "Indonesian"
}

print(f"Sending request to {url}...")
start_time = time.time()
try:
    response = requests.post(url, json=payload, timeout=180) # 3 minutes timeout
    end_time = time.time()
    print(f"Status Code: {response.status_code}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    
    if response.status_code == 200:
        data = response.json()
        print("\n--- Match Results ---")
        for i, pkg in enumerate(data.get("recommended_packages", [])):
            print(f"\nPackage {i+1}:")
            print(f"Type: {pkg.get('package_type')}")
            print(f"Reasoning (Translated): {pkg.get('package_reasoning')}")
            print(f"Itinerary Summary (Translated): {pkg.get('structured_itinerary', {}).get('summary')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
