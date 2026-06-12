"""Re-analyze heuristic-scored prospects with a real LLM, in batches.

Upgrades prospects whose analysis.source == "heuristic" to a real LLM verdict
(source="claude"... here, source="llm"). The LLM is whatever you configured in
config.llm_cli — see lib/llm_client.py. The candidate profile and resume options
come from config.llm_profile, so the prompt is yours, not anyone else's.

DEFAULTS:
  --batch-size 5   prospects per LLM call (fewer total process spawns)
  --cooldown 10    seconds between batches

Run:
  python scripts/reanalyze.py
  python scripts/reanalyze.py --batch-size 5 --cooldown 2
  python scripts/reanalyze.py --state new --limit 10
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG_ROOT)
from lib.config import (  # noqa: E402
    load_config, prospects_dir, resume_clusters, llm_profile,
)
from lib.llm_client import call_llm  # noqa: E402

MAX_JD_CHARS_PER_PROSPECT = 2500


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resume_options(cfg):
    """Return [(path, description), ...]. Descriptions come from
    config.llm_profile.resume_descriptions; fall back to the cluster keywords."""
    descs = (llm_profile(cfg) or {}).get("resume_descriptions", {}) or {}
    clusters = resume_clusters(cfg)
    opts = []
    for path in clusters:
        d = descs.get(path) or ("keywords: " + ", ".join(clusters[path][:10]))
        opts.append((path, d))
    # Include any description-only resumes not in clusters
    for path, d in descs.items():
        if path not in clusters:
            opts.append((path, d))
    return opts


def build_batch_prompt(batch, cfg):
    prof = llm_profile(cfg) or {}
    opts = resume_options(cfg)
    resume_keys = {p for p, _ in opts}
    resume_block = "\n".join(f"  - `{p}` -- {d}" for p, d in opts)

    blockers = prof.get("hard_blockers") or []
    blockers_block = "\n".join(f"{i+1}. {b}" for i, b in enumerate(blockers)) or "(none configured)"

    jobs_parts = []
    for r, jd in batch:
        jobs_parts.append(f"""
==== PROSPECT_ID: {r['id']} ====
Company: {r.get('company', '?')}
Role: {r.get('role', '?')}
Location: {r.get('location', '?')}
Work model: {r.get('work_model', '?')}
JD (truncated):
{jd[:MAX_JD_CHARS_PER_PROSPECT]}
==== END_PROSPECT_ID: {r['id']} ====
""")
    jobs_block = "\n".join(jobs_parts)

    return f"""You are evaluating {len(batch)} job postings against this candidate's profile.

CANDIDATE PROFILE:
{prof.get('candidate_summary', '(no summary configured)')}
Work authorization: {prof.get('work_authorization', 'not specified')}

HARD BLOCKERS (only these => skip):
{blockers_block}

