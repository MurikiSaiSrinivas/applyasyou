"""CLI wrapper around lib.sweep.

The gmail-sweeper agent (markdown prompt) iterates Gmail threads via the
Gmail MCP and calls this CLI for each event it needs to record. The
session-start nudge logic uses the `overdue` subcommand.

Subcommands:

  classify          Print {kind, confidence} for an email by sender+subject+body
  match-active      Find a matching active.json row by company (and optional role)
  close             Move an active.json row to closed.json
  write-last-check  Write a summary block to data/last_email_check.json
  overdue           Print {overdue, days_since, last_checked_at} for the
                    session-start nudge

Usage examples:

  python scripts/sweep.py classify \\
      --sender "no-reply@ashbyhq.com" \\
      --subject "Regarding Your Application at Zip" \\
      --body "after carefully reviewing your background..."

  python scripts/sweep.py match-active --company "Zip" --role "Forward Deployed"

  python scripts/sweep.py close --id 165 --kind rejection \\
      --why "Ashby boilerplate reject 2026-06-12 16:14 UTC"

  python scripts/sweep.py overdue

Exit codes:
  0  success
  1  domain error (e.g. id not found)
  2  bad CLI args
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from lib import sweep  # noqa: E402


def _emit(result) -> None:
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sweep", description="Gmail sweep helpers.")
    sub = p.add_subparsers(dest="cmd", required=True)

    cls = sub.add_parser("classify")
    cls.add_argument("--sender", default="")
    cls.add_argument("--subject", default="")
    cls.add_argument("--body", default="")

    ma = sub.add_parser("match-active")
    ma.add_argument("--company", required=True)
    ma.add_argument("--role", default="")

    close = sub.add_parser("close")
    close.add_argument("--id", type=int, required=True, dest="active_id")
    close.add_argument("--kind", required=True,
                       choices=["rejection", "job_closed", "withdrawn", "offer"])
    close.add_argument("--why", required=True)
    close.add_argument("--lessons", default="")

    wlc = sub.add_parser("write-last-check")
    wlc.add_argument("--rejections-found", type=int, default=0)
    wlc.add_argument("--rejections-logged", type=int, default=0)
    wlc.add_argument("--matched-closed-ids", default="[]",
                     help="JSON list of ints, e.g. '[165, 176]'")
    wlc.add_argument("--companies-rejected", default="[]",
                     help="JSON list of strings")
    wlc.add_argument("--application-receipts", type=int, default=0)
    wlc.add_argument("--application-receipts-note", default="")
    wlc.add_argument("--drafts-created", default="[]",
                     help="JSON list of draft objects")
    wlc.add_argument("--silent-thread-status", default="{}",
                     help="JSON dict")
    wlc.add_argument("--noise-pattern", default="")
    wlc.add_argument("--lookback-days", type=int, default=3)

    sub.add_parser("overdue")

    return p


def _parse_json_arg(raw: str, default):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.cmd == "classify":
            _emit(sweep.classify_email(args.sender, args.subject, args.body))

        elif args.cmd == "match-active":
            row = sweep.match_active_row(args.company, args.role)
            _emit(row or {"match": None})

        elif args.cmd == "close":
            _emit(sweep.close_active_row(
                active_id=args.active_id,
                kind=args.kind,
                why=args.why,
                lessons=args.lessons,
            ))

        elif args.cmd == "write-last-check":
            sweep.write_last_check(
                rejections_found=args.rejections_found,
                rejections_logged=args.rejections_logged,
                matched_closed_ids=_parse_json_arg(args.matched_closed_ids, []),
                companies_rejected=_parse_json_arg(args.companies_rejected, []),
                application_receipts=args.application_receipts,
                application_receipts_note=args.application_receipts_note,
                drafts_created=_parse_json_arg(args.drafts_created, []),
                silent_thread_status=_parse_json_arg(args.silent_thread_status, {}),
                noise_pattern=args.noise_pattern,
                lookback_days=args.lookback_days,
            )
            _emit({"status": "written"})

        elif args.cmd == "overdue":
            _emit(sweep.is_sweep_overdue())

        return 0

    except sweep.SweepError as e:
        sys.stderr.write(f"sweep error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
