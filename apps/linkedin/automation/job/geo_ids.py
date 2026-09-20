"""LinkedIn job-search geoId values (often differ from people-search geoUrns)."""

import re

# Confirmed from LinkedIn /jobs/search-results/ URLs (2026).
# Pune jobs geoId 114806696 ≠ people geoUrn 102713980.
DEFAULT_JOB_LOCATION_GEO_IDS = {
    "bangalore": "105214831",
    "bengaluru": "105214831",
    "pune": "114806696",
    "mumbai": "106164952",
    # Navi Mumbai is usually under Mumbai city/MMR in job search.
    "navi mumbai": "106164952",
    "mumbai metropolitan region": "106164952",
    "hyderabad": "105556573",
    "chennai": "106032064",
    "delhi": "106057199",
    "new delhi": "106057199",
    "gurgaon": "106142749",
    "gurugram": "106142749",
    "noida": "103644278",
    "kolkata": "104494288",
    "ahmedabad": "104990346",
    "jaipur": "101282230",
    "indore": "103671728",
    "india": "102095887",
}


def _normalize_location_key(location):
    return re.sub(r"\s+", " ", str(location or "").strip().lower())


def resolve_job_geo_id(location, geo_map=None):
    if not location:
        return None
    geo_map = geo_map or DEFAULT_JOB_LOCATION_GEO_IDS
    key = _normalize_location_key(location)
    if key in geo_map:
        return geo_map[key]
    key_short = key.split(",")[0].strip()
    if key_short in geo_map:
        return geo_map[key_short]
    for name, geo_id in geo_map.items():
        if name in key or key in name or name in key_short or key_short in name:
            return geo_id
    return None
