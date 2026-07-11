"""LinkedIn job search time-window helpers (f_TPR filter)."""

MIN_JOB_AGE_HOURS = 1
MAX_JOB_AGE_HOURS = 48


def normalize_job_age_hours(value, default=24):
    try:
        hours = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_JOB_AGE_HOURS, min(MAX_JOB_AGE_HOURS, hours))


def linkedin_time_filter_param(hours):
    """LinkedIn jobs search f_TPR value, e.g. r3600 for past 1 hour."""
    seconds = normalize_job_age_hours(hours) * 3600
    return f"r{seconds}"


def job_age_label(hours):
    h = normalize_job_age_hours(hours)
    if h == 1:
        return "Past 1 hour"
    return f"Past {h} hours"


def job_age_max_seconds(hours):
    return normalize_job_age_hours(hours) * 3600
