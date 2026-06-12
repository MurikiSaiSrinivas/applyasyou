# Email writing standards

The reference for every email the agent drafts in the user's voice. Codified
from observed patterns + the user's `master_prompt.txt`. Defer to this file
when drafting; if a draft feels wrong, check this file before iterating.

This template lives in `generic/templates/` and should be copied to the
project root as `EMAIL_STANDARDS.md` once the user's actual patterns are
filled in (the email-writer agent does this during onboarding).

---

## 1. Core voice rules (read these from master_prompt.txt)

Most voice rules live in `master_prompt.txt` (the voice-extractor agent
populates it from real writing samples). This file extends those with
email-specific structure rules.

Standard defaults if `master_prompt.txt` is empty:

- No buzzwords. Never appear: `passionate`, `leverage`, `synergize`, `utilize`,
  `dynamic`, `results-driven`, `go-getter`, `self-starter`, `team player`,
  `strong communicator`, `hard worker`, `motivated`, `energetic`,
  `detail-oriented`, `proven track record`, `thought leader`, `ninja`,
  `rockstar`, `guru`, `world-class`.
- Brutally honest. No flattery, no fake enthusiasm.
- Concrete over generic.
- Direct, no fluff. No "I hope this email finds you well." No "I just wanted
  to reach out."
- Casual but readable. Not corporate, not text-speak.
- No "I won't oversell on X" preemptive gap closer.
- Match recipient's energy (founder/recruiter/senior IC/peer).

If the user's `master_prompt.txt` includes additional rules (no dashes, no
first-person plural, specific banned/preferred words), those override the
defaults.

---

## 2. The canonical structure (cold founder/recruiter outreach)

This is the highest-converting cold outreach format for engineering roles.
Use as the default; deviate with reason.

```
Subject: <Role title> application, <User Full Name>

Hi <First Name>,

<One declarative sentence: how you found them or what triggered the email.>
I'm applying for the <Role> role. Resume attached, and this is my LinkedIn
<URL>.

<Fit paragraph, ~80-100 words>
  - Start: "I'm a <role descriptor> working in exactly your stack."
    (or whatever framing actually fits the role)
  - Current role: one sentence with team size + tech + scope
  - Stack: explicit list of relevant technologies
  - AI workflow: how the user uses AI day-to-day if relevant to the role
  - Recent shipped work: 2-3 concrete projects with stack + outcome.

<Why-them paragraph, ~50-80 words>
  - Reference something specific from their post / company positioning.
    Quote their phrase if it's distinctive.
  - Tie it to the user's actual shape (one concrete sentence).
  - One forward-looking sentence about what pulls them.
  - "Happy to talk." (close)

Best,
<User Full Name>
```

**Target length: 150-200 words.** Cold emails over 250 words don't get read.

---

## 3. Patterns by email type

### A. Cold founder outreach (~150-200 words)
Use the canonical structure above. Reference one specific thing from the
company's positioning or the recipient's recent post. End with "Happy to talk."

### B. Thank-you after a meeting (~30-50 words)
Short. No asks. No recap of meeting content. No "excited about the
opportunity." Acknowledge the time, sign off.

Template:
```
Hey <Name>,

Thanks for taking the time today.

Best,
<User First Name>
```

Variations: add one sentence with a specific reference to something they said
ONLY if genuinely useful, not as filler.

### C. Status check / soft nudge (~50-100 words)
For day-7 to day-10 silence after a high-signal interaction. Don't say "any
updates?" (anxious). Don't repeat the pitch. Implicit ask is "look at my app."

Template:
```
Hi <Name>,

Following up briefly. Wanted to confirm <thing they had access to> came
through cleanly. Happy to send anything else useful if there's a next step.

Best,
<User First Name>
```

### D. Visa-first question (LinkedIn comment or short DM)
Use ONLY when:
- The user has prior auto-rejection from this employer 2+ times (referral is
  the only realistic path)
- OR the JD has hardest-tier no-sponsor wording the user wants to confirm
  before investing time

NOT the default. Most cold outreach follows the canonical structure and lets
visa come up naturally.

Template:
```
Hey <Name>, saw your <team> post. <One concrete fit signal>. Quick question
first: does this role include <visa type> sponsorship? <User First Name>
```

### E. Decline an outreach (~50-60 words)
For recruiter/founder pitches that are a real mismatch. Be honest, decline
without burning the bridge.

Template:
```
Hi <Name>,

Thanks for reaching out. The <role> isn't a fit for my background. My work
is <user's actual lane>, and I don't have <specific gap> experience.

Happy to stay connected if any <relevant role types> come up in your pipeline.

Best,
<User First Name>
```

