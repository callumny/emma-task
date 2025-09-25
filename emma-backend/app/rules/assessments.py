from __future__ import annotations
import re
from typing import Optional, Tuple

def which_risk_assessment(text: str, incident_type: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer which risk assessment/review is appropriate from transcript text and detected incident_type.
    Returns (assessment_name, evidence_quote) or (None, None) if nothing applies.

    Notes:
      - "moving and handling risk assessment review" is explicitly referenced in policy for recurring falls.
      - Other reviews are sensible, policy-aligned extensions (care plan / medication / infection control / wellbeing).
    """
    low = text.lower()

    # 1) Explicit policy rule: recurring falls within a short time frame
    recurring_falls_patterns = [
        r"\b(third|second|3rd|2nd)\s+time\b.*\b(week|this week)\b",
        r"\b(again)\b.*\b(fall|fallen|on the floor)\b",
    ]
    if incident_type == "fall":
        for pat in recurring_falls_patterns:
            m = re.search(pat, low, flags=re.IGNORECASE)
            if m:
                return "moving and handling risk assessment review", text[m.start():m.end()]

    # 2) Medication management review
    if incident_type in {"medication_refusal", "medication_missed", "medication_error"}:
        m = re.search(r"\b(refus|missed|wrong|incorrect|confus)\w*\b.*\b(med(ication)?|tablet|pill|dose)\b", low, flags=re.IGNORECASE)
        if m:
            return "medication management review", text[m.start():m.end()]
    else:
        m = re.search(r"\b(confused|unsure)\b.*\b(med(ication)?|tablet|pill|dose)\b", low, flags=re.IGNORECASE)
        if m:
            return "medication management review", text[m.start():m.end()]

    # 3) Mental health / wellbeing review
    m = re.search(r"\b(confused|disoriented|distressed|hopeless|anxious|worried|depressed)\b", low, flags=re.IGNORECASE)
    if m:
        return "mental health/wellbeing review", text[m.start():m.end()]

    # 4) Infection control review (illness or PPE issue)
    m = re.search(r"\b(ppe (unavailable|missing)|no ppe|flu|covid|infectious|isolate|contagious)\b", low, flags=re.IGNORECASE)
    if m:
        return "infection control review", text[m.start():m.end()]

    # 5) Personal care & dignity plan review (repeated refusals)
    m = re.search(r"\b(refus\w*)\b.*\b(personal care|wash|bath|shower|toilet)\b", low, flags=re.IGNORECASE)
    if m and re.search(r"\b(again|more than once|repeated|another time)\b", low, flags=re.IGNORECASE):
        return "personal care & dignity plan review", text[m.start():m.end()]

    # 6) Moving & handling / equipment safety review (equipment failure during transfer/mobility)
    m = re.search(r"\b(hoist|wheelchair|alarm|lift|walking aid|stick|frame)\b.*\b(broken|failed|not working|malfunction|strap snapped)\b", low, flags=re.IGNORECASE)
    if m:
        return "moving & handling / equipment safety review", text[m.start():m.end()]

    return None, None
