import random
import re
import time

from common.dedupe import dedupe_records
from common.normalize import (
    EMPTY,
    clean_text,
    extract_package_lpa,
    job_id_from_url,
    normalize_apply_link,
    normalize_company_name,
    normalize_company_size,
)
from common.senior_filter import is_senior_text

INDIAN_CITIES = [
    "Pune", "Bangalore", "Bengaluru", "Hyderabad", "Mumbai",
    "Chennai", "Delhi", "Noida", "Gurgaon", "Gurugram", "Kolkata",
    "Ahmedabad", "Jaipur", "Indore", "Nagpur", "Kochi", "Chandigarh",
]

# Skills we look for inside a job description.
# display order in the Excel, and more specific skills sit before the general
# ones they would otherwise be swallowed by (e.g. "Spring Boot" before
# "Spring") so SKILL_SUPPRESSES can drop the redundant general match.
SKILL_PATTERNS = [
    ("Python", r"\bpython\b"),
    ("Django", r"\bdjango\b"),
    ("Flask", r"\bflask\b"),
    ("FastAPI", r"\bfast\s?api\b"),
    ("Pandas", r"\bpandas\b"),
    ("NumPy", r"\bnumpy\b"),
    ("Java", r"\bjava\b(?!script)"),
    ("Spring Boot", r"\bspring\s?boot\b"),
    ("Spring", r"\bspring\b"),
    ("Hibernate", r"\bhibernate\b"),
    ("J2EE", r"\bj2ee\b|\bjava ee\b"),
    ("JSP", r"\bjsp\b"),
    ("Servlets", r"\bservlets?\b"),
    ("Maven", r"\bmaven\b"),
    ("JUnit", r"\bjunit\b"),
    ("Microservices", r"micro\s?services?"),
    ("REST API", r"\brest(?:ful)?\b|\brest api\b"),
    ("GraphQL", r"\bgraphql\b"),
    ("JavaScript", r"\bjavascript\b"),
    ("TypeScript", r"\btypescript\b"),
    ("React", r"\breact(?:\.?js)?\b"),
    ("Angular", r"\bangular\b"),
    ("Node.js", r"\bnode\.?\s?js\b"),
    ("HTML", r"\bhtml5?\b"),
    ("CSS", r"\bcss3?\b"),
    ("Bootstrap", r"\bbootstrap\b"),
    ("SQL", r"\bsql\b"),
    ("MySQL", r"\bmysql\b"),
    ("PostgreSQL", r"\bpostgre(?:sql|s)?\b"),
    ("MongoDB", r"\bmongo\s?db\b"),
    ("Oracle", r"\boracle\b"),
    ("Redis", r"\bredis\b"),
    ("Kafka", r"\bkafka\b"),
    ("Git", r"\bgit\b|\bgithub\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("AWS", r"\baws\b|amazon web services"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|google cloud"),
    ("Linux", r"\blinux\b|\bunix\b"),
    ("Selenium", r"\bselenium\b"),
    ("Pytest", r"\bpytest\b"),
    ("Machine Learning", r"machine learning"),
    ("Data Structures", r"data structures"),
    ("Algorithms", r"\balgorithms?\b"),
    ("OOP", r"\boops?\b|object[- ]oriented"),
    ("Agile", r"\bagile\b|\bscrum\b"),
]

# When the key skill is detected, the listed general skills are dropped so the
# cell does not show both "Spring Boot" and "Spring".
SKILL_SUPPRESSES = {
    "Spring Boot": ("Spring",),
}

# Cap so the cell stays readable even for a long, keyword-stuffed description.
MAX_SKILLS = 12


def normalize_job_role(title):
    role = clean_text(title)
    if role == EMPTY:
        return EMPTY
    role = re.sub(r"\s*\(.*?\)\s*", " ", role).strip()
    role = re.sub(r"\s+", " ", role)
    return role[:200] if role else EMPTY


