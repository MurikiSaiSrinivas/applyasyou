"""Education section helper.

The Education block is usually identical across every tailor. Fill in your
degrees once here; tailors just call add_education(doc).
"""

EDUCATION_PRIMARY = {
    "degree": "M.S., Your Field (Track)",
    "dates": "Aug 20XX - Dec 20XX",
    "school_location": "Your Graduate School, City, ST  ·  GPA X.XX",
}

EDUCATION_SECONDARY = {
    "degree": "B.Tech., Your Field",
    "dates": "Jun 20XX - Jul 20XX",
    "school_location": "Your Undergrad, Country  ·  GPA X.X",
}


def add_education(doc):
    """Write the standard Education section to the document."""
    from resume_lib import section_heading, education_block
    section_heading(doc, "Education")
    education_block(doc, **EDUCATION_PRIMARY)
    if EDUCATION_SECONDARY:
        education_block(doc, **EDUCATION_SECONDARY)
