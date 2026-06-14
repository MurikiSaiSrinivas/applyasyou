"""CLI wrapper around lib.feedback.send_event for use by agents.

Agents (which are markdown prompts, not Python) can't call Python functions
directly. They call this script via shell to fire telemetry events.

Usage examples:

  # Auto event: jd-analyzer was re-invoked on the same JD twice in 5 min
  python scripts/feedback_event.py auto jd-analyzer re-invoked \\
      --prev-action analyze-jd --output-kind jd-analysis \\
      --invocation-count 2

  # Manual event from the /feedback slash command
  python scripts/feedback_event.py manual manual manual \\
      --message "the email-writer keeps adding em dashes"

  # Onboarding pain question at the end of onboarding
  python scripts/feedback_event.py manual onboarding onboarding-pain \\
      --message "tailoring step felt confusing"

  # Status check (no event sent, just print current state)
  python scripts/feedback_event.py status

Exit code is ALWAYS 0 so the calling agent never fails because of telemetry.
A `silent=true` line goes to stderr if the event was dropped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the lib/ package importable whether you run this from repo root or
# from inside scripts/.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib import feedback  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="feedback_event",
        description="Send a feedback event (or print status).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    auto = sub.add_parser("auto", help="auto-fired event from an agent")
    auto.add_argument("agent", choices=sorted(feedback.ALLOWED_AGENTS))
    auto.add_argument("trigger_reason", choices=sorted(feedback.ALLOWED_TRIGGERS))
    auto.add_argument("--prev-action", choices=sorted(feedback.ALLOWED_PREV_ACTION))
    auto.add_argument("--output-kind", choices=sorted(feedback.ALLOWED_OUTPUT_KIND))
    auto.add_argument("--invocation-count", type=int)
    auto.add_argument("--seconds-since-prev", type=int)

    manual = sub.add_parser("manual", help="user-typed event")
    manual.add_argument("agent", choices=sorted(feedback.ALLOWED_AGENTS))
    manual.add_argument("trigger_reason", choices=sorted(feedback.ALLOWED_TRIGGERS))
    manual.add_argument("--message", required=True)
    manual.add_argument("--prev-action", choices=sorted(feedback.ALLOWED_PREV_ACTION))
    manual.add_argument("--output-kind", choices=sorted(feedback.ALLOWED_OUTPUT_KIND))

    sub.add_parser("status", help="print current consent + identity state as JSON")

    return p


def _context_from_args(args: argparse.Namespace) -> dict:
    ctx: dict = {}
    if getattr(args, "prev_action", None):
        ctx["prev_action"] = args.prev_action
    if getattr(args, "output_kind", None):
        ctx["output_kind"] = args.output_kind
    if getattr(args, "invocation_count", None) is not None:
        ctx["invocation_count_in_session"] = args.invocation_count
    if getattr(args, "seconds_since_prev", None) is not None:
        ctx["seconds_since_prev_event"] = args.seconds_since_prev
    return ctx


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "status":
        json.dump(feedback.status_summary(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    sent = feedback.send_event(
        agent=args.agent,
        trigger_reason=args.trigger_reason,
        context=_context_from_args(args),
        user_message=getattr(args, "message", None),
        event_type=args.cmd,  # "auto" or "manual"
    )
    if not sent:
        # Diagnostic ONLY (stderr); never fail the calling agent.
        sys.stderr.write("feedback_event: silent (opt-out or transport error)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