def normalize_location(raw, workplace_type=""):
    """Clean a raw location into a city, or "Remote"/"Hybrid - City".

    Remote/Hybrid are decided ONLY from the job's own location text and its
    workplace tag (On-site/Remote/Hybrid from job_scraper). We deliberately do
    NOT scan the whole page body here: the word "remote" appears all over a
    LinkedIn page (filters, "similar jobs"), and scanning it used to tag every
    job as Remote. Anything not Remote/Hybrid falls through to the city.
    """
    if not raw or raw == EMPTY:
        raw = ""
    else:
        raw = raw.strip()

    # Only the location string + the explicit workplace tag, never page body.
    combined = f"{raw} {workplace_type}".lower()

    if "work from home" in combined or re.search(r"\bremote\b", combined):
        return "Remote"
    if "hybrid" in combined:
        for city in INDIAN_CITIES:
            if city.lower() in raw.lower():
                return f"Hybrid - {city if city != 'Bengaluru' else 'Bangalore'}"
        return "Hybrid"

    for city in INDIAN_CITIES:
        if city.lower() in raw.lower():
            return "Bangalore" if city == "Bengaluru" else city

    if raw:
        first_part = raw.split(",")[0].strip()
        first_part = re.sub(
            r"\s+(District|Division|Metropolitan|Area|Region).*$",
            "",
            first_part,
            flags=re.IGNORECASE,
        )
        if first_part and len(first_part) < 40:
            return first_part

    return EMPTY


def parse_posted(raw, max_hours=None):
    """Return (posted_hours float, posted_text str) or (None, EMPTY) if too old."""
    if max_hours is None:
        from job.config import MAX_JOB_AGE_HOURS

        max_hours = MAX_JOB_AGE_HOURS

    if not raw or raw == EMPTY:
        return None, EMPTY

    text = raw.lower().strip()
    text = re.sub(r"^reposted\s+", "", text)

    if "just now" in text:
        return 0.0, "Just Now"

    if "yesterday" in text:
        hours = 24.0
        if hours > max_hours:
            return None, EMPTY
        return hours, "Yesterday"

    second_match = re.search(r"(\d+)\s*second", text)
    if second_match:
        hours = int(second_match.group(1)) / 3600.0
        if hours > max_hours:
            return None, EMPTY
        n = int(second_match.group(1))
        label = "1 Second Ago" if n == 1 else f"{n} Seconds Ago"
        return hours, label

    minute_match = re.search(r"(\d+)\s*minute", text)
    if minute_match:
        hours = int(minute_match.group(1)) / 60.0
        if hours > max_hours:
            return None, EMPTY
        n = int(minute_match.group(1))
        label = "1 Minute Ago" if n == 1 else f"{n} Minutes Ago"
        return hours, label

    hour_match = re.search(r"(\d+)\s*hour", text)
    if hour_match:
        hours = float(hour_match.group(1))
        if hours > max_hours:
            return None, EMPTY
        n = int(hour_match.group(1))
        label = "1 Hour Ago" if n == 1 else f"{n} Hours Ago"
        return hours, label

    day_match = re.search(r"(\d+)\s*day", text)
    if day_match:
        days = int(day_match.group(1))
        hours = days * 24.0
        if hours > max_hours:
            return None, EMPTY
        label = "1 Day Ago" if days == 1 else f"{days} Days Ago"
        return float(hours), label

    week_match = re.search(r"(\d+)\s*week", text)
    if week_match:
        return None, EMPTY

    month_match = re.search(r"(\d+)\s*month", text)
    if month_match:
        return None, EMPTY

    return None, EMPTY


EXPERIENCE_MENTION_PATTERN = re.compile(
    r"(?:"
    r"\d+\s*[-–to]+\s*\d+\s*years?|"
    r"\d+\+\s*years?|"
    r"\d+\s*years?|"
    r"\d+\s*year\b|"
    r"entry[- ]level|fresher|no experience|internship?"
    r")",
    re.IGNORECASE,
)


def has_senior_level_words(text):
    return is_senior_text(text)


def description_mentions_experience(text, experience_raw=""):
    if experience_raw:
        return True
    if not text:
        return False
    return EXPERIENCE_MENTION_PATTERN.search(text) is not None


