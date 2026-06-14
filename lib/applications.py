"""ApplyAsYou -- deterministic application state mutations.

Functions here own the dual-write contract: when a user applies, BOTH
data/active.json (the live pipeline row) AND data/prospects/prospects.json
(state flip) must update atomically. The orchestrator never improvises
this logic; it calls these functions via scripts/apply.py.

Why deterministic Python instead of LLM-interpreted? Two reasons:
  1. Data mutations must be reproducible (LLM occasionally hallucinates
     fields).
  2. The dual-write must be transactional in spirit (if one half fails,
     the other shouldn't proceed).

Public API:
  apply_with_prospect_id(prospect_id)
  apply_with_jd_in_context(jd_text, role=None, company=None, link=None)
  tag_for_tailor(prospect_id, reason)
  detect_apply_intent(user_message)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


# --- Workspace layout ---
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DATA_DIR = REPO_ROOT / "data"
ACTIVE_FILE = DATA_DIR / "active.json"
PROSPECTS_DIR = DATA_DIR / "prospects"
PROSPECTS_FILE = PROSPECTS_DIR / "prospects.json"
JD_CACHE_FILE = PROSPECTS_DIR / "jd_cache.json"


# --- IO helpers ---
def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _next_id(rows) -> int:
    if not rows:
        return 1
    return max(int(r.get("id", 0)) for r in rows) + 1


# --- Prospect lookups ---
def _find_prospect(prospect_id: int):
    prospects = _read_json(PROSPECTS_FILE, [])
    for row in prospects:
        if row.get("id") == prospect_id:
            return prospects, row
    return prospects, None


# --- Public API ---

class ApplicationsError(Exception):
    """Raised when an application-state mutation cannot proceed."""


def apply_with_prospect_id(prospect_id: int) -> dict:
    """User applied to a job that already exists in prospects.json.

    Triggered by:
      - User types "applied p#1234" in chat
      - User clicks "I applied" button in the viewer (Path A)
      - Gmail sweep matches an ATS receipt to a prospect (auto-detected)

    Action:
      1. Flip prospect state ("new" or "shortlist") -> "applied"
      2. Append a new row to data/active.json (id = max+1)
      3. Link them via active_row._prospect_id = prospect_id

    Returns dict with active_id + a short status string.
    """
    prospects, prospect = _find_prospect(prospect_id)
    if prospect is None:
        raise ApplicationsError(f"prospect id {prospect_id} not found")

    if prospect.get("state") == "applied":
        return {
            "status": "already_applied",
            "prospect_id": prospect_id,
            "active_id": None,
        }

    # Flip prospect state
    prospect["state"] = "applied"

    # Build active row from prospect facts
    active_rows = _read_json(ACTIVE_FILE, [])
    new_id = _next_id(active_rows)
    new_row = {
        "id": new_id,
        "company": prospect.get("company", ""),
        "role": prospect.get("role", ""),
        "location": prospect.get("location", ""),
        "visa": _visa_from_analysis(prospect.get("analysis")),
        "resume": _resume_from_analysis(prospect.get("analysis")),
        "date_applied": _today_iso(),
        "status": "applied",
        "last_touch": _today_iso(),
        "next_action": "Watch ATS for response.",
        "link": prospect.get("link", ""),
        "_prospect_id": prospect_id,
        "notes": _notes_from_analysis(prospect.get("analysis")),
        "via": "prospect_pipeline",
    }
    active_rows.append(new_row)

    _write_json(PROSPECTS_FILE, prospects)
    _write_json(ACTIVE_FILE, active_rows)

    return {"status": "applied", "prospect_id": prospect_id, "active_id": new_id}


def apply_with_jd_in_context(
    jd_text: str,
    role: str = "",
    company: str = "",
    link: str = "",
) -> dict:
    """User pasted a JD, agent analyzed it, user said 'applied'.
    The JD doesn't exist in prospects.json.

    Action:
      1. Create a new prospects.json row with state="applied"
      2. Cache the JD text in data/prospects/jd_cache.json keyed by new prospect id
      3. Append a row to data/active.json linked via _prospect_id

    Returns dict with prospect_id + active_id.
    """
    if not jd_text:
        raise ApplicationsError("jd_text is required for apply_with_jd_in_context")

    prospects = _read_json(PROSPECTS_FILE, [])
    new_prospect_id = _next_id(prospects)
    new_prospect = {
        "id": new_prospect_id,
        "company": company,
        "role": role,
        "location": "",
        "link": link,
        "date_posted": _today_iso(),
        "date_posted_raw": _today_iso(),
        "work_model": "",
        "flags": [],
        "sources": ["chat-paste"],
        "state": "applied",
        "notes": "Added via chat paste + applied. Never went through triage.",
    }
    prospects.append(new_prospect)

    jd_cache = _read_json(JD_CACHE_FILE, {})
    jd_cache[str(new_prospect_id)] = jd_text
    _write_json(JD_CACHE_FILE, jd_cache)

    active_rows = _read_json(ACTIVE_FILE, [])
    new_active_id = _next_id(active_rows)
    new_active = {
        "id": new_active_id,
        "company": company,
        "role": role,
        "location": "",
        "visa": "",
        "resume": "",
        "date_applied": _today_iso(),
        "status": "applied",
        "last_touch": _today_iso(),
        "next_action": "Watch ATS for response.",
        "link": link,
        "_prospect_id": new_prospect_id,
        "notes": "Direct chat-paste application. JD text in jd_cache.json.",
        "via": "chat_paste",
    }
    active_rows.append(new_active)

    _write_json(PROSPECTS_FILE, prospects)
    _write_json(ACTIVE_FILE, active_rows)

    return {
        "status": "applied",
        "prospect_id": new_prospect_id,
        "active_id": new_active_id,
    }


def tag_for_tailor(prospect_id: int, reason: str) -> dict:
    """Flag a prospect as needing a tailored resume.

    Triggered by jd-analyzer when:
      analysis.match_pct >= 80 AND best_existing_variant_match < 75

    Does NOT run the tailor itself -- user batches the work later by
    saying "tailor resume for p#<id>".
    """
    prospects, prospect = _find_prospect(prospect_id)
    if prospect is None:
        raise ApplicationsError(f"prospect id {prospect_id} not found")

    prospect["requires_tailor"] = True
    prospect["tailor_reason"] = reason or "high match without good existing variant"
    _write_json(PROSPECTS_FILE, prospects)

    return {
        "status": "tagged",
        "prospect_id": prospect_id,
        "tailor_reason": prospect["tailor_reason"],
    }


# --- Intent detection (used by the orchestrator) ---

PROSPECT_ID_RE = re.compile(r"\bp\s*#\s*(\d+)\b", re.IGNORECASE)
APPLY_VERBS = (
    "applied", "just applied", "submitted", "i applied",
    "i submitted", "sent the application", "fired off the app",
)


def detect_apply_intent(user_message: str) -> dict:
    """Parse a chat message to figure out which apply scenario it is.

    Returns one of:
      {"scenario": "with_prospect_id", "prospect_id": <int>}
      {"scenario": "jd_in_context"}       # last assistant turn was a JD analysis
      {"scenario": "ambiguous", "ask_user": True}

    The orchestrator decides between jd_in_context and ambiguous based on
    its own conversation context -- this function only looks at the message
    text.
    """
    msg = (user_message or "").strip().lower()
    if not any(verb in msg for verb in APPLY_VERBS):
        return {"scenario": "ambiguous", "ask_user": True}

    m = PROSPECT_ID_RE.search(msg)
    if m:
        return {"scenario": "with_prospect_id", "prospect_id": int(m.group(1))}

    return {"scenario": "jd_in_context"}


# --- Private helpers ---

def _visa_from_analysis(analysis):
    if isinstance(analysis, dict):
        return analysis.get("visa_signal", "")
    return ""


def _resume_from_analysis(analysis):
    if isinstance(analysis, dict):
        return analysis.get("resume", "")
    return ""


def _notes_from_analysis(analysis):
    if isinstance(analysis, dict):
        notes = []
        if "match_pct" in analysis:
            notes.append(f"Match ~{analysis['match_pct']}%.")
        if analysis.get("notes"):
            notes.append(str(analysis["notes"]))
        return " ".join(notes)
    return ""
