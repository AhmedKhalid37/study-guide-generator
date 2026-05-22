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
    def validation_json(self) -> Path:
        return self.dir / "validation.json"

    @property
    def render_log(self) -> Path:
        return self.logs_dir / "render.log"

    @property
    def repair_log(self) -> Path:
        return self.logs_dir / "repair.log"

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

    def set_status(self, status: str, error: str | None = None) -> None:
        self.update(status=status, error=error)

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
