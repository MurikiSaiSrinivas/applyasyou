"""local_sink.py — tiny localhost HTTP server bridging the Chrome scraper
extension <-> this repo. SCRAPE-ONLY build (no autofill / no auto-apply).

Endpoints:
  GET  /status                          -> harvest counters
  POST /ingest                          -> Google-jobs metadata batch (content.js)
  POST /api/wellfound/scrape            -> Wellfound pass 1 (metadata -> prospects)
  POST /api/wellfound/jd                -> Wellfound pass 2 (HTML -> JD cache + auto-score)
  GET  /api/wellfound/pending_jds       -> wellfound rows still needing a JD
  POST /api/linkedin/scrape             -> LinkedIn pass 1 (search/saved/applied)
  POST /api/linkedin/jd                 -> LinkedIn pass 2 (HTML -> JD cache + auto-score)
  GET  /api/linkedin/pending_jds        -> linkedin rows still needing a JD
  POST /api/linkedin/process_post       -> classify a pasted LinkedIn post (LLM)
  POST /api/active/log_applied          -> viewer 'I applied' button (dual-writes via lib.applications)
  POST /api/prospect/update             -> viewer 'skip' / set state on a prospect row
  OPTIONS *                             -> CORS preflight

Filtering uses lib.filters; auto-scoring uses lib.scoring; the post classifier
uses your configured LLM via lib.llm_client. All paths come from config.json.

Binds to 127.0.0.1 only. Run:  python scripts/local_sink.py
"""
import json
import os
import sys
import threading
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG_ROOT)
from lib.config import load_config, prospects_dir, data_dir  # noqa: E402
from lib.filters import passes_filters  # noqa: E402
from lib.scoring import score_prospect  # noqa: E402
from lib.llm_client import call_llm  # noqa: E402

CFG = load_config()
DATA = prospects_dir(CFG)
RAW_PATH = os.path.join(DATA, "google_jobs_raw.json")
PROSPECTS_PATH = os.path.join(DATA, "prospects.json")
JD_CACHE_PATH = os.path.join(DATA, "jd_cache.json")
FILTERS_PATH = os.path.join(DATA, "filters.json")
ACTIVE_PATH = os.path.join(data_dir(CFG), "active.json")

PORT = 8765
HOST = "127.0.0.1"   # localhost-only — never bind to 0.0.0.0

