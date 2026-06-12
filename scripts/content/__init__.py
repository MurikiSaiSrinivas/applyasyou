"""Canonical resume content blocks for tailors. Template version.

Why this exists:
  Every build_<company>.py copies and tweaks the same Hexaware-equivalent
  bullets, Zemoso-equivalent bullets, Education block, etc. Pulling them
  into shared modules means changing your "primary author" framing (or
  whatever your honesty rule is) once, not N times.

What lives here:
  - jobs.py        Bullet pools per company you have worked at, with named
                   variants (default, frontend-leaning, auth-foregrounded).
  - projects.py    Bullet pools per project (your "EvOnGO" equivalent,
                   side projects, capstones), with named variants per
                   emphasis (perf, auth, frontend, etc.).
  - education.py   The Education section.
  - credentials.py Publications + certifications block.

How to use from a build script (see scripts/build_resume.py for a full
demo of all the imports):

  from content.jobs import EMPLOYER_A_DEFAULT, EMPLOYER_A_FRONTEND
  from content.projects import PROJECT_LEAD, PROJECT_LEAD_AUTH
  from content.education import add_education
  from content.credentials import add_credentials

  job_block(doc, ..., bullets=EMPLOYER_A_DEFAULT)
  project_block(doc, "ProjectLead", ..., bullets=PROJECT_LEAD_AUTH)
  add_education(doc)
  add_credentials(doc)

Naming convention:
  ALL_CAPS constants for static bullet lists.
  Suffixes (_DEFAULT, _FRONTEND, _AUTH, _SHORT, _FULL) name the emphasis.
  When you need a different angle on the same employer/project, add a NEW
  variant -- don't override the existing one in the build script. That
  way the honest framing rule (e.g. "primary author / big majority of
  commits" not "solo / Nx commits") never drifts.
"""
