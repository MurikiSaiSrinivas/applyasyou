# End-to-end test checklist

Internal QA doc (not part of the shipped bundle). The automated half is already
verified (see `BUILD_PLAN.md` Phase 4). This is the half that needs a human, a
browser, and real resumes — best done from a fresh clone on a clean path so you're
testing what a friend actually gets.

## Setup (5 min)

- [ ] Clone the package to a fresh path (not your working copy). Confirm `git status`
      shows no `config.json` / `profile.json` / `resumes/*` (gitignore working).
- [ ] Point an LLM CLI: `cp config.example.json config.json`, set `llm_cli`.
      (Or let onboarding do the copy and just edit `llm_cli` when asked.)

## A. Conversational onboarding (the main thing)

- [ ] Open the folder in Claude Code, say "hi". Agent should detect first run
      (no `.onboarded`) and ask for resumes.
- [ ] Drop 2-3 real resumes in `resumes/`, say "done". Agent should: read them,
      organize into subfolders, and populate `config.json` (stack_keywords,
      resume_clusters), `profile.json`, `filters.json`, `RESUME_DESCRIPTIONS.md`,
      `RESUME_CONTENT.md`. Spot-check those files look right.
- [ ] Projects step: agent asks about new/updated projects and offers
      `PROJECT_INTAKE_PROMPT.md`. Run that prompt in a real project's Claude/Cursor,
      paste the result back, confirm it lands in `PROJECTS.md`.
- [ ] Paste a few real JDs. For each: agent gives the analysis template, recommends
      a resume, and (when nothing fits) offers to tailor/build one. Accept a build
      once — confirm a `.docx` + `.pdf` appear under `resumes/<lane>/`.
- [ ] Ask it to draft a "why this company" answer. Check it sounds like you (it's
      been learning your voice; `master_prompt.txt` should be filling in).
- [ ] Say "applied" on one. Confirm a row appears in `data/active.json` AND the
      prospect flips to `state: "applied"` in `data/prospects/prospects.json`.
- [ ] After the run, confirm `.onboarded` exists and the agent handed over the
      sink/extension/viewer commands.

## B. Scraper extension (browser)

- [ ] `python scripts/local_sink.py` starts and prints the scrape-only endpoints.
- [ ] `chrome://extensions` -> Developer mode -> Load unpacked -> `chrome_extension/`.
      Loads with no manifest errors, named "Job Scraper Companion".
- [ ] On a Google Jobs search: popup shows the harvest panel; "Send to local" ->
      sink `/status` count goes up.
- [ ] On wellfound.com/jobs or linkedin.com/jobs: "Scrape + fetch JDs" runs pass 1 +
      pass 2; new rows land in `data/prospects/prospects.json` already scored.
- [ ] Paste a `linkedin.com/posts/...` URL in the post panel -> it classifies intent
      via your LLM and offers an action.
- [ ] Confirm NO autofill behaviour exists (no submit clicking, no resume upload) —
      this build is scrape-only.

## C. Viewer (browser)

- [ ] Open `viewer/index.html`. It loads and renders the active/prospects/closed
      data without console errors. Triage controls work.

## D. Portability (optional, if a friend isn't on Windows+Word)

- [ ] On a machine without Word: `build_resume.py` still writes the `.docx` and
      prints the "open in Word/Docs to export PDF" note instead of crashing.
- [ ] `llm_cli` pointed at a non-claude CLI (ollama / openai) returns text through
      `reanalyze.py`.
