# Onboarding simulation log

A dry-run walkthrough of a new user from `git clone` to the
"give me 20 jobs" handoff in CLAUDE.md Step 6. Captures friction
inline so we know what to file down before real users hit it.

**Run date:** 2026-06-14
**Workspace version:** v0.2 (commit `247d23d`, applyasyou repo)
**Simulated by:** orchestrator dry-run, no real user

If the workspace changes shape (new steps, removed steps, reshuffled
ordering), re-run the simulation and stamp a new date below the next
findings block. Don't delete past findings; mark them resolved.

---

## The walkthrough

### Stage 0 -- Get the code

```bash
git clone git@github.com:MurikiSaiSrinivas/applyasyou.git
cd applyasyou
ls
```

User sees the file tree. No automated next-step hint.

```bash
claude
```

CLI starts. CLAUDE.md loads as system prompt.

### Stage 1 -- First message

```
> hi
```

Agent detects no `.onboarded` marker -> onboarding mode -> runs
Step 0 (welcome + feedback opt-in).

Behind the scenes:

```bash
python -c "from lib.feedback import opt_in_prompt_text; print(opt_in_prompt_text())"
```

Generates `~/.applyasyou/user_id` (fresh UUID) and prints the opt-in
copy. User sees:

> Hey, welcome in. Quick thing before we set up your workspace.
>
> Quick ask.
>
> Hope this tool helps your search land. The only way I make it
> better is hearing where it broke for you. So I built a feedback
> channel that's context-free, no JDs, no resumes, no names. Just
> which agent and what felt off. Fully anonymous.
>
> It auto-fires a small event at clear friction moments (re-running
> the same agent twice, abandoning a build mid-flow), and you can
> send one anytime with /feedback.
>
> Your ID: 8f4c2a91-e7d3-4b16-9d5a-3a8e7c2f1d6b
> Email msaisrinivas08@gmail.com anytime to see or delete everything
> tied to it.
>
> Opt in? [Y/n]

```
> y
```

```bash
python -c "from lib.feedback import set_feedback_consent; set_feedback_consent(True)"
```

> Got it. Thanks.

### Stage 2 -- Step 1: Drop resumes

> Alright, first thing. Drop all your resumes into the `resumes/`
> folder. Any format works (PDF, docx). Every variant you have, even
> drafts. Say "done" when you have.

User drops 4 PDFs into `resumes/`.

```
> done
```

### Stage 3 -- Step 2: Read + organize

Agent reads each PDF, infers angle, organizes:

```bash
mkdir -p resumes/{frontend,backend,ai,new_grad}
mv resumes/Frontend_Heavy.pdf resumes/frontend/
mv resumes/Backend_Java.pdf resumes/backend/
mv resumes/AI_RAG_Focused.pdf resumes/ai/
mv resumes/New_Grad_2025.pdf resumes/new_grad/
```

> Read 4 variants. Organized them:
> - resumes/frontend/Frontend_Heavy.pdf (React + TypeScript + design systems)
> - resumes/backend/Backend_Java.pdf (Spring Boot + Postgres + microservices)
> - resumes/ai/AI_RAG_Focused.pdf (Python + LangChain + RAG production)
> - resumes/new_grad/New_Grad_2025.pdf (intern + projects, condensed)
>
> Good, that's done.

### Stage 4 -- Step 3: Pre-populate config + voice

Agent does the heaviest write step. Behind the scenes:

```bash
cp config.example.json config.json
cp profile.example.json profile.json
cp data/prospects/filters.example.json data/prospects/filters.json
```

Fills each with data inferred from resumes. Writes
`RESUME_DESCRIPTIONS.md` + `RESUME_CONTENT.md`. Invokes
`voice-extractor` on the resumes to seed `master_prompt.txt`.

> Set up your workspace. Here's what I wrote:
>
> - `config.json`: 28 stack keywords detected, top weighted as
>   React (5), TypeScript (5), Python (4), Java (4), LangChain (4),
>   AWS (3). 4 resume clusters mapped.
> - `profile.json`: filled name, email, phone, LinkedIn (your GitHub
>   link is missing, leave blank or add).
> - `data/prospects/filters.json`: role_include set to Software
>   Engineer / Full Stack Engineer / AI Engineer / Backend Engineer;
>   location set to your resume city.
> - `RESUME_DESCRIPTIONS.md` and `RESUME_CONTENT.md` populated.
> - `master_prompt.txt` drafted by voice-extractor. Resumes are weak
>   voice signals (no first-person prose); voice rules will sharpen as
>   you paste cover letters or longer writing samples later.
>
> One thing I guessed: marked you as targeting "AI/ML Engineer" too
> since your AI/RAG resume leans heavily there. If wrong, tell me.

