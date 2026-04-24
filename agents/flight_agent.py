import os
from typing import Dict, List
from amadeus import Client, ResponseError
from dotenv import load_dotenv

load_dotenv()

AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")

def get_amadeus_client():
    if not AMADEUS_API_KEY or not AMADEUS_API_SECRET:
        return None
    try:
        return Client(
            client_id=AMADEUS_API_KEY,
            client_secret=AMADEUS_API_SECRET
        )
    except Exception as e:
        print(f"Amadeus Client Error: {e}")
        return None

def find_flights(origin_country: str, destination_airport: str = "KUL", date: str = "2024-12-01") -> List[Dict]:
    """
    Uses Amadeus Flight Offers Search API to find flights.
    Mocks the response if Amadeus is not configured or fails.
    """
    # Simple mapping for ASEAN origins to IATA codes (for demo purposes)
    iata_mapping = {
        "thailand": "BKK",
        "indonesia": "CGK",
        "vietnam": "SGN",
        "singapore": "SIN",
        "philippines": "MNL"
    }
    
    origin_airport = iata_mapping.get(origin_country.lower(), "BKK")
    
    amadeus = get_amadeus_client()
    
    if amadeus:
        try:
            response = amadeus.shopping.flight_offers_search.get(
                originLocationCode=origin_airport,
                destinationLocationCode=destination_airport,
                departureDate=date,
                adults=1,
                max=3
            )
            
            flights = []
            for offer in response.data:
                price = offer['price']['total']
                currency = offer['price']['currency']
                airline = offer['validatingAirlineCodes'][0] if offer['validatingAirlineCodes'] else "Unknown"
                flights.append({
                    "airline": airline,
                    "price": f"{price} {currency}",
                    "type": "Commercial Flight (API)"
                })
            return flights
        except ResponseError as error:
            print(f"Amadeus API Error: {error}")
            # Fallback to mock if API fails
            pass
            
    # Mock fallback
    print("⚠️ Using mock flight data (Amadeus API not configured or failed)")
    return [
        {
            "airline": "AirAsia (Mock)",
            "price": "120 USD",
            "type": "Commercial Flight"
        },
        {
            "airline": "Malaysia Airlines (Mock)",
            "price": "250 USD",
            "type": "Commercial Flight"
        }
    ]

def get_flight_options(logistics_data: Dict, origin_country: str) -> Dict:
    """
    Analyzes logistics requirements and fetches appropriate flights.
    """
    mobility = logistics_data.get("mobility_level", "Ambulatory")
    
    # If they need a stretcher, commercial flights from Amadeus aren't sufficient.
    if mobility == "Stretcher":
        return {
            "recommendation": "Air Ambulance Required",
            "options": [
                {
                    "provider": "Asia Air Ambulance",
                    "price": "Estimated USD 5,000 - 10,000",
                    "type": "Private Medical Charter"
                }
            ],
            "notes": "Patient requires stretcher. Standard commercial flights are not applicable."
        }
        
    flights = find_flights(origin_country)
    
    return {
        "recommendation": f"Commercial Flight suitable for {mobility} passengers",
        "options": flights,
        "notes": "Wheelchair assistance can be requested at the airport." if mobility == "Wheelchair" else "Standard travel."
    }
