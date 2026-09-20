import re


def extract_experience_raw(text):
    if not text:
        return ""

    lower = text.lower()

    patterns = [
        r"\d+\s*[-–to]+\s*\d+\s*years?",
        r"\d+\+\s*years?",
        r"\d+\s*years?",
        r"\d+\s*year",
        r"entry[- ]level",
        r"fresher",
        r"no experience",
        r"internship?",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return match.group(0)

    return ""


def _extract_company_size(lines):
    """Find a '... employees' phrase on the page, e.g. '51-200 employees'."""
    for line in lines:
        range_match = re.search(
            r"(\d[\d,]*\s*-\s*\d[\d,]*\s*employees)",
            line,
            re.IGNORECASE,
        )
        if range_match:
            return range_match.group(1)

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
    """Find LinkedIn's workplace tag: Remote, Hybrid, or On-site (or "")."""
    for line in lines:
        match = re.search(
            r"workplace type is\s+(remote|hybrid|on-?site)",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

    for line in lines:
        if len(line) > 30:
            continue
        match = re.match(r"(remote|hybrid|on-?site)\b", line, re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def _job_description_text(text):
    """Return the 'About the job' section when present."""
    start = -1
    for marker in ("About the job", "Job description", "About the role", "Role description"):
        pos = text.find(marker)
        if pos != -1:
            start = pos
            break
    if start == -1:
        return text

    end = len(text)
    for marker in (
        "About the company",
        "Similar jobs",
        "People also viewed",
        "Show more jobs",
        "More jobs like this",
    ):
        pos = text.find(marker, start + 1)
        if pos != -1:
            end = min(end, pos)

    return text[start:end]


_SECTION_HEADINGS = {
    "summary",
    "requirements",
    "minimum qualifications",
    "preferred qualifications",
    "responsibilities",
    "qualifications",
    "about the job",
    "job description",
    "about the company",
    "benefits",
    "what you'll do",
    "what you will do",
    "who you are",
    "apply",
    "easy apply",
    "show more",
    "show less",
}


def _looks_like_meta_line(line):
    lower = (line or "").lower().strip().rstrip(":")
    if not lower:
        return True
    if lower in _SECTION_HEADINGS:
        return True
    if lower in {
        "share",
        "save",
        "promoted",
        "follow",
    }:
        return True
    if "ago" in lower and ("·" in line or "hour" in lower or "day" in lower):
        return True
    if re.fullmatch(r"\d[\d,]*\s+applicants?", lower):
        return True
    if lower.endswith(":") and len(lower) < 40:
        return True
    return False


def _clean_title(title):
    title = (title or "").strip()
    if title.lower().startswith("job title:"):
        title = title[10:].strip()
    return title


def _extract_title_company_ai(lines):
    """Parse job detail pane text for title/company."""
    job_title = ""
    company_name = ""

    for idx, line in enumerate(lines):
        if line == "Share":
            try:
                company_name = lines[idx - 1]
                job_title = _clean_title(lines[idx + 2])
            except IndexError:
                pass
            if job_title and company_name and not _looks_like_meta_line(job_title):
                return job_title, company_name

    candidates = [ln for ln in lines[:50] if not _looks_like_meta_line(ln)]
    if candidates:
        job_title = _clean_title(candidates[0])
        for ln in candidates[1:8]:
            if _looks_like_meta_line(ln):
                continue
            if len(ln) <= 90 and "http" not in ln.lower():
                company_name = ln
                break

    for idx, line in enumerate(lines[:60]):
        if "ago" in line.lower() and "·" in line:
            for back in range(idx - 1, max(-1, idx - 5), -1):
                prev = lines[back]
                if _looks_like_meta_line(prev):
                    continue
                if prev == job_title:
                    continue
                if not company_name:
                    company_name = prev
                break
            break

    return job_title, company_name


def parse_job_detail(text, apply_link=""):
    """Extract raw job fields from LinkedIn job detail panel text."""
    lines = [x.strip() for x in (text or "").split("\n") if x.strip()]

    job_title, company_name = _extract_title_company_ai(lines)
    location = ""
    posted_raw = ""
    company_size = _extract_company_size(lines)
    workplace_type = _extract_workplace_type(lines)

    for line in lines:
        if "ago" in line.lower():
            parts = line.split("·")
            if len(parts) >= 2:
                location = parts[0].strip()
                posted_raw = parts[1].strip()
            else:
                posted_raw = line.strip()
            break

    experience_text = _job_description_text(text)

    return {
        "job_title": job_title,
        "company_name": company_name,
        "company_size": company_size,
        "workplace_type": workplace_type,
        "location": location,
        "apply_link": apply_link,
        "posted_raw": posted_raw,
        "experience_raw": extract_experience_raw(experience_text),
        "description_text": experience_text,
        "raw_text": text,
    }
