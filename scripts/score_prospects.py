"""Heuristic verdict generator for prospects without an analysis yet.

For each new prospect with a cached JD, scores stack overlap, picks a resume,
and sets a verdict using config.json. The scoring logic lives in lib/scoring.py
(shared with the sink's auto-score path); this is the batch CLI over it.

Run:
  python scripts/score_prospects.py
  python scripts/score_prospects.py --force   # re-score all
"""
import argparse
import json
import os
import sys

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG_ROOT)
from lib.config import load_config, prospects_dir  # noqa: E402
from lib.scoring import score_prospect  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-score all prospects (overwrite existing)")
    args = ap.parse_args()

    cfg = load_config()
    pdir = prospects_dir(cfg)
    prospects_path = os.path.join(pdir, "prospects.json")
    cache_path = os.path.join(pdir, "jd_cache.json")

    with open(prospects_path, encoding="utf-8") as f:
        prospects = json.load(f)
    with open(cache_path, encoding="utf-8") as f:
        cache = json.load(f)

    scored = skipped = no_jd = 0
    by_verdict = {"apply": 0, "maybe": 0, "skip": 0}
    for r in prospects:
        pid = str(r.get("id"))
        existing = r.get("analysis") or {}
        has_real_analysis = existing.get("source") and existing.get("source") != "unanalyzed"
        if has_real_analysis and not args.force:
            skipped += 1
            continue
        if r.get("state") == "applied":
            continue
        ce = cache.get(pid)
        if not ce or ce.get("status") != "success" or not ce.get("jd_text"):
            no_jd += 1
            continue
        entry = score_prospect(r, ce["jd_text"], cfg)
        r["analysis"] = entry
        scored += 1
        by_verdict[entry["verdict"]] = by_verdict.get(entry["verdict"], 0) + 1

    tmp = prospects_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prospects, f, indent=2, ensure_ascii=False)
    os.replace(tmp, prospects_path)

    print(f"Scored {scored} new prospects. (skipped_existing={skipped}, no_jd={no_jd})")
    if scored:
        print(f"  apply={by_verdict.get('apply', 0)}  maybe={by_verdict.get('maybe', 0)}  skip={by_verdict.get('skip', 0)}")


if __name__ == "__main__":
    main()
