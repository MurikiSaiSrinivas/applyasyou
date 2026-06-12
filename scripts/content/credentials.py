"""Publications & Certifications helper.

Same content across every tailor. Adjust the lists below; tailors just
call add_credentials(doc).

If you have no publications or no certifications, leave the list empty or
remove the loop in add_credentials.
"""

PUBLICATIONS = [
    # Example: 'Publication: "Your Paper Title," Conference Name (Year)',
]

CERTIFICATIONS = [
    # Example: "Certification: AWS Solutions Architect Associate",
]


def add_credentials(doc):
    """Write the standard Publications & Certifications section.

    Section heading is only written if there's at least one entry to list.
    """
    if not PUBLICATIONS and not CERTIFICATIONS:
        return
    from resume_lib import section_heading, bullet
    section_heading(doc, "Publications & Certifications")
    for line in PUBLICATIONS:
        bullet(doc, line)
    for line in CERTIFICATIONS:
        bullet(doc, line)
