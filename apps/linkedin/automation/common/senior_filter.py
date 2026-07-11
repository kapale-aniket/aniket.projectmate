"""Shared senior-level title/description filtering."""

import re

SENIOR_TITLE_PATTERN = re.compile(
    r"\b(?:senior|sr\.?|lead|staff|principal|architect|manager|director|"
    r"mid[\s-]?level|mid[\s-]?senior|head of|vp|vice president|"
    r"chief|team lead|tech lead)\b",
    re.IGNORECASE,
)


def is_senior_text(text):
    return bool(text) and SENIOR_TITLE_PATTERN.search(text) is not None
