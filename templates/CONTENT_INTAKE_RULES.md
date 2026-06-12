# Content intake rules

How the agent converts user-pasted content (READMEs, design docs, project
descriptions) into resume bullets without losing information.

## The 3-place split

When the user shares N facts about a project, all of them land somewhere:

| Lives in | What | Read by |
|---|---|---|
| `PROJECTS.md` | ALL N facts, lightly cleaned | Future tailors, interview prep, the user |
| `scripts/content/projects.py` | 4-5 strongest facts, resume-grade | Build scripts |
| (discard pile) | Nothing | -- |

Never throw away a fact the user shared. PROJECTS.md is the canonical
archive. `content/projects.py` is a curated cut for the resume.

## Intake flow

1. User pastes project content. (Or pastes a PROJECT_INTAKE_PROMPT.md
   output from running the prompt against their code repo with Claude
   Code / Cursor.)

2. The bullet-writer agent extracts structured facts:
   - **Scope** (what is this project, who's it for, what does it solve)
   - **Tech** (specific tools, versions, stack)
   - **Metrics** (latency, scale, accuracy, users, perf)
   - **Outcomes** (what shipped, who used it, what changed)
   - **Ownership** (solo / primary author / team-of-N / contributor)

3. ALL extracted facts go into `PROJECTS.md` (using
   `templates/PROJECTS.template.md` as the block shape).

4. The agent picks the 4-5 strongest for the DEFAULT resume variant.

   Selection priority (in order):
   1. **Quantifiable impact** -- "cut by X%", "scaled to N users",
      "98% accuracy"
   2. **Hard technical depth** -- specific tools/patterns with
      measurable scope ("atomic component architecture across ~25
      screens", "single in-flight Future for token refresh race")
   3. **End-to-end ownership signal** -- "from concept to release prep",
      "owned the data-to-UI path", "primary author across N modules"
   4. **Recognition** -- award, publication, real user adoption,
      real customer name

5. Bullets get written to `scripts/content/projects.py` as
   `PROJECT_X_DEFAULT`, following `RESUME_BULLET_STYLE.md`.

6. The leftover facts stay in `PROJECTS.md`. When a future role needs
   a different angle (e.g. security-foregrounded), bullet-writer can
   create `PROJECT_X_AUTH` by going back to `PROJECTS.md` and picking
   the auth-relevant facts.

## When the user pastes raw content

Recognize the type:

| Source | First move |
|---|---|
| GitHub README | Extract scope/tech/setup. ASK for metrics + ownership clarity. |
| Design doc | Extract architecture/decisions. ASK for shipped outcome + impact. |
| Job description from their old role | ASK what THEY specifically owned vs the team. |
| Personal project blurb | Often already resume-adjacent; light edit. |
| Hackathon submission | Usually has the structured pieces -- just bullet-ify. |
| Code repo (via Claude Code) | Have them run PROJECT_INTAKE_PROMPT.md first. |

If facts are missing (no metric, no ownership clarity), ASK before
writing the bullet. Never invent.

## Asking pattern

When the agent needs to ask for missing context, ask only the questions
that can't be answered from the source content. Don't run a full intake
interview if 4 of the 5 pieces are already in the paste.

Standard questions when something is missing:

  Missing metric:
    "What's the number a recruiter would remember about this? Perf
     improvement, scale, accuracy, user count, anything quantifiable."

  Missing ownership clarity:
    "Were you sole contributor or part of a team? If team, what was
     your specific role?"

  Missing outcome:
    "What was the strongest concrete outcome? Did users see X? Did
     the system handle Y? Did it ship to production?"

  Missing scope:
    "How big was this -- N feature modules? N screens? N users? N
     records processed?"

## Maximum per project on the resume

4-5 bullets in the resume variant. If the user has 10 strong facts,
`PROJECTS.md` gets all 10; the resume gets the 4-5 strongest. The
other 5-6 stay available for variant generation later.

## Updating an existing project

If the user updates a project (added a new feature, shipped a new
metric), the agent:

1. Appends the update to `PROJECTS.md` (with a date stamp).
2. Re-checks if the existing `PROJECT_X_DEFAULT` variant should
   change (new metric stronger than an old bullet? Promote it).
3. If a resume variant changes, FLAG to the user that the
   corresponding PDFs in their corpus are now stale; they should
   rebuild the affected tailors before sending the resume again.

## Never invent

Never write a bullet whose underlying fact isn't in `PROJECTS.md` or
the user's resume corpus. If you find yourself wanting to say "this
project probably had X impact," go ASK.

The point of the 3-place split is that every claim in a resume is
traceable back to a sourced fact in `PROJECTS.md`. Don't break that
chain.
