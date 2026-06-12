"""fetch_prospect_jds.py — pull job-description text for each row in
data/prospects/prospects.json and cache it to data/prospects/jd_cache.json.
Best-effort: skip + move on when a row can't be fetched.

Run:
  python scripts/fetch_prospect_jds.py              # all prospects
  python scripts/fetch_prospect_jds.py --limit 20   # first 20 only
  python scripts/fetch_prospect_jds.py --retry-failed
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG_ROOT)
from lib.config import load_config, prospects_dir  # noqa: E402

PRESERVED_STATES = {"shortlist", "applied", "skip"}


def is_aged_out(date_iso, grace_days, today):
    if not date_iso or grace_days <= 0:
        return False
    try:
        d = date.fromisoformat(date_iso)
    except (ValueError, TypeError):
        return False
    return (today - d).days > grace_days


try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.stderr.write(
        "Missing deps. Install with:\n"
        "  python -m pip install requests beautifulsoup4\n"
    )
    sys.exit(1)

CFG = load_config()
PDIR = prospects_dir(CFG)
PROSPECTS_PATH = os.path.join(PDIR, "prospects.json")
CACHE_PATH = os.path.join(PDIR, "jd_cache.json")
FILTERS_PATH = os.path.join(PDIR, "filters.json")
TOMBSTONES_PATH = os.path.join(PDIR, "tombstones.json")
HISTORY_PATH = os.path.join(PDIR, "fetch_history.json")
META_PATH = os.path.join(PDIR, "meta.json")


def append_history(entry):
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except (ValueError, OSError):
            history = []
    history.append(entry)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    os.replace(tmp, HISTORY_PATH)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)
TIMEOUT_S = 15
PER_DOMAIN_DELAY_S = 1.5
SAVE_EVERY = 25
RETRY_FAILED_AFTER_DAYS = 7


# ---------- JD-level kill patterns (US work-authorization). Generic. ----------
VISA_KILL_PATTERNS = [
    r"\b(?:must\s+be|require[ds]?|only\s+(?:hiring|consider))\s+(?:a\s+)?u\.?\s?s\.?\s+citizen",
    r"\bu\.?\s?s\.?\s+citizen(?:ship)?\s+(?:is\s+)?(?:required|mandatory|a\s+must)",
    r"\bu\.?\s?s\.?\s+citizens?\s+(?:and|or)\s+(?:green\s+card|permanent\s+resident|lawful\s+permanent)",
    r"\bu\.?\s?s\.?\s+citizens?\s+or\s+permanent\s+residents?\s+only",
    r"\bgreen\s+card\s+holders?\s+only",
    r"\bpermanent\s+resident(?:s)?\s+only",
    r"\bcitizens?\s+of\s+the\s+united\s+states",
    r"(?:does\s+not|cannot|will\s+not|unable\s+to|not\s+able\s+to)\s+(?:offer|provide|support|sponsor)\s+(?:visa\s+|work\s+|employment\s+)?(?:sponsorship|visas?)",
    r"\bno\s+(?:visa\s+|work\s+|employment\s+)?sponsorship\s+(?:is\s+|will\s+be\s+)?(?:offered|available|provided)?",
    r"sponsorship\s+(?:is\s+)?not\s+(?:offered|available|provided|possible)",
    r"unable\s+to\s+sponsor",
    r"without\s+(?:current\s+or\s+future\s+)?sponsorship",
    r"no\s+current\s+or\s+future\s+sponsorship",
    r"\b(?:top\s+secret|ts/sci|sci)\s+(?:clearance|with)",
    r"\bsecurity\s+clearance\s+(?:is\s+)?(?:required|needed|necessary|mandatory)",
    r"\bactive\s+(?:secret|top\s+secret|dod|government|federal)\s+clearance",
    r"\bpoly(?:graph)?\s+(?:required|examination|test)",
    r"\bmust\s+(?:be\s+able\s+to\s+)?(?:obtain|hold|pass|possess)\s+(?:and\s+maintain\s+)?(?:a\s+)?(?:secret|top\s+secret|sci|ts\b|polygraph)",
    r"\bitar\b",
    r"\bear\s+(?:restricted|controlled|regulated)",
    r"\bexport\s+control(?:led|s|\s+regulation)",
    r"\bus\s+person\s+(?:status|requirement|only)",
]
VISA_KILL_RE = re.compile("|".join(VISA_KILL_PATTERNS), re.I)


def apply_jd_kills(jd_text, role, filters):
    m = VISA_KILL_RE.search(jd_text)
    if m:
        snippet = jd_text[max(0, m.start() - 20):m.end() + 40].replace("\n", " ")
        return True, f"visa: '{m.group(0).strip()[:60]}' (...{snippet[:80]}...)"

    head = jd_text[:1500].lower()
    for kw in filters.get("role_exclude", []):
        kw_lc = kw.lower().strip()
        if not kw_lc:
            continue
        if re.search(r"(?<!\w)" + re.escape(kw_lc) + r"(?!\w)", head):
            return True, f"title: '{kw}' in JD head"
    for kw in filters.get("seniority_exclude", []):
        kw_lc = kw.lower().strip()
        if not kw_lc:
            continue
        if re.search(r"(?<!\w)" + re.escape(kw_lc) + r"(?!\w)", head):
            return True, f"seniority: '{kw}' in JD head"
    return False, None


def norm_key(company, role):
    co = re.sub(r"\s+", " ", (company or "").lower().strip())
    ro = re.sub(r"\s+", " ", (role or "").lower().strip())
    return f"{co}||{ro}"


def load_tombstones():
    if not os.path.exists(TOMBSTONES_PATH):
        return {}
    with open(TOMBSTONES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_tombstones(tombs):
    tmp = TOMBSTONES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tombs, f, indent=2, ensure_ascii=False)
    os.replace(tmp, TOMBSTONES_PATH)


def classify(host):
    h = (host or "").lower()
    if "jobright.ai" in h: return "jobright"
    if "ashby" in h: return "ashby"
    if "greenhouse" in h: return "greenhouse"
    if "lever.co" in h: return "lever"
    if "workday" in h or "myworkdayjobs" in h: return "workday"
    if "icims.com" in h: return "icims"
    if "workatastartup" in h: return "yc-waas"
    if "smartrecruiters" in h: return "smartrecruiters"
    if "jobvite" in h: return "jobvite"
    if "eightfold" in h: return "eightfold"
    if "rippling" in h: return "rippling"
    return "direct"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache):
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CACHE_PATH)


def should_skip(entry, retry_failed):
    if entry is None:
        return False
    if entry.get("status") == "success":
        return True
    if retry_failed:
        return False
    ts = entry.get("fetched_at")
    if not ts:
        return False
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - when < timedelta(days=RETRY_FAILED_AFTER_DAYS)


def clean_text(text):
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(ln)
    return "\n".join(out).strip()


def extract_jd(html, fam):
    if not html or len(html.strip()) < 200:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    selectors_by_fam = {
        "greenhouse": ["#content", ".content", ".job__description", "[class*=description]"],
        "smartrecruiters": [".job-description", "[data-test=job-description]", "main"],
        "jobright": ["main", "[class*=description]", "[class*=jd-]", "[class*=job-]"],
        "ashby": ["main", "[class*=description]", "[class*=job]"],
        "lever": [".posting", ".posting-page", "main"],
        "workday": ["[data-automation-id*=jobPostingDescription]", "main"],
        "icims": ["#icimsContentDiv", "#job_description", "main"],
        "yc-waas": ["main", "[class*=job]"],
    }
    for sel in selectors_by_fam.get(fam, []):
        node = soup.select_one(sel)
        if node:
            text = clean_text(node.get_text("\n", strip=True))
            if len(text) >= 200:
                return text

    body = soup.body or soup
    text = clean_text(body.get_text("\n", strip=True))
    return text if len(text) >= 200 else None


def fetch_one(url, fam, last_hit):
    host = urlparse(url).hostname or ""
    if host in last_hit:
        wait = PER_DOMAIN_DELAY_S - (time.time() - last_hit[host])
        if wait > 0:
            time.sleep(wait)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            timeout=TIMEOUT_S,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        last_hit[host] = time.time()
        return "failed", None, "timeout"
    except requests.exceptions.RequestException as e:
        last_hit[host] = time.time()
        return "failed", None, f"request_error_{type(e).__name__}"
    last_hit[host] = time.time()

    if resp.status_code == 404:
        return "failed", None, "http_404_stale"
    if resp.status_code == 403:
        return "failed", None, "http_403_blocked"
    if resp.status_code == 429:
        return "failed", None, "http_429_rate_limited"
    if not resp.ok:
        return "failed", None, f"http_{resp.status_code}"

    jd = extract_jd(resp.text, fam)
    if not jd:
        return "failed", None, "empty_or_js_rendered"
    return "success", jd, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max rows to process this run (0 = all)")
    ap.add_argument("--retry-failed", action="store_true", help="also retry rows previously marked failed")
    ap.add_argument("--no-tombstone", action="store_true", help="skip tombstone write + prospects rewrite")
    args = ap.parse_args()

    run_started_at = now_iso()
    run_start = time.time()

    with open(PROSPECTS_PATH, encoding="utf-8") as f:
        prospects = json.load(f)
    cache_before_count = len(load_cache())
    cache = load_cache()
    tombstones = load_tombstones()
    tomb_before = len(tombstones)
    prospects_before = len(prospects)
    filters = {}
    if os.path.exists(FILTERS_PATH):
        with open(FILTERS_PATH, encoding="utf-8") as f:
            filters = json.load(f)
    last_hit = {}

    total = len(prospects)
    processed = skipped = ok = fail = 0
    rekill_visa = rekill_title = rekill_seniority = 0
    kill_inline = 0
    aged_count = 0
    seen_count = 0
    aged_keys = set()
    seen_keys = set()
    today = date.today()
    grace_days = int(filters.get("grace_days", 0) or 0)

    seen_cutoff = None
    if os.path.exists(META_PATH):
        try:
            with open(META_PATH, encoding="utf-8") as f:
                meta = json.load(f)
            prev_iso = (meta.get("last_pulled") or "")[:10]
            if prev_iso:
                prev_pull_date = date.fromisoformat(prev_iso)
                if prev_pull_date < today:
                    seen_cutoff = prev_pull_date
        except (ValueError, OSError, KeyError):
            pass

    for row in prospects:
        if row.get("state") in PRESERVED_STATES:
            continue
        key = norm_key(row.get("company"), row.get("role"))
        dp = row.get("date_posted")
        if seen_cutoff and dp:
            try:
                d = date.fromisoformat(dp)
                if d <= seen_cutoff:
                    seen_keys.add(key)
                    seen_count += 1
                    continue
            except (ValueError, TypeError):
                pass
        if grace_days > 0 and is_aged_out(dp, grace_days, today):
            aged_keys.add(key)
            aged_count += 1
    if seen_count:
        print(f"seen_in_prev_fetch pre-pass: {seen_count} rows posted <= {seen_cutoff} marked for removal.")
    if aged_count:
        print(f"Age-out pre-pass: {aged_count} rows older than {grace_days}d marked for removal.")

    rows_by_id = {str(r.get("id")): r for r in prospects}
    print(f"Loaded {total} prospects. Cache has {len(cache)} entries. Tombstones: {len(tombstones)}.")
    print("Pre-pass: re-applying kills to cached JDs...")
    for pid, entry in list(cache.items()):
        if entry.get("status") != "success":
            continue
        jd = entry.get("jd_text") or ""
        if not jd:
            continue
        row = rows_by_id.get(pid)
        role = (row or {}).get("role", "")
        killed, reason = apply_jd_kills(jd, role, filters)
        if killed:
            cat = reason.split(":", 1)[0]
            if cat == "visa":
                rekill_visa += 1
            elif cat == "title":
                rekill_title += 1
            elif cat == "seniority":
                rekill_seniority += 1
            entry["status"] = "killed_by_jd"
            entry["kill_reason"] = reason
            entry["killed_at"] = now_iso()
            entry.pop("jd_text", None)
            entry.pop("text_len", None)
    print(f"  pre-pass kills: visa={rekill_visa} title={rekill_title} seniority={rekill_seniority}")
    print()

    if args.limit:
        print(f"Limit: {args.limit} rows this run.")
    for i, row in enumerate(prospects, 1):
        pid = str(row.get("id"))
        url = row.get("link") or ""
        if not url or not pid:
            continue
        rk = norm_key(row.get("company"), row.get("role"))
        if rk in aged_keys or rk in seen_keys:
            skipped += 1
            continue
        if should_skip(cache.get(pid), args.retry_failed):
            skipped += 1
            continue

        fam = classify(urlparse(url).hostname or "")
        status, jd, reason = fetch_one(url, fam, last_hit)
        entry = {"fetched_at": now_iso(), "status": status, "ats": fam, "url": url}

        if status == "success":
            killed, kr = apply_jd_kills(jd, row.get("role", ""), filters)
            if killed:
                cat = kr.split(":", 1)[0]
                if cat == "visa":
                    rekill_visa += 1
                elif cat == "title":
                    rekill_title += 1
                elif cat == "seniority":
                    rekill_seniority += 1
                entry["status"] = "killed_by_jd"
                entry["kill_reason"] = kr
                entry["killed_at"] = now_iso()
                kill_inline += 1
                tail = f"KILL: {kr[:50]}"
                marker = "KX"
            else:
                entry["jd_text"] = jd
                entry["text_len"] = len(jd)
                ok += 1
                tail = f"{len(jd)} chars"
                marker = "OK"
        else:
            entry["reason"] = reason
            fail += 1
            tail = reason
            marker = "--"
        cache[pid] = entry

        co = (row.get("company") or "")[:38]
        print(f"  {processed+1:4d}  [{marker}]  {fam:16s}  id={pid:>4s}  {co:38s}  {tail}")
        processed += 1

        if processed % SAVE_EVERY == 0:
            save_cache(cache)
        if args.limit and processed >= args.limit:
            break

    save_cache(cache)

    new_tomb_count = 0
    to_remove_keys = set(aged_keys) | set(seen_keys)
    for pid, entry in cache.items():
        row = rows_by_id.get(pid)
        if not row:
            continue
        st = entry.get("status")
        reason = entry.get("kill_reason") or entry.get("reason") or ""
        should_tomb = False
        if st == "killed_by_jd":
            should_tomb = True
        elif st == "failed" and entry.get("reason") == "http_404_stale":
            should_tomb = True
            reason = "stale_404"
        if not should_tomb:
            continue
        key = norm_key(row.get("company"), row.get("role"))
        if key not in tombstones:
            tombstones[key] = {
                "reason": reason,
                "url": row.get("link"),
                "company": row.get("company"),
                "role": row.get("role"),
                "tombstoned_at": now_iso(),
                "prospect_id": row.get("id"),
            }
            new_tomb_count += 1
        to_remove_keys.add(key)

    removed_count = 0
    if not args.no_tombstone and to_remove_keys:
        kept = []
        for r in prospects:
            if norm_key(r.get("company"), r.get("role")) in to_remove_keys:
                removed_count += 1
            else:
                kept.append(r)
        tmp = PROSPECTS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(kept, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PROSPECTS_PATH)
        save_tombstones(tombstones)
        print(f"\nTombstones: +{new_tomb_count} new (cumulative {len(tombstones)}).")
        print(f"Prospects: removed {removed_count} rows. {len(kept)} remain (was {len(prospects)}).")
    elif args.no_tombstone:
        print(f"\n[--no-tombstone] Would tombstone {new_tomb_count} and remove {len(to_remove_keys)} prospects. No writes.")

    print()
    print(f"Done. processed={processed} ok={ok} kill_inline={kill_inline} failed={fail} skipped_cache={skipped} aged_out={aged_count} seen_prev={seen_count}")
    print(f"Pre-pass + inline kills: visa={rekill_visa} title={rekill_title} seniority={rekill_seniority}")

    by_ok = {}
    by_fail = {}
    by_killed = {}
    for e in cache.values():
        fam = e.get("ats", "?")
        st = e.get("status")
        if st == "success":
            by_ok[fam] = by_ok.get(fam, 0) + 1
        elif st == "killed_by_jd":
            by_killed[fam] = by_killed.get(fam, 0) + 1
        else:
            by_fail[fam] = by_fail.get(fam, 0) + 1
    print("\nCumulative cache by ATS family:")
    fams = sorted(set(by_ok) | set(by_fail) | set(by_killed))
    by_ats_summary = {}
    for fam in fams:
        s = by_ok.get(fam, 0)
        k = by_killed.get(fam, 0)
        x = by_fail.get(fam, 0)
        tot = s + k + x
        rate = (100 * s / tot) if tot else 0
        print(f"  {fam:16s}  ok={s:4d}  killed={k:4d}  fail={x:4d}  ({rate:.0f}% usable)")
        by_ats_summary[fam] = {"ok": s, "killed": k, "fail": x}

    duration_s = round(time.time() - run_start, 2)
    prospects_after = prospects_before - removed_count if not args.no_tombstone else prospects_before
    append_history({
        "type": "jd_fetch_run",
        "at": run_started_at,
        "duration_s": duration_s,
        "args": {"limit": args.limit or None, "retry_failed": args.retry_failed, "no_tombstone": args.no_tombstone},
        "cache_before": cache_before_count,
        "cache_after": len(cache),
        "processed": processed,
        "fetched_ok": ok,
        "fetched_failed": fail,
        "killed_inline": kill_inline,
        "skipped_already_cached": skipped,
        "kills_by_category": {"visa": rekill_visa, "title": rekill_title, "seniority": rekill_seniority},
        "aged_out": {"count": aged_count, "grace_days": grace_days},
        "seen_in_prev_fetch": {"count": seen_count, "cutoff_date": seen_cutoff.isoformat() if seen_cutoff else None},
        "tombstones": {"before": tomb_before, "added_this_run": new_tomb_count,
                       "after": tomb_before + new_tomb_count if not args.no_tombstone else tomb_before},
        "prospects": {"before": prospects_before, "removed_this_run": removed_count, "after": prospects_after},
        "cache_by_ats": by_ats_summary,
    })
    print(f"\nRun appended to {HISTORY_PATH} ({duration_s}s)")


if __name__ == "__main__":
    main()
