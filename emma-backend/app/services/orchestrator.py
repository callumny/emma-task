"""
orchestrator.py

This module coordinates transcript analysis: it calls LLM and/or rules-based extractors,
normalizes results into a standard incident form, builds a draft email, and returns evidence.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import re

from app.infra.logging import get_logger
from app.llm.extract import extract_with_llm
from app.rules.extract import extract_with_rules
from app.config.incident_config import (
    load_notifications,
    load_global_policy_triggers,
)
from app.util.datetime_extract import extract_incident_datetime

log = get_logger("app.services.orchestrator")
UK_TZ = ZoneInfo("Europe/London")


def _default_form() -> Dict[str, Any]:
    """
    Create a new blank incident form with default values.
    Used to ensure all required keys are always present.
    """
    return {
        # Let the LLM set this; if missing, we'll fallback to explicit parsing.
        "date_time_of_incident": None,
        # Always capture when this report was created (auditable, Europe/London).
        "reported_at": datetime.now(tz=UK_TZ).isoformat(),
        "service_user_name": None,
        "location": None,
        "type_of_incident": None,
        "description_of_the_incident": "",
        "immediate_actions_taken": None,
        "was_first_aid_administered": False,
        "were_emergency_services_contacted": False,
        "who_was_notified": None,
        "witnesses": None,
        "agreed_next_steps": None,
        "risk_assessment_needed": False,
        "if_yes_which_risk_assessment": None,
    }


def _maybe_append_action(form: Dict[str, Any], transcript: str) -> None:
    """
    Add GP/999 suggestions to immediate_actions_taken if global triggers match the transcript.
    This is policy suggestion (not extraction), so it stays here in the orchestrator.
    """
    triggers = load_global_policy_triggers()
    low = transcript.lower()
    actions: List[str] = []

    # Contact GP triggers
    for pat in triggers.get("contact_gp_if", []):
        try:
            if re.search(pat, low, flags=re.IGNORECASE):
                actions.append("Contact GP immediately (policy trigger)")
                break
        except re.error:
            continue

    # Call 999 triggers
    for pat in triggers.get("call_999_if", []):
        try:
            if re.search(pat, low, flags=re.IGNORECASE):
                actions.append("Call 999 / emergency services (life-threatening trigger)")
                break
        except re.error:
            continue

    if actions:
        existing = form.get("immediate_actions_taken")
        joined = " | ".join(actions)
        form["immediate_actions_taken"] = f"{existing} | {joined}" if existing else joined


def _build_email(form: Dict[str, Any]) -> str:
    """
    Construct a plain-text draft email summarizing the incident form.
    'To' and 'CC' come from config:
      - To: notifications.always_notify (defaults to "Supervisor")
      - CC: notifications.cc_by_assessment[<risk_assessment_name>] if present
    """
    notifications = load_notifications() or {}
    to_addr = notifications.get("always_notify", "Supervisor")
    cc_map = notifications.get("cc_by_assessment", {}) or {}

    # CC by selected risk assessment name (if configured)
    cc: List[str] = []
    ra_name = form.get("if_yes_which_risk_assessment")
    if ra_name and ra_name in cc_map:
        cc.append(cc_map[ra_name])

    # Ensure 'who_was_notified' reflects the default policy if empty
    if not form.get("who_was_notified"):
        form["who_was_notified"] = to_addr

    subject = f"Incident report: {form.get('type_of_incident') or 'Unknown'} – {form.get('service_user_name') or 'Service User'}"
    lines = [
        f"To: {to_addr}",
        f"CC: {', '.join(cc)}" if cc else "",
        f"Subject: {subject}",
        "",
        f"Date/Time: {form.get('date_time_of_incident') or 'None'}",
        f"Reported At: {form.get('reported_at') or 'None'}",
        f"Service User: {form.get('service_user_name') or 'Unknown'}",
        f"Location: {form.get('location') or 'Unknown'}",
        f"Type: {form.get('type_of_incident') or 'Unknown'}",
        "",
        "Description:",
        form.get("description_of_the_incident") or "-",
        "",
        "Immediate Actions Taken:",
        form.get("immediate_actions_taken") or "-",
        "",
        f"First Aid: {'Yes' if form.get('was_first_aid_administered') else 'No'}",
        f"Emergency Services: {'Yes' if form.get('were_emergency_services_contacted') else 'No'}",
        f"Who Was Notified: {form.get('who_was_notified') or '-'}",
        f"Witnesses: {form.get('witnesses') or '-'}",
        "",
        "Next Steps:",
        form.get("agreed_next_steps") or "-",
        f"Risk Assessment Needed: {'Yes' if form.get('risk_assessment_needed') else 'No'}",
        f"If Yes, Which: {ra_name or '-'}",
    ]
    return "\n".join([l for l in lines if l is not None])


def _facts_to_form(facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a dictionary of extracted facts into a fully-formed incident form,
    ensuring key names match the expected output schema.
    """
    form = _default_form()
    mapping = {
        "date_time_of_incident": "date_time_of_incident",
        "service_user_name": "service_user_name",
        "location": "location",
        "incident_type": "type_of_incident",
        "description": "description_of_the_incident",
        "immediate_actions_taken": "immediate_actions_taken",
        "was_first_aid_administered": "was_first_aid_administered",
        "were_emergency_services_contacted": "were_emergency_services_contacted",
        "who_was_notified": "who_was_notified",
        "witnesses": "witnesses",
        "agreed_next_steps": "agreed_next_steps",
        "risk_assessment_needed": "risk_assessment_needed",
        "if_yes_which_risk_assessment": "if_yes_which_risk_assessment",
    }
    for k_src, k_dst in mapping.items():
        if k_src in facts:
            form[k_dst] = facts[k_src]
    return form


