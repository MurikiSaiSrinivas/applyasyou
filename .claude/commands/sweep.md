---
name: sweep
description: Run a Gmail inbox sweep to find rejections, ATS receipts, recruiter touches, and friend replies since the last sweep. Categorizes each thread, updates active.json/closed.json/last_email_check.json, drafts follow-ups when relevant. NEVER sends; NEVER deletes.
allowed-tools: Bash, Read, mcp__claude_ai_Gmail__search_threads, mcp__claude_ai_Gmail__get_thread, mcp__claude_ai_Gmail__create_draft
---

The user invoked `/sweep`. They want the recurring inbox sweep.

## What you do

**Invoke the `gmail-sweeper` agent.** Its full instructions are at
`.claude/agents/gmail-sweeper.md`. Pass the user any signals worth
seeing (specifically the contact names they're tracking in active.json
+ watchlist).

## Why this is a slash command

The sweep is a multi-step routine: search inbox, classify threads,
mutate state, draft follow-ups, write summary. Predictability matters.
Same shape every time.

## Constraints (the agent enforces these; restated for clarity)

- NEVER read bank emails (see `templates/GMAIL_RULES.md`)
- NEVER send -- drafts only
- NEVER delete anything
- ALWAYS report what was actually touched at the Gmail layer

## After completion

The agent returns a summary block. Surface it to the user. If any
drafts were created, list the draft IDs so the user can find them in
their Drafts folder.

If there are unmatched closures (e.g., a rejection email for a company
that isn't in `data/active.json`), surface them as: "Got a rejection
from <X>. Was that a real application you forgot to log?" Don't
auto-create rows.
