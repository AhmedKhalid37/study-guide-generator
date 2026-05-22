from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO, Iterable

from pipeline.job_manager import Job

MARKDOWN_SUFFIXES = {".md", ".markdown"}
EXTRACTABLE_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt"}


def needs_extraction(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in MARKDOWN_SUFFIXES:
        return False
    if suffix in EXTRACTABLE_SUFFIXES:
        return True
    raise ValueError(f"Unsupported input type: {suffix}")


def accept_paste(job: Job, text: str) -> Path:
    return job.save_text(job.input_dir / "pasted.md", text)


def accept_markdown_upload(job: Job, source: Path) -> Path:
    if source.suffix.lower() not in MARKDOWN_SUFFIXES:
        raise ValueError(f"Expected a Markdown file, got: {source.suffix}")
    return job.save_upload(source)


def accept_uploads(job: Job, files: Iterable[Path]) -> list[Path]:
    saved: list[Path] = []
    for file in files:
        saved.append(job.save_upload(file))
    return saved


def save_upload_stream(job: Job, file: BinaryIO, filename: str) -> Path:
    target = job.input_dir / Path(filename).name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        shutil.copyfileobj(file, out)
    return target
