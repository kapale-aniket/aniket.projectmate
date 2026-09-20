"""LinkedIn geoUrn IDs for people search location filters."""

import re

DEFAULT_LOCATION_GEO_URNS = {
    "pune": "102713980",
    "bangalore": "105214831",
    "bengaluru": "105214831",
    "mumbai": "102356536",
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
    "maharashtra": "106030522",
    "karnataka": "106059524",
    "tamil nadu": "106035099",
    "gujarat": "106031611",
    "rajasthan": "101728296",
    "uttar pradesh": "106030604",
    "west bengal": "106050032",
    "india": "102095887",
}


def _normalize_location_key(location):
    return re.sub(r"\s+", " ", str(location or "").strip().lower())


def resolve_geo_urn(location, geo_map=None):
    if not location:
        return None
    geo_map = geo_map or DEFAULT_LOCATION_GEO_URNS
    key = _normalize_location_key(location)
    if key in geo_map:
        return geo_map[key]
    # "Maharashtra, India" → maharashtra
    key_short = key.split(",")[0].strip()
    if key_short in geo_map:
        return geo_map[key_short]
    for name, urn in geo_map.items():
        if name in key or key in name or name in key_short or key_short in name:
            return urn
    return None
