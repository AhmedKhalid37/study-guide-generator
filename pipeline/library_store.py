"""File-based persistence for the Library: folders + job-to-folder assignment.

Two JSON files under ``library/``:

* ``folders.json``       -> user/default folder definitions
* ``job_folders.json``   -> ``{job_id: folder_id}`` assignment registry

**Why a separate assignment registry instead of writing ``folder_id`` into each
``job.json``?** ``job.json`` is owned and rewritten by the generation pipeline on
every status transition (``set_status``/``update``). Storing folder assignment
there would risk races with an in-flight job and couple Library concerns to the
pipeline we must not break. A standalone registry keeps the two fully decoupled,
is trivial to back up/mount, and never touches a running job's manifest.

Folder ids are validated against a strict pattern and are only ever used as JSON
keys (never as filesystem paths), so there is no path-traversal surface.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
LIBRARY_DIR = BASE_DIR / "library"
FOLDERS_JSON = LIBRARY_DIR / "folders.json"
JOB_FOLDERS_JSON = LIBRARY_DIR / "job_folders.json"

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
COLOR_PATTERN = re.compile(r"^#?[0-9a-zA-Z]{2,16}$")

MAX_NAME_CHARS = 80
MAX_FOLDERS = 200

# Virtual folders are computed views, never stored, never editable.
VIRTUAL_ALL = "all"
VIRTUAL_UNFILED = "unfiled"
SYSTEM_FOLDER_IDS = {VIRTUAL_ALL, VIRTUAL_UNFILED}

# Seeded once on first run; afterwards they are ordinary folders the user may
# rename or delete (deletion sticks — they are not re-seeded).
DEFAULT_FOLDERS = [
    {"id": "exam_prep", "name": "Exam Prep", "color": "#F59E0B"},
    {"id": "reports", "name": "Reports", "color": "#60A5FA"},
    {"id": "presentations", "name": "Presentations", "color": "#A855F7"},
    {"id": "projects", "name": "Projects", "color": "#34D399"},
]


class LibraryStoreError(RuntimeError):
    """Invalid input or a forbidden operation."""


class FolderNotFoundError(LibraryStoreError):
    pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:48].strip("-")
    return slug or "folder"


def is_valid_folder_id(folder_id: str) -> bool:
    return bool(ID_PATTERN.match(folder_id))


def _clean_name(name: str) -> str:
    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        raise LibraryStoreError("Folder name must not be empty.")
    return cleaned[:MAX_NAME_CHARS]


def _clean_color(color: Any) -> str | None:
    if color is None:
        return None
    value = str(color).strip()
    if not value:
        return None
    if not COLOR_PATTERN.match(value):
        raise LibraryStoreError("Invalid folder color.")
    return value


def _write_json(path: Path, data: dict[str, Any]) -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=LIBRARY_DIR, prefix=f".{path.stem}-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# folders.json
# ---------------------------------------------------------------------------

def _seed_default_folders() -> dict[str, Any]:
    timestamp = _now_iso()
    folders = [
        {
            "id": folder["id"],
            "name": folder["name"],
            "color": folder["color"],
            "created_at": timestamp,
            "updated_at": timestamp,
            "sort_order": index,
        }
        for index, folder in enumerate(DEFAULT_FOLDERS)
    ]
    data = {"version": 1, "folders": folders}
    _write_json(FOLDERS_JSON, data)
    return data


def _read_folders() -> dict[str, Any]:
    if not FOLDERS_JSON.exists():
        return _seed_default_folders()
    try:
        data = json.loads(FOLDERS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "folders": []}
    if not isinstance(data, dict) or not isinstance(data.get("folders"), list):
        return {"version": 1, "folders": []}
    return data


def _valid_folder_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _read_folders().get("folders", []):
        if not isinstance(entry, dict):
            continue
        fid = str(entry.get("id") or "")
        if not is_valid_folder_id(fid) or fid in SYSTEM_FOLDER_IDS or fid in seen:
            continue
        seen.add(fid)
        records.append(entry)
    return records


def _folder_public(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry["id"]),
        "name": str(entry.get("name") or entry["id"]),
        "color": entry.get("color"),
        "created_at": entry.get("created_at"),
        "updated_at": entry.get("updated_at"),
        "sort_order": int(entry.get("sort_order") or 0),
        "system": False,
    }


def list_folders() -> list[dict[str, Any]]:
    records = _valid_folder_records()
    records.sort(key=lambda item: (int(item.get("sort_order") or 0), str(item.get("created_at") or "")))
    return [_folder_public(entry) for entry in records]


def folder_exists(folder_id: str) -> bool:
    return is_valid_folder_id(folder_id) and any(r["id"] == folder_id for r in _valid_folder_records())


def get_folder(folder_id: str) -> dict[str, Any] | None:
    for record in _valid_folder_records():
        if record["id"] == folder_id:
            return _folder_public(record)
    return None


def _generate_folder_id(name: str, existing: set[str]) -> str:
    base = _slugify(name)
    if base not in existing and base not in SYSTEM_FOLDER_IDS and is_valid_folder_id(base):
        return base
    for _ in range(20):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if candidate not in existing and candidate not in SYSTEM_FOLDER_IDS:
            return candidate
    while True:
        candidate = f"folder-{secrets.token_hex(4)}"
        if candidate not in existing:
            return candidate


def create_folder(*, name: str, color: Any = None) -> dict[str, Any]:
    clean_name = _clean_name(name)
    clean_color = _clean_color(color)

    data = _read_folders()
    folders = [entry for entry in data.get("folders", []) if isinstance(entry, dict)]
    if len(folders) >= MAX_FOLDERS:
        raise LibraryStoreError("Folder limit reached.")

    existing_ids = {str(entry.get("id")) for entry in folders}
    folder_id = _generate_folder_id(clean_name, existing_ids)
    next_order = max((int(entry.get("sort_order") or 0) for entry in folders), default=-1) + 1
    timestamp = _now_iso()
    record = {
        "id": folder_id,
        "name": clean_name,
        "color": clean_color,
        "created_at": timestamp,
        "updated_at": timestamp,
        "sort_order": next_order,
    }
    data["version"] = data.get("version", 1)
    data["folders"] = [*folders, record]
    _write_json(FOLDERS_JSON, data)
    return _folder_public(record)


def update_folder(
    folder_id: str,
    *,
    name: str | None = None,
    color: Any = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    if folder_id in SYSTEM_FOLDER_IDS:
        raise LibraryStoreError("System folders cannot be modified.")
    if not is_valid_folder_id(folder_id):
        raise FolderNotFoundError(f"Unknown folder: {folder_id}")

    data = _read_folders()
    folders = [entry for entry in data.get("folders", []) if isinstance(entry, dict)]
    record = next((entry for entry in folders if str(entry.get("id")) == folder_id), None)
    if record is None:
        raise FolderNotFoundError(f"Unknown folder: {folder_id}")

    if name is not None:
        record["name"] = _clean_name(name)
    if color is not None:
        record["color"] = _clean_color(color)
    if sort_order is not None:
        record["sort_order"] = int(sort_order)
    record["updated_at"] = _now_iso()

    data["folders"] = folders
    _write_json(FOLDERS_JSON, data)
    return _folder_public(record)


def delete_folder(folder_id: str) -> int:
    """Delete a folder. Assigned jobs fall back to Unfiled (assignment removed).

    Returns the number of jobs that were unassigned. Never touches job artifacts.
    """
    if folder_id in SYSTEM_FOLDER_IDS:
        raise LibraryStoreError("System folders cannot be deleted.")
    if not is_valid_folder_id(folder_id):
        raise FolderNotFoundError(f"Unknown folder: {folder_id}")

    data = _read_folders()
    folders = [entry for entry in data.get("folders", []) if isinstance(entry, dict)]
    if not any(str(entry.get("id")) == folder_id for entry in folders):
        raise FolderNotFoundError(f"Unknown folder: {folder_id}")

    data["folders"] = [entry for entry in folders if str(entry.get("id")) != folder_id]
    _write_json(FOLDERS_JSON, data)

    # Drop assignments pointing at the deleted folder -> those jobs become Unfiled.
    assignments = _read_assignments()
    reassigned = [jid for jid, fid in assignments.items() if fid == folder_id]
    if reassigned:
        for jid in reassigned:
            assignments.pop(jid, None)
        _write_assignments(assignments)
    return len(reassigned)


# ---------------------------------------------------------------------------
# job_folders.json
# ---------------------------------------------------------------------------

def _read_assignments() -> dict[str, str]:
    if not JOB_FOLDERS_JSON.exists():
        return {}
    try:
        data = json.loads(JOB_FOLDERS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = data.get("assignments") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}


def _write_assignments(assignments: dict[str, str]) -> None:
    _write_json(JOB_FOLDERS_JSON, {"version": 1, "assignments": assignments})


def assignments() -> dict[str, str]:
    """Public copy of job_id -> folder_id (only folders that still exist)."""
    valid = {record["id"] for record in _valid_folder_records()}
    return {jid: fid for jid, fid in _read_assignments().items() if fid in valid}


def folder_id_for(job_id: str) -> str:
    """Return the folder a job belongs to, or 'unfiled' if unassigned/orphaned."""
    fid = _read_assignments().get(job_id)
    if fid and folder_exists(fid):
        return fid
    return VIRTUAL_UNFILED


def _normalize_target(folder_id: str | None) -> str | None:
    """Return a concrete folder id to assign, or None to unfile."""
    if folder_id in (None, "", VIRTUAL_UNFILED):
        return None
    if folder_id == VIRTUAL_ALL:
        raise LibraryStoreError("Cannot assign a job to 'All Guides'.")
    if not is_valid_folder_id(folder_id) or not folder_exists(folder_id):
        raise FolderNotFoundError(f"Unknown folder: {folder_id}")
    return folder_id


def normalize_target(folder_id: str | None) -> str | None:
    """Public validation of an assign/move target.

    Returns a concrete folder id, or ``None`` to leave the job unfiled. Raises
    :class:`FolderNotFoundError`/:class:`LibraryStoreError` for unknown folders
    or the virtual "all" target. Use this to validate a target *before* running
    an expensive job so a bad folder id fails fast.
    """
    return _normalize_target(folder_id)


def move_job(job_id: str, folder_id: str | None) -> str:
    job_id = str(job_id or "").strip()
    if not job_id:
        raise LibraryStoreError("job_id must not be empty.")
    target = _normalize_target(folder_id)

    current = _read_assignments()
    if target is None:
        current.pop(job_id, None)
    else:
        current[job_id] = target
    _write_assignments(current)
    return target or VIRTUAL_UNFILED


def move_jobs(job_ids: list[str], folder_id: str | None) -> int:
    target = _normalize_target(folder_id)
    current = _read_assignments()
    moved = 0
    for raw in job_ids:
        jid = str(raw or "").strip()
        if not jid:
            continue
        if target is None:
            if jid in current:
                current.pop(jid, None)
                moved += 1
        else:
            current[jid] = target
            moved += 1
    _write_assignments(current)
    return moved