SOFT SIGNALS (mention, don't skip on): {prof.get('soft_signals_note', 'title/comp/relocation mismatches')}

VERDICT CUTOFFS: apply >= 65, maybe 45-64, skip < 45 OR a hard blocker.

RESUME OPTIONS (pick one path, or null if verdict=skip):
{resume_block}

JOBS TO EVALUATE:
{jobs_block}

OUTPUT FORMAT — return ONLY a single JSON array (no prose, no markdown fence) with one
object per prospect, in the same order. Each object MUST have these exact keys:
[
  {{
    "id": <int — the PROSPECT_ID from the input>,
    "verdict": "apply" | "maybe" | "skip",
    "match_pct": <int 0-100>,
    "resume": <one of the resume paths above, or null if skip>,
    "visa_signal": "ok" | "not_declared" | "low" | "us_citizen_only" | "n/a",
    "notes": "<= 280 chars: company + location + comp band + 1-2 sentence honest assessment. No fluff."
  }}
]
Return exactly {len(batch)} objects. The "id" field must match one PROSPECT_ID per object.""", resume_keys


def parse_batch_response(text, expected_ids, resume_keys):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    start = t.find("[")
    end = t.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {text[:300]}")
    arr = json.loads(t[start:end + 1])
    if not isinstance(arr, list):
        raise ValueError(f"expected list, got {type(arr).__name__}")

    by_id = {}
    for obj in arr:
        if not isinstance(obj, dict):
            continue
        try:
            pid = int(obj.get("id"))
        except (TypeError, ValueError):
            continue
        for k in ("verdict", "match_pct", "resume", "visa_signal", "notes"):
            if k not in obj:
                raise ValueError(f"missing key '{k}' in object id={pid}: {obj}")
        if obj["verdict"] not in ("apply", "maybe", "skip"):
            raise ValueError(f"bad verdict for id={pid}: {obj['verdict']}")
        obj["match_pct"] = int(obj["match_pct"])
        if obj["resume"] is not None and obj["resume"] not in resume_keys:
            coerced = None
            for p in resume_keys:
                if obj["resume"].replace("/", "\\").lower() == p.lower():
                    coerced = p
                    break
            if coerced:
                obj["resume"] = coerced
            else:
                raise ValueError(f"resume not allowed for id={pid}: {obj['resume']!r}")
        by_id[pid] = obj

    missing = [pid for pid in expected_ids if pid not in by_id]
    if missing:
        raise ValueError(f"response missing prospects: {missing}")
    return [by_id[pid] for pid in expected_ids]


def state_priority(state):
    return {"new": 0, "skip": 1, "applied": 2}.get(state, 9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--state", default=None, choices=["new", "skip", "applied"])
    ap.add_argument("--id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cooldown", type=float, default=10.0)
    args = ap.parse_args()

    cfg = load_config()
    pdir = prospects_dir(cfg)
    prospects_path = os.path.join(pdir, "prospects.json")
    cache_path = os.path.join(pdir, "jd_cache.json")

    with open(prospects_path, encoding="utf-8") as f:
        prospects = json.load(f)
    with open(cache_path, encoding="utf-8") as f:
        cache = json.load(f)

    targets = []
    for r in prospects:
        a = r.get("analysis") or {}
        if a.get("source") != "heuristic":
            continue
        if args.id is not None and r.get("id") != args.id:
            continue
        if args.state is not None and r.get("state") != args.state:
            continue
        ce = cache.get(str(r["id"])) or {}
        if ce.get("status") != "success" or not ce.get("jd_text"):
            continue
        targets.append(r)

    targets.sort(key=lambda r: (state_priority(r.get("state", "?")), r.get("id", 0)))
    print(f"Targets: {len(targets)} heuristic prospects with cached JDs")
    if args.limit:
        targets = targets[:args.limit]
        print(f"(limited to first {args.limit})")
    if args.dry_run:
        n = (len(targets) + args.batch_size - 1) // args.batch_size
        print(f"Would run {n} batches of {args.batch_size}.")
        return

    batches = []
    for i in range(0, len(targets), args.batch_size):
        chunk = targets[i:i + args.batch_size]
        batches.append([(r, cache[str(r["id"])]["jd_text"]) for r in chunk])

    succeeded = failed = 0
    start = time.time()
    for bi, batch in enumerate(batches, 1):
        prompt, resume_keys = build_batch_prompt(batch, cfg)
        ids = [r["id"] for r, _ in batch]
        t0 = time.time()
        try:
            raw = call_llm(prompt, cfg)
            parsed_list = parse_batch_response(raw, ids, resume_keys)
        except Exception as e:
            print(f"  batch {bi}/{len(batches)} ids={ids} FAIL: {e}", flush=True)
            failed += len(batch)
            time.sleep(args.cooldown)
            continue
        dt = time.time() - t0

        for (r, _), parsed in zip(batch, parsed_list):
            r["analysis"] = {
                "verdict": parsed["verdict"],
                "match_pct": parsed["match_pct"],
                "resume": parsed["resume"],
                "visa_signal": parsed["visa_signal"],
                "notes": parsed["notes"],
                "source": "llm",
                "analyzed_at": now_iso(),
            }

        tmp = prospects_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(prospects, f, indent=2, ensure_ascii=False)
        os.replace(tmp, prospects_path)

        succeeded += len(batch)
        line = f"  batch {bi}/{len(batches)} ({len(batch)} prospects, {dt:.1f}s): "
        line += ", ".join(
            f"p#{r['id']}={p['verdict']}/{p['match_pct']}%"
            for (r, _), p in zip(batch, parsed_list)
        )
        print(line, flush=True)
        time.sleep(args.cooldown)

    total_min = (time.time() - start) / 60
    print(f"\nDone. Succeeded={succeeded} Failed={failed} ({total_min:.1f} min)")


if __name__ == "__main__":
    main()
