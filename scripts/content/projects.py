"""Bullet pools per project.

TEMPLATE: replace every entry with your real projects.

IMPORTANT honesty rule:
  When a project involves collaboration, frame it accurately. If you were
  the primary author but other contributors exist, say "primary author /
  big majority of commits", NOT "solo build". A wrong framing here will
  silently propagate into every tailor that imports it -- that is the
  whole point of keeping it in one place, but it is also the whole risk.
  Fix it once here and it propagates everywhere; don't fix it in N build
  scripts.

For each project, expose:
  <PROJECT>_STACK     a single string with the tech stack + year line
  <PROJECT>_DEFAULT   the baseline 3-4 bullet description
  <PROJECT>_FRONTEND  optional: frontend-platform reframe
  <PROJECT>_AUTH      optional: auth/security reframe
  <PROJECT>_SHORT     optional: 2-bullet condensed version

Pick the variant per tailor; don't override in the build script.
"""

# ===== Lead project (your highest-impact work) =====

PROJECT_LEAD_STACK = "React · Next.js · TypeScript · Node.js · PostgreSQL  |  20XX"

PROJECT_LEAD_DEFAULT = [
    "Replace with a one-line scope: what is this project, who is it for, what does it do.",
    "Replace with a concrete metric (perf cut, user count, completion rate).",
    "Replace with a technical depth bullet (architecture decision, tricky problem you solved).",
    "Replace with an end-to-end bullet (data pipeline, design system, CI/CD, etc.).",
]

PROJECT_LEAD_AUTH = [
    "Auth-foregrounded variant of the lead project.",
    "Concrete: OAuth provider(s), session strategy, token refresh handling, etc.",
    "Other end-to-end context.",
]


# ===== Second project =====

PROJECT_TWO_STACK = "TypeScript · React · Node.js  |  20XX"

PROJECT_TWO_DEFAULT = [
    "One scope bullet.",
    "One impact bullet (recognition, user feedback, metric).",
]


# ===== Third project (optional) =====

PROJECT_THREE_STACK = "Your stack  |  20XX"

PROJECT_THREE_DEFAULT = [
    "Replace.",
    "Replace.",
]
