# Resume honesty rules

These rules supersede style. If a bullet has to be slightly less polished
to be accurate, accuracy wins.

The cost of getting caught in an interview (or a reference check) is
much higher than the marginal benefit of a slightly stronger bullet.

## "Solo" vs "primary author"

Use "solo" ONLY if you were the sole contributor AND the git log backs
it up. Otherwise:

  "primary author / big majority of commits"  -- you led, others contributed
  "lead developer on a team of N"             -- you led a team
  "as part of an N-person team"               -- you contributed
  "contributor on <project>"                  -- you helped

NEVER claim solo on a team project. If the project README or
package.json or git log lists collaborators, you're not solo even if
you wrote 90% of the code.

## Quantify or qualify, never neither

Every metric in a bullet must be real. If you write "cut response time
from 25s to 8s," the actual number was 25 -> 8 (not a rough estimate).

If you don't have a real number, qualify with concrete scope ("for
fraud detection pipelines processing customer transactions") instead
of inflating a fake metric.

## Skills list discipline

Only list a technology if you've:
  - Shipped with it in a paid role, OR
  - Built and shipped a substantial personal project with it, OR
  - Used it productively for >40 hours of real work.

Tutorial-level exposure (followed a YouTube guide once) does not count
and will get caught the first time an interviewer probes.

If a technology is on your resume, you should be able to answer at
least 3 increasingly specific questions about it without bluffing.

## Project credit framing

If a project was a team effort:
  - "team of N" with your specific role
  - "as part of an N-person team"
  - Never just imply you owned it

If unsure of your contribution percentage, use "primary author" or
"contributor" rather than "owner" or "creator."

## Recognition claims

Awards, publications, certifications: only list ones you actually have.
  - If you placed 2nd, say 2nd. Don't round up.
  - If your paper is "accepted," it's not yet "published."
  - If your talk was at a meetup, say "meetup" not "conference."
  - Cert exam scheduled but not passed isn't a cert.

## "Production" vs "production-like"

"Shipped to production" means real users use it. If it's an internal
tool that you and three friends use, say "internal tool used by N
people" or "in active use at <company>."

A side project that's only on GitHub but never deployed isn't "shipped"
unless you specifically say "open-sourced and adopted by N stars/forks/users."

## Time-anchored claims

Date claims must be current.
  - "Currently leading 3 mobile devs" must be true right now, not
    6 months ago.
  - If you left a role, the bullet shifts to past tense and the date
    range matches your actual employment.
  - "Recently shipped" should be within ~6 months.

## When in doubt, downgrade

When you're not sure whether a stronger claim is honest, use the weaker
one. Examples:

  Unsure if "scaled to 10K users" or "scaled to thousands of users"?
  -> Use "scaled to thousands" until you can pull the real number.

  Unsure if you "architected" or "contributed to the architecture"?
  -> Use "contributed to the architecture."

  Unsure if your metric was "30% latency cut" or "noticeable latency cut"?
  -> Pull the real number from your monitoring before adding it; if
     you can't, drop the metric and use scope ("for production traffic").

## What to do when you find a violation

If the validator (or you, or an interviewer) flags a bullet that
overclaims:

  1. Fix it in the relevant scripts/content/ module immediately.
  2. Rebuild any tailors that import that variant.
  3. Do NOT send the corrected resume to anyone who already received
     the old one (don't draw attention to the change).
  4. Update PROJECTS.md if the underlying fact (not just the framing)
     was wrong.
