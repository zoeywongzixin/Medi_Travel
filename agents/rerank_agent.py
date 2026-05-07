import json
import os
import re
from typing import Dict, List

from utils.llm import call_gemini


def llm_rerank(candidates: List[Dict], medical_data: Dict, top_n: int = 3) -> List[Dict]:
    """
    Use Gemini 3.0 Flash as a judge to rerank up to 5 pre-vetted doctor candidates.
    Fallback: returns candidates as-is (already in scored order) if Gemini fails.
    """
    if not candidates:
        return []

    if len(candidates) <= top_n:
        return candidates[:top_n]

    diagnosis = medical_data.get("condition", "unknown condition")
    severity = medical_data.get("severity", "Unknown")
    urgency = medical_data.get("urgency", "Unknown")

    candidate_summaries = []
    for c in candidates:
        candidate_summaries.append({
            "id": c.get("id", ""),
            "name": c.get("name", "Unknown"),
            "specialty": c.get("specialty", "Unknown"),
            "specialty_tags": c.get("specialty_tags", ""),
            "hospital": c.get("hospital", "Unknown"),
            "tier": c.get("tier", "Unknown"),
            "registered": bool(
                c.get("full_registration_number") or c.get("provisional_registration_number")
            ),
        })

    system_prompt = (
        "You are a highly experienced medical coordinator specializing in medical tourism in Malaysia. "
        "Your goal is to rank 5 doctor candidates by clinical suitability for a patient's specific condition. "
        "Prioritize based on:\n"
        "1. Sub-specialty match: Does the doctor's specific tags align with the patient's condition details?\n"
        "2. Hospital Tier: For Critical/High severity, prioritize Tier 1 hospitals (advanced equipment).\n"
        "3. Registration status: Valid registration is mandatory.\n"
        "4. Specialty Group: Ensure the doctor belongs to the correct clinical group (Oncology, Cardiology, etc.).\n\n"
        "Return ONLY a valid JSON array of doctor IDs in order from most to least suitable. "
        "Do NOT include any explanation or extra text."
    )

    user_prompt = (
        f"Patient diagnosis: {diagnosis}\n"
        f"Severity: {severity} | Urgency: {urgency}\n"
        f"Age Group: {medical_data.get('age_group', 'Not specified')}\n\n"
        f"Compare these {len(candidates)} doctors and return the top {top_n} as a JSON array of IDs "
        f"(most suitable first). Focus on the sub-specialty tags vs patient diagnosis:\n\n"
        f"{json.dumps(candidate_summaries, indent=2)}"
    )

    try:
        print(f"  [RerankAgent] Calling Gemini to rerank {len(candidates)} candidates for '{diagnosis}'...")
        res = call_gemini(system_prompt, user_prompt, model_name="gemini-3.0-flash")
        raw_content = res.get("text", "").strip()

        # Extract a JSON array from the response (handle model wrapping it in an object)
        ranked_ids = _parse_ranked_ids(raw_content)

        if not ranked_ids:
            raise ValueError(f"LLM returned no valid IDs. Raw: {raw_content[:200]}")

        # Re-order candidates according to LLM ranking
        id_to_candidate = {c.get("id"): c for c in candidates}
        reranked = [id_to_candidate[rid] for rid in ranked_ids if rid in id_to_candidate]

        # Append any candidates the LLM missed (shouldn't happen, but safety net)
        reranked_ids_set = {c.get("id") for c in reranked}
        for c in candidates:
            if c.get("id") not in reranked_ids_set:
                reranked.append(c)

        print(
            f"[RerankAgent] LLM ranked {len(candidates)} candidates → "
            f"top-{top_n}: {[c.get('name') for c in reranked[:top_n]]}"
        )
        return reranked[:top_n]

    except Exception as exc:
        print(f"[RerankAgent] LLM rerank failed, using scored order: {exc}")
        return candidates[:top_n]


def _parse_ranked_ids(raw: str) -> List[str]:
    """
    Extract a list of ID strings from the model's response.
    Handles:
      - Plain JSON array:    ["id1", "id2"]
      - Object wrapping:     {"ranked": ["id1", "id2"]}
      - Object with any key: {"result": ["id1", "id2"]}
    """
    # Try direct parse first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        if isinstance(parsed, dict):
            # Find the first list value
            for v in parsed.values():
                if isinstance(v, list):
                    return [str(x) for x in v]
    except json.JSONDecodeError:
        pass

    # Fallback: regex-extract the first JSON array in the string
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if match:
        try:
            return [str(x) for x in json.loads(match.group(0))]
        except json.JSONDecodeError:
            pass

    return []
