"""ApplyAsYou — anonymous feedback client.

Sends small, anonymous events to a Supabase backend so the maintainer can
see where the workspace breaks for users in the real world.

Privacy contract
----------------
- No JD text. No resume text. No names. No companies. No emails.
- Events carry only:
  * a per-machine UUID generated at onboarding (`user_id`)
  * the agent that fired (jd-analyzer, email-writer, ...)
  * the trigger_reason (a small fixed enum: re-invoked, manual, etc.)
  * a tiny `context` jsonb of WHITELISTED enum fields only (validated below)
  * `user_message`: free-form text the user typed via /feedback (only set
    for event_type='manual')

The Supabase URL + publishable key are PUBLIC values, safe to commit. RLS
at the database level allows INSERT for anon and blocks SELECT, so even
with the key in hand nobody can read other users' events. If you fork
applyasyou and want telemetry routed to your own Supabase, change the two
constants below.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# --- Public Supabase config (safe to commit; RLS protects the data) ---
SUPABASE_URL = "https://dgtghlpmitnxcplbziux.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_RNa_bun6nVoYnVQsZ5GaZg_QDFeTRtH"
FEEDBACK_ENDPOINT = f"{SUPABASE_URL}/rest/v1/feedback_events"

# --- Local state lives in ~/.applyasyou/ ---
STATE_DIR = Path.home() / ".applyasyou"
USER_ID_FILE = STATE_DIR / "user_id"
FEEDBACK_ENABLED_FILE = STATE_DIR / "feedback_enabled"
FEEDBACK_DISABLED_FILE = STATE_DIR / "feedback_disabled"
NUDGE_STATE_FILE = STATE_DIR / "nudge_state.json"

# --- Enums: the only values allowed in events ---
ALLOWED_EVENT_TYPES = {"auto", "manual"}

ALLOWED_AGENTS = {
    "jd-analyzer", "resume-builder", "resume-validator",
    "bullet-writer", "voice-extractor", "prospect-scorer",
    "email-writer", "onboarding", "manual",
}

ALLOWED_TRIGGERS = {
    "re-invoked",
    "correction-50pct",
    "abandoned",
    "manual",
    "onboarding-pain",
}

ALLOWED_PREV_ACTION = {
    "analyze-jd", "build-tailor", "validate-resume",
    "draft-email", "score-prospect", "extract-voice",
    "intake-project", "write-bullet",
}

ALLOWED_OUTPUT_KIND = {
    "tailor-1page", "tailor-2page",
    "cold-outreach", "thank-you", "status-check",
    "connect-note", "linkedin-dm",
    "jd-analysis", "prospect-score",
    "voice-rules", "project-bullets",
}

# --- Nudge rate limits ---
NUDGE_COOLDOWN_HOURS = 24
NUDGE_BACKOFF_HOURS = 168          # 7 days after 2 consecutive skips
MAX_NUDGES_PER_SESSION = 1
SESSION_BOUNDARY_HOURS = 8         # gap > this = new session


# --- VERSION file (semver of the public repo) ---
def _read_version() -> str:
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "VERSION", here / "VERSION"):
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    return "unknown"


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


# === Identity ===

def get_or_create_user_id() -> str:
    """Stable per-machine UUID. Generated once at onboarding, never changes."""
    _ensure_state_dir()
    if USER_ID_FILE.exists():
        try:
            existing = USER_ID_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
    new_id = str(uuid.uuid4())
    USER_ID_FILE.write_text(new_id, encoding="utf-8")
    return new_id


# === Consent ===

def is_feedback_enabled() -> bool:
    return FEEDBACK_ENABLED_FILE.exists()


def is_feedback_decided() -> bool:
    """True if user has answered the opt-in question (either way)."""
    return FEEDBACK_ENABLED_FILE.exists() or FEEDBACK_DISABLED_FILE.exists()


def set_feedback_consent(enabled: bool) -> None:
    _ensure_state_dir()
    if enabled:
        FEEDBACK_ENABLED_FILE.touch()
        FEEDBACK_DISABLED_FILE.unlink(missing_ok=True)
    else:
        FEEDBACK_DISABLED_FILE.touch()
        FEEDBACK_ENABLED_FILE.unlink(missing_ok=True)


# === Context sanitization (whitelist enum-only fields) ===

def _validate_context(context: dict | None) -> dict:
    if not isinstance(context, dict):
        return {}
    clean: dict = {}
    pa = context.get("prev_action")
    if isinstance(pa, str) and pa in ALLOWED_PREV_ACTION:
        clean["prev_action"] = pa
    ok = context.get("output_kind")
    if isinstance(ok, str) and ok in ALLOWED_OUTPUT_KIND:
        clean["output_kind"] = ok
    ic = context.get("invocation_count_in_session")
    if isinstance(ic, int) and 0 < ic < 100:
        clean["invocation_count_in_session"] = ic
    ss = context.get("seconds_since_prev_event")
    if isinstance(ss, (int, float)) and 0 < ss < 86400:
        clean["seconds_since_prev_event"] = int(ss)
    return clean


# === Nudge rate limiter ===

def _read_nudge_state() -> dict:
    if not NUDGE_STATE_FILE.exists():
        return {
            "last_nudge_ts": None,
            "consecutive_skips": 0,
            "session_nudges": 0,
            "session_start_ts": None,
        }
    try:
        return json.loads(NUDGE_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "last_nudge_ts": None,
            "consecutive_skips": 0,
            "session_nudges": 0,
            "session_start_ts": None,
        }


def _write_nudge_state(state: dict) -> None:
    _ensure_state_dir()
    NUDGE_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def _parse_iso(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def can_nudge_now() -> tuple[bool, str]:
    """Check rate limits. Returns (allowed, reason)."""
    state = _read_nudge_state()
    now = datetime.now(timezone.utc)

    # Rotate session counter if the prior session_start is stale
    session_start = _parse_iso(state.get("session_start_ts"))
    if session_start is None or (now - session_start).total_seconds() > SESSION_BOUNDARY_HOURS * 3600:
        state["session_start_ts"] = now.isoformat()
        state["session_nudges"] = 0

    if state.get("session_nudges", 0) >= MAX_NUDGES_PER_SESSION:
        _write_nudge_state(state)
        return False, "session-cap"

    last = _parse_iso(state.get("last_nudge_ts"))
    if last is not None:
        hours_since = (now - last).total_seconds() / 3600
        cooldown = NUDGE_BACKOFF_HOURS if state.get("consecutive_skips", 0) >= 2 else NUDGE_COOLDOWN_HOURS
        if hours_since < cooldown:
            _write_nudge_state(state)
            return False, "cooldown"

    _write_nudge_state(state)
    return True, "ok"


def record_nudge_fired(user_responded: bool) -> None:
    """Update local nudge bookkeeping after a nudge actually fires.

    user_responded=True   -> user typed something (resets skip counter)
    user_responded=False  -> user dismissed / ignored (increments backoff)
    """
    state = _read_nudge_state()
    state["last_nudge_ts"] = datetime.now(timezone.utc).isoformat()
    state["session_nudges"] = state.get("session_nudges", 0) + 1
    if user_responded:
        state["consecutive_skips"] = 0
    else:
        state["consecutive_skips"] = state.get("consecutive_skips", 0) + 1
    _write_nudge_state(state)


# === The actual sender ===

def send_event(
    agent: str,
    trigger_reason: str,
    context: dict | None = None,
    user_message: str | None = None,
    event_type: str = "auto",
    timeout: float = 5.0,
) -> bool:
    """POST a feedback event to Supabase.

    Silently no-ops if the user opted out, the payload is invalid, or the
    network is unhappy. Returns True only if the event reached Supabase.

    Telemetry must NEVER block user flow. All failure modes are silent.
    """
    if not is_feedback_enabled():
        return False
    if event_type not in ALLOWED_EVENT_TYPES:
        return False
    if agent not in ALLOWED_AGENTS:
        return False
    if trigger_reason not in ALLOWED_TRIGGERS:
        return False

    if user_message is not None:
        user_message = str(user_message)[:2000]

    payload = {
        "user_id": get_or_create_user_id(),
        "event_type": event_type,
        "agent": agent,
        "trigger_reason": trigger_reason,
        "context": _validate_context(context),
        "user_message": user_message,
        "client_version": _read_version(),
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        FEEDBACK_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {SUPABASE_PUBLISHABLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


# === Onboarding opt-in copy ===

OPT_IN_COPY = """\
Quick ask.

Hope this tool helps your search land. The only way I make it
better is hearing where it broke for you. So I built a feedback
channel that's context-free -- no JDs, no resumes, no names. Just
which agent and what felt off. Fully anonymous.

It auto-fires a small event at clear friction moments (re-running
the same agent twice, abandoning a build mid-flow), and you can
send one anytime with /feedback.

Your ID: {user_id}
Email msaisrinivas08@gmail.com anytime to see or delete everything
tied to it.

Opt in? [Y/n]"""


def opt_in_prompt_text() -> str:
    """Formatted opt-in copy with the user's ID embedded."""
    return OPT_IN_COPY.format(user_id=get_or_create_user_id())


# === Convenience for shell-based status checks ===

def status_summary() -> dict:
    """Dict describing current consent + identity state. For diagnostics."""
    return {
        "user_id": get_or_create_user_id() if STATE_DIR.exists() else None,
        "feedback_enabled": is_feedback_enabled(),
        "feedback_decided": is_feedback_decided(),
        "version": _read_version(),
        "state_dir": str(STATE_DIR),
    }


if __name__ == "__main__":
    # `python -m lib.feedback` prints a status JSON, useful for debugging.
    json.dump(status_summary(), sys.stdout, indent=2)
    sys.stdout.write("\n")
