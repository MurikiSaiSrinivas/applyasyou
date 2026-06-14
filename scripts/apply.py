"""CLI wrapper around lib.applications.

Used by:
  - Orchestrator (Claude) when it detects an apply intent in chat
  - Viewer "I applied" button (via local_sink)
  - Gmail sweep when an ATS receipt matches a prospect

Usage:
  # Path A (viewer button) OR user says "applied p#1234"
  python scripts/apply.py with-prospect-id --id 1234

  # User pasted a JD, agent analyzed, user said "applied"
  python scripts/apply.py with-jd-context --jd-file /tmp/last_jd.txt \\
      --role "Forward Deployed AI Engineer" --company "IFS" --link "https://..."

  # jd-analyzer found high-value match, no good existing variant
  python scripts/apply.py tag-tailor --id 1234 --reason "high match, no good variant"

  # Diagnostic: parse a chat message and print the detected intent
  python scripts/apply.py intent --message "applied p#1234"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib import applications  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="apply",
        description="Application state mutations (deterministic).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pid = sub.add_parser("with-prospect-id", help="apply via existing prospect")
    pid.add_argument("--id", type=int, required=True, dest="prospect_id")

    jdc = sub.add_parser("with-jd-context", help="apply from a pasted JD (not in prospects)")
    jdc.add_argument("--jd-file", required=True, help="path to a file containing the JD text")
    jdc.add_argument("--role", default="")
    jdc.add_argument("--company", default="")
    jdc.add_argument("--link", default="")

    tag = sub.add_parser("tag-tailor", help="tag a prospect for human-triggered tailoring")
    tag.add_argument("--id", type=int, required=True, dest="prospect_id")
    tag.add_argument("--reason", required=True)

    intent = sub.add_parser("intent", help="print detected intent for a chat message")
    intent.add_argument("--message", required=True)

    return p


def _emit(result: dict) -> None:
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.cmd == "with-prospect-id":
            _emit(applications.apply_with_prospect_id(args.prospect_id))

        elif args.cmd == "with-jd-context":
            jd_path = Path(args.jd_file).expanduser().resolve()
            if not jd_path.exists():
                sys.stderr.write(f"jd file not found: {jd_path}\n")
                return 2
            jd_text = jd_path.read_text(encoding="utf-8")
            _emit(applications.apply_with_jd_in_context(
                jd_text=jd_text,
                role=args.role,
                company=args.company,
                link=args.link,
            ))

        elif args.cmd == "tag-tailor":
            _emit(applications.tag_for_tailor(args.prospect_id, args.reason))

        elif args.cmd == "intent":
            _emit(applications.detect_apply_intent(args.message))

        return 0

    except applications.ApplicationsError as e:
        sys.stderr.write(f"apply error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
