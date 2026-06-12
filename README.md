# Job-search starter kit

A clone-and-run system for running a high-volume job search: scrape curated job
lists, cache and score postings against your stack, triage them in a local viewer,
and draft applications with an LLM of your choice. Everything personal lives in
config files you fill in once. No code changes needed to make it yours.

> **Status:** under construction. Foundation (config + data templates) is in place.
> The runnable scripts and walkthrough are being ported in. See `BUILD_PLAN.md` for
> what's done and what's next.

## How it works (4 steps)

1. **Fetch** — pull job lists from configurable GitHub sources, filter to your roles + region.
2. **Cache JDs** — fetch the full job description text for each new posting.
3. **Score** — rank each posting against your stack and pick which of your resumes fits.
4. **Triage + apply** — review in the local viewer, draft answers with your LLM CLI, log applications.

### Plus: a scraper browser extension

`chrome_extension/` is a scrape-only Chrome extension that harvests jobs straight from
**Google Jobs, Wellfound, and LinkedIn** into the same pipeline. It talks to a local
server, `scripts/local_sink.py` (run it first), on `127.0.0.1:8765`. It filters and
heuristic-scores each posting as it lands. It does NOT autofill or submit applications.
See `chrome_extension/README.md` to load it.

## Quick start (once Phase 2 lands)

```
# 1. Copy the example configs and fill them in
cp config.example.json config.json
cp profile.example.json profile.json
cp data/prospects/filters.example.json data/prospects/filters.json

# 2. Point config.json -> llm_cli at whatever LLM CLI you have
#    (claude, ollama, an openai CLI — any of them)

# 3. Add your resumes to resumes/ and map them in config.json -> resume_clusters

# 4. Run the pipeline
python scripts/fetch_prospects.py
python scripts/fetch_prospect_jds.py
python scripts/score_prospects.py
```

## Making it yours (personalization)

No forms, no prompts to paste. You open this project in **Claude Code** and say hi.
The agent (driven by `CLAUDE.md`) asks for your resumes, reads them, and writes most
of your setup from them — stack keywords, resume map, profile, filters. It asks about
your projects (handing you a prompt to run in your project's Claude/Cursor), then
walks you through ~20 real jobs one at a time (analyze fit, pick/tailor/build a
resume, draft answers, log the application), learning your voice and what you're
after as it goes. At the end it hands you the scraper commands and the viewer.

Start here: **`ONBOARD.md`**. The full logic the agent follows is **`CLAUDE.md`**.
Day-to-day + the scraper phase: **`WALKTHROUGH.md`**.

## Privacy

`config.json`, `profile.json`, `resumes/`, and your live `data/*.json` are gitignored.
Only the `*.example.json` files and empty templates are meant to be committed. Before
you push, confirm `git status` does not list `profile.json` or `config.json`.

## License

TBD — choose a license before any public release.
