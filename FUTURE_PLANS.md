# Future plans

Things this workspace will grow into. Captured here so they don't fall
through cracks between sessions. None of these are committed dates;
they're sketches.

---

## Chrome extension expansion

Today the extension does Google Jobs harvest, Wellfound scrape +
JD-fetch, LinkedIn scrape (search / saved / applied), and a LinkedIn
post URL processor.

Three additions worth designing:

### 1. LinkedIn profile scraper (for legitimacy checks)

**Why:** when a recruiter or founder DMs cold, the first move is
"is this person real and what's their track record?" Right now this
requires a separate browser tab + manual search + sometimes a
RocketReach/Clay.earth lookup. The extension could:

- On a LinkedIn profile URL, capture: current role, past roles,
  founded-companies, mutual connections, post count, post hashtags
  (the way `#inthearena` was a signal for Andrew Garcia)
- Send to a new local_sink endpoint `POST /api/linkedin/profile`
- The sink runs a quick LLM classification: "legit recruiter /
  founder / engineer / suspect" + a one-line summary
- Output lands in `data/contacts/` keyed by their LinkedIn handle

Acceptance criteria: the agent can answer "is X legit?" in 5 seconds
from a profile URL the user pastes, with cached evidence the user
can review.

### 2. Generalized post scraper

Today the post URL processor handles LinkedIn posts (`linkedin.com/posts/...`).
Worth generalizing to:
- Reddit posts (someone shared a job in a subreddit)
- HN comments / Show HN ("we're hiring" threads)
- Twitter/X posts (recruiter or founder hiring tweets)

Same shape: paste URL -> background tab fetches -> LLM classifies
intent (`careers_page`, `email_resume`, `referral_ask`,
`open_role_link`, `other`) -> outputs a structured suggestion.

### 3. Job scraping expansion

Today: GitHub-curated lists (vanshb03, SimplifyJobs, jobright-ai),
Wellfound, LinkedIn job search/saved/applied.

Add:
- **Y Combinator Work at a Startup** (`workatastartup.com`) -- huge
  founding-engineer source, no public API
- **Google Jobs as a CLI flow** (today only the extension does
  Google; the CLI version would let `/fetch-jobs` cover it without
  the browser)
- **AngelList / Wellfound public job board** (not the logged-in
  feed)

Each one is a per-source scraper that emits prospects in the same
shape, then the existing pipeline takes over (filters -> heuristic
scoring -> auto AI upgrade).

---

## Interview prep template + agent

The Golden Analytics prep doc (Resume/Golden Analytics/INTERVIEW_PREP_*.md)
has a shape worth abstracting:

- **Pipeline state** -- who routed you, contact info, current step
- **Intel block** -- company, founders, funding, values, product
  principles
- **Strategy decisions** -- what to lead with, what to skip, what
  to hold for later rounds
- **Round-by-round** -- R1 conversational (anchor + 3 questions);
  R2 technical depth (heavy artillery goes here); R3 system design /
  in-person
- **Recalibration block** -- "earlier we thought X; new intel
  changes the plan to Y." This is where Kate's clarification
  ("round 1 is conversational, not technical") landed in the
  Golden Analytics doc.
- **Honest gaps** -- what NOT to fake. Visa, comp expectations,
  domain knowledge.
- **Logistics flags** -- in-person date, time zone, travel needs,
  comp band confirmation point.

**What to build:**

1. `templates/INTERVIEW_PREP.md` -- the canonical shape, with each
   block named + a one-line "what to fill"
2. `.claude/commands/prep.md` -- slash command `/prep <company>`
3. `.claude/agents/interview-prep.md` -- subagent that takes a
   company name + role + any intel the user has, produces the doc
   skeleton, and asks targeted questions for the gaps

**Why defer:** the current Golden Analytics process is mid-flight.
After it concludes (whatever the outcome), capture what mattered vs.
what was noise. Then build the template/agent so it reflects real
signal, not theoretical structure.

---

## Other deferred items

- **`/voice <sample>` slash command** -- the voice-extractor agent
  is already wired to fire on natural-language corrections (see
  CLAUDE.md Section 6). A slash-command alias may not be needed.
  Reassess after 10+ real corrections to see if users want an
  explicit invocation path.

- **`/status` dashboard command** -- decided against (CLAUDE.md
  Section 7 keyword routing covers "how am I doing"). Could
  revisit if users start asking for a JSON dump.

- **Sweep auto-create row for unmatched ATS receipts** -- today
  the sweep ASKS when a receipt doesn't match a row. Could auto-create
  with a "needs review" tag instead. Defer until we see how often
  this happens.

- **Notion mirror for feedback events** -- mentioned in the feedback
  system design (Supabase Edge Function pushing summaries to a
  Notion page). Defer until the volume justifies a daily glance.

- **Per-user dashboard view in Supabase** -- once events accumulate,
  build SQL views (`recent_feedback`, `top_complaints_by_agent`,
  `friction_by_session`). Defer until 100+ events exist.
