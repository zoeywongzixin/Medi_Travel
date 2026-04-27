"""
Rerank Agent
============
Takes a pre-filtered shortlist of doctor candidates (up to 5) and uses
the local Ollama LLM as a judge to select and rank the final top-3.

The LLM receives only the candidates that have already passed:
  1. Hybrid RRF search (semantic + keyword)
  2. Specialty-group hard gate
  3. Metadata-enriched numeric scoring

So the prompt is deliberately small and tightly scoped — the model just
compares 5 well-matched doctors and returns a ranked JSON list of IDs.

Fallback: if Ollama is unavailable or returns invalid JSON, the function
returns the candidates as-is (already in scored order from Stage 3).
"""

import json
import os
import re
from typing import Dict, List

import ollama


def llm_rerank(candidates: List[Dict], medical_data: Dict, top_n: int = 3) -> List[Dict]:
    """
    Use Ollama as a judge to rerank up to 5 pre-vetted doctor candidates.

    Args:
        candidates:   List of up to 5 candidate dicts (already scored & filtered).
        medical_data: Original patient data dict (condition, severity, urgency, etc.)
        top_n:        How many final results to return (default 3).

    Returns:
        Reranked list of up to `top_n` doctor dicts.
    """
    if not candidates:
        return []

    # If only 1–2 candidates, no point calling the LLM
    if len(candidates) <= top_n:
        return candidates[:top_n]

    diagnosis = medical_data.get("condition", "unknown condition")
    severity = medical_data.get("severity", "Unknown")
    urgency = medical_data.get("urgency", "Unknown")

    # Build a compact representation of each candidate for the prompt
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
        "You are a medical matching expert for a Malaysian healthcare platform. "
        "Your only task is to rank doctors by suitability for a given patient. "
        "Return ONLY a valid JSON array of doctor IDs in order from most to least suitable. "
        "Example output: [\"id_a\", \"id_b\", \"id_c\"]. "
        "Do NOT include any explanation or extra text — only the JSON array."
    )

    user_prompt = (
        f"Patient diagnosis: {diagnosis}\n"
        f"Severity: {severity} | Urgency: {urgency}\n\n"
        f"Compare these {len(candidates)} doctors and return the top {top_n} as a JSON array of IDs "
        f"(most suitable first):\n\n"
        f"{json.dumps(candidate_summaries, indent=2)}"
    )

    try:
        print(f"  [RerankAgent] Calling AI judge (Ollama) to compare {len(candidates)} candidates for '{diagnosis}'...")
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        client = ollama.Client(host=ollama_host)
        response = client.chat(
            model="llama3.2:3b",
            format="json",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.0, "num_ctx": 1024},
        )

        # Handle both old (dict) and new (object) Ollama response formats
        raw_content = (
            response.message.content.strip()
            if hasattr(response, "message")
            else response["message"]["content"].strip()
        )

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
