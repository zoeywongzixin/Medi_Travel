import os
import re
from typing import Dict, List
import serpapi
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DISABLE_LIVE_FLIGHTS_ENV = "DISABLE_LIVE_FLIGHTS"


def live_flight_search_enabled() -> bool:
    return os.getenv(DISABLE_LIVE_FLIGHTS_ENV, "").lower() not in ("1", "true", "yes")

def get_serpapi_search(params):
    if not live_flight_search_enabled():
        return None
    if not SERPAPI_KEY:
        return None
    try:
        # Use the standard GoogleSearch class from the serpapi library
        from serpapi import GoogleSearch
        params["api_key"] = SERPAPI_KEY
        search = GoogleSearch(params)
        return search.get_dict()
    except Exception as e:
        print(f"SerpApi Error: {e}")
        return None

def search_google(query: str):
    """General Google Search via SerpApi to find specialized logistics."""
    params = {
        "engine": "google",
        "q": query,
        "location": "Malaysia",
        "hl": "en",
        "gl": "my",
        "num": 3
    }
    results = get_serpapi_search(params)
    if not results:
        return []
    
    organic = results.get("organic_results", [])
    return [{"title": r.get("title"), "link": r.get("link"), "snippet": r.get("snippet")} for r in organic]


def _parse_price_to_usd(price_value) -> float:
    if isinstance(price_value, (int, float)):
        return float(price_value)
    text = str(price_value or "")
    match = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(",", ""))
    return float(match.group(1)) if match else 0.0


def _parse_duration_hours(duration_value) -> float:
    if isinstance(duration_value, (int, float)):
        return round(float(duration_value) / 60.0, 1) if float(duration_value) > 24 else round(float(duration_value), 1)
    text = str(duration_value or "").lower()
    hours = 0.0
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*h", text)
    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*m", text)
    if hour_match:
        hours += float(hour_match.group(1))
    if minute_match:
        hours += float(minute_match.group(1)) / 60.0
    if hours:
        return round(hours, 1)
    numeric = re.search(r"(\d+(?:\.\d+)?)", text)
    return round(float(numeric.group(1)), 1) if numeric else 0.0

def find_flights(origin_country: str, destination_airport: str = "KUL", date: str = None, adults: int = 1, max_offers: int = 3) -> List[Dict]:
    """
    Uses SerpApi Google Flights to find real flights.
    Mocks the response if SerpApi is not configured or fails.
    """
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        
    # Mapping for all 11 ASEAN countries to IATA codes
    iata_mapping = {
        "brunei": "BWN",
        "cambodia": "PNH",
        "indonesia": "CGK",
        "laos": "VTE",
        "malaysia": "KUL",
        "myanmar": "RGN",
        "philippines": "MNL",
        "singapore": "SIN",
        "thailand": "BKK",
        "timor-leste": "DIL",
        "vietnam": "SGN"
    }
    
    origin_airport = iata_mapping.get(origin_country.lower(), "BKK")
    
    params = {
        "engine": "google_flights",
        "departure_id": origin_airport,
        "arrival_id": destination_airport,
        "outbound_date": date,
        "currency": "USD",
        "hl": "en",
        "adults": adults,
        "type": "2" # One Way
    }
    
    search = get_serpapi_search(params)
    
    if search:
        try:
            # Official client.search() returns a dict-like object (SerpResults)
            response = search
            
            best_flights = response.get("best_flights", [])
            other_flights = response.get("other_flights", [])
            all_offers = best_flights + other_flights
            
            flights = []
            for offer in all_offers[:max_offers]:
                price = offer.get('price', 'Unknown')
                flights_info = offer.get('flights', [])
                
                airline = "Unknown"
                departing_at = "Unknown"
                arriving_at = "Unknown"
                
                if flights_info:
                    airline = flights_info[0].get('airline', 'Unknown')
                    departing_at = flights_info[0].get("departure_airport", {}).get("time", "Unknown")
                    # Use last segment for arrival if there are connections
                    arriving_at = flights_info[-1].get("arrival_airport", {}).get("time", "Unknown")

                duration_value = offer.get("total_duration") or offer.get("duration") or offer.get("carbon_emissions", {}).get("duration")
                travel_cost_usd = _parse_price_to_usd(price)
                travel_duration_hours = _parse_duration_hours(duration_value)
                route = f"{origin_airport} to {destination_airport}"
                
                price_str = f"{travel_cost_usd:.0f} USD" if travel_cost_usd else (f"{price} USD" if isinstance(price, (int, float)) else str(price))
                
                flights.append({
                    "airline": airline,
                    "price": price_str,
                    "departure": departing_at,
                    "arrival": arriving_at,
                    "type": "Commercial Flight (Google Flights)",
                    "travel_mode": "Commercial Flight",
                    "travel_cost_usd": travel_cost_usd,
                    "travel_duration_hours": travel_duration_hours,
                    "route": route,
                    "source": "serpapi_google_flights",
                })
            
            if flights:
                return flights
        except Exception as error:
            print(f"SerpApi Error: {error}")
            # Fallback to mock if API fails
            pass
            
    # Mock fallback
    print("Using mock flight data (live flight search disabled, unavailable, or failed)")
    return [
        {
            "airline": "AirAsia (Mock)",
            "price": "120 USD",
            "type": "Commercial Flight",
            "travel_mode": "Commercial Flight",
            "travel_cost_usd": 120.0,
            "travel_duration_hours": 2.3,
            "route": f"{origin_airport} to {destination_airport}",
            "source": "mock_fallback",
        },
        {
            "airline": "Malaysia Airlines (Mock)",
            "price": "250 USD",
            "type": "Commercial Flight",
            "travel_mode": "Commercial Flight",
            "travel_cost_usd": 250.0,
            "travel_duration_hours": 2.0,
            "route": f"{origin_airport} to {destination_airport}",
            "source": "mock_fallback",
        }
    ]

