"""Role / seniority / location filter core. Shared by scripts/fetch_prospects.py
and the sink's scrape-ingest paths so the filter rules live in one place.

passes_filters(row, filters_dict) -> (ok: bool, reason: str|None)
"""
import re

US_STATE_CODES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN "
    "MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA "
    "WA WV WI WY DC".split()
)
STATE_CODE_RE = re.compile(r',\s*([A-Z]{2})(?:\b|$)')


def matches_any(text, keywords):
    text_lc = (text or "").lower()
    for k in keywords or []:
        k_lc = k.lower().strip()
        if not k_lc:
            continue
        if re.search(r'(?<!\w)' + re.escape(k_lc) + r'(?!\w)', text_lc):
            return True
    return False


def has_us_state_code(location):
    for m in STATE_CODE_RE.findall(location or ""):
        if m in US_STATE_CODES:
            return True
    return False


def passes_filters(row, f):
    """row needs at least {role, location, flags}. f is the filters.json dict."""
    for flag in f.get("drop_flags", []):
        if flag in row.get("flags", []):
            return False, f"flag:{flag}"
    role = row.get("role", "")
    if matches_any(role, f.get("role_exclude", [])):
        return False, "role_excluded"
    if matches_any(role, f.get("seniority_exclude", [])):
        return False, "seniority_too_high"
    if f.get("role_include") and not matches_any(role, f["role_include"]):
        return False, "role_not_in_include"
    loc = row.get("location", "")
    if loc and matches_any(loc, f.get("non_us_keywords", [])):
        is_us = matches_any(loc, f.get("us_signals", [])) or has_us_state_code(loc)
        if not is_us:
            return False, "non_us_location"
    return True, None
