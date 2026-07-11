"""Load Excel/output format JSON written by dashboard settings."""

import json
import os

from common.excel_format_defaults import get_default_format, visible_columns

_FORMAT_CACHE = {}

__all__ = [
    "load_excel_format",
    "visible_columns",
    "column_headers",
    "column_keys",
]


def _config_dir():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "config", "excel_format")


def _default_path(scraper_type):
    return os.path.join(_config_dir(), f"{scraper_type}.json")


def load_excel_format(scraper_type):
    if scraper_type in _FORMAT_CACHE:
        return _FORMAT_CACHE[scraper_type]

    path = _default_path(scraper_type)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and data.get("columns"):
                _FORMAT_CACHE[scraper_type] = data
                return data
        except (OSError, json.JSONDecodeError):
            pass

    data = get_default_format(scraper_type)
    _FORMAT_CACHE[scraper_type] = data
    return data


def column_headers(fmt):
    return [col["header"] for col in visible_columns(fmt)]


def column_keys(fmt):
    return [col["key"] for col in visible_columns(fmt)]
