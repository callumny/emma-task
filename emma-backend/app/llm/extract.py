"""
LLM extractor: builds a prompt, calls OpenAI, and normalizes the model's JSON
into (facts, evidence) suitable for the incident pipeline.
"""

from typing import Dict, Any, List, Tuple
import json
import os
import re

# Whitelists used to clamp/normalize model output
ALLOWED_INCIDENT_TYPES = [
    "fall",
    "medication_refusal",
    "medication_missed",
    "medication_error",
    "aggressive_behavior",
    "verbal_abuse",
    "self_harm",
    "wandering",
    "medical_emergency",
    "near_miss",
    "equipment_failure",
    "safeguarding_concern",
    None,
]

ALLOWED_RISK_ASSESSMENTS = [
    "moving and handling risk assessment review",
    "medication management review",
    "mental health/wellbeing review",
    "infection control review",
    "personal care & dignity plan review",
    "moving & handling / equipment safety review",
    None,
]

def _build_prompt(transcript: str) -> str:
    """
    Compose the instruction + schema-constrained prompt for the LLM.
    Returns a single string that asks the model to output ONLY valid JSON.
    """
    return (
        "You are an information extraction assistant for adult social care incident reporting.\n"
        "From the call transcript below, return ONLY valid JSON with these keys:\n"
        "- date_time_of_incident (ISO8601 if present or null)\n"
        "- service_user_name (full name if present or null)\n"
        "- location (free text, e.g., \"living room\", or null)\n"
        "- incident_type (one of: fall | medication_refusal | medication_missed | medication_error | "
        "aggressive_behavior | verbal_abuse | self_harm | wandering | medical_emergency | near_miss | "
        "equipment_failure | safeguarding_concern | null)\n"
        "- description (1-3 sentence neutral summary of what happened)\n"
        "- immediate_actions_taken (null if not stated)\n"
        "- was_first_aid_administered (boolean; default false if not stated)\n"
        "- were_emergency_services_contacted (boolean; default false unless clearly stated)\n"
        "- who_was_notified (null if not stated)\n"
        "- witnesses (null if not stated)\n"
        "- agreed_next_steps (null if not stated)\n"
        "- risk_assessment_needed (boolean)\n"
        "- if_yes_which_risk_assessment (one of: \"moving and handling risk assessment review\" | "
        "\"medication management review\" | \"mental health/wellbeing review\" | \"infection control review\" | "
        "\"personal care & dignity plan review\" | \"moving & handling / equipment safety review\" | null)\n"
        "- evidence: array of {\"field\":\"<key>\", \"quote\":\"<short supporting quote>\"}\n\n"
        "Guidance:\n"
        "- Set risk_assessment_needed true when the transcript shows a recurring pattern or policy trigger.\n"
        "- Use \"moving and handling risk assessment review\" for recurring falls (e.g., 2nd/3rd time this week).\n"
        "- If unsure, set fields to null. Do NOT invent names or facts.\n\n"
        "Transcript:\n"
        f"{transcript}"
    )

def _strip_md_fences(s: str) -> str:
    """
    Remove ```json ... ``` fences if the model wrapped the JSON in Markdown code blocks.
    Returns the cleaned string for JSON parsing.
    """
    s = s.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'```\s*$', '', s)
    return s.strip()

def extract_with_llm(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Call the OpenAI Chat Completions API with the prompt, parse/validate JSON,
    clamp to allowed values, and return (facts, evidence). Falls back to {} / []
    if the API key is missing or a parsing error occurs.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {}, []

    try:
        from openai import OpenAI
        client = OpenAI()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        prompt = _build_prompt(text)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        content = (resp.choices[0].message.content or "")
        content = _strip_md_fences(content)
        data = json.loads(content)

        # Defensive normalization against hallucinations
        if data.get("incident_type") not in ALLOWED_INCIDENT_TYPES:
            data["incident_type"] = None
        if data.get("if_yes_which_risk_assessment") not in ALLOWED_RISK_ASSESSMENTS:
            data["if_yes_which_risk_assessment"] = None
        if "risk_assessment_needed" not in data:
            data["risk_assessment_needed"] = bool(data.get("if_yes_which_risk_assessment"))

        facts: Dict[str, Any] = {}
        keys_map = {
            "date_time_of_incident": "date_time_of_incident",
            "service_user_name": "service_user_name",
            "location": "location",
            "incident_type": "incident_type",
            "description": "description",
            "immediate_actions_taken": "immediate_actions_taken",
            "was_first_aid_administered": "was_first_aid_administered",
            "were_emergency_services_contacted": "were_emergency_services_contacted",
            "who_was_notified": "who_was_notified",
            "witnesses": "witnesses",
            "agreed_next_steps": "agreed_next_steps",
            "risk_assessment_needed": "risk_assessment_needed",
            "if_yes_which_risk_assessment": "if_yes_which_risk_assessment",
        }
        for k_src, k_dst in keys_map.items():
            if k_src in data:
                facts[k_dst] = data[k_src]

        evidence_in = data.get("evidence", [])
        evidence: List[Dict[str, Any]] = []
        for item in evidence_in:
            if isinstance(item, dict) and "field" in item and "quote" in item:
                evidence.append({
                    "field": item["field"],
                    "quote": item["quote"],
                    "start_idx": None,
                    "end_idx": None
                })
        return facts, evidence
    except Exception:
        # On any failure, let rules fallback handle it.
        return {}, []