def is_fresher_friendly_experience(text, experience_raw=""):
    """True when stated experience is fresher-friendly (0 / 0-1 / 0-2 years)."""
    source = experience_raw or text or ""
    normalized = normalize_experience_required(source)
    if normalized != EMPTY:
        low, high = experience_bounds(normalized)
        if low is None:
            return False
        return low <= 1 and high <= 2

    combined = f"{experience_raw} {text or ''}".lower()
    fresher_keywords = (
        "fresher", "entry level", "entry-level", "no experience",
        "0 year", "0 years", "0-1 year", "0-1 years", "0-2 year", "0-2 years",
        "0 to 1 year", "0 to 2 year",
    )
    if any(k in combined for k in fresher_keywords):
        return True

    if "intern" in combined:
        return True

    return False


def should_skip_for_fresher_filter(description_text="", job_title="", experience_raw=""):
    """Return (skip, reason) for fresher-only scraping.

    Senior roles are blocked by title (and explicit senior titles in experience line).
    Full description is NOT scanned for the word 'senior' (too many false positives
    like 'report to a senior engineer').
    """
    description_text = description_text or ""
    job_title = job_title or ""

    if has_senior_level_words(job_title):
        return True, "senior-level title"

    if experience_raw and has_senior_level_words(experience_raw):
        return True, "senior-level experience line"

    if not description_mentions_experience(description_text, experience_raw):
        # No explicit years → keep (often fresher/unspecified).
        return False, ""

    if is_fresher_friendly_experience(description_text, experience_raw):
        return False, ""

    return True, "experience not fresher-friendly (allowed: fresher / 0 / 0-1 / 0-2 years)"


KEYWORD_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "entry",
    "for",
    "fresher",
    "freshers",
    "graduate",
    "graduates",
    "in",
    "intern",
    "internship",
    "job",
    "jobs",
    "junior",
    "level",
    "of",
    "or",
    "role",
    "roles",
    "the",
    "to",
    "with",
}

# Generic role words — alone they match too many unrelated jobs (Java, ServiceNow…).
ROLE_WORDS = {
    "associate",
    "consultant",
    "developer",
    "engineer",
    "programmer",
    "analyst",
    "specialist",
}

# max = keep more jobs, but still require skill terms when present (e.g. python)
# balanced = all terms in title/card
# strict = all terms in title only
KEYWORD_MATCH_MODE = "max"


def keyword_match_terms(keyword):
    """Significant tokens from a search keyword (drops fresher/junior filler words)."""
    tokens = re.findall(r"[a-z0-9+#.\-]+", (keyword or "").lower())
    return [t for t in tokens if t not in KEYWORD_STOPWORDS and len(t) > 1]