_data_lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_raw():
    if not os.path.exists(RAW_PATH):
        return {"_meta": {"created": now_iso(), "last_ingest": None}, "batches": []}
    with open(RAW_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_raw(data):
    tmp = RAW_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, RAW_PATH)


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_filters():
    if os.path.exists(FILTERS_PATH):
        try:
            with open(FILTERS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[sink] failed to load filters.json: {e}", flush=True)
    return {}


def _extract_jd_verbose(html):
    """Extract JD body text from a job-detail HTML page. Tries JSON-LD
    JobPosting.description, then og:description, then largest text block.
    Returns (text, diagnostics)."""
    diag = {"html_len": len(html), "jsonld_count": 0, "jsonld_jobposting": False,
            "jsonld_desc_chars": 0, "og_chars": 0, "biggest_div_chars": 0}
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[sink] beautifulsoup4 not installed; pip install beautifulsoup4", flush=True)
        return "", diag
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", {"type": "application/ld+json"}):
        diag["jsonld_count"] += 1
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        for c in (data if isinstance(data, list) else [data]):
            if isinstance(c, dict) and c.get("@type") == "JobPosting":
                diag["jsonld_jobposting"] = True
                if c.get("description"):
                    text = BeautifulSoup(c["description"], "html.parser").get_text("\n", strip=True)
                    diag["jsonld_desc_chars"] = len(text)
                    if text and len(text) >= 200:
                        return text, diag

    og = soup.find("meta", attrs={"property": "og:description"})
    if og and og.get("content"):
        text = og["content"].strip()
        diag["og_chars"] = len(text)
        if len(text) >= 200:
            return text, diag

    biggest = ""
    for div in soup.find_all(["div", "section", "article"]):
        text = div.get_text("\n", strip=True)
        if len(text) > len(biggest):
            biggest = text
    diag["biggest_div_chars"] = len(biggest)
    return (biggest, diag) if len(biggest) >= 200 else ("", diag)


def _auto_score(pid, jd_text):
    """Heuristic-score a prospect once its JD lands, unless it already has a
    real LLM verdict. Returns (verdict, match_pct)."""
    try:
        prospects = load_json_file(PROSPECTS_PATH, [])
        row = next((r for r in prospects if r.get("id") == pid), None)
        if not row:
            return "?", None
        if (row.get("analysis") or {}).get("source") == "llm":
            return "?", None
        entry = score_prospect(row, jd_text, CFG)
        row["analysis"] = entry
        save_json_atomic(PROSPECTS_PATH, prospects)
        return entry.get("verdict", "?"), entry.get("match_pct")
    except Exception as e:
        print(f"[sink] auto-score failed for p#{pid}: {e}", flush=True)
        return "?", None


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as e:
            self._json(400, {"error": f"bad json: {e}"})
            return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/status":
            self._handle_status(); return
        if p == "/api/wellfound/pending_jds":
            self._handle_pending_jds("wellfound"); return
        if p == "/api/linkedin/pending_jds":
            self._handle_pending_jds("linkedin"); return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/ingest":
            self._handle_ingest(); return
        if self.path == "/api/wellfound/scrape":
            self._handle_scrape("wellfound"); return
        if self.path == "/api/wellfound/jd":
            self._handle_jd("wellfound"); return
        if self.path == "/api/linkedin/scrape":
            self._handle_scrape("linkedin"); return
        if self.path == "/api/linkedin/jd":
            self._handle_jd("linkedin"); return
        if self.path == "/api/linkedin/process_post":
            self._handle_process_post(); return
        if self.path == "/api/active/log_applied":
            self._handle_log_applied(); return
        if self.path == "/api/prospect/update":
            self._handle_prospect_update(); return
        self._json(404, {"error": "not found"})

    # ---------- applied / prospect mutation handlers ----------

    def _handle_log_applied(self):
        """Viewer 'I applied' button. Calls scripts/apply.py to do the
        dual-write (active.json + prospects.json state flip).
        """
        payload = self._read_json_body()
        if payload is None: return
        prospect_id = payload.get("prospect_id")
        if not isinstance(prospect_id, int):
            self._json(400, {"error": "prospect_id (int) required"}); return
        try:
            # Delegate to the deterministic lib so the viewer button and
            # the chat command share one source of truth.
            from lib import applications  # PKG_ROOT is on sys.path already
            result = applications.apply_with_prospect_id(prospect_id)
            self._json(200, result)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _handle_prospect_update(self):
        """Viewer 'skip' / 'shortlist' / generic field-set on a prospect row.
        Body: { id: <int>, fields: { state: 'skip', ... } }
        """
        payload = self._read_json_body()
        if payload is None: return
        pid = payload.get("id")
        fields = payload.get("fields") or {}
        if not isinstance(pid, int) or not isinstance(fields, dict):
            self._json(400, {"error": "id (int) and fields (object) required"}); return
        try:
            prospects = load_json_file(PROSPECTS_PATH, [])
            target = None
            for r in prospects:
                if r.get("id") == pid:
                    target = r
                    break
            if target is None:
                self._json(404, {"error": f"prospect id {pid} not found"}); return
            for k, v in fields.items():
                if k in {"state", "notes", "requires_tailor", "tailor_reason"}:
                    target[k] = v
            save_json_atomic(PROSPECTS_PATH, prospects)
            self._json(200, {"status": "updated", "id": pid})
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ---------- handlers ----------
    def _handle_status(self):
        data = load_raw()
        total = sum(len(b.get("jobs", [])) for b in data.get("batches", []))
        self._json(200, {
            "total_in_raw": total,
            "batches": len(data.get("batches", [])),
            "last_ingest": data["_meta"].get("last_ingest"),
        })

    def _handle_ingest(self):
        payload = self._read_json_body()
        if payload is None: return
        jobs = payload.get("jobs") or []
        if not isinstance(jobs, list):
            self._json(400, {"error": "jobs must be a list"}); return
        data = load_raw()
        data["batches"].append({
            "received_at": now_iso(),
            "source_url": payload.get("url", ""),
            "scraped_at": payload.get("scraped_at", ""),
            "strategy": payload.get("strategy", "?"),
            "jobs": jobs,
        })
        data["_meta"]["last_ingest"] = now_iso()
        save_raw(data)
        print(f"[ingest] +{len(jobs)} jobs from {(payload.get('url') or '')[:80]!r}", flush=True)
        self._json(200, {"ok": True, "saved": len(jobs), "total_batches": len(data["batches"])})

    def _handle_pending_jds(self, source):
        prospects = load_json_file(PROSPECTS_PATH, [])
        jd_cache = load_json_file(JD_CACHE_PATH, {})
        pending = []
        for r in prospects:
            if source not in (r.get("sources") or []):
                continue
            ce = jd_cache.get(str(r["id"])) or {}
            if ce.get("status") == "success" and ce.get("jd_text"):
                continue
            link = (r.get("link") or "").strip()
            if link:
                pending.append({"prospect_id": r["id"], "url": link})
        print(f"[api] {source}.pending_jds count={len(pending)}", flush=True)
        self._json(200, {"ok": True, "pending": pending})

    def _handle_scrape(self, source):
        """Pass 1: ingest a metadata batch, filter it, create new prospect rows.
        LinkedIn supports mode=search|saved|applied; applied also logs to
        active.json. Wellfound has no modes."""
        payload = self._read_json_body()
        if payload is None: return
        jobs = payload.get("jobs") or []
        if not isinstance(jobs, list):
            self._json(400, {"error": "jobs must be a list"}); return
        mode = (payload.get("mode") or "search").lower()
        if source == "linkedin" and mode not in ("search", "saved", "applied"):
            self._json(400, {"error": f"mode must be search|saved|applied, got {mode!r}"}); return

        stats = {"new_prospects": 0, "matched_existing": 0, "filtered_out": 0,
                 "new_active_rows": 0, "active_already_logged": 0}
        filter_reasons = {}
        added_prospect_ids, added_active_ids, needs_jd_fetch = [], [], []
        filters_cfg = load_filters()
        new_state = "applied" if (source == "linkedin" and mode == "applied") else "new"

        with _data_lock:
            prospects = load_json_file(PROSPECTS_PATH, [])
            jd_cache = load_json_file(JD_CACHE_PATH, {})
            active = load_json_file(ACTIVE_PATH, []) if new_state == "applied" else None
            today = date.today().isoformat()

            by_link = {}
            for r in prospects:
                k = (r.get("link") or "").split("?")[0].split("#")[0]
                if k:
                    by_link[k] = r
            active_by_pid = {r.get("_prospect_id"): r for r in (active or []) if r.get("_prospect_id") is not None}
            active_by_link = {(r.get("link") or "").split("?")[0].split("#")[0]: r for r in (active or []) if r.get("link")}

            for job in jobs:
                link = (job.get("link") or "").split("?")[0].split("#")[0]
                if not link:
                    continue
                company = (job.get("company") or "?").strip()
                role = (job.get("role") or "?").strip()
                location = (job.get("location") or "").strip()
                comp = (job.get("comp") or "").strip()
                work_model = (job.get("work_model") or "").strip()
                snippet = (job.get("snippet") or "").strip()
                status_text = (job.get("status_text") or "").strip()

                existing = by_link.get(link)
                if existing:
                    stats["matched_existing"] += 1
                    if new_state == "applied" and existing.get("state") != "applied":
                        existing["state"] = "applied"
                    if jd_cache.get(str(existing["id"]), {}).get("status") != "success":
                        needs_jd_fetch.append({"prospect_id": existing["id"], "url": link})
                    pid_for_active = existing["id"]
                else:
                    if filters_cfg:
                        ok, reason = passes_filters({"role": role, "location": location, "flags": []}, filters_cfg)
                        if not ok:
                            stats["filtered_out"] += 1
                            filter_reasons[reason] = filter_reasons.get(reason, 0) + 1
                            continue
                    next_pid = max((r.get("id", 0) for r in prospects), default=0) + 1
                    bits = [b for b in (comp, work_model, snippet[:150]) if b]
                    if status_text:
                        bits.append(f"{source}: {status_text}")
                    placeholder = " | ".join(bits) or f"{source} scrape; JD fetch + scoring pending."
                    prospects.append({
                        "id": next_pid, "company": company, "role": role, "location": location,
                        "link": link, "date_posted": today, "date_posted_raw": "",
                        "work_model": work_model, "flags": [], "sources": [source],
                        "state": new_state, "notes": "",
                        "analysis": {"verdict": "apply", "match_pct": None, "resume": None,
                                     "visa_signal": "not_declared", "notes": placeholder,
                                     "source": "unanalyzed", "analyzed_at": now_iso()},
                    })
                    by_link[link] = prospects[-1]
                    stats["new_prospects"] += 1
                    added_prospect_ids.append(next_pid)
                    needs_jd_fetch.append({"prospect_id": next_pid, "url": link})
                    pid_for_active = next_pid

                if new_state == "applied":
                    if pid_for_active in active_by_pid or link in active_by_link:
                        stats["active_already_logged"] += 1
                    else:
                        next_aid = max((r.get("id", 0) for r in active), default=0) + 1
                        loc_full = f"{location} | {comp}" if (location and comp) else (location or comp)
                        active_row = {
                            "id": next_aid, "company": f"{company} (via LinkedIn)", "role": role,
                            "location": loc_full or "?",
                            "visa": "Not declared (LinkedIn listing did not surface visa policy)",
                            "resume": "(synced from LinkedIn; resume not tracked)",
                            "date_applied": today, "status": "applied", "last_touch": today,
                            "next_action": "Watch LinkedIn / email for response.",
                            "link": link, "_prospect_id": pid_for_active,
                            "notes": f"Synced from LinkedIn applied tab on {today}. Status: {status_text or 'applied'}.",
                        }
                        active.append(active_row)
                        active_by_pid[pid_for_active] = active_row
                        active_by_link[link] = active_row
                        stats["new_active_rows"] += 1
                        added_active_ids.append(next_aid)

            save_json_atomic(PROSPECTS_PATH, prospects)
            if new_state == "applied":
                save_json_atomic(ACTIVE_PATH, active)

        stats["filter_reasons"] = filter_reasons
        print(f"[api] {source}.scrape mode={mode} jobs={len(jobs)} new={stats['new_prospects']} "
              f"existing={stats['matched_existing']} filtered={stats['filtered_out']} "
              f"new_active={stats['new_active_rows']} needs_jd={len(needs_jd_fetch)}", flush=True)
        self._json(200, {"ok": True, "stats": stats, "added_prospect_ids": added_prospect_ids,
                         "added_active_ids": added_active_ids, "needs_jd_fetch": needs_jd_fetch})

    def _handle_jd(self, source):
        """Pass 2: extension POSTs rendered HTML; extract JD, cache it, auto-score."""
        payload = self._read_json_body()
        if payload is None: return
        try:
            pid = int(payload.get("prospect_id"))
        except (TypeError, ValueError):
            self._json(400, {"error": "prospect_id must be int"}); return
        url = (payload.get("url") or "").strip()
        html = payload.get("html") or ""
        if not html:
            self._json(400, {"error": "html required"}); return

        jd_text, diag = _extract_jd_verbose(html)
        with _data_lock:
            jd_cache = load_json_file(JD_CACHE_PATH, {})
            if not jd_text or len(jd_text) < 200:
                jd_cache[str(pid)] = {"url": url, "ats": source, "status": "empty_or_js_rendered",
                                      "fetched_at": now_iso(), "jd_text": "", "_diag": diag}
                save_json_atomic(JD_CACHE_PATH, jd_cache)
                print(f"[api] {source}.jd p#{pid} EMPTY html={diag['html_len']}b", flush=True)
                self._json(200, {"ok": False, "jd_chars": 0, "diag": diag, "warning": "JD too short or not found"})
                return
            jd_cache[str(pid)] = {"url": url, "ats": source, "status": "success",
                                  "fetched_at": now_iso(), "jd_text": jd_text}
            save_json_atomic(JD_CACHE_PATH, jd_cache)
            verdict, match_pct = _auto_score(pid, jd_text)

        note = f" verdict={verdict}/{match_pct}%" if verdict != "?" else " (no score)"
        print(f"[api] {source}.jd p#{pid} OK ({len(jd_text)} chars){note}", flush=True)
        self._json(200, {"ok": True, "jd_chars": len(jd_text), "verdict": verdict, "match_pct": match_pct})

    def _handle_process_post(self):
        """Classify a pasted LinkedIn post via the configured LLM."""
        import re as _re
        payload = self._read_json_body()
        if payload is None: return
        url = (payload.get("url") or "").strip()
        post_body = (payload.get("post_body") or "").strip()
        embedded_urls = payload.get("embedded_urls") or []
        embedded_emails = payload.get("embedded_emails") or []
        if not post_body or len(post_body) < 50:
            self._json(400, {"error": f"post_body too short ({len(post_body)} chars)."}); return

        prompt = (
            "You are reading a LinkedIn post a job seeker found while browsing. Classify what it "
            "asks for and extract actionable details. Return ONLY a JSON object (no prose, no fence):\n"
            '{\n  "intent": "careers_page" | "email_resume" | "referral" | "other",\n'
            '  "confidence": <int 0-100>,\n  "company": <string|null>,\n  "role": <string|null>,\n'
            '  "location": <string|null>,\n  "careers_url": <string|null>,\n'
            '  "contact_email": <string|null>,\n  "contact_name": <string|null>,\n'
            '  "summary": <string>,\n  "suggested_action": <string>\n}\n\n'
            "Intent rules: careers_page = apply at a URL (set careers_url); email_resume = email a "
            "resume (set contact_email); referral = someone offering referrals; other = generic.\n\n"
            f"POST URL: {url}\n\nPOST BODY:\n{post_body[:3500]}\n\n"
            f"EMBEDDED URLS:\n{chr(10).join('- ' + u for u in embedded_urls[:15]) or '(none)'}\n\n"
            f"EMBEDDED EMAILS: {', '.join(embedded_emails[:5]) if embedded_emails else '(none)'}\n"
        )
        try:
            text = call_llm(prompt, CFG)
            t = text.strip()
            if t.startswith("```"):
                t = _re.sub(r"^```(?:json)?\s*", "", t)
                t = _re.sub(r"\s*```\s*$", "", t)
            start, end = t.find("{"), t.rfind("}")
            if start == -1 or end == -1:
                raise ValueError(f"no JSON object in response: {text[:300]}")
            parsed = json.loads(t[start:end + 1])
        except Exception as e:
            print(f"[api] linkedin.process_post FAIL: {e}", flush=True)
            self._json(500, {"error": f"intent classification failed: {e}"}); return

        parsed["_source_post_url"] = url
        print(f"[api] linkedin.process_post intent={parsed.get('intent')} company={parsed.get('company')}", flush=True)
        self._json(200, {"ok": True, "result": parsed})

    def log_message(self, *args, **kwargs):
        return


def main():
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(RAW_PATH):
        save_raw(load_raw())
        print(f"Initialized empty {RAW_PATH}")
    print(f"local_sink (scrape-only) listening on http://{HOST}:{PORT}")
    print("  Google:    POST /ingest, GET /status")
    print("  Wellfound: POST /api/wellfound/scrape, /api/wellfound/jd, GET /api/wellfound/pending_jds")
    print("  LinkedIn:  POST /api/linkedin/scrape, /api/linkedin/jd, /api/linkedin/process_post, GET /api/linkedin/pending_jds")
    print("  Ctrl+C to stop.\n")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[shutdown]")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