def get_flight_options(logistics_data: Dict, origin_country: str, destination_airport: str = "KUL") -> Dict:
    """
    Analyzes logistics requirements and fetches appropriate flights.
    """
    mobility = logistics_data.get("mobility_level", "Ambulatory")
    date = logistics_data.get("departure_date")
    adults = logistics_data.get("adults", 1)
    max_offers = logistics_data.get("max_offers", 3)
    
    # If they need a stretcher, standard commercial flights are not sufficient.
    if mobility == "Stretcher":
        query = f"Air Ambulance medical charter {origin_country} to Malaysia"
        charter_providers = search_google(query)
        
        email_body = (
            f"Dear Air Ambulance Provider,\n\n"
            f"We are requesting a quote for a private medical charter for a patient requiring a stretcher.\n\n"
            f"Origin: {origin_country}\n"
            f"Mobility Level: Stretcher\n"
            f"Companions: {adults - 1}\n\n"
            f"Please provide an estimated quote and availability.\n\n"
            f"Thank you."
        )
        
        options = []
        if charter_providers:
            for p in charter_providers:
                options.append({
                    "provider": p['title'],
                    "link": p['link'],
                    "price": "Contact for Quote",
                    "type": "Private Medical Charter",
                    "snippet": p['snippet']
                })
        else:
            options.append({
                "provider": "Air Ambulance Operator",
                "price": "Contact for Quote",
                "type": "Private Medical Charter",
                "email_draft": {
                    "to": "",
                    "subject": f"Medical Charter Request - Stretcher Patient from {origin_country}",
                    "body": email_body
                }
            })

        return {
            "recommendation": "Air Ambulance Required",
            "options": options,
            "notes": "Patient requires stretcher. Standard commercial flights are not applicable. We have found several specialized medical flight operators for you."
        }
        
    flights = find_flights(
        origin_country=origin_country,
        destination_airport=destination_airport,
        date=date,
        adults=adults,
        max_offers=max_offers
    )

    # For Wheelchair, we also search for specialized ground logistics in Malaysia
    ground_logistics = []
    if mobility == "Wheelchair":
        ground_query = "Wheelchair accessible van rental airport transfer Kuala Lumpur"
        ground_logistics = search_google(ground_query)

    return {
        "recommendation": f"Commercial Flight suitable for {mobility} passengers",
        "options": flights,
        "ground_transport": ground_logistics,
        "notes": "Wheelchair assistance can be requested at the airport." if mobility == "Wheelchair" else "Standard travel."
    }
