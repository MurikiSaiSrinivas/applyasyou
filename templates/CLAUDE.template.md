# Project handoff — <<FILL: your name>>'s job search workspace

Entry point for any agent picking up this workspace. The bootstrap fills the
`<<FILL>>` sections from your onboarding samples; the operational sections are
already generic and correct. Read `master_prompt.txt` for voice rules and
`PROJECTS.md` for project facts before writing anything in your voice.

---

## 1. Who you are

<<FILL: 3-4 lines — role, years, stack, what you optimize for, target roles, and
any hard constraint (visa, location, remote-only). Infer from the resumes and the
jobs brought during onboarding. Keep it concrete.>>

## 2. How to communicate

Voice and tone rules live in `master_prompt.txt`. Follow them exactly. Short
version the bootstrap should mirror here: <<FILL: 3-5 of your strongest tone rules>>.

## 3. Directory structure

```
config.json              your settings (LLM CLI, stack, resume picker) — gitignored
profile.json             your PII (name, contact, work auth) — gitignored
data/                    application + prospect state (JSON, source of truth)
scripts/                 fetch / score / reanalyze / local_sink
chrome_extension/        scrape-only browser extension
resumes/                 your resume files
PROJECTS.md              your project registry (freshest project facts)
master_prompt.txt        your voice + coaching rules
```

## 4. Standard workflow per JD

1. **Analyze**: % match, key alignment, gaps, visa/work-auth likelihood, comp read, apply/skip, which resume.
2. **Recommend a resume** from your corpus (config.resume_clusters maps stack -> resume).
3. **Build a tailored one** only if nothing hits ~70% fit.
4. **Draft application answers** in your voice (master_prompt.txt) when the JD has open prompts.
5. **Log it** when you apply: append to `data/active.json`, flip the prospect's `state` to `applied`.

## 5. Application strategy (your real filters)

<<FILL: what you actually apply to, and your HARD blockers. Infer the umbrella of
roles you'd take from the jobs brought during onboarding. State the 1-3 things that are
real skips (e.g. visa dead, zero stack overlap) vs soft signals you mention but
don't skip on (title, comp, relocation). Lean APPLY by default unless a hard
blocker fires.>>

## 6. Resume corpus map (which one to use when)

<<FILL: one row per resume in your resumes/ folder — when to use each. This should
match config.resume_clusters. If you only have one resume, say so.>>

## 7. Application data (JSON, source of truth)

- `data/active.json` — applied, not yet closed. Fields: id, company, role, location, visa, resume, date_applied, status, last_touch, next_action, link, notes, optional `_prospect_id`.
- `data/watchlist.json` — tracking, not applying.
- `data/closed.json` — rejected / offer / withdrawn / ghosted.
- `data/prospects/prospects.json` — scraped, scored leads (state: new | shortlist | applied | skip).

When you apply: append to active.json (increment id) AND flip the matching
prospect's `state` to `applied`. Do both.

## 8. Anti-patterns to avoid

1. Don't skip a JD on title/comp/trajectory alone — only your hard blockers skip.
2. Don't create a company folder for a resume *reuse* — a log row is enough.
3. <<FILL: your own corrections as they accumulate, e.g. specific phrasings you dislike in application answers.>>

## 9. Memory

Durable facts about you live in your Claude Code memory directory (outside this
repo). It starts empty — this is your workspace, not anyone else's. Add facts as
you learn what works.
