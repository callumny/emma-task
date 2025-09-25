
import os, os.path as p, yaml
from typing import Dict, List, Tuple

def _config_path() -> str:
    envp = os.getenv("INCIDENT_CONFIG")
    if envp:
        return envp
    here = p.dirname(p.abspath(__file__))
    return p.abspath(p.join(here, "..", "..", "config", "incident_patterns.yml"))

def load_incident_config_strict() -> Tuple[Dict[str, List[str]], List[str]]:
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