### Stage 5 -- Step 4: Projects intake

> One more before we do real jobs. Do you have any new projects, or
> updates to existing ones, that aren't reflected in those resumes?
>
> Two ways to get them in:
>
> 1. From Claude Code / Cursor on the project repo: open
>    `PROJECT_INTAKE_PROMPT.md`, paste the prompt into Claude Code
>    while it's open on that project, paste the output back here.
> 2. From memory: just answer here. Name, stack, what it does, your
>    role, what's special, and any concrete numbers.

User pastes:

```
> yeah I built an LLM judge eval framework called "rubric-py", open
> source, 800 stars, evaluates RAG pipelines with custom metrics
```

Agent invokes `bullet-writer`:

> Got it. bullet-writer added rubric-py to `PROJECTS.md` and wrote 3
> bullet variants in `scripts/content/projects.py`:
>
> - `RUBRIC_PY_DEFAULT` (eval framework + 800 stars + RAG focus)
> - `RUBRIC_PY_AI` (LangChain integration + custom metrics)
> - `RUBRIC_PY_OSS` (OSS leadership + contributor count + adoption)
>
> If you have more, drop them now. Otherwise we move on.

```
> that's it
```

### Stage 6 -- Step 5: Content modules

> Filling out the rest of `scripts/content/`:
>
> - `jobs.py`: bullets per employer from your resumes (4 employers,
>   3-4 bullets each)
> - `education.py`: your MS + B.Tech entries
> - `credentials.py`: 2 certifications + 1 publication detected
>
> That's the foundation. Every future tailor picks bullets from these
> files instead of duplicating across build scripts.

### Stage 7 -- Step 6: Ask for ~20 real jobs (the handoff)

> Last setup piece. To actually tune everything to the jobs you'd
> apply to, I want to walk through ~20 real ones with you.
>
> Paste a real job posting (full text, or a URL if you'd rather), one
> at a time. For each one I'll run the analyzer, give you % match,
> alignment, gaps, visa read, comp read, apply/skip. If it's worth
> tailoring, I'll flag it for later.
>
> If you say "applied" at the end, I log it. If you're not interested,
> just paste the next one.
>
> Ready when you are, drop the first JD.

**End of simulated walkthrough.** Real conversation begins with the
first JD paste, which fires the jd-analyzer agent and enters Section 3
"Steady state" behavior.

---

## Findings (the friction log)

Numbered for traceability. Status: `open` until proven fixed.

### F1 -- No "what to do after `git clone`" signal
**Stage:** 0
**Status:** open
**Detail:** User runs `git clone`, then has to know to `cd` in and
run `claude`. README/ONBOARD/WALKTHROUGH should make this dead
obvious in the FIRST line of README.
**Fix surface:** `README.md` -- audit the entry-point section. Make
sure `claude` is the first command shown.

### F2 -- `resumes/` folder existence unclear
**Stage:** 2
**Status:** open
**Detail:** User is told to drop resumes into `resumes/`, but the
folder may not ship in the repo (was likely filter-repo'd out as
empty-with-`.gitkeep`). If it's not there, Finder errors.
**Fix surface:** add `resumes/.gitkeep`, OR change Step 1 to first
create the folder and tell the user the path.

### F3 -- `/feedback` mentioned before user knows what slash commands are
**Stage:** 1
**Status:** open
**Detail:** The opt-in copy references `/feedback` as if the user
knows what that means. They don't yet. Reads weird.
**Fix surface:** soften to "you can flag anything later." Drop the
slash command name from Step 0 copy.

### F4 -- Step 3 is a wall of text
**Stage:** 4
**Status:** open
**Detail:** The post-Step-3 report lists ~6 file writes and a guess
all in one block. Overwhelming.
**Fix surface:** split into 2 messages. First: "Wrote config + profile
+ filters". Second: "Voice rules drafted; here's what I'm assuming."

### F5 -- voice-extractor on resumes is weak signal
**Stage:** 4
**Status:** open / acknowledged
**Detail:** Resumes don't carry first-person prose voice. Running
voice-extractor on them produces shallow rules. The agent already
flags this honestly.
**Fix surface:** keep the honest disclaimer. Maybe in Step 8 prompt
the user once for a cover letter or LinkedIn About paste to enrich.

### F6 -- "variants" language assumes multiple resumes
**Stage:** 2, 4
**Status:** open
**Detail:** Single-resume users get language that implies plural.
**Fix surface:** Step 2 + Step 3 dialogue should branch on
`len(resumes) == 1` vs `> 1`. Simple count check.

### F7 -- Step 3 writes 6 files without confirmation
**Stage:** 4
**Status:** open
**Detail:** No "is this right?" checkpoint before writing config,
profile, filters, RESUME_DESCRIPTIONS, RESUME_CONTENT, and
master_prompt. User might want to redirect before files land.
**Fix surface:** Step 3 should show its planned writes as a list +
"sound right? [Y/n]" before executing. Cheap insurance against
mis-classification.

### F8 -- `PROJECT_INTAKE_PROMPT.md` cross-repo flow is high friction
**Stage:** 5
**Status:** open
**Detail:** Step 4 Option 1 asks the user to open Claude Code in
another repo, paste a prompt, paste output back. Real users will skip
to Option 2 (just type in chat) every time. Promoting Option 1 to
"first option" misframes the realistic path.
**Fix surface:** reverse the order in Step 4. Lead with "just answer
here" (Option 2). Demote the cross-repo prompt to "if you want a
deeper brief from your repo's Claude Code session."

### F9 -- User-claimed metrics get recorded without verification
**Stage:** 5
**Status:** open
**Detail:** User said "800 stars" and the bullet-writer wrote it
straight in. Three months later the count is stale. No audit trail.
**Fix surface:** the bullet should include a `<verifiable: GitHub
star count, as of 2026-06-14>` tag inline, OR a separate
`PROJECTS_METRIC_AUDIT.md` that timestamps stated metrics. Hook into
voice-extractor's "stale metric" check (doesn't exist yet).

