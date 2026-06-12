# Project intake prompt

During onboarding the agent asks about your projects. The richest way to capture a
project is to let the tool that already knows the code describe it. If you have
**Claude Code** or **Cursor** open on a project repo, paste the prompt below into
that session, then paste its output back into your job-search chat. The agent folds
it into `PROJECTS.md` and uses it when writing applications.

Run it once per project that matters. (No agent on the repo? Just answer the same
questions in your own words.)

---

```
Read this repository and write a tight project brief I can hand to my job-search
assistant. Be concrete and honest — pull real facts from the code, never invent.
Output ONLY this markdown block:

## <Project name> — <one-line what-it-is>

- **Status:** <in progress / live / shipped / hackathon> + a live/demo/repo link if any
- **Ownership:** <solo, or which parts are mine vs teammates' — be precise, don't overclaim>
- **What it is:** <1-2 sentences a non-engineer understands>
- **Tech:** <the real stack: languages, frameworks, datastores, infra, key libraries>
- **Highlights:**
  - <concrete, measurable wins from the actual code/history — "cut payload 5MB -> 87KB",
     "60fps map interactions", named trade-offs and real decisions. Numbers > adjectives.>
  - <3 to 6 of these, strongest first>
- **My role / what I built:** <the parts you personally own, with specifics>

Pull metrics from the code where you can (bundle sizes, query times, test counts,
commit counts, scale numbers). If you can't verify a number, leave it out rather
than guess.
```