def _card_title_hint(card_text):
    """Use the first meaningful card lines as the job title hint."""
    lines = []
    for raw in (card_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        # Skip LinkedIn chrome / meta lines.
        if lower in {"promoted", "viewed", "easy apply", "actively reviewing applicants"}:
            continue
        if lower.startswith("be an early applicant"):
            continue
        if re.fullmatch(r"\d+\s*(second|minute|hour|day|week|month)s?\s*ago", lower):
            continue
        lines.append(line)
        if len(lines) >= 2:
            break
    return " ".join(lines)


def job_matches_search_keyword(
    keyword,
    title="",
    card_text="",
    description="",
    strict_title=False,
    match_mode=None,
):
    """
    Return whether a job is related enough to the search keyword.

    Modes:
      - max: require skill terms when present (python/java/…); role words alone are not enough
      - balanced: all significant terms in title or card text
      - strict: all significant terms in title (or card title lines)
    """
    mode = (match_mode or KEYWORD_MATCH_MODE or "max").lower()
    if strict_title and mode != "max":
        mode = "strict"

    terms = keyword_match_terms(keyword)
    if not terms:
        return True, ""

    title_l = (title or "").lower().strip()
    card_title_l = _card_title_hint(card_text).lower()
    card_l = (card_text or "").lower()
    desc_l = (description or "").lower()[:5000]
    primary = title_l or card_title_l
    haystack = f"{title_l} {card_title_l} {card_l} {desc_l}".strip()

    if mode == "max":
        skill_terms = [t for t in terms if t not in ROLE_WORDS]
        role_terms = [t for t in terms if t in ROLE_WORDS]
        if skill_terms:
            # "python developer" → must mention python (not just any developer job).
            if not any(t in haystack for t in skill_terms):
                return False, f"does not match keyword '{keyword}'"
            return True, ""
        if any(t in haystack for t in (role_terms or terms)):
            return True, ""
        return False, f"does not match keyword '{keyword}'"

    if mode == "balanced":
        pool = f"{primary} {card_l}".strip()
        missing = [t for t in terms if t not in pool]
        if not missing:
            return True, ""
        # Allow one missing term from description.
        if len(missing) == 1 and missing[0] in desc_l:
            return True, ""
        return False, f"does not match keyword '{keyword}'"

    # strict
    if not primary:
        return False, f"does not match keyword '{keyword}'"
    missing = [t for t in terms if t not in primary]
    if not missing:
        return True, ""
    return False, f"does not match keyword '{keyword}'"


def should_skip_for_keyword_mismatch(
    keyword,
    job_title="",
    card_text="",
    description_text="",
    experience_raw="",
    strict_title=False,
    match_mode=None,
    allow_experience_bypass=True,
):
    """
    Return (skip, reason).

    When allow_experience_bypass is True, keyword mismatch never skips here — the
    fresher/experience filter (should_skip_for_fresher_filter) decides keep/skip.
    """
    ok, reason = job_matches_search_keyword(
        keyword,
        title=job_title,
        card_text=card_text,
        description=description_text,
        strict_title=strict_title,
        match_mode=match_mode,
    )
    if ok:
        return False, ""
    if allow_experience_bypass:
        return False, "keyword optional (experience filter applies)"
    return True, reason


def normalize_experience_required(text):
    if not text or text == EMPTY:
        return EMPTY

    lower = text.lower()

    range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*years?", lower)
    if range_match:
        return f"{range_match.group(1)}-{range_match.group(2)} Years"

    plus_match = re.search(r"(\d+)\+\s*years?", lower)
    if plus_match:
        return f"{plus_match.group(1)}+ Years"

    single_match = re.search(r"(\d+)\s*years?", lower)
    if single_match:
        n = int(single_match.group(1))
        return "0 Years" if n == 0 else f"{n} Years"

    if any(k in lower for k in ("fresher", "entry level", "entry-level", "0 year", "no experience")):
        return "0 Years"

    if "intern" in lower:
        return "0 Years"

    return EMPTY


def experience_bounds(experience_required):
    """Parse a normalized experience string into (min_years, max_years).

    Examples: "0 Years" -> (0, 0), "0-2 Years" -> (0, 2),
    "5+ Years" -> (5, inf), "-"/"" -> (None, None) when not stated.
    """
    if not experience_required or experience_required == EMPTY:
        return None, None

    text = experience_required.lower()

    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)", text)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    plus_match = re.search(r"(\d+)\s*\+", text)
    if plus_match:
        return int(plus_match.group(1)), float("inf")

    single_match = re.search(r"(\d+)", text)
    if single_match:
        n = int(single_match.group(1))
        return n, n

    return None, None


def normalize_freshers_eligible(text, experience_required):
    lower = (text or "").lower()
    exp = (experience_required or "").lower()

    yes_signals = [
        "fresher", "entry level", "entry-level", "0 year", "0 years",
        "no experience", "intern", "internship", "graduate program",
        "campus hiring", "campus recruit", "trainee", "graduate developer",
        "associate level", "new grad", "fresh graduate",
    ]
    no_signals = [
        r"\d+\+?\s*years?\s+(of\s+)?experience",
        r"minimum\s+\d+\s+year",
        r"at least\s+\d+\s+year",
        r"\d+\s*-\s*\d+\s*years",
    ]

    if "preferred" in lower and any(s in lower for s in ("fresher", "entry level")):
        return "Preferred"

    for pattern in no_signals:
        if re.search(pattern, lower):
            if not any(s in lower for s in ("fresher", "entry level", "0 year")):
                return "No"

    if exp and exp not in (EMPTY.lower(), "0 years", "-"):
        if exp != "0 years" and "0-" not in exp:
            digits = re.findall(r"\d+", exp)
            if digits and int(digits[0]) >= 1:
                return "No"

    if any(s in lower for s in yes_signals):
        return "Yes"

    if experience_required == "0 Years":
        return "Yes"

    if "preferred" in lower:
        return "Preferred"

    return EMPTY


