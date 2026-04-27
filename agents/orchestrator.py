from typing import Dict, List
from agents.medical_agent import match_hospitals
from agents.flight_agent import get_flight_options
from agents.charity_agent import match_charities
import ollama
import os

def orchestrate_packages(medical_data: Dict, logistics_data: Dict, origin_country: str, budget_usd: int) -> List[Dict]:
    """
    Combines layers 1, 2, and 3 to create holistic medical travel packages.
    """
    print(f"\n--- 🚀 Starting Orchestration for {origin_country} ---")
    
    # Layer 1
    print("[Orchestrator] Step 1: Matching Hospitals & Reranking Specialists (AI judge)...")
    hospitals = match_hospitals(medical_data)
    
    # Layer 2
    print("[Orchestrator] Step 2: Fetching Flight Options...")
    logistics = get_flight_options(logistics_data, origin_country)
    
    # Layer 3
    print("[Orchestrator] Step 3: Matching Financial Aid...")
    charities = match_charities(medical_data, origin_country)
    
    print(f"[Orchestrator] Step 4: Generating {len(hospitals)} Personalized Package Descriptions (AI reasoning)...")
    packages = []
    
    # We will generate up to 3 packages by combining these options
    for i, doc in enumerate(hospitals):
        print(f"  > Creating Package {i+1} for {doc.get('hospital')}...")
        
        # Determine top charity name
        charity_names = [c['name'] for c in charities]
        charity_text = f"Charities: {', '.join(charity_names)}" if charity_names else "No specific charities"
        
        prompt = (
            f"Context: Travel coordination for an international visitor to Malaysia.\n"
            f"Destination: {doc.get('hospital')}. Origin: {origin_country}. Budget: ${budget_usd} USD.\n"
            f"Specialist: {doc.get('name')} ({doc.get('specialty')})\n"
            f"Transport: {logistics.get('recommendation')}\n"
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
            
        package = {
            "package_id": f"PKG_{i+1}",
            "package_reasoning": package_reasoning,
            "specialist": doc,
            "flight_logistics": logistics,
            "recommended_charities": charities
        }
        packages.append(package)
        
    print("--- ✅ Orchestration Complete ---\n")
    return packages
