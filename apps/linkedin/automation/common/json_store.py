"""Shared JSON file load/save helpers."""

import json
import os


def load_json(path, default=None):
    if not os.path.exists(path):
        return default() if callable(default) else default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return default() if callable(default) else default


def save_json(path, data, *, indent=2):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=indent)


def merge_json_defaults(data, defaults):
    merged = dict(defaults)
    if isinstance(data, dict):
        merged.update({key: data[key] for key in defaults if key in data})
    return merged
