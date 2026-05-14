"""User-safe explanations of how the system processes data (no raw PHI)."""

from typing import Any, Dict, List


def extract_transparency(privacy_log_count: int) -> Dict[str, Any]:
    return {
        "title": "How your document was processed",
        "subtitle": "Each step runs on structured rules and models—not random guessing.",
        "steps": [
            {
                "id": "ocr",
                "label": "Text extraction",
                "detail": "We read text from your file using OCR or PDF parsing so the rest of the pipeline can work from words, not pixels.",
            },
            {
                "id": "privacy",
                "label": "Privacy scrubbing",
                "detail": (
                    f"We mask or remove identifiers where possible ({privacy_log_count} privacy event(s) logged)."
                    if privacy_log_count
                    else "We mask or remove identifiers where possible before any cloud model sees the text."
                ),
            },
            {
                "id": "translate",
                "label": "Normalize to English",
                "detail": "Non-English text is translated so the structured parser and specialist search use one consistent language.",
            },
            {
                "id": "parse",
                "label": "Structured medical summary",
                "detail": "A model turns the narrative into fields (condition, urgency, etc.) that drive matching—not free-form guesses.",
            },
        ],
    }


def hospital_match_transparency(medical_data: Dict[str, Any]) -> Dict[str, Any]:
    from utils.medical_specialty import build_case_profile

    profile = build_case_profile(medical_data)
    groups = sorted(profile.get("groups") or [])
    specialties = list(profile.get("specialties") or [])

    return {
        "title": "How specialist matches are chosen",
        "subtitle": "Rankings combine database search, keyword signals, and scoring—not a single random draw.",
        "case_signals": {
            "condition": (profile.get("condition") or "").strip() or None,
            "inferred_specialties": specialties,
            "specialty_groups_for_filtering": groups,
            "urgency": profile.get("urgency"),
            "severity": profile.get("severity"),
        },
        "algorithm_steps": [
            "Vector search over a Malaysia doctor index (embeddings from specialist profiles).",
            "Keyword overlap between your case text and each profile to reinforce obvious term matches.",
            "Reciprocal Rank Fusion (RRF) merges semantic and keyword rankings fairly.",
            "A specialty-group gate drops candidates that do not fit the inferred clinical group.",
            "Rule-based scoring rewards registration metadata, group overlap, and list position.",
            "When configured, a small LLM (Gemini) re-orders the top few candidates using only structured fields—still grounded in the same shortlist.",
        ],
        "data_sources": ["ChromaDB collection `malaysia_doctors`", "Structured fields from your uploaded summary"],
    }


def flight_match_transparency(
    origin_country: str,
    logistics_data: Dict[str, Any],
    flight_bundle: Dict[str, Any],
) -> Dict[str, Any]:
    mobility = logistics_data.get("mobility_level", "Ambulatory")
    adults = logistics_data.get("adults", 1)
    rec = flight_bundle.get("recommendation", "")
    notes = flight_bundle.get("notes", "")
    sources = []
    for opt in flight_bundle.get("options") or []:
        src = opt.get("source")
        if src and src not in sources:
            sources.append(src)

    return {
        "title": "How travel options are built",
        "subtitle": "Logistics constraints decide the mode; prices come from live search or transparent fallbacks.",
        "inputs": {
            "origin": origin_country,
            "mobility_level": mobility,
            "travelers": adults,
        },
        "algorithm_steps": [
            "We infer mobility and escort needs from your case summary.",
            "If a stretcher is required, we pivot to medical charter / air ambulance style results instead of economy seats.",
            "Otherwise we query commercial routes (live Google Flights via SerpApi when enabled, or clearly labeled mock fares).",
            "Each option keeps its `source` tag so you can see whether a row is live, cached, or a demo estimate.",
        ],
        "engine_note": rec or notes or None,
        "option_sources": sources or ["mock_fallback"],
    }


def charity_match_transparency(origin_country: str, condition: str) -> Dict[str, Any]:
    return {
        "title": "How financial aid options are matched",
        "subtitle": "Charities are retrieved from your indexed database and explained in plain language.",
        "inputs": {"origin_country": origin_country, "condition_focus": condition or None},
        "algorithm_steps": [
            "Search the charities vector index using your condition and context.",
            "Prefer organizations whose stated scope aligns with the case.",
            "Optional web lookup for official website links when an API key is configured.",
        ],
        "data_sources": ["ChromaDB collection `charities`", "Structured condition from your case"],
    }
