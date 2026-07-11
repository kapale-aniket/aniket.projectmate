import re

from common.normalize import (
    EMPTY,
    extract_package_lpa,
    normalize_apply_link,
    normalize_company_name,
    normalize_company_size,
)

HIRING_PHRASES = (
    "hiring",
    "we are hiring",
    "we're hiring",
    "now hiring",
    "openings",
    "opening for",
    "vacancy",
    "vacancies",
    "join our team",
    "join us",
    "looking for",
    "walk-in",
    "walk in",
    "urgent requirement",
    "job opportunity",
    "recruiting",
    "immediate joining",
)

FRESHER_INTERN_PHRASES = (
    "fresher",
    "freshers",
    "intern",
    "interns",
    "internship",
    "entry level",
    "entry-level",
    "graduate",
    "trainee",
    "0 year",
    "0-1 year",
    "0 to 1 year",
    "no experience",
    "campus hire",
    "campus recruitment",
)

JOB_ROLE_PATTERNS = (
    r"(?:hiring|looking for|opening for|requirement for|role for)\s+([A-Za-z0-9][A-Za-z0-9 /\-&.+]{2,60})",
    r"(?:position|role)\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9 /\-&.+]{2,60})",
    r"#([A-Za-z0-9][A-Za-z0-9_]{2,40})",
)


def is_hiring_post(text):
    lower = (text or "").lower()
    return any(phrase in lower for phrase in HIRING_PHRASES)


def is_fresher_or_intern(text):
    lower = (text or "").lower()
    return any(phrase in lower for phrase in FRESHER_INTERN_PHRASES)


def extract_company_size(text):
    if not text:
        return EMPTY
    match = re.search(
        r"(\d[\d,]*\s*-\s*\d[\d,]*\s*employees|\d[\d,]+\+?\s*employees)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return EMPTY
    return normalize_company_size(match.group(1))


def extract_job_role(text):
    if not text:
        return EMPTY
    for pattern in JOB_ROLE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            role = match.group(1).strip(" .,-|")
            if len(role) >= 3:
                return role[:120]
    return EMPTY


def extract_company_name(author, text):
    company = normalize_company_name(author)
    if company != EMPTY:
        return company

    patterns = (
        r"(?:at|@)\s+([A-Z][A-Za-z0-9& .\-]{2,80})",
        r"(?:company|organization|organisation)\s*[:\-]\s*([A-Z][A-Za-z0-9& .\-]{2,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            name = normalize_company_name(match.group(1))
            if name != EMPTY:
                return name
    return EMPTY


URL_PATTERN = re.compile(r"https?://[^\s<>\"'\])]+")

APPLY_HREF_KEYWORDS = (
    "jobs/view",
    "currentjobid",
    "/jobs/",
    "apply",
    "career",
    "opening",
    "recruit",
    "intern",
    "form",
)


def extract_apply_link(text, hrefs=None):
    candidates = []
    for href in hrefs or []:
        href = (href or "").strip()
        if href.startswith("http"):
            candidates.append(href)

    for match in URL_PATTERN.finditer(text or ""):
        candidates.append(match.group(0).rstrip(".,);]"))

    linkedin_links = []
    other_links = []
    seen = set()

    for url in candidates:
        normalized = normalize_apply_link(url)
        if normalized != EMPTY:
            if normalized not in seen:
                seen.add(normalized)
                linkedin_links.append(normalized)
            continue

        lower = url.lower()
        if any(keyword in lower for keyword in APPLY_HREF_KEYWORDS):
            if url not in seen:
                seen.add(url)
                other_links.append(url)

    if linkedin_links:
        return linkedin_links[0]
    if other_links:
        return other_links[0]
    return EMPTY


def parse_hiring_post(post_id, post_url, author, text, apply_link_hrefs=None):
    if not text or not is_hiring_post(text) or not is_fresher_or_intern(text):
        return None

    description = re.sub(r"\s+", " ", text).strip()
    return {
        "post_id": post_id,
        "post_url": post_url,
        "apply_link": extract_apply_link(text, apply_link_hrefs),
        "company_name": extract_company_name(author, text),
        "job_role": extract_job_role(text),
        "company_size": extract_company_size(text),
        "package_lpa": extract_package_lpa(text),
        "description": description[:2000],
    }
