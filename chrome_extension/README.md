# Job Scraper Companion (Chrome extension)

Scrape-only companion for the starter kit. It harvests job postings from Google
Jobs, Wellfound, and LinkedIn into your local pipeline. It does NOT autofill or
submit applications.

Everything bridges through `scripts/local_sink.py` on `localhost:8765`.

## What it does

```
content.js          (google.com/search?udm=8)     ->  POST /ingest
content_wellfound.js (wellfound.com/jobs)          ->  POST /api/wellfound/scrape + /jd
content_linkedin.js  (linkedin.com/jobs|my-items)  ->  POST /api/linkedin/scrape + /jd
popup.js (toolbar UI)                              ->  GET /status, pending_jds
background.js (service worker)                     ->  relays all of the above + process_post
```

Two-pass scrape (Wellfound + LinkedIn): pass 1 ingests visible job metadata and
filters it through `filters.json`; pass 2 opens each job in a background tab to
capture the rendered JD (bypasses anti-bot blocks on plain `fetch()`), caches it,
and auto-runs heuristic scoring at the sink.

The popup also has a LinkedIn post-URL classifier: paste a `linkedin.com/posts/...`
link and it extracts the post, asks your configured LLM to classify intent
(careers page / email a resume / referral / other), and offers a relevant action.

## Setup

1. Start the sink: `python scripts/local_sink.py` (needs `config.json` — see the
   package README).
2. Open `chrome://extensions`, enable Developer mode.
3. Click "Load unpacked".
4. Select this `chrome_extension/` folder (wherever you cloned the package).
5. Pin the extension. Open a supported page and click the icon.

## Notes

- **Localhost-only sink.** The Python server binds to `127.0.0.1` only.
- **Manual trigger only.** No scheduled or automatic scraping. You click "Scrape".
- **LinkedIn anti-scraping risk is real.** The popup throttles tab opens; scrape in
  moderation.
- **Popup says "NOT REACHABLE"**: the sink isn't running. Start `local_sink.py`.
- The post classifier uses whatever LLM you set in `config.json` -> `llm_cli`.
