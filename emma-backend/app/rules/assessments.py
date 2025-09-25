"""
assessments.py

Infers which risk assessment/review is required by evaluating **config-driven**
regex rules (from incident_patterns.yml) against the transcript, optionally
filtered by detected incident_type.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple, List, Dict, Any
from functools import lru_cache

# Primary: use your existing config loader
from app.config import incident_config as _cfg

try:
    # Optional: YAML fallback if loader doesn't expose assessments
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # graceful if PyYAML not available (but loader should be)


@lru_cache(maxsize=1)
def _load_assessment_rules() -> List[Dict[str, Any]]:
    """
    Load the `assessments` list from incident_patterns.yml.

    Tries to use load_incident_config_strict(); if that function only returns
    (patterns, locations), falls back to reading the YAML directly via the same path.
    """
    assessments: List[Dict[str, Any]] = []

    try:
        # Try calling the loader and see how many values it returns
        loaded = _cfg.load_incident_config_strict()
        # Support both 2-tuple (legacy) and 4-tuple (extended) signatures
        if isinstance(loaded, tuple):
            if len(loaded) >= 4:
                # (patterns, locations, notifications, assessments)
                assessments = loaded[3] or []
            else:
                # Legacy (patterns, locations): attempt YAML fallback
                assessments = _load_assessments_from_yaml_fallback()
        else:
            assessments = _load_assessments_from_yaml_fallback()
    except Exception:
        # Any failure → fallback
        assessments = _load_assessments_from_yaml_fallback()

    # Normalize structure
    out: List[Dict[str, Any]] = []
    for rule in assessments or []:
        if not isinstance(rule, dict):
            continue
        name = rule.get("name")
        pats = rule.get("patterns") or []
        if not name or not isinstance(pats, list) or not pats:
            continue
        out.append({
            "name": str(name),
            "incident_types": rule.get("incident_types") or None,  # list[str] or None
            "patterns": [str(p) for p in pats],
        })
    return out


def _load_assessments_from_yaml_fallback() -> List[Dict[str, Any]]:
    """
    Best-effort fallback: open the same YAML file used by the loader and read `assessments`.
    """
    try:
        if not yaml:
            return []
        # Reuse the loader's path resolution helpers if present
        path = None
        if hasattr(_cfg, "_config_path"):
            path = _cfg._config_path()  # type: ignore[attr-defined]
        if not path:
            # Derive path similarly to the loader (relative to this module)
            import os, os.path as p  # local import to avoid polluting namespace
            here = p.dirname(p.abspath(__file__))
            path = p.abspath(p.join(here, "..", "..", "config", "incident_patterns.yml"))

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        assessments = data.get("assessments") or []
        return assessments if isinstance(assessments, list) else []
    except Exception:
        return []


def which_risk_assessment(text: str, incident_type: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Evaluate assessment rules from config against the transcript.
    Returns (assessment_name, evidence_quote) or (None, None) if nothing matches.

    Matching behavior:
      - If a rule specifies `incident_types`, it only applies when `incident_type` is in that list.
      - Within a rule, patterns are tested in order; the first match wins.
      - Across rules, the first rule that matches returns the assessment.
    """
    low = text.lower()
    rules = _load_assessment_rules()

    for rule in rules:
        name = rule["name"]
        allowed_types = rule.get("incident_types")
        if allowed_types and incident_type not in allowed_types:
            continue

        for pat in rule["patterns"]:
            try:
                m = re.search(pat, low, flags=re.IGNORECASE)
            except re.error:
                # Bad regex in config; skip this pattern
                continue
            if m:
                start, end = m.start(), m.end()
                return name, text[start:end]

    # Nothing matched
    return None, None
