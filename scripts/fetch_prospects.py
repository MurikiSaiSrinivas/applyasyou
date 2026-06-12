"""Job prospect scraper.

Pulls from the GitHub-curated lists in config.github_sources, applies filters from
data/prospects/filters.json, normalizes date_posted to ISO, preserves user state
across pulls.

Source IDs are yours (config.github_sources keys). The id "jobright" triggers a
column layout specific to the jobright list; any other id uses the standard
4-column markdown / 5-column HTML layouts.

State semantics:
  - "new"       (default) — not reviewed; dropped if absent from next pull
  - "shortlist" — going to apply; preserved across pulls
  - "applied"   — submitted; preserved
  - "skip"      — reviewed and rejected; preserved

Run: python scripts/fetch_prospects.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG_ROOT)
from lib.config import load_config, prospects_dir, github_sources  # noqa: E402
from lib.filters import passes_filters  # noqa: E402

CFG = load_config()
DATA = Path(prospects_dir(CFG))
OUT = DATA / "prospects.json"
META = DATA / "meta.json"
FILTERS = DATA / "filters.json"
TOMBSTONES = DATA / "tombstones.json"
HISTORY = DATA / "fetch_history.json"

SOURCES = github_sources(CFG)
PRESERVED_STATES = {"shortlist", "applied", "skip"}


def append_history(entry: dict) -> None:
    history: list = []
    if HISTORY.exists():
        try:
            history = json.loads(HISTORY.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (ValueError, OSError):
            history = []
    history.append(entry)
    tmp = HISTORY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(HISTORY)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


# ---------- regex helpers ----------
URL_RE = re.compile(r'https?://[^\s)"<>]+')
MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
HREF_RE = re.compile(r'<a[^>]*href="([^"]+)"', re.I)
HTML_TAG_RE = re.compile(r'<[^>]+>')
TR_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.I | re.S)
TD_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.I | re.S)


def strip_html(s: str) -> str:
    return re.sub(r'\s+', ' ', HTML_TAG_RE.sub(" ", s)).strip()


def strip_md_decor(s: str) -> str:
    s = MD_LINK_RE.sub(r'\1', s.strip())
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
    s = re.sub(r'__([^_]+)__', r'\1', s)
    s = re.sub(r'\*([^*]+)\*', r'\1', s)
    return s.strip()


def extract_apply_url(cell: str) -> str | None:
    for href in HREF_RE.findall(cell):
        if "simplify.jobs" in href and "utm_source=Simplify" in href:
            continue
        return href
    m = MD_LINK_RE.search(cell)
    if m:
        return m.group(2)
    m = URL_RE.search(cell)
    return m.group(0) if m else None


FLAGS = {
    "\U0001F6C2": "no_sponsorship",       # passport control
    "\U0001F1FA\U0001F1F8": "citizenship_required",  # US flag
    "\U0001F512": "closed",                # lock
    "\U0001F525": "faang",                 # fire
    "\U0001F393": "advanced_degree",       # graduation cap
}


def extract_flags(text: str) -> list[str]:
    return [v for emoji, v in FLAGS.items() if emoji in text]


def strip_emojis(s: str) -> str:
    for emoji in FLAGS:
        s = s.replace(emoji, "")
    return s.strip()


# ---------- date normalization ----------
MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), start=1)}


def normalize_date(raw: str, today: date) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    m = re.match(r'^(\d+)d$', s)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = re.match(r'^(\d+)mo$', s)
    if m:
        return (today - timedelta(days=int(m.group(1)) * 30)).isoformat()
    m = re.match(r'^(\d+)y$', s)
    if m:
        return (today - timedelta(days=int(m.group(1)) * 365)).isoformat()
    m = re.match(r'^([a-z]{3})\s+(\d+)$', s)
    if m:
        mname, day = m.group(1), int(m.group(2))
        if mname in MONTHS:
            year = today.year
            try:
                d = date(year, MONTHS[mname], day)
            except ValueError:
                return None
            if d > today:
                try:
                    d = date(year - 1, MONTHS[mname], day)
                except ValueError:
                    return None
            return d.isoformat()
    return None


# ---------- parsers ----------
def parse_md_table(text: str, source: str) -> list[dict]:
    lines = text.splitlines()
    rows: list[dict] = []
    last_company: str | None = None
    sep_idx = None
    for i, line in enumerate(lines):
        if re.match(r'\s*\|[\s|:-]+\|\s*$', line) and i > 0 and "|" in lines[i - 1]:
            sep_idx = i
            break
    if sep_idx is None:
        return rows
    for line in lines[sep_idx + 1:]:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        company_raw, role_raw, location_raw = cells[0], cells[1], cells[2]
        link_raw = cells[3] if len(cells) > 3 else ""
        date_raw = cells[-1] if len(cells) > 4 else ""
        work_model = ""
        if source == "jobright" and len(cells) >= 5:
            work_model = cells[3].strip()
            link_raw = cells[1]
            date_raw = cells[4]

        if strip_md_decor(company_raw).strip() == "↳":
            company = last_company or ""
        else:
            company = strip_md_decor(company_raw)

        link_text = strip_html(link_raw).strip()
        if link_text == "\U0001F512" or (link_text and all(c in "\U0001F512 " for c in link_text)):
            continue

        role = strip_md_decor(role_raw)
        location = strip_md_decor(location_raw)
        flags = extract_flags(company_raw + role_raw + link_raw)
        company = strip_emojis(company)
        role = strip_emojis(role)
        if "closed" in flags:
            continue
        apply_url = extract_apply_url(link_raw) or extract_apply_url(role_raw) or extract_apply_url(company_raw)
        if not company or not role:
            continue
        if company.strip() != "↳":
            last_company = company
        rows.append({
            "company": company, "role": role, "location": location,
            "link": apply_url, "date_posted_raw": date_raw,
            "work_model": work_model or None, "flags": flags, "source": source,
        })
    return rows


def parse_html_table(text: str, source: str) -> list[dict]:
    rows: list[dict] = []
    last_company: str | None = None
    for tr in TR_RE.findall(text):
        tds = TD_RE.findall(tr)
        if len(tds) < 5:
            continue
        company_raw, role_raw, location_raw, app_raw, age_raw = tds[:5]
        company_text = strip_html(company_raw)
        if company_text.strip() == "↳":
            company = last_company or ""
        else:
            company = strip_html(company_raw)
            last_company = company
        role = strip_html(role_raw)
        location = re.sub(r'\s+', ' ', strip_html(location_raw)).strip()
        flags = extract_flags(company_raw + role_raw + app_raw)
        company = strip_emojis(company)
        role = strip_emojis(role)
        if "closed" in flags:
            continue
        apply_url = extract_apply_url(app_raw)
        age = strip_html(age_raw)
        if not company or not role:
            continue
        rows.append({
            "company": company, "role": role, "location": location,
            "link": apply_url, "date_posted_raw": age,
            "work_model": None, "flags": flags, "source": source,
        })
    return rows


# ---------- merge across sources ----------
def norm_key(row: dict) -> str:
    co = re.sub(r'\s+', ' ', row["company"].lower().strip())
    ro = re.sub(r'\s+', ' ', row["role"].lower().strip())
    return f"{co}||{ro}"


def merge_rows(rows: list[dict]) -> list[dict]:
    out: dict[str, dict] = {}
    for r in rows:
        k = norm_key(r)
        if k not in out:
            r = dict(r)
            r["sources"] = [r.pop("source")]
            out[k] = r
        else:
            existing = out[k]
            src = r["source"]
            if src not in existing["sources"]:
                existing["sources"].append(src)
            for f in ("link", "location", "date_posted_raw", "work_model"):
                if not existing.get(f) and r.get(f):
                    existing[f] = r[f]
            for fl in r["flags"]:
                if fl not in existing["flags"]:
                    existing["flags"].append(fl)
    return list(out.values())


# ---------- filters: passes_filters imported from lib.filters ----------


# ---------- main ----------
def main() -> None:
    run_started_at = datetime.now().isoformat(timespec="seconds")
    run_start = time.time()

    today = date.today()
    filters = json.loads(FILTERS.read_text(encoding="utf-8")) if FILTERS.exists() else {}

    tombstone_keys: set[str] = set()
    if TOMBSTONES.exists():
        tombs = json.loads(TOMBSTONES.read_text(encoding="utf-8"))
        if isinstance(tombs, dict):
            tombstone_keys = set(tombs.keys())

    seen_cutoff: date | None = None
    if META.exists():
        try:
            prev_meta = json.loads(META.read_text(encoding="utf-8"))
            prev_iso = (prev_meta.get("last_pulled") or "")[:10]
            if prev_iso:
                prev_pull_date = date.fromisoformat(prev_iso)
                if prev_pull_date < today:
                    seen_cutoff = prev_pull_date
        except (ValueError, OSError, KeyError):
            pass

    existing: dict[str, dict] = {}
    if OUT.exists():
        for r in json.loads(OUT.read_text(encoding="utf-8")):
            existing[norm_key(r)] = r

    raw_rows: list[dict] = []
    per_source_raw: dict[str, int] = {}
    for src in SOURCES:
        print(f"Fetching {src['id']}...", file=sys.stderr)
        try:
            text = fetch(src["url"])
        except Exception as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            per_source_raw[src["id"]] = 0
            continue
        parser = parse_md_table if src.get("parser", "md") == "md" else parse_html_table
        rows = parser(text, src["id"])
        per_source_raw[src["id"]] = len(rows)
        raw_rows.extend(rows)
        print(f"  {len(rows)} rows", file=sys.stderr)

    merged = merge_rows(raw_rows)
    for r in merged:
        r["date_posted"] = normalize_date(r.get("date_posted_raw", ""), today)

    filtered: list[dict] = []
    drop_reasons: dict[str, int] = {}
    for r in merged:
        if seen_cutoff and r.get("date_posted"):
            try:
                dp = date.fromisoformat(r["date_posted"])
                if dp <= seen_cutoff:
                    existing_row = existing.get(norm_key(r))
                    if not (existing_row and existing_row.get("state") in PRESERVED_STATES):
                        drop_reasons["seen_in_prev_fetch"] = drop_reasons.get("seen_in_prev_fetch", 0) + 1
                        continue
            except ValueError:
                pass

        if norm_key(r) in tombstone_keys:
            drop_reasons["tombstoned"] = drop_reasons.get("tombstoned", 0) + 1
            continue
        ok, reason = passes_filters(r, filters)
        if ok:
            filtered.append(r)
        else:
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1

    grace_days = int(filters.get("grace_days", 0) or 0)
    if grace_days > 0:
        before = len(filtered)
        kept = []
        for r in filtered:
            dp = r.get("date_posted")
            if not dp:
                kept.append(r)
                continue
            existing_row = existing.get(norm_key(r))
            if existing_row and existing_row.get("state") in PRESERVED_STATES:
                kept.append(r)
                continue
            try:
                d = date.fromisoformat(dp)
            except (ValueError, TypeError):
                kept.append(r)
                continue
            if (today - d).days > grace_days:
                drop_reasons["aged_out"] = drop_reasons.get("aged_out", 0) + 1
                continue
            kept.append(r)
        filtered = kept
        print(f"Age-out: dropped {before - len(filtered)} rows older than {grace_days}d", file=sys.stderr)

    pulled_keys = {norm_key(r) for r in filtered}
    existing_keys = set(existing.keys())
    missing_keys = existing_keys - pulled_keys

    next_id = max((r.get("id", 0) for r in existing.values()), default=0) + 1
    result: list[dict] = []
    new_added = 0
    refreshed = 0

    for r in filtered:
        k = norm_key(r)
        if k in existing:
            old = existing[k]
            r["id"] = old.get("id", next_id)
            r["state"] = old.get("state", "new")
            r["notes"] = old.get("notes", "")
            refreshed += 1
        else:
            r["id"] = next_id
            next_id += 1
            r["state"] = "new"
            r["notes"] = ""
            new_added += 1
        result.append(r)

    preserved_missing = 0
    dropped_missing = 0
    for k in missing_keys:
        old = existing[k]
        if old.get("state") in PRESERVED_STATES:
            result.append(old)
            preserved_missing += 1
        else:
            dropped_missing += 1

    result.sort(key=lambda r: (r.get("date_posted") or "0000-00-00", r.get("id", 0)), reverse=True)

    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = {
        "last_pulled": datetime.now().isoformat(timespec="seconds"),
        "per_source_raw": per_source_raw,
        "totals": {
            "raw": sum(per_source_raw.values()),
            "unique_after_merge": len(merged),
            "passed_filters": len(filtered),
            "in_prospects": len(result),
        },
        "delta": {
            "new_added": new_added,
            "refreshed": refreshed,
            "missing_in_pull": len(missing_keys),
            "preserved_due_to_user_state": preserved_missing,
            "dropped_missing": dropped_missing,
        },
        "filter_drops": drop_reasons,
        "state_breakdown": {
            s: sum(1 for r in result if r.get("state") == s)
            for s in ("new", "shortlist", "applied", "skip")
        },
    }
    META.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    append_history({
        "type": "scrape_run",
        "at": run_started_at,
        "duration_s": round(time.time() - run_start, 2),
        "per_source_raw": per_source_raw,
        "after_merge": len(merged),
        "filter_drops": drop_reasons,
        "passed_filters": len(filtered),
        "new_added": new_added,
        "refreshed": refreshed,
        "missing_in_pull": len(missing_keys),
        "missing_kept_user_state": preserved_missing,
        "missing_dropped": dropped_missing,
        "prospects_after": len(result),
        "state_breakdown": stats["state_breakdown"],
    })

    print()
    print(f"Per source raw:    {per_source_raw}")
    print(f"After merge:       {len(merged)}")
    print(f"Filter drops:      {drop_reasons}")
    print(f"Passed filters:    {len(filtered)}")
    print(f"New added:         {new_added}")
    print(f"Refreshed:         {refreshed}")
    print(f"Missing kept:      {preserved_missing}")
    print(f"Missing dropped:   {dropped_missing}")
    print(f"Total in file:     {len(result)}")
    print(f"State breakdown:   {stats['state_breakdown']}")
    print(f"Wrote {OUT} and {META}")


if __name__ == "__main__":
    main()
