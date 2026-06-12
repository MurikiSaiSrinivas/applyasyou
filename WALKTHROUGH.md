# Walkthrough — clone to first scrape

From zero to a scored prospect in about 30 minutes (plus the one-time
personalization in `ONBOARD.md`).

## Prerequisites

| Item | Why |
|---|---|
| Python 3.x | runs the scripts + the sink |
| `requests`, `beautifulsoup4` | JD fetching: `pip install requests beautifulsoup4` |
| An LLM CLI | the AI steps shell out to it (`claude`, an `ollama` model, an openai CLI — your choice) |
| Chrome | for the scraper extension |

## 1. Clone

```
git clone <your fork of this repo>
cd <repo>/generic
```

## 2. Personalize (the agent runs this with you)

Open this folder in **Claude Code** (`claude`) and say **hi**. The agent runs
onboarding (`ONBOARD.md`): you drop your resumes into `resumes/`, it reads them and
writes your `config.json`, `profile.json`, `filters.json`, and resume catalog **from
them**, asks about your projects (it gives you a prompt to run in your project's
Claude/Cursor), then walks you through ~20 real jobs to tune itself to how you work
and write. Point `config.json` -> `llm_cli` at your LLM CLI when it asks, and fill
any `profile.json` PII it couldn't read off your resumes.

> You start with **empty memory and your own resumes**. Nothing is pre-filled with
> anyone else's identity or voice. The agent learns *you* as it goes. The full logic
> it follows is in `CLAUDE.md`.

## 4. First scrape (CLI pipeline)

```
python scripts/fetch_prospects.py        # pull + filter job lists
python scripts/fetch_prospect_jds.py     # fetch JD text (slow; runs in background fine)
python scripts/score_prospects.py        # heuristic verdicts
python scripts/reanalyze.py              # optional: upgrade verdicts with your LLM
```

## 5. First scrape (browser extension)

```
python scripts/local_sink.py             # start the local bridge (leave running)
```

Then load `chrome_extension/` via `chrome://extensions` -> Developer mode ->
Load unpacked (see `chrome_extension/README.md`). Open Google Jobs, Wellfound, or
LinkedIn jobs and click the extension. Scraped jobs flow into the same pipeline,
filtered and scored on arrival.

## 6. Review

Open `viewer/index.html` to triage prospects, or read `data/prospects/prospects.json`
directly. Apply, log, repeat.

## What does NOT carry across machines

- `config.json`, `profile.json`, your `resumes/`, and live `data/*.json` are
  gitignored. Move them yourself (or re-run the bootstrap) on a new machine.
- Your Claude Code memory is per-machine and starts empty. That's intentional.
