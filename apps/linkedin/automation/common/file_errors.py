"""Plain-language messages for common file access errors."""

import errno
from pathlib import Path


def friendly_file_error(exc, path=None, action="use"):
    """Turn OS/Windows file errors into messages users can act on."""
    name = Path(path).name if path else "this file"
    prefixes = {
        "delete": f'Could not delete "{name}".',
        "read": f'Could not open "{name}" for reading.',
        "write": f'Could not save "{name}".',
        "preview": f'Could not preview "{name}".',
        "download": f'Could not download "{name}".',
        "merge": "Could not create the merged file.",
        "use": f'Could not access "{name}".',
    }
    prefix = prefixes.get(action, prefixes["use"])

    winerror = getattr(exc, "winerror", None)
    errno_code = getattr(exc, "errno", None)
    msg_lower = str(exc).lower()

    file_locked = (
        winerror == 32
        or errno_code in (errno.EACCES, 13)
        or "being used by another process" in msg_lower
        or "permission denied" in msg_lower
        or "access is denied" in msg_lower
        or "process cannot access the file" in msg_lower
    )

    if file_locked:
        return (
            f"{prefix} The file is open in another program (such as Excel). "
            f'Close "{name}" and try again.'
        )

    if errno_code == errno.ENOENT or "no such file" in msg_lower or "not found" in msg_lower:
        return f'"{name}" was not found. It may have been moved or deleted already.'

    if errno_code == errno.ENOSPC or "disk full" in msg_lower or "no space" in msg_lower:
        return f"{prefix} Your disk is full. Free up space and try again."

    detail = str(exc).strip()
    if detail.startswith("[WinError"):
        detail = detail.split("]", 1)[-1].strip().strip("'\"")
    elif ":" in detail and detail.count(":") >= 2:
        detail = detail.split(":", 2)[-1].strip().strip("'\"")

    if detail and detail.lower() not in prefix.lower():
        return f"{prefix} {detail}"
    return prefix
