from __future__ import annotations

import json
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = BASE_DIR / "jobs"
# Soft-deleted jobs live here, inside the jobs root but EXCLUDED from the active
# job listing (the listing globs ``*/job.json``, one level deep, while trashed
# manifests sit at ``.trash/<id>/job.json``, two levels deep).
TRASH_DIR = JOBS_DIR / ".trash"
TRASHED_MARKER = "_trashed.json"


class JobManagerError(Exception):
    """Raised for recoverable job-management problems (collisions, bad state)."""


def _timestamp_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


@dataclass(frozen=True)
class Job:
    id: str
    root: Path = JOBS_DIR

    @classmethod
    def create(cls, meta: dict[str, Any] | None = None) -> "Job":
        job = cls(_timestamp_id())
        job.input_dir.mkdir(parents=True, exist_ok=False)
        job.logs_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "id": job.id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "created",
            "error": None,
            "favorite": False,
            "timings": {},
        }
        if meta:
            manifest.update(meta)
        job._write_manifest(manifest)
        return job

    @property
    def dir(self) -> Path:
        return self.root / self.id

    @property
    def input_dir(self) -> Path:
        return self.dir / "input"

    @property
    def logs_dir(self) -> Path:
        return self.dir / "logs"

    @property
    def manifest(self) -> Path:
        return self.dir / "job.json"

    @property
    def raw_md(self) -> Path:
        return self.dir / "raw.md"

    @property
    def clean_md(self) -> Path:
        return self.dir / "clean.md"

    @property
    def extracted_txt(self) -> Path:
        return self.dir / "extracted.txt"

    @property
    def final_html(self) -> Path:
        return self.dir / "final.html"

    @property
    def final_pdf(self) -> Path:
        return self.dir / "final.pdf"

    @property
    def final_docx(self) -> Path:
        return self.dir / "final.docx"

    @property
    def validation_json(self) -> Path:
        return self.dir / "validation.json"

    @property
    def render_log(self) -> Path:
        return self.logs_dir / "render.log"

    @property
    def repair_log(self) -> Path:
        return self.logs_dir / "repair.log"

    @property
    def versions_dir(self) -> Path:
        return self.dir / "versions"

    @property
    def quizzes_dir(self) -> Path:
        return self.dir / "quizzes"

    def save_clean_md(self, new_text: str, source: str) -> None:
        """Single chokepoint for ALL clean.md writes.

        Snapshots the new content as the next numbered version under
        versions/<n>/clean.md, then writes it to the canonical clean.md, then
        appends version metadata to job.json.  source must be one of:
        generated | edited | rerendered | reverted.
        """
        existing = sorted(
            int(p.name)
            for p in (self.versions_dir.glob("*/") if self.versions_dir.exists() else [])
            if p.is_dir() and p.name.isdigit()
        )
        next_n = (existing[-1] + 1) if existing else 1
        v_dir = self.versions_dir / str(next_n)
        v_dir.mkdir(parents=True, exist_ok=True)
        (v_dir / "clean.md").write_text(new_text, encoding="utf-8")
        self.clean_md.parent.mkdir(parents=True, exist_ok=True)
        self.clean_md.write_text(new_text, encoding="utf-8")
        manifest = self.read_manifest()
        versions_list: list[dict] = manifest.get("versions", [])
        versions_list.append(
            {
                "version": next_n,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source": source,
            }
        )
        manifest["versions"] = versions_list
        self._write_manifest(manifest)

    def save_text(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def save_upload(self, source: Path, filename: str | None = None) -> Path:
        target = self.input_dir / (filename or source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target

    def read_manifest(self) -> dict[str, Any]:
        if not self.manifest.exists():
            return {}
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def update(self, **fields: Any) -> None:
        manifest = self.read_manifest()
        manifest.update(fields)
        self._write_manifest(manifest)

    def set_favorite(self, value: bool) -> None:
        self.update(favorite=bool(value))

    def set_status(
        self,
        status: str,
        error: str | None = None,
        *,
        error_category: str | None = None,
        log_path: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {"status": status, "error": error}
        if error_category is not None:
            updates["error_category"] = error_category
        if log_path is not None:
            updates["error_log_path"] = log_path
        self.update(**updates)

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trash (soft delete) + permanent delete
#
# Safety model: permanent removal is a TWO-STEP flow. A job is first MOVED into
# ``jobs/.trash/<id>/`` (reversible), and only a job already sitting in that trash
# can be permanently purged. Every purge path is hard-guarded to operate strictly
# inside ``jobs/.trash/`` — it can never touch the active jobs dir or escape it.
# ──────────────────────────────────────────────────────────────────────────────


def _validate_job_id(job_id: str) -> str:
    """Reject ids that contain path separators or traversal segments."""
    if "/" in job_id or "\\" in job_id or job_id in {"", ".", ".."}:
        raise ValueError(f"Invalid job id: {job_id!r}")
    return job_id


def _guarded_trash_target(job_id: str) -> Path:
    """Resolve ``jobs/.trash/<id>/`` and HARD-assert it lives inside the trash.

    Raises ``ValueError`` for any id that would point outside ``jobs/.trash/``.
    This is the single chokepoint every destructive trash operation routes
    through, so a traversal id can never escape the trash directory.
    """
    _validate_job_id(job_id)
    trash_dir = TRASH_DIR.resolve()
    target = (TRASH_DIR / job_id).resolve()
    if not target.is_relative_to(trash_dir):
        raise ValueError(f"Refusing to operate on path outside trash: {target}")
    # Belt-and-suspenders: the target must sit DIRECTLY in the trash dir, never
    # in the active jobs dir or any nested location.
    if target.parent != trash_dir:
        raise ValueError(f"Refusing to operate on non-trash path: {target}")
    return target


def trash_job(job_id: str) -> dict[str, Any]:
    """Move ``jobs/<id>/`` -> ``jobs/.trash/<id>/`` and write a trash marker.

    Returns the marker metadata ``{original_id, trashed_at}``.
    """
    _validate_job_id(job_id)
    src = JOBS_DIR / job_id
    if not src.is_dir() or not (src / "job.json").exists():
        raise FileNotFoundError(f"Active job not found: {job_id}")

    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    dest = _guarded_trash_target(job_id)
    if dest.exists():
        raise JobManagerError(f"A trashed job with id {job_id} already exists.")

    shutil.move(str(src), str(dest))
    marker = {
        "original_id": job_id,
        "trashed_at": datetime.now().isoformat(timespec="seconds"),
    }
    (dest / TRASHED_MARKER).write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return marker


def restore_job(job_id: str) -> None:
    """Move ``jobs/.trash/<id>/`` back to ``jobs/<id>/`` and drop the marker."""
    src = _guarded_trash_target(job_id)
    if not src.is_dir():
        raise FileNotFoundError(f"Trashed job not found: {job_id}")

    dest = JOBS_DIR / job_id
    if dest.exists():
        raise JobManagerError(f"An active job with id {job_id} already exists.")

    marker = src / TRASHED_MARKER
    if marker.exists():
        marker.unlink()
    shutil.move(str(src), str(dest))


def list_trashed() -> list[dict[str, Any]]:
    """Return metadata for every job currently in ``jobs/.trash/``."""
    items: list[dict[str, Any]] = []
    if not TRASH_DIR.exists():
        return items
    for entry in TRASH_DIR.iterdir():
        if not entry.is_dir():
            continue
        manifest: dict[str, Any] = {}
        manifest_path = entry / "job.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {}
        marker: dict[str, Any] = {}
        marker_path = entry / TRASHED_MARKER
        if marker_path.exists():
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                marker = {}
        items.append(
            {
                "id": entry.name,
                "original_id": marker.get("original_id", entry.name),
                "trashed_at": marker.get("trashed_at"),
                "manifest": manifest,
            }
        )
    return items


def is_trashed(job_id: str) -> bool:
    """True iff ``job_id`` is currently a directory inside ``jobs/.trash/``."""
    try:
        return _guarded_trash_target(job_id).is_dir()
    except ValueError:
        return False


def purge_trashed_job(job_id: str) -> None:
    """PERMANENTLY remove ``jobs/.trash/<id>/`` from disk.

    This is the ONLY place an ``rmtree``/permanent removal happens. The target is
    resolved and asserted to live inside ``jobs/.trash/`` both up front (via
    :func:`_guarded_trash_target`) and again immediately before the removal.
    """
    target = _guarded_trash_target(job_id)
    if not target.is_dir():
        raise FileNotFoundError(f"Trashed job not found: {job_id}")

    # Final assertion immediately before removal — never remove from the active
    # jobs dir, and never escape the trash.
    trash_dir = TRASH_DIR.resolve()
    resolved = target.resolve()
    if not resolved.is_relative_to(trash_dir) or resolved.parent != trash_dir:
        raise ValueError(f"Refusing to purge path outside trash: {resolved}")

    shutil.rmtree(resolved)


def empty_trash() -> list[str]:
    """Purge ALL trashed jobs via the same guarded per-job purge.

    Returns the list of ids removed.
    """
    if not TRASH_DIR.exists():
        return []
    removed: list[str] = []
    for entry in list(TRASH_DIR.iterdir()):
        if entry.is_dir():
            purge_trashed_job(entry.name)
            removed.append(entry.name)
    return removed
