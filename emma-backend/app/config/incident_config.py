"""
incident_config.py

This module loads and validates the incident configuration (regex patterns for incident types
and a list of allowed locations) from a YAML file.
"""

import os, os.path as p, yaml
from typing import Dict, List, Tuple

def _config_path() -> str:
    """
    Resolve the path to the incident configuration YAML.

    - If the `INCIDENT_CONFIG` environment variable is set, return that path.
    - Otherwise, return the default path: two levels up, then `config/incident_patterns.yml`.

    Returns:
        str: Absolute path to the YAML config file.
    """
    envp = os.getenv("INCIDENT_CONFIG")
    if envp:
        return envp
    here = p.dirname(p.abspath(__file__))
    return p.abspath(p.join(here, "..", "..", "config", "incident_patterns.yml"))

def load_incident_config_strict() -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Load and validate the incident configuration file.

    - Resolves the path using `_config_path()`.
    - Reads the YAML file and extracts `patterns` (dict) and `locations` (list).
    - Ensures the file exists and has the correct structure.
    - Always lowercases the locations before returning.

    Returns:
        Tuple[Dict[str, List[str]], List[str]]:
            - patterns: mapping of incident type → list of regex patterns
            - locations: list of normalized (lowercased) location names

    Raises:
        RuntimeError: if the config file is missing or malformed.
    """
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