### F10 -- Step 4 / Step 5 overlap
**Stage:** 5, 6
**Status:** open
**Detail:** bullet-writer in Step 4 wrote to
`scripts/content/projects.py` already. Step 5 then claims it'll fill
out content modules, but projects.py is already done. The user might
feel "wait, didn't we just do this?"
**Fix surface:** rewrite Step 5 to be ONLY about the OTHER content
modules (`jobs.py`, `education.py`, `credentials.py`). Make explicit
that projects.py was done in Step 4. Or merge 4 + 5 cleanly.

### F11 -- Single-paragraph onboarding tone might still slip
**Stage:** all
**Status:** open
**Detail:** The tone rules in CLAUDE.md Section 1 are clear (warm,
no buzzwords, no exclamation marks). But the dry-run examples in this
log show phrases like "Good, that's done" which is fine, AND phrases
like "the foundation" which leans corporate. Real runs need vigilance.
**Fix surface:** keep observing in real onboardings. After 3 real
runs, distill the actual tone slips and update Section 1 rules.

### F12 -- "ready when you are" sign-off is generic
**Stage:** 7
**Status:** open
**Detail:** Step 6 handoff ends with "Ready when you are, drop the
first JD." Fine but bland. Could be sharper given how much setup just
happened.
**Fix surface:** consider "OK, you're set up. Show me what you're
considering." Or similar. Minor polish.

---

## Action items (prioritized)

P0 (block real users):
- F1 README audit
- F2 confirm `resumes/.gitkeep` ships

P1 (quality of first impression):
- F4 split Step 3 report
- F7 add Step 3 confirmation gate
- F8 reverse Step 4 option ordering

P2 (correctness + audit trail):
- F9 metric audit pattern
- F10 clarify Step 4/5 boundary

P3 (polish):
- F3 opt-in copy
- F6 single-resume language
- F11 ongoing tone observation
- F12 Step 6 sign-off

---

## Open questions (not yet decided)

1. **Should the simulation be re-run automatically?** Could write a
   `scripts/simulate_onboarding.py` that pipes a fake user transcript
   through a sandboxed Claude session and diffs against this log.
   Probably overkill until v0.5+.

2. **Should friction findings auto-create GitHub Issues?** Each
   numbered F becomes an issue. Easier to triage but adds maintenance.
   Defer until real users surface things first.

3. **Stage 8 simulation (the per-JD loop) -- worth doing?** Walking
   through the first JD paste -> analyzer -> tag-for-tailor decision
   -> "applied" handoff would surface friction in the steady-state
   loop too. Reasonable next dry-run.
