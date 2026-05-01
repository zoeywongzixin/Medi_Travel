import os
import requests
from dotenv import load_dotenv

load_dotenv()

CURRENCY_FREAKS_API_KEY = os.getenv("CURRENCY_FREAKS_API_KEY")

# Fallback conversion rates (1 USD to X)
FALLBACK_RATES = {
    "MYR": 4.7,
    "IDR": 15500.0,
    "SGD": 1.35,
    "THB": 36.5,
    "VND": 24500.0,
    "PHP": 56.0
}

def get_conversion_rate(target_currency: str, base_currency: str = "USD") -> float:
    """
    Gets the conversion rate from base_currency to target_currency.
    Uses CurrencyFreaks API if available, else fallback rates.
    """
    if target_currency == base_currency:
        return 1.0

    if CURRENCY_FREAKS_API_KEY:
        try:
            url = f"https://api.currencyfreaks.com/v2.0/rates/latest?apikey={CURRENCY_FREAKS_API_KEY}&symbols={target_currency}&base={base_currency}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "rates" in data and target_currency in data["rates"]:
                    return float(data["rates"][target_currency])
        except Exception as e:
            print(f"CurrencyFreaks Error: {e}")
            pass
            
    # Fallback logic
    if base_currency == "USD" and target_currency in FALLBACK_RATES:
        return FALLBACK_RATES[target_currency]
    
    return 1.0 # Default if unable to convert

def convert_usd_to(amount_usd: float, target_currency: str) -> float:
    rate = get_conversion_rate(target_currency, "USD")
    return amount_usd * rate

def convert_to_usd(amount: float, from_currency: str) -> float:
    if from_currency == "USD":
        return amount
    rate = get_conversion_rate(from_currency, "USD")
    if rate <= 0:
        return amount
    return amount / rate

def get_currency_for_country(country_name: str) -> str:
    mapping = {
        "malaysia": "MYR",
        "indonesia": "IDR",
        "singapore": "SGD",
        "thailand": "THB",
        "vietnam": "VND",
        "philippines": "PHP",
        "cambodia": "KHR",
        "laos": "LAK",
        "myanmar": "MMK",
        "brunei": "BND"
    }
    return mapping.get(country_name.lower(), "USD")