def normalize_easy_apply(description_text):
    if description_text and re.search(r"\beasy\s*apply\b", description_text.lower()):
        return "Yes"
    return EMPTY


def extract_skills(text):
    """Comma-separated list of skills mentioned in a job description.

    Scans for each known skill (case-insensitive, word-boundary aware),
    drops general skills made redundant by a more specific match, keeps the
    SKILL_PATTERNS order, and caps the result at MAX_SKILLS. Returns "-" when
    nothing is found.
    """
    if not text:
        return EMPTY

    lower = text.lower()
    found = []
    for name, pattern in SKILL_PATTERNS:
        if re.search(pattern, lower):
            found.append(name)

    if not found:
        return EMPTY

    suppressed = set()
    for skill in found:
        for general in SKILL_SUPPRESSES.get(skill, ()):
            suppressed.add(general)

    # Keep SKILL_PATTERNS order, drop redundant general skills, then trim.
    skills = [s for s in found if s not in suppressed][:MAX_SKILLS]

    return ", ".join(skills) if skills else EMPTY


def normalize_job(raw_job):
    """Convert raw parsed job into normalized record. Returns None if invalid.

    This is the heart of the cleaning step. It runs every raw field through its
    matching cleaner and returns one tidy dictionary. It returns None (meaning
    "throw this job away") in three cases: no usable apply link, posted more
    than 24 hours ago, or missing a role/company after cleaning.
    """
    # Reject anything without a proper LinkedIn job link.
    apply_link = normalize_apply_link(raw_job.get("apply_link", ""))
    if apply_link == EMPTY:
        return None

    # parse_posted returns (hours, "5 Hours Ago"). hours is None if the job is
    # older than the configured window — drop those listings.
    from job.config import MAX_JOB_AGE_HOURS

    posted_hours, posted_text = parse_posted(
        raw_job.get("posted_raw", ""), max_hours=MAX_JOB_AGE_HOURS
    )
    if posted_hours is None:
        return None

    # body_text = whole page (fallback); description_text = "About the job" only.
    body_text = raw_job.get("raw_text", "")
    description_text = raw_job.get("description_text", "") or body_text
    experience_raw = raw_job.get("experience_raw", "")
    experience_required = normalize_experience_required(experience_raw)
    freshers_eligible = normalize_freshers_eligible(body_text, experience_required)

    # Build the clean record - these keys are exactly the columns in the Excel.
    job = {
        "job_role": normalize_job_role(raw_job.get("job_title", "")),
        "company_name": normalize_company_name(raw_job.get("company_name", "")),
        "company_size": normalize_company_size(raw_job.get("company_size", "")),
        "freshers_eligible": freshers_eligible,
        "experience_required": experience_required,
        "skills_required": extract_skills(description_text),
        "location": normalize_location(
            raw_job.get("location", ""), raw_job.get("workplace_type", "")
        ),
        "package_lpa": extract_package_lpa(body_text),
        "easy_apply": normalize_easy_apply(description_text),
        "posted_hours": posted_hours,        # number, used only for sorting
        "posted_text": posted_text,          # human-friendly, shown in Excel
        "apply_link": apply_link,
    }

    # If cleaning wiped out the role or company, the row would be useless.
    if job["job_role"] == EMPTY or job["company_name"] == EMPTY:
        return None

    return job


def deduplicate_jobs(jobs):
    """Remove repeats, keeping the first time each apply_link is seen."""
    return dedupe_records(jobs, lambda job: job.get("apply_link"))


def sort_jobs_newest_first(jobs):
    return sorted(
        jobs,
        key=lambda j: (
            0 if j.get("easy_apply") == "Yes" else 1,
            j.get("posted_hours", 999),
        ),
    )
