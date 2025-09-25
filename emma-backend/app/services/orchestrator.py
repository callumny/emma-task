from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime
import os

from app.infra.logging import get_logger
from app.llm.extract import extract_with_llm
from app.rules.extract import extract_with_rules

log = get_logger("app.services.orchestrator")

def _default_form() -> Dict[str, Any]:
    return {
        "date_time_of_incident": datetime.utcnow().isoformat(),
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

def _build_email(form: Dict[str, Any]) -> str:
    to = "supervisor@example.com"
    cc = []

    # CC Risk Assessor ONLY when it's the explicit moving & handling recurring-falls review
    if form.get("if_yes_which_risk_assessment") == "moving and handling risk assessment review":
        cc.append("risk.assessor@example.com")

    subject = f"Incident report: {form.get('type_of_incident') or 'Unknown'} – {form.get('service_user_name') or 'Service User'}"
    lines = [
        f"To: {to}",
        f"CC: {', '.join(cc)}" if cc else "",
        f"Subject: {subject}",
        "",
        f"Date/Time: {form.get('date_time_of_incident')}",
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
        f"If Yes, Which: {form.get('if_yes_which_risk_assessment') or '-'}",
    ]
    return "\n".join([l for l in lines if l is not None])

def _facts_to_form(facts: Dict[str, Any]) -> Dict[str, Any]:
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

def analyze_transcript(transcript: str) -> Dict[str, Any]:
    log.info("analyze_transcript.start")
    evidence: List[Dict[str, Any]] = []
    source = "rules"
    facts: Dict[str, Any] = {}

    key_present = bool(os.getenv("OPENAI_API_KEY"))
    log.info(f"env.OPENAI_API_KEY.present={key_present}")

    if key_present:
        try:
            facts, evidence = extract_with_llm(transcript)
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
    email = _build_email(form)
    log.info(f"analyze_transcript.done source={source}")
    return {
        "extraction_source": source,
        "incident_form": form,
        "evidence": evidence,
        "draft_email": email,
    }

def analyze_transcript_llm_only(transcript: str) -> Dict[str, Any]:
    log.info("analyze_transcript_llm_only.start")
    facts, evidence = extract_with_llm(transcript)
    form = _facts_to_form(facts)
    email = _build_email(form)
    log.info(f"analyze_transcript_llm_only.done facts_present={bool(facts)}")
    return {
        "extraction_source": "llm" if facts else "llm_empty",
        "incident_form": form,
        "evidence": evidence,
        "draft_email": email,
    }

def llm_diagnostic() -> Dict[str, Any]:
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
