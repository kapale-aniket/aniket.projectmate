"""Helpers for skipping keyword x location searches from the admin checklist."""

from __future__ import annotations


def _norm_keyword(keyword: str) -> str:
    return str(keyword or "").strip()


def _norm_location(location: str) -> str:
    return str(location or "").strip().casefold()


def search_pair_key(keyword: str, location: str) -> str:
    return f"{_norm_keyword(keyword)}|{_norm_location(location)}"


def is_search_skipped(keyword: str, location: str, skip_searches) -> bool:
    key = search_pair_key(keyword, location)
    skip_set = set()
    for item in skip_searches or []:
        if isinstance(item, str):
            if "|" in item:
                parts = item.split("|", 1)
                skip_set.add(search_pair_key(parts[0], parts[1]))
            else:
                skip_set.add(item.strip())
        elif isinstance(item, dict):
            skip_set.add(search_pair_key(item.get("keyword", ""), item.get("location", "")))
    return key in skip_set


def count_active_searches(keywords, locations, skip_searches=None):
    keywords = keywords or []
    locations = locations or [""]
    total = 0
    for keyword in keywords:
        for location in locations:
            if not is_search_skipped(keyword, location, skip_searches):
                total += 1
    return total


def load_runtime_skip_searches():
    """Load live skip list written by the admin UI during an active scrape."""
    import json
    import os

    task_id = os.environ.get("TERRA_TASK_ID")
    data_dir = os.environ.get("TERRA_DATA_DIR")
    if not task_id or not data_dir:
        return None
    path = os.path.join(data_dir, f"skip_searches_task_{task_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return list(data) if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, TypeError):
        return None