Rules:
- Acknowledge them
- State the specific mismatch (don't be vague)
- Leave the door open
- Don't apologize, don't soften, don't pretend to be flattered

### F. Negotiation / clarification (numbered concrete asks)
When the user needs specific operational answers. Status check + numbered
questions + quiet close.

Template:
```
Hey <Name>,

<One sentence status update on prior work>.

Wanted to lock down some logistics so I can plan around them. A few quick
questions:

1. <Specific question>
2. <Specific question>
3. <Specific question>

Would help a lot to have clarity on these. Thanks.
```

Rules:
- Numbered questions, one per line, no padding
- Don't apologize for asking
- Don't explain why you need to know
- Quiet "Thanks" close, not "really appreciate it"

### G. LinkedIn connect note (max ~200 chars for free accounts)
Specific role + one concrete receipt with metric + "wanted to flag it" +
first-name sign-off.

Template:
```
Hey <Name>, just applied to the <Role> role. <One concrete project receipt
with metric>. Wanted to flag it. <User First Name>
```

Variant for lighter touch (no specific project to drop):
```
Hey <Name>, just applied to the <Role>. <Lane fit description>. Wanted to
flag it. <User First Name>
```

---

## 4. Anti-patterns

Each of these reduces conversion. Codify them so the agent doesn't reintroduce
them across drafts.

### "I won't oversell on X" closer
Don't end an application answer with preemptive gap acknowledgment.
("I won't oversell on healthcare. My experience there is light.")
Why: meta-commentary on the user's own honesty draws attention to the gap
before the reader probes; weakens the answer.

### Bullets in cold emails
Don't paste a bullet list of resume highlights into an email body.
Why: reads as "here's my resume in slightly different format." Lazy.
Fix: prose. Three sentences of fit, one paragraph of why-them.

### Buzzwords creeping in
Every word on the buzzword blocklist (see §1) gets caught by the
resume-validator if the email is reviewed. Don't introduce them in drafts.

### Presuming next steps
Don't assume a code challenge / interview / next step that hasn't been
confirmed. ("Looking forward to the code challenge.")
Why: reads as presumptuous if the recruiter hasn't committed to that step.

### Double-apologizing for minor things
Don't apologize twice for being 5 seconds late, getting a name wrong, etc.
Why: reads as anxious. Confidence is signal.

### Mentioning mutual connections without permission
Don't write "I saw <mutual name> is connected to you" in a cold outreach.
Why: the mutual hasn't consented to being name-dropped. LinkedIn surfaces
mutuals automatically.

### Honesty rules from RESUME_HONESTY.md apply here too
- Solo / N commits framing on team projects: use "primary author / big
  majority of commits" instead.
- Metric claims: only real numbers, sourced from PROJECTS.md.
- Recognition claims: exact (2nd place not "winner", "accepted" not
  "published").

---

## 5. Length guidelines per email type

| Type | Word count |
|---|---|
| Cold founder/recruiter outreach | 150-200 |
| Thank-you after meeting | 30-50 |
| Status check / soft nudge | 50-100 |
| Visa-first question (LinkedIn comment) | 30-60 |
| Decline outreach | 50-60 |
| Negotiation / clarification | 80-150 |
| LinkedIn connect note | 200 chars max (LinkedIn free cap) |
| Internal team comms | 30-80 |

Anything over the upper bound: either split or cut.

---

## 6. When to break the template

The canonical structure is the default. Break it when:

- **Already warm**: existing relationship means less stack-fit recital, more
  "context update" / "next step."
- **Power-dynamic shift**: VP / staff+ / older recipient — slightly more
  formal, drop voice markers.
- **Crisis / urgency**: condense, lead with the thing.
- **Reply, not first contact**: anchor to what they said, don't restart the
  pitch.
- **Internal team comms**: shorter, less context-setting.
- **Group / multiple recipients**: address by team name not individual.

If unsure whether to break the template, ask the user before drafting.

---

## 7. Subject line rules

- **Application cold**: `<Role title> application, <Full Name>`
- **Reply to existing thread**: leave subject alone (Re: ...)
- **Status check**: `Re: <original subject>` if continuing a thread
- **Thank-you**: `Thanks for today` / `Re: <calendar event subject>`
- **Negotiation**: descriptive of the operational topic, not "Quick question"

Avoid: subjects with em dashes (use comma instead), "Urgent", clickbait,
exclamation marks.

---

## 8. How this file relates to other artifacts

- **`master_prompt.txt`** — voice rules (vocabulary, sentence shape, tone).
  This file extends with email-specific structure rules.
- **`templates/RESUME_BULLET_STYLE.md`** — bullet-shape rules for the resume.
  Buzzword blocklist is shared.
- **`templates/RESUME_HONESTY.md`** — fact-keeping rules. Apply to claims
  made in emails too (no inflated metrics, accurate ownership framing).
- **`.claude/agents/email-writer.md`** — the agent that drafts emails. Reads
  this file + `master_prompt.txt` + the user's prior sent emails for voice.
