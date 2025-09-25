"""
datetime_extract.py

Fallback extractor for incident datetime when the LLM doesn't provide one.
Parses explicit dates/times and simple relative phrases, anchored to Europe/London.
"""

from __future__ import annotations
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")

DATE_PATTERNS = [
    r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b",                   # 25/09/2025
    r"\b(\d{1,2})-(\d{1,2})-(\d{2,4})\b",                   # 25-09-2025
    r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(\d{2,4})\b",
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{2,4})\b",
]

TIME_PATTERNS = [
    r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b",                     # 1:45 pm
    r"\b(\d{1,2})\s*(am|pm)\b",                             # 1 pm
    r"\b(\d{1,2}):(\d{2})\b",                               # 13:45
    r"\bnoon\b",                                            # 12:00
    r"\bmidnight\b",                                        # 00:00
]

RELATIVE_PATTERNS = [
    (r"\b(\d{1,2})\s+minutes?\s+ago\b", "minutes"),
    (r"\b(\d{1,2})\s+hours?\s+ago\b", "hours"),
    (r"\byesterday\b", "yesterday"),
    (r"\bthis\s+(morning|afternoon|evening|night)\b", "daypart"),
    (r"\blast\s+night\b", "last_night"),
]

DAYPART_DEFAULTS = {
    "morning": (9, 0),
    "afternoon": (15, 0),
    "evening": (19, 0),
    "night": (22, 0),
}

def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None

def extract_incident_datetime(text: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Return:
      {
        "value": Optional[str],   # ISO8601 (Europe/London) or None
        "confidence": "high"|"medium"|"low"|"none",
        "method": "explicit"|"relative"|"none",
        "evidence_quote": Optional[str]
      }
    """
    if not now:
        now = datetime.now(tz=UK_TZ)
    low = text.lower()

    # explicit date
    date_val = None
    date_quote = None
    for pat in DATE_PATTERNS:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if not m:
            continue
        date_quote = m.group(0)
        d, mth, y = m.group(1), m.group(2), m.group(3)
        day = _safe_int(d)
        year = int(y) + 2000 if len(y) == 2 else _safe_int(y)
        month = None
        if mth.isdigit():
            month = _safe_int(mth)
        else:
            try:
                month = datetime.strptime(mth[:3].title(), "%b").month
            except Exception:
                month = None
        if day and month and year:
            try:
                date_val = datetime(year, month, day, tzinfo=UK_TZ)
                break
            except Exception:
                pass

    # explicit time
    time_val = None
    time_quote = None
    for pat in TIME_PATTERNS:
        m = re.search(pat, low, flags=re.IGNORECASE)
        if not m:
            continue
        time_quote = m.group(0)
        if "noon" in time_quote:
            time_val = (12, 0); break
        if "midnight" in time_quote:
            time_val = (0, 0); break
        if len(m.groups()) == 3 and m.group(3) in ("am","pm"):
            h = _safe_int(m.group(1)) or 0
            mm = _safe_int(m.group(2)) or 0
            if m.group(3) == "pm" and h != 12: h += 12
            if m.group(3) == "am" and h == 12: h = 0
            time_val = (h % 24, mm % 60); break
        if len(m.groups()) == 2:
            if m.group(2) in ("am","pm"):
                h = _safe_int(m.group(1)) or 0
                if m.group(2) == "pm" and h != 12: h += 12
                if m.group(2) == "am" and h == 12: h = 0
                time_val = (h % 24, 0); break
            else:
                h = _safe_int(m.group(1)) or 0
                mm = _safe_int(m.group(2)) or 0
                time_val = (h % 24, mm % 60); break

    if date_val or time_val:
        base = date_val or now
        hh, mm = time_val if time_val else (12, 0)
        dt = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return {"value": dt.isoformat(), "confidence": "high" if (date_val and time_val) else "medium",
                "method": "explicit", "evidence_quote": time_quote or date_quote}

    # relative
    for pat, kind in RELATIVE_PATTERNS:
        m = re.search(pat, low, flags=re.IGNORECASE)
        if not m: continue
        quote = m.group(0)
        if kind in ("minutes","hours"):
            qty = _safe_int(m.group(1)) or 0
            dt = (now - timedelta(**{kind: qty})).replace(second=0, microsecond=0)
            return {"value": dt.isoformat(), "confidence":"low","method":"relative","evidence_quote":quote}
        if kind == "yesterday":
            dt = (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            return {"value": dt.isoformat(), "confidence":"low","method":"relative","evidence_quote":quote}
        if kind == "last_night":
            dt = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
            return {"value": dt.isoformat(), "confidence":"low","method":"relative","evidence_quote":quote}
        if kind == "daypart":
            part = m.group(1)
            h, mi = DAYPART_DEFAULTS.get(part, (12, 0))
            dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            return {"value": dt.isoformat(), "confidence":"low","method":"relative","evidence_quote":quote}

    return {"value": None, "confidence": "none", "method": "none", "evidence_quote": None}
