---
name: fetch-jobs
description: Run the full prospect refresh pipeline. Pulls fresh job lists from the configured GitHub sources, fetches JDs for new postings, runs the heuristic scorer, and auto-upgrades the actionable subset (state=new + verdict=apply/maybe) to AI scoring. One command, full pipeline.
allowed-tools: Bash
---

The user invoked `/fetch-jobs`. They want fresh prospects in the
pipeline, fully scored.

## What you do

Run the three scrapers in order, then auto-chain the AI upgrade.

### Step 1 - Fetch new prospect rows

```bash
python scripts/fetch_prospects.py
```

This pulls fresh new-grad / SWE job lists from the GitHub repos
configured in `data/prospects/filters.json`, applies the user's
filters, appends new rows to `data/prospects/prospects.json`, and
drops rows that disappeared from the source. State on existing rows
(`new` / `shortlist` / `applied` / `skip`) is preserved.

Fast: usually under 60s.

### Step 2 - Cache the JDs for new prospects

```bash
python scripts/fetch_prospect_jds.py
```

For each NEW prospect (state=new, no cached JD yet), fetches the JD
text from the linked URL and caches it.

Slow: 3-10 minutes depending on how many new postings landed. If the
user wants you to run this in the background, that's fine -- background
it with `&` and tell them.

### Step 3 - Heuristic scoring

```bash
python scripts/score_prospects.py
```

Runs the lazy keyword heuristic to produce
`analysis.verdict / match_pct / resume / visa_signal / notes` for
each new prospect with a cached JD. Writes inline on the row with
`source: "heuristic"`.

Fast: under 30s.

### Step 4 - Auto AI upgrade on the actionable subset

```bash
python scripts/reanalyze.py --tag-auto-to-ai
```

This was previously a separate `/auto-to-ai` command. As of v0.2 it
runs automatically as the last step of `/fetch-jobs` because:
1. It only re-scores the actionable subset (state=new AND
   verdict=apply/maybe AND source=heuristic). Already-skipped or
   already-applied prospects are untouched, so cost stays bounded.
2. Users shouldn't have to remember a separate command to upgrade
   their pipeline.

Default batch defaults are in the reanalyze script; do NOT override
them unless the user asks.

## After completion

Report the four-step result:

```
FETCH COMPLETE
Step 1 (fetch): <N new>, <N dropped>
Step 2 (JD cache): <N fetched>, <N failed>
Step 3 (heuristic): <N scored>
Step 4 (AI upgrade): <N upgraded>, <N skipped>
NEXT: `/dashboard` to open the viewer and triage.
```

If any step errored, surface the error and stop. Do not proceed past
a failed step.

## Edge cases

- Network down -> step 1 fails -> stop, tell user
- No new prospects after step 1 -> skip 2-4, report "0 new"
- Step 4 has nothing to score (all heuristics ranked skip) -> that's
  fine, report "0 targets, queue already clean"
