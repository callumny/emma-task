"""
incident_config.py

Loads incident patterns/locations and exposes helpers to read notifications,
assessment rules, and global policy triggers from incident_patterns.yml.
"""

import os, os.path as p, yaml
from typing import Dict, List, Tuple, Any

def _config_path() -> str:
    envp = os.getenv("INCIDENT_CONFIG")
    if envp:
        return envp
    here = p.dirname(p.abspath(__file__))
    return p.abspath(p.join(here, "..", "..", "config", "incident_patterns.yml"))

def load_incident_config_strict() -> Tuple[Dict[str, List[str]], List[str]]:
    """Back-compat loader used by rules.extract: returns (patterns, locations)."""
    path = _config_path()
    if not p.exists(path):
        raise RuntimeError(f"Incident config not found at {path}")
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    patterns = data.get("patterns") or {}
    locations = data.get("locations") or []
    if not isinstance(patterns, dict) or not isinstance(locations, list):
        raise RuntimeError("Invalid incident config structure")
    return patterns, [loc.lower() for loc in locations]

# ---- New helpers (safe to add; do not break existing imports) ----

def load_notifications() -> Dict[str, Any]:
    """Return notifications policy block (always_notify, cc_by_assessment, global_policy_triggers)."""
    path = _config_path()
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("notifications") or {}

def load_assessment_rules() -> List[Dict[str, Any]]:
    """Return the 'assessments' rules list (each with name, optional incident_types, patterns[], policy_actions?)."""
    path = _config_path()
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    assessments = data.get("assessments") or []
    return assessments if isinstance(assessments, list) else []

def load_global_policy_triggers() -> Dict[str, List[str]]:
    """Shortcut to notifications.global_policy_triggers (contact_gp_if[], call_999_if[])."""
    notif = load_notifications()
    trig = notif.get("global_policy_triggers") or {}
    # Ensure list types
    return {
        "contact_gp_if": list(trig.get("contact_gp_if") or []),
        "call_999_if": list(trig.get("call_999_if") or []),
    }
