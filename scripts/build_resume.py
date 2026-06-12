"""Template resume builder. COPY this per tailor, edit, and run.

Workflow (from CLAUDE.md Section 5):
  1. cp scripts/build_resume.py scripts/build_<variant>.py
  2. Edit OUT_DIR, BASENAME, and the tailor-specific bits below
     (header / summary / skills / which content variants to use /
     project order).
  3. Run with the user's Python:  python scripts/build_<variant>.py
  4. Writes <OUT_DIR>/<BASENAME>.docx + .pdf (+ a .content.md sidecar).
     PDF needs Microsoft Word installed; without it you still get the .docx.

Architecture (Option B, added 2026-06-09):
  - Shared bullet pools live in scripts/content/ -- one Python module per
    domain (jobs, projects, education, credentials).
  - Each tailor imports the variants it needs by name. Adding a new variant
    in content/ propagates to every tailor that imports it.
  - This template shows the import shape with placeholder names. Replace
    EMPLOYER_A / PROJECT_LEAD with whatever you named the user's real
    constants in scripts/content/jobs.py and scripts/content/projects.py.

Honesty:
  Bullet framing rules (e.g. "primary author / big majority of commits"
  rather than "solo" when others contributed) live in scripts/content/
  modules. Don't override them inside this build script -- if you need a
  different angle, add a new variant in content/ and import it here.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resume_lib import (
    create_document, header_block, section_heading, normal_para,
    labeled_bullet, job_block, project_block, save_docx_and_pdf,
)
# Shared content -- replace placeholder names with the user's real ones
# (defined once in scripts/content/jobs.py + scripts/content/projects.py).
from content.jobs import (
    EMPLOYER_A_DEFAULT,
    EMPLOYER_B_DEFAULT,
    EMPLOYER_C_DEFAULT,
)
from content.projects import (
    PROJECT_LEAD_STACK, PROJECT_LEAD_DEFAULT,
    PROJECT_TWO_STACK, PROJECT_TWO_DEFAULT,
)
from content.education import add_education
from content.credentials import add_credentials

# Output paths -- relative to the repo root, OS-agnostic.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(HERE, "resumes", "frontend")
BASENAME = "YourName_Frontend"

os.makedirs(OUT_DIR, exist_ok=True)

doc = create_document()

# ===== Header (tailor-specific) =====
header_block(
    doc,
    name="YOUR NAME",
    title="Software Engineer  |  <stack one-liner>",
    contact="City, ST · email · phone · LinkedIn · GitHub",
)

# ===== Summary (tailor-specific) =====
section_heading(doc, "Summary")
normal_para(doc,
    "Two to three lines positioning this variant. Lead with the angle this resume "
    "is for. Concrete, no buzzwords."
)

# ===== Skills (tailor-specific) =====
section_heading(doc, "Technical Skills")
for label, body in [
    ("Languages: ", "..."),
    ("Frontend: ", "..."),
    ("Backend & APIs: ", "..."),
    ("Data & Infra: ", "..."),
]:
    labeled_bullet(doc, label, body)

# ===== Professional Experience (bullets from shared content) =====
section_heading(doc, "Professional Experience")
job_block(doc,
    title="Job Title",
    dates="Mon YYYY - Present",
    company_location="Company  ·  Location",
    bullets=EMPLOYER_A_DEFAULT)
job_block(doc,
    title="Previous Job Title",
    dates="Mon YYYY - Mon YYYY",
    company_location="Previous Company  ·  Location",
    bullets=EMPLOYER_B_DEFAULT)
job_block(doc,
    title="Earlier Job Title",
    dates="Mon YYYY - Mon YYYY",
    company_location="Earlier Company  ·  Location",
    bullets=EMPLOYER_C_DEFAULT)

# ===== Projects (stack + bullets from shared content) =====
section_heading(doc, "Projects")
project_block(doc,
    title="Project Lead Name",
    stack_year=PROJECT_LEAD_STACK,
    bullets=PROJECT_LEAD_DEFAULT)
project_block(doc,
    title="Project Two Name",
    stack_year=PROJECT_TWO_STACK,
    bullets=PROJECT_TWO_DEFAULT)

# ===== Education + Credentials (single function call each) =====
add_education(doc)
add_credentials(doc)

save_docx_and_pdf(doc, OUT_DIR, BASENAME)
