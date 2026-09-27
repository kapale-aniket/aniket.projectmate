import os
import shutil
import tempfile
import time
from pathlib import Path


def _is_lock_error(exc):
    winerror = getattr(exc, "winerror", None)
    errno_code = getattr(exc, "errno", None)
    msg = str(exc).lower()
    return (
        winerror in (5, 32)
        or errno_code == 13
        or "access is denied" in msg
        or "permission denied" in msg
        or "being used by another process" in msg
        or "process cannot access the file" in msg
    )


def _unique_sidecar(target: Path) -> Path:
    candidate = target.with_name(f"{target.stem}_saved{target.suffix}")
    n = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}_saved_{n}{target.suffix}")
        n += 1
    return candidate


def _replace_with_retry(tmp_path: Path, target: Path, retries=6):
    """Replace target; if locked (Excel open), write a sidecar file instead."""
    last_exc = None
    for attempt in range(retries):
        try:
            os.replace(str(tmp_path), str(target))
            return target
        except OSError as exc:
            last_exc = exc
            if not _is_lock_error(exc):
                raise
            time.sleep(0.35 * (attempt + 1))

    # Destination is likely open in Excel — keep data in a free sidecar path.
    sidecar = _unique_sidecar(target)
    try:
        os.replace(str(tmp_path), str(sidecar))
        return sidecar
    except OSError:
        try:
            shutil.copy2(str(tmp_path), str(sidecar))
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return sidecar
        except OSError:
            if last_exc:
                raise last_exc
            raise


def atomic_workbook_save(workbook, target_path):
    """Write an XLSX to a temporary file and replace the destination atomically.

    Returns the path that was actually written (may be a sidecar if the
    original file is locked by Excel on Windows).
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        workbook.save(tmp_path)
        try:
            workbook.close()
        except Exception:
            pass
        return _replace_with_retry(tmp_path, target)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise
