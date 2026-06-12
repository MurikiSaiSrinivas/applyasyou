# Getting started

There's no form to fill and no prompt to paste. You open this project in Claude
Code and say hello. The agent guides you the rest of the way.

## What to do

1. Open this folder in **Claude Code** (`claude` in the project directory).
2. Say **hi**.
3. Follow along. The agent will:
   - ask you to drop **all your resumes** into `resumes/`,
   - read and organize them, and write most of your setup **from them** — your
     stack keywords, resume map, profile, filters, and the resume catalog,
   - ask about any **new projects or updates** — it hands you a prompt
     (`PROJECT_INTAKE_PROMPT.md`) you can run in your project's Claude/Cursor to
     pull the details, then paste back,
   - then walk you through **~20 real jobs** one at a time: for each, it analyzes
     fit, picks (or tailors, or builds) the right resume, drafts answers if you
     want them, and logs the application when you say you've applied,
   - and hand you the scraper commands + the viewer (frontend) at the end.

While you work, it learns how you write and what you're after, and tunes itself to
your voice. That's why the 20 jobs matter: they're how it calibrates to you.

## The only things you do by hand

- Put your resume files in `resumes/`.
- Fill `profile.json` PII it can't read off your resumes (copy from
  `profile.example.json`).
- Point `config.json` -> `llm_cli` at your LLM CLI (it'll remind you).

After onboarding, `WALKTHROUGH.md` covers the day-to-day + the scraper phase. The
full operating logic the agent follows is in `CLAUDE.md`.
