import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

from apps.linkedin.services.stats import _estimate_records

TRASH_DIR = settings.LINKEDIN_DATA_DIR / "trash" / "files"
INDEX_PATH = settings.LINKEDIN_DATA_DIR / "trash" / "index.json"


def _automation_root():
    return Path(settings.LINKEDIN_AUTOMATION_ROOT).resolve()


def _validate_output_file(path_str: str) -> Path:
    file_path = Path(path_str).resolve()
    root = _automation_root()
    if not str(file_path).startswith(str(root)) or not file_path.is_file():
        raise FileNotFoundError("File not found")
    return file_path


def _ensure_trash_dirs():
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_index():
    _ensure_trash_dirs()
    if not INDEX_PATH.exists():
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else data.get("entries", [])
    except (OSError, json.JSONDecodeError):
        return []


def _save_index(entries):
    _ensure_trash_dirs()
    with open(INDEX_PATH, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2)


def _guess_file_type(name: str, original_path: str) -> str:
    lower = name.lower()
    path_lower = original_path.lower()
    if "hiring_posts" in lower or "/posts/" in path_lower:
        return "Posts"
    if "/connections/" in path_lower or lower.endswith(".csv"):
        return "Connections"
    return "Job Data"


def _entry_to_dict(entry):
    deleted_at = entry.get("deleted_at", "")
    try:
        dt = datetime.fromisoformat(deleted_at.replace("Z", "+00:00"))
        date_label = dt.astimezone().strftime("%b %d, %Y %H:%M")
    except ValueError:
        date_label = deleted_at

    trash_path = Path(entry["trash_path"])
    records = entry.get("records", 0)
    if trash_path.exists():
        try:
            records = _estimate_records(trash_path)
        except Exception:
            pass

    return {
        "id": entry["id"],
        "name": entry["name"],
        "original_path": entry["original_path"],
        "trash_path": entry["trash_path"],
        "type": entry.get("type", "Job Data"),
        "records": records,
        "deleted_at": deleted_at,
        "date": date_label,
    }


def list_trashed_files():
    entries = _load_index()
    active = []
    for entry in entries:
        trash_path = Path(entry.get("trash_path", ""))
        if trash_path.is_file():
            active.append(entry)
        else:
            continue
    if len(active) != len(entries):
        _save_index(active)
    active.sort(key=lambda item: item.get("deleted_at", ""), reverse=True)
    return [_entry_to_dict(entry) for entry in active]


def move_to_trash(path_str: str):
    file_path = _validate_output_file(path_str)
    _ensure_trash_dirs()

    trash_id = str(uuid.uuid4())
    trash_name = f"{trash_id}_{file_path.name}"
    trash_path = TRASH_DIR / trash_name

    shutil.move(str(file_path), str(trash_path))

    entry = {
        "id": trash_id,
        "name": file_path.name,
        "original_path": str(file_path),
        "trash_path": str(trash_path),
        "type": _guess_file_type(file_path.name, str(file_path)),
        "records": _estimate_records(trash_path),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }

    entries = _load_index()
    entries.insert(0, entry)
    _save_index(entries)
    return _entry_to_dict(entry)


def restore_from_trash(trash_id: str):
    entries = _load_index()
    entry = next((item for item in entries if item.get("id") == trash_id), None)
    if not entry:
        raise FileNotFoundError("Deleted file not found")

    trash_path = Path(entry["trash_path"])
    if not trash_path.is_file():
        entries = [item for item in entries if item.get("id") != trash_id]
        _save_index(entries)
        raise FileNotFoundError("Deleted file no longer exists in trash")

    original_path = Path(entry["original_path"]).resolve()
    root = _automation_root()
    if not str(original_path).startswith(str(root)):
        raise ValueError("Invalid restore path")

    if original_path.exists():
        raise FileExistsError(
            f"A file named \"{original_path.name}\" already exists at the original location."
        )

    original_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(trash_path), str(original_path))

    entries = [item for item in entries if item.get("id") != trash_id]
    _save_index(entries)

    return {
        "id": trash_id,
        "name": entry["name"],
        "path": str(original_path),
        "message": f"Restored {entry['name']}",
    }


def permanent_delete_from_trash(trash_id: str):
    entries = _load_index()
    entry = next((item for item in entries if item.get("id") == trash_id), None)
    if not entry:
        raise FileNotFoundError("Deleted file not found")

    trash_path = Path(entry["trash_path"])
    if trash_path.is_file():
        trash_path.unlink()

    entries = [item for item in entries if item.get("id") != trash_id]
    _save_index(entries)

    return {
        "id": trash_id,
        "name": entry["name"],
        "message": f"Permanently deleted {entry['name']}",
    }


def permanent_delete_many_from_trash(trash_ids):
    unique_ids = list(
        dict.fromkeys(str(trash_id).strip() for trash_id in trash_ids if str(trash_id).strip())
    )
    if not unique_ids:
        raise ValueError("No files selected")

    entries = _load_index()
    id_set = set(unique_ids)
    deleted = []
    remaining = []

    for entry in entries:
        entry_id = entry.get("id")
        if entry_id in id_set:
            trash_path = Path(entry.get("trash_path", ""))
            if trash_path.is_file():
                trash_path.unlink()
            deleted.append({"id": entry_id, "name": entry.get("name", "File")})
            id_set.discard(entry_id)
        else:
            remaining.append(entry)

    _save_index(remaining)

    count = len(deleted)
    if count == 1:
        message = f'Permanently deleted "{deleted[0]["name"]}"'
    elif count:
        message = f"Permanently deleted {count} files"
    else:
        message = "No files were deleted"

    return {
        "deleted": deleted,
        "count": count,
        "not_found": list(id_set),
        "message": message,
    }
