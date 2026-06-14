"""ApplyAsYou -- Gmail sweep helpers (deterministic side).

The gmail-sweeper agent (markdown prompt) does the LLM-mediated work:
search inbox via Gmail MCP tools, iterate threads, decide what each one
means. For every concrete event it decides on, it calls these functions
to mutate state.

This module owns:
  - Email classification heuristics (rejection vs job-closed vs ATS receipt
    vs noise) as a sanity-check the agent can call
  - The dual-write contract for closing an application
  - Updating data/last_email_check.json
  - Detecting "is this sweep overdue" for the session-start nudge

The agent owns prose interpretation; these functions own the data layer.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


# --- Workspace layout ---
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DATA_DIR = REPO_ROOT / "data"
ACTIVE_FILE = DATA_DIR / "active.json"
CLOSED_FILE = DATA_DIR / "closed.json"
PROSPECTS_FILE = DATA_DIR / "prospects" / "prospects.json"
LAST_CHECK_FILE = DATA_DIR / "last_email_check.json"

# --- Defaults ---
SWEEP_STALE_DAYS = 2


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_id(rows) -> int:
    if not rows:
        return 1
    return max(int(r.get("id", 0)) for r in rows) + 1


# --- Email classification ---

REJECTION_PHRASES = (
    "not moving forward",
    "moving forward with other candidates",
    "decided not to move forward",
    "won't be moving forward",
    "unable to offer",
    "regret to inform",
    "unfortunately",
    "not be moving forward",
    "after carefully reviewing",
    "carefully reviewed your application",
    "we have decided not to proceed",
)

JOB_CLOSED_PHRASES = (
    "this requisition has been closed",
    "the position has been filled",
    "position is no longer available",
    "no longer accepting applications",
    "the role has been closed",
    "requisition closed",
    "filled internally",
)

ATS_RECEIPT_SENDERS = (
    "no-reply@ashbyhq.com",
    "notification@smartrecruiters.com",
    "no-reply@us.greenhouse-mail.io",
    "donotreply@myworkday.com",
    "noreply@workday.com",
    "no-reply@lever.co",
    "noreply@tesla.com",
)

ATS_RECEIPT_SUBJECT_HINTS = (
    "thank you for applying",
    "thank you for your application",
    "we received your application",
    "application received",
    "your application has been received",
)


def classify_email(sender: str, subject: str, body: str) -> dict:
    """Return a small dict describing what this email looks like.

    Output:
      {"kind": "rejection",     "confidence": "high" | "medium"}
      {"kind": "job_closed",    "confidence": "high" | "medium"}
      {"kind": "ats_receipt",   "confidence": "high" | "medium"}
      {"kind": "noise",         "confidence": "high"}

    Heuristic only -- the agent should still read the body and override
    if needed. This is a sanity check, not a rule of law.
    """
    s = (sender or "").lower()
    subj = (subject or "").lower()
    body_l = (body or "").lower()

    if any(p in body_l for p in JOB_CLOSED_PHRASES):
        return {"kind": "job_closed", "confidence": "high"}

    if any(p in body_l for p in REJECTION_PHRASES):
        return {"kind": "rejection", "confidence": "high"}

    if any(sender_hint in s for sender_hint in ATS_RECEIPT_SENDERS):
        if any(h in subj for h in ATS_RECEIPT_SUBJECT_HINTS):
            return {"kind": "ats_receipt", "confidence": "high"}
        if any(p in body_l for p in REJECTION_PHRASES):
            return {"kind": "rejection", "confidence": "high"}

    if any(h in subj for h in ATS_RECEIPT_SUBJECT_HINTS):
        return {"kind": "ats_receipt", "confidence": "medium"}

    return {"kind": "noise", "confidence": "high"}


# --- Active row matching ---

def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match_active_row(company: str, role: str = "") -> dict | None:
    """Find a row in active.json whose company (and optionally role) match.

    Soft matching: case-insensitive, alphanumeric-only normalize on both
    sides. Returns the row dict or None. If multiple match, returns the
    most recently applied one.
    """
    company_n = _normalize(company)
    if not company_n:
        return None
    role_n = _normalize(role)

    rows = _read_json(ACTIVE_FILE, [])
    candidates = []
    for r in rows:
        r_company_n = _normalize(r.get("company", ""))
        if company_n not in r_company_n and r_company_n not in company_n:
            continue
        if role_n:
            r_role_n = _normalize(r.get("role", ""))
            if role_n not in r_role_n and r_role_n not in role_n:
                continue
        candidates.append(r)

    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("date_applied", ""), reverse=True)
    return candidates[0]


# --- Closure mutation ---

class SweepError(Exception):
    pass


def close_active_row(
    active_id: int,
    kind: str,
    why: str,
    lessons: str = "",
) -> dict:
    """Move a row from active.json to closed.json.

    kind: "rejection" | "job_closed" | "withdrawn" | "offer"
    """
    if kind not in {"rejection", "job_closed", "withdrawn", "offer"}:
        raise SweepError(f"invalid closure kind: {kind}")

    active_rows = _read_json(ACTIVE_FILE, [])
    target = None
    remaining = []
    for r in active_rows:
        if r.get("id") == active_id:
            target = r
        else:
            remaining.append(r)
    if target is None:
        raise SweepError(f"active id {active_id} not found")

    closed_rows = _read_json(CLOSED_FILE, [])
    closed_row = {
        "id": target.get("id"),
        "company": target.get("company", ""),
        "role": target.get("role", ""),
        "outcome": _outcome_label(kind),
        "date": _today_iso(),
        "why": why,
        "lessons": lessons,
        "date_applied": target.get("date_applied", ""),
        "link": target.get("link", ""),
    }
    # Preserve prospect linkage so the viewer can still cross-reference
    if target.get("_prospect_id") is not None:
        closed_row["_prospect_id"] = target["_prospect_id"]

    # Closed file is reverse-chronological (newest first) per convention
    closed_rows.insert(0, closed_row)

    _write_json(ACTIVE_FILE, remaining)
    _write_json(CLOSED_FILE, closed_rows)

    return {"status": "closed", "active_id": active_id, "outcome": closed_row["outcome"]}


def _outcome_label(kind: str) -> str:
    return {
        "rejection": "reject (boilerplate)",
        "job_closed": "job closed",
        "withdrawn": "withdrawn",
        "offer": "offer",
    }[kind]


# --- Last sweep tracking ---

def write_last_check(
    rejections_found: int,
    rejections_logged: int,
    matched_closed_ids: list[int],
    companies_rejected: list[str],
    application_receipts: int = 0,
    application_receipts_note: str = "",
    drafts_created: list | None = None,
    silent_thread_status: dict | None = None,
    noise_pattern: str = "",
    lookback_days: int = 3,
) -> None:
    data = {
        "_note": (
            "Tracks the last time agent ran a Gmail sweep for rejection/status "
            "updates. Written by Claude when sweep completes. Read on next sweep "
            "to know how far back to search."
        ),
        "last_checked_at": _now_iso(),
        "lookback_days": lookback_days,
        "search_window": {
            "from_date": (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat(),
            "to_date": _today_iso(),
        },
        "result_summary": {
            "rejections_found": rejections_found,
            "rejections_logged": rejections_logged,
            "matched_closed_ids": matched_closed_ids,
            "companies_rejected": companies_rejected,
            "application_receipts": application_receipts,
            "application_receipts_note": application_receipts_note,
            "drafts_created": drafts_created or [],
            "silent_thread_status": silent_thread_status or {},
            "noise_pattern": noise_pattern,
        },
    }
    _write_json(LAST_CHECK_FILE, data)


def is_sweep_overdue(stale_days: int = SWEEP_STALE_DAYS) -> dict:
    """Used by the session-start nudge.

    Returns:
      {"overdue": True,  "days_since": <int>, "last_checked_at": <iso>}
      {"overdue": False, "days_since": <int>, "last_checked_at": <iso>}
      {"overdue": True,  "days_since": None, "last_checked_at": None}   # never swept
    """
    data = _read_json(LAST_CHECK_FILE, None)
    if data is None or "last_checked_at" not in data:
        return {"overdue": True, "days_since": None, "last_checked_at": None}

    try:
        last = datetime.fromisoformat(data["last_checked_at"])
    except (TypeError, ValueError):
        return {"overdue": True, "days_since": None, "last_checked_at": None}

    delta = datetime.now(timezone.utc) - last
    days_since = max(0, delta.days)
    return {
        "overdue": days_since >= stale_days,
        "days_since": days_since,
        "last_checked_at": data["last_checked_at"],
    }
