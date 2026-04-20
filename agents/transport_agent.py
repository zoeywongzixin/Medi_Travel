import asyncio
import json
import ollama
from pydantic import BaseModel, Field
from typing import List
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# ✅ Schema
class TransportOption(BaseModel):
    provider_name: str
    service_type: str
    price_estimate: str
    currency: str
    suitability_note: str

PROVIDER_URLS = [
    "https://www.medical-air-service.com/",
    "https://www.air-ambulance.com/"
]

async def get_real_time_transport(context: dict):
    mobility = context.get("mobility_level", "Stretcher")
    equipment = ", ".join(context.get("required_equipment", []))
    
    print(f"--- 🕵️ Transport Agent: Enriching data for {mobility} (CPU Mode) ---")

    browser_config = BrowserConfig(headless=True)
    # We use a simple run config WITHOUT extraction to get the text fast
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    all_markdown_content = ""

    # 1. QUICK SCRAPE (Get the data and get out)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in PROVIDER_URLS:
            try:
                print(f"--- 🔍 Fetching {url} ---")
                result = await crawler.arun(url=url, config=run_config)
                if result.success:
                    scraped_text = result.markdown.raw_markdown[:2000] 
                    all_markdown_content += f"\nSource {url}:\n" + scraped_text
            except Exception as e:
                print(f"⚠️ Could not fetch {url}: {e}")

    # 2. LOCAL AI ANALYSIS (Outside the browser session)
    if all_markdown_content:
        print("--- 🧠 CPU is analyzing scraped content... ---")
        try:
            response = ollama.chat(
                model='llama3.2:3b',
                format='json',
                messages=[
                    {
                        'role': 'system', 
                        'content': (
                            "You are a Data Extraction Agent. Extract a list of medical transport providers from the text. "
                            "Each item MUST have: 'provider_name', 'service_type', 'price_estimate', 'currency', and 'suitability_note'. "
                            "If no price is found, use 'Contact for Quote'. "
                            "ONLY return a JSON list of objects."
                        )
                    },
                    {
                        'role': 'user', 
                        'content': f"Scraped Content:\n{all_markdown_content}"
                    }
                ],
                options={
                    'temperature': 0, 
                    'num_ctx': 3000,   # Keep it small for your CPU
                    'top_p': 0.1       # Force the model to be very predictable
                }
            )
            data = json.loads(response['message']['content'])
            return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"🧠 AI Analysis failed: {e}")

    # ✅ Fallback for the UM Technothon Demo
    print("--- 🔄 Returning vetted regional providers (Fallback) ---")
    return [
        {
            "provider_name": "Asia Air Ambulance",
            "service_type": "Commercial Stretcher",
            "price_estimate": "USD 4,800 - 9,500",
            "currency": "USD",
            "suitability_note": "Optimized for Bangkok-Malaysia transfers."
        }
    ]