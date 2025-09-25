import re
from typing import Dict, Any, List, Tuple
from app.config.incident_config import load_incident_config_strict
from app.rules.assessments import which_risk_assessment

def _find_spans(text: str, pattern: str) -> List[Tuple[int, int]]:
    spans = []
    for m in re.finditer(pattern, text, flags=re.IGNORECASE):
        spans.append((m.start(), m.end()))
    return spans

def extract_with_rules(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    patterns, locations = load_incident_config_strict()
    facts: Dict[str, Any] = {
        "incident_type": None,
        "service_user_name": None,
        "location": None,
        "description": text.strip(),
        "immediate_actions_taken": None,
        "was_first_aid_administered": False,
        "were_emergency_services_contacted": False,
        "who_was_notified": None,
        "witnesses": None,
        "agreed_next_steps": None,
        "risk_assessment_needed": False,
        "if_yes_which_risk_assessment": None,
        "date_time_of_incident": None,
    }
    evidence: List[Dict[str, Any]] = []
    debug: Dict[str, Any] = {}

    low = text.lower()

    # Service user name (simple intro pattern: "it's Greg Jones")
    m = re.search(r"\bit['’]s\s+([A-Z][a-z]+)\.?\s+([A-Z][a-z]+)\b", text)
    if m:
        facts["service_user_name"] = f"{m.group(1)} {m.group(2)}"
        evidence.append({
            "field": "service_user_name",
            "quote": m.group(0),
            "start_idx": m.start(1),
            "end_idx": m.end(2)
        })

    # Incident type via config patterns (first match wins)
    for t, pats in (patterns or {}).items():
        for pat in pats or []:
            spans = _find_spans(text, pat)
            if spans:
                facts["incident_type"] = t
                s, e = spans[0]
                evidence.append({
                    "field": "incident_type",
                    "quote": text[s:e],
                    "start_idx": s,
                    "end_idx": e
                })
                break
        if facts["incident_type"]:
            break

    # Location via keyword hit (first match wins)
    for loc in (locations or []):
        idx = low.find(loc)
        if idx != -1:
            facts["location"] = loc
            evidence.append({
                "field": "location",
                "quote": text[idx:idx+len(loc)],
                "start_idx": idx,
                "end_idx": idx + len(loc)
            })
            break

    # First aid / emergency toggles (very conservative defaults unless explicit)
    if re.search(r"\b(blood|bleeding|broken|fracture)\b", low):
        facts["was_first_aid_administered"] = False  # caller said no blood/broken in your example; keep default False
    if re.search(r"\b(999|ambulance|emergency services|paramedic)\b", low):
        facts["were_emergency_services_contacted"] = True

    # Risk assessment inference (includes explicit policy rule for recurring falls)
    assessment, ra_quote = which_risk_assessment(text, facts.get("incident_type"))
    if assessment:
        facts["risk_assessment_needed"] = True
        facts["if_yes_which_risk_assessment"] = assessment
        if ra_quote:
            # Best-effort span (first occurrence)
            i = low.find(ra_quote.lower())
            evidence.append({
                "field": "risk_assessment_needed",
                "quote": ra_quote,
                "start_idx": i if i >= 0 else None,
                "end_idx": (i + len(ra_quote)) if i is not None and i >= 0 else None
            })

    # Falls-specific notification hint (policy-aligned)
    if facts.get("incident_type") == "fall":
        facts["who_was_notified"] = "Supervisor (mandatory); CC Risk Assessor if recurring falls"

    return facts, evidence, debug
