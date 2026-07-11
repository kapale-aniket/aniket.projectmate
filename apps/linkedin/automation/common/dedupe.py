"""Deduplicate record lists by a key function."""


def dedupe_records(items, key_fn):
    seen = set()
    unique = []
    for item in items:
        key = key_fn(item)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
