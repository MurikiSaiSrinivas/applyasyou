"""Bullet pools per company you have worked at.

TEMPLATE: replace every entry with your real content. Pull from
RESUME_CONTENT.md and your existing resumes; never invent facts.

For each employer add one or more named variants. Pick the variant that
matches each tailor's emphasis. When you need a new angle, add a new
constant here -- never override the framing inside a build script (that
is how honest details drift over time).

Suggested variant suffixes:
  _DEFAULT     baseline framing
  _FRONTEND    frontend / UI-platform emphasis
  _BACKEND     backend / API emphasis
  _AUTH        auth / security foregrounded
  _LEADERSHIP  leadership / team-lead framing
  _SHORT       2-3 bullets for tight 2-page tailors
"""

# ===== Most recent employer =====

EMPLOYER_A_DEFAULT = [
    "Replace this line with a real bullet describing what you owned and shipped.",
    "Replace with a quantitative impact bullet (e.g., cut X by Y%, scaled to Z users).",
    "Replace with a cross-functional / leadership bullet if relevant.",
]

EMPLOYER_A_FRONTEND = [
    "Frontend-specific variant of the bullets above. Lead with reusable components, rendering performance, or design-system work.",
    "Concrete tooling: React, TypeScript, build pipeline, performance metric.",
]


# ===== Previous employer =====

EMPLOYER_B_DEFAULT = [
    "Replace with what you shipped at this employer.",
    "Replace with a concrete metric or scope detail.",
]


# ===== Earlier employer (intern / first job / etc.) =====

EMPLOYER_C_DEFAULT = [
    "One bullet capturing scope.",
    "One bullet capturing impact or skill.",
]
