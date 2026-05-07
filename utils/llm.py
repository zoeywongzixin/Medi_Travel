import os
import requests
import json
from typing import Dict, Any, Optional, List


MODEL_FALLBACKS = {
    "gemini-3.0-flash": [
        os.getenv("GEMINI_REASONING_MODEL", "gemini-2.5-flash"),
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
    ],
    "gemini-2.0-flash": [
        os.getenv("GEMINI_PARSER_MODEL", "gemini-2.5-flash"),
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash",
    ],
    "gemini-1.5-flash": [
        os.getenv("GEMINI_TRANSLATION_MODEL", "gemini-2.5-flash-lite"),
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-001",
        "gemini-2.0-flash-lite",
    ],
}


def _model_candidates(model_name: str) -> List[str]:
    candidates = [model_name]
    candidates.extend(MODEL_FALLBACKS.get(model_name, []))

    deduped = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped

def call_gemini(system_prompt: str, user_content: str, model_name: str = "gemini-1.5-flash", tools: Optional[list] = None) -> Dict[str, Any]:
    """
    Centralized routing for Gemini API calls.
    Supports basic text generation and tool calling.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(f"Warning: GEMINI_API_KEY not found. Fallback to mock response for {model_name}.")
        return {"text": "MOCK: Gemini response.", "tool_calls": []}

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_content}]
            }
        ]
    }

    if tools:
        payload["tools"] = [{"function_declarations": tools}]

    headers = {"Content-Type": "application/json"}

    last_error = None
    for candidate_model in _model_candidates(model_name):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={api_key}"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return {"text": "", "tool_calls": []}

            parts = candidates[0].get("content", {}).get("parts", [])

            result_text = ""
            tool_calls = []

            for part in parts:
                if "text" in part:
                    result_text += part["text"]
                if "functionCall" in part:
                    tool_calls.append({
                        "name": part["functionCall"]["name"],
                        "args": part["functionCall"].get("args", {})
                    })

            if candidate_model != model_name:
                print(f"Gemini fallback model in use: requested={model_name}, resolved={candidate_model}")
            return {"text": result_text, "tool_calls": tool_calls}

        except requests.HTTPError as e:
            last_error = e
            status_code = getattr(e.response, "status_code", None)
            response_text = ""
            try:
                response_text = e.response.text[:500]
            except Exception:
                response_text = ""
            if status_code == 404:
                print(f"Gemini model not found for {candidate_model}, trying next fallback...")
                continue
            print(f"Gemini API Error ({candidate_model}): {e}. Response: {response_text}")
            break
        except Exception as e:
            last_error = e
            print(f"Gemini API Error ({candidate_model}): {e}")
            break

    print(f"Gemini API Error: {last_error}")
    return {"text": "", "tool_calls": [], "error": str(last_error) if last_error else "Unknown Gemini error"}

CLARIFICATION_TOOL = {
    "name": "request_clarification",
    "description": "Trigger this tool if the medical chart or the user's data is missing a critical clinical detail required to safely make a hospital or package recommendation.",
    "parameters": {
        "type": "object",
        "properties": {
            "missing_detail_description": {
                "type": "string",
                "description": "A clear description of what is missing. e.g., 'The patient's condition severity is not mentioned.'"
            },
            "clarification_question": {
                "type": "string",
                "description": "The exact question to ask the user to get this detail. e.g., 'Could you please confirm if the lung cancer is at an early or advanced stage?'"
            }
        },
        "required": ["missing_detail_description", "clarification_question"]
    }
}

def check_for_clinical_gaps(medical_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Checks if the medical data is missing critical details. 
    Returns the clarification tool arguments if a gap is found.
    """
    system_prompt = (
        "You are a clinical reviewer. Review the extracted medical data. "
        "If you find that a CRITICAL detail is missing that is absolutely necessary to recommend a hospital or package (like severity for cancer, or age for pediatric conditions), "
        "use the 'request_clarification' tool. If the data is sufficient, just return 'OK'."
    )
    user_content = f"Medical Data:\n{json.dumps(medical_data, indent=2)}"
    
    res = call_gemini(system_prompt, user_content, model_name="gemini-3.0-flash", tools=[CLARIFICATION_TOOL])
    
    for tool_call in res.get("tool_calls", []):
        if tool_call["name"] == "request_clarification":
            return tool_call["args"]
            
    return None
