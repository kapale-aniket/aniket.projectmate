import os
from datetime import date

from common.json_store import load_json, merge_json_defaults, save_json
from job.config import JOB_KEYWORDS, LOCATIONS
from job.master_store import OUTPUT_DIR

STATE_PATH = os.path.join(OUTPUT_DIR, "scrape_state.json")


def default_checkpoint(day=None):
    return {
        "date": (day or date.today()).strftime("%Y-%m-%d"),
        "location_index": 0,
        "keyword_index": 0,
        "page_num": 0,
        "card_index": 0,
        "interrupted": False,
        "context": "",
    }


def load_checkpoint():
    data = load_json(STATE_PATH, default_checkpoint)
    return merge_json_defaults(data, default_checkpoint())


def save_checkpoint(checkpoint):
    save_json(STATE_PATH, checkpoint)


def clear_checkpoint():
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)


def checkpoint_context(checkpoint):
    location_index = checkpoint.get("location_index", 0)
    keyword_index = checkpoint.get("keyword_index", 0)
    page_num = checkpoint.get("page_num", 0)
    card_index = checkpoint.get("card_index", 0)

    location = (
        LOCATIONS[location_index]
        if 0 <= location_index < len(LOCATIONS)
        else "unknown location"
    )
    keyword = (
        JOB_KEYWORDS[keyword_index]
        if 0 <= keyword_index < len(JOB_KEYWORDS)
        else "unknown keyword"
    )
    return f"{keyword} | {location} | page {page_num + 1}, card {card_index + 1}"


def sync_checkpoint_context(checkpoint):
    checkpoint["context"] = checkpoint_context(checkpoint)
    return checkpoint