def _llm_datetime_fallback(form: Dict[str, Any], transcript: str, evidence: List[Dict[str, Any]]) -> None:
    """
    If the LLM did not provide a date_time_of_incident, attempt explicit/relative parsing.
    On low-confidence inference, add a gentle confirmation hint to immediate_actions_taken.
    """
    if form.get("date_time_of_incident"):
        return
    dt_info = extract_incident_datetime(transcript, now=datetime.now(tz=UK_TZ))
    if not dt_info.get("value"):
        return

    form["date_time_of_incident"] = dt_info["value"]
    # Optional hint if low confidence
    if dt_info.get("confidence") == "low":
        hint = "Incident time inferred from context – please confirm"
        existing = form.get("immediate_actions_taken")
        form["immediate_actions_taken"] = f"{existing} | {hint}" if existing else hint

    # Optional: attach evidence
    quote = dt_info.get("evidence_quote")
    if quote:
        evidence.append({
            "field": "date_time_of_incident",
            "quote": quote,
            "start_idx": None,
            "end_idx": None
        })


# --- Sanity guard for implausible LLM times (when no explicit date in transcript) ---

_EXPLICIT_DATE_REGEXES = [
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",
    r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b",
    r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4}\b",
]

def _has_explicit_date(text: str) -> bool:
    low = text.lower()
    for pat in _EXPLICIT_DATE_REGEXES:
        try:
            if re.search(pat, low, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False

def _parse_iso(dt_s: Optional[str]):
    if not dt_s:
        return None
    try:
        return datetime.fromisoformat(dt_s.replace("Z", "+00:00"))
    except Exception:
        return None

def _sanity_fix_incident_time(form: Dict[str, Any], transcript: str, anchor: datetime, evidence: List[Dict[str, Any]]):
    """
    If LLM gave an implausible incident time (e.g., years off) and there is NO explicit date in transcript,
    fallback to deterministic parsing relative to `anchor` (Europe/London). Otherwise null it out.
    """
    dt = _parse_iso(form.get("date_time_of_incident"))
    if not dt:
        return  # nothing to fix

    if _has_explicit_date(transcript):
        return  # caller said an actual date; respect it

    # If LLM time is more than 7 days away from anchor, consider it implausible
    delta = abs((dt - anchor).total_seconds())
    seven_days = 7 * 24 * 3600
    if delta > seven_days:
        info = extract_incident_datetime(transcript, now=anchor)
        new_val = info.get("value")
        if new_val:
            form["date_time_of_incident"] = new_val
            if info.get("confidence") == "low":
                hint = "Incident time inferred from context – please confirm"
                existing = form.get("immediate_actions_taken")
                form["immediate_actions_taken"] = f"{existing} | {hint}" if existing else hint
            q = info.get("evidence_quote")
            if q:
                evidence.append({
                    "field": "date_time_of_incident",
                    "quote": q,
                    "start_idx": None,
                    "end_idx": None
                })
        else:
            form["date_time_of_incident"] = None


def analyze_transcript(transcript: str) -> Dict[str, Any]:
    """
    Analyze a transcript using the LLM if available, falling back to rule-based extraction otherwise.
    Returns the source used, a completed incident form, evidence, and a draft email.
    """
    log.info("analyze_transcript.start")
    evidence: List[Dict[str, Any]] = []
    source = "rules"
    facts: Dict[str, Any] = {}

    anchor = datetime.now(tz=UK_TZ)
    anchor_iso = anchor.isoformat()

    key_present = bool(os.getenv("OPENAI_API_KEY"))
    log.info(f"env.OPENAI_API_KEY.present={key_present}")

    if key_present:
        try:
            # IMPORTANT: pass anchor to LLM for relative time conversion
            facts, evidence = extract_with_llm(transcript, report_time_iso=anchor_iso)
            log.info(f"llm.result.keys={list(facts.keys()) if facts else []}")
            if facts:
                source = "llm"
        except Exception as e:
            log.error(f"llm.extract.failed: {e}")

    if not facts:
        log.info("rules.fallback")
        facts, evidence, _ = extract_with_rules(transcript)
        source = "rules"

    form = _facts_to_form(facts)

    # If LLM (or rules) omitted incident time, try explicit/relative fallback.
    _llm_datetime_fallback(form, transcript, evidence)

    # Sanity fix if LLM produced implausible time (no explicit date)
    _sanity_fix_incident_time(form, transcript, anchor, evidence)

    # Add GP/999 hints from global triggers BEFORE building the email
    _maybe_append_action(form, transcript)

    email = _build_email(form)
    log.info(f"analyze_transcript.done source={source}")
    return {
        "extraction_source": source,
        "incident_form": form,
        "evidence": evidence,
        "draft_email": email,
    }


def analyze_transcript_llm_only(transcript: str) -> Dict[str, Any]:
    """
    Analyze a transcript using only the LLM (no rules fallback).
    Useful for debugging or comparing model vs. rules performance.
    """
    log.info("analyze_transcript_llm_only.start")

    anchor = datetime.now(tz=UK_TZ)
    anchor_iso = anchor.isoformat()

    facts, evidence = extract_with_llm(transcript, report_time_iso=anchor_iso)
    form = _facts_to_form(facts)

    # Same behavior: try fallback parsing if LLM leaves datetime empty.
    _llm_datetime_fallback(form, transcript, evidence)

    # Sanity fix for implausible times
    _sanity_fix_incident_time(form, transcript, anchor, evidence)

    # Apply global policy triggers
    _maybe_append_action(form, transcript)

    email = _build_email(form)
    log.info(f"analyze_transcript_llm_only.done facts_present={bool(facts)}")
    return {
        "extraction_source": "llm" if facts else "llm_empty",
        "incident_form": form,
        "evidence": evidence,
        "draft_email": email,
    }


def llm_diagnostic() -> Dict[str, Any]:
    """
    Run diagnostic checks for the LLM integration:
    - confirm env vars are set
    - verify SDK import
    - attempt a minimal test call if possible
    Returns a dictionary of diagnostic info.
    """
    info: Dict[str, Any] = {}
    info["env_key_present"] = bool(os.getenv("OPENAI_API_KEY"))
    info["model"] = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    try:
        from openai import OpenAI  # type: ignore
        info["sdk_import_ok"] = True
    except Exception as e:
        info["sdk_import_ok"] = False
        info["sdk_import_error"] = str(e)
        return info

    if not info["env_key_present"]:
        info["test_call_skipped"] = True
        return info

    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=info["model"],
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON."},
                {"role": "user", "content": "{\"ok\": true}"},
            ],
            temperature=0.0,
        )
        info["test_call_ok"] = True
        info["raw_first_token"] = (resp.choices[0].message.content or "")[:120]
    except Exception as e:
        info["test_call_ok"] = False
        info["test_call_error"] = str(e)
    return info
