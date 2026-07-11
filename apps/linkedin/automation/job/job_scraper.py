import re


def extract_experience_raw(text):
    if not text:
        return ""

    lower = text.lower()   # search case-insensitively by lower-casing first

    # Each string below is a regex (a search pattern). \d means "a digit",
    # \s* means "optional spaces", ? means "the previous thing is optional".
    patterns = [
        r"\d+\s*[-–to]+\s*\d+\s*years?",   # "2 - 4 years" / "2 to 4 years"
        r"\d+\+\s*years?",                  # "3+ years"
        r"\d+\s*years?",                    # "5 years"
        r"\d+\s*year",                      # "1 year"
        r"entry[- ]level",                  # "entry level" / "entry-level"
        r"fresher",                         # "fresher"
        r"no experience",                   # "no experience"
        r"internship?",                     # "intern" / "internship"
    ]

    # Return the text of the first pattern that matches anywhere in the string.
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group(0)   # group(0) = the exact text that matched

    return ""


def _extract_company_size(lines):
    """Find a "... employees" phrase on the page, e.g. "51-200 employees".

    Tries a range ("11-50 employees") first; if none, accepts a single count
    ("5,000+ employees"). Returns "" when the page doesn't list a size.
    """
    # First preference: a range like "51-200 employees".
    for line in lines:
        range_match = re.search(
            r"(\d[\d,]*\s*-\s*\d[\d,]*\s*employees)",
            line,
            re.IGNORECASE,
        )
        if range_match:
            return range_match.group(1)

    # Fallback: a single number like "5,000+ employees".
    for line in lines:
        count_match = re.search(
            r"(\d[\d,]+\+?\s*employees)",
            line,
            re.IGNORECASE,
        )
        if count_match:
            return count_match.group(1)

    return ""


def _extract_workplace_type(lines):
    """Find LinkedIn's workplace tag: Remote, Hybrid, or On-site (or "").

    LinkedIn shows the workplace type as its own UI element, so it lands on its
    own short line in the page text. We trust only two reliable spots:
      1. The insight line "...workplace type is Remote/Hybrid/On-site."
      2. A short standalone pill that STARTS with the workplace word, possibly
         joined to the employment type (e.g. "Hybrid", "Remote · Full-time").

    Returns "" when the page states no workplace type, so the city is kept.

    Scanning only these spots (never the whole page) is the fix for the bug
    where the word "remote" appearing anywhere — sidebars, "similar jobs" —
    wrongly tagged every single job as Remote.
    """
    # Most reliable: the explicit "workplace type is X" insight line.
    for line in lines:
        match = re.search(
            r"workplace type is\s+(remote|hybrid|on-?site)",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

    # Fallback: a short standalone pill anchored at the start of the line.
    for line in lines:
        if len(line) > 30:
            continue
        match = re.match(r"(remote|hybrid|on-?site)\b", line, re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def _job_description_text(text):
    """Return just the 'About the job' section, not the whole page.

    We slice from "About the job" up to the next section ("About the company"
    or "Similar jobs"). This keeps skill/experience scanning focused on the
    actual description and away from unrelated sidebar text.
    """
    start = text.find("About the job")
    if start == -1:
        return text   # heading not found -> fall back to the whole page

    # Find where the description ends: the earliest of the following headings.
    end = len(text)
    for marker in ("About the company", "Similar jobs"):
        pos = text.find(marker, start + 1)
        if pos != -1:
            end = min(end, pos)

    return text[start:end]


def parse_job_detail(text, apply_link=""):
    """Extract raw job fields from LinkedIn job detail page text."""

    # Split the page into non-empty, trimmed lines so we can scan line by line.
    lines = [x.strip() for x in text.split("\n") if x.strip()]

    job_title = ""
    company_name = ""
    location = ""
    posted_raw = ""
    company_size = _extract_company_size(lines)
    workplace_type = _extract_workplace_type(lines)

    # Walk every line looking for two landmarks on a LinkedIn job page.
    for idx, line in enumerate(lines):
        # The word "Share" sits just below the header block, so the company
        # name and title are at known offsets around it. (Layout-dependent,
        # wrapped in try/except in case the structure isn't what we expect.)
        if line == "Share":
            try:
                company_name = lines[idx - 1]
                job_title = lines[idx + 2]
            except IndexError:
                pass

        # The location + "posted X ago" usually share one line separated by
        # a "·" dot, e.g. "Pune, India · 5 hours ago".
        if "ago" in line.lower():
            parts = line.split("·")
            if len(parts) >= 2:
                location = parts[0].strip()
                posted_raw = parts[1].strip()
            else:
                posted_raw = line.strip()

    # Pull out the description once so we can reuse it for experience + skills.
    experience_text = _job_description_text(text)

    # Hand back a dictionary of raw fields. job_filter.normalize_job() takes
    # this and produces the clean record that finally goes into the Excel.
    return {
        "job_title": job_title,            # e.g. "Python Developer"
        "company_name": company_name,      # e.g. "Acme Corp"
        "company_size": company_size,      # e.g. "51-200 employees" (or "")
        "workplace_type": workplace_type,  # "Remote"/"Hybrid"/"On-site" (or "")
        "location": location,              # e.g. "Pune, India"
        "apply_link": apply_link,          # the job's URL (passed in by job.py)
        "posted_raw": posted_raw,          # e.g. "5 hours ago"
        "experience_raw": extract_experience_raw(experience_text),  # e.g. "2-4 years"
        "description_text": experience_text,  # the "About the job" section, for skills
        "raw_text": text,                  # the full page text, used as a fallback
    }
