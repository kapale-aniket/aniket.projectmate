import os
import tempfile
from pathlib import Path


def atomic_workbook_save(workbook, target_path):
    """Write an XLSX to a temporary file and replace the destination atomically."""
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
        workbook.close()
        os.replace(tmp_path, target)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise
