"""Shared text/company/package/link normalization used by job and posts scrapers."""

import re

EMPTY = "-"

INVALID_COMPANY_NAMES = {
    "Next",
    "Previous",
    "Share",
    "Save",
    "Apply",
    "Follow",
    "1",
    "2",
    "3",
    "4",
    "5",
    "…",
    "Jump to active job details",
    "Show more options",
    "Promoted",
    "Easy Apply",
}

_JOB_ID_RE = re.compile(r"(?:currentJobId=|/jobs/view/)(\d+)")


def clean_text(value):
    if value is None:
        return EMPTY
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if text else EMPTY


def normalize_company_name(name):
    company = clean_text(name)
    if company in INVALID_COMPANY_NAMES or len(company) < 2:
        return EMPTY
    return company[:200]


def _bucket_employees(count):
    if count <= 10:
        return "1-10 Employees"
    if count <= 50:
        return "11-50 Employees"
    if count <= 200:
        return "51-200 Employees"
    if count <= 500:
        return "201-500 Employees"
    if count <= 1000:
        return "501-1000 Employees"
    if count <= 5000:
        return "1001-5000 Employees"
    return "5000+ Employees"


def normalize_company_size(raw):
    if not raw or raw == EMPTY:
        return EMPTY

    text = raw.lower().replace(",", "")
    range_match = re.search(r"(\d+)\s*-\s*(\d+)\s*employees?", text)
    if range_match:
        low, high = int(range_match.group(1)), int(range_match.group(2))
        return _bucket_employees(max(low, high))

    plus_match = re.search(r"(\d+)\+\s*employees?", text)
    if plus_match:
        return _bucket_employees(int(plus_match.group(1)))

    count_match = re.search(r"(\d+)\s*employees?", text)
    if count_match:
        return _bucket_employees(int(count_match.group(1)))

    return EMPTY


def extract_package_lpa(text):
    if not text:
        return EMPTY

    patterns = [
        r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)",
        r"(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)?",
        r"₹?\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)",
        r"(\d+(?:\.\d+)?)\s*(?:lpa|lakhs? per annum|lakhs?/annum)",
    ]

    lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return f"{groups[0]}-{groups[1]} LPA"
            return f"{groups[0]} LPA"

    return EMPTY


def job_id_from_url(url):
    if not url:
        return None
    match = _JOB_ID_RE.search(url)
    return match.group(1) if match else None


def normalize_apply_link(url):
    if not url:
        return EMPTY
    url = url.strip()
    if "linkedin.com" not in url:
        return EMPTY
    job_id = job_id_from_url(url)
    if job_id:
        return f"https://www.linkedin.com/jobs/view/{job_id}/"
    return EMPTY
