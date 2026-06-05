"""Thin, read-only artifact reader for Ask Your Guide context inventory.

Ask Slice 2 (backend context inventory). This module ONLY reads existing job
artifacts (``clean.md`` / ``extracted.txt``) to compute cheap summary counts so a
future Ask Your Guide workspace can show what context is available for a guide.

Hard constraints (see ``docs/ASK_YOUR_GUIDE_DESIGN.md`` §8):
  * read-only — never writes, never mutates a manifest, never calls
    ``Job.save_clean_md``;
  * no model call, no chunking, no retrieval/indexing;
  * returns only counts/booleans — never a guide/source BODY;
  * no secret surface — it reads plain artifact text, never keys or base URLs.

All redaction of manifest/attachment metadata stays in the API layer
(``api/server.py`` ``_safe_*`` helpers); this module deliberately exposes no
manifest fields at all.
"""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.job_manager import Job

# Markdown ATX headings: 1–6 leading '#', whitespace, then non-space content.
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S", re.MULTILINE)
# Source page anchors emitted by PDF extraction, e.g. "## Page 12".
_PAGE_ANCHOR_RE = re.compile(r"^##[ \t]+Page[ \t]+\d+", re.MULTILINE | re.IGNORECASE)


def _read_text(path: Path) -> str | None:
    """Read an artifact's text, or ``None`` if it is missing/unreadable."""
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def has_generated_guide(job: Job) -> bool:
    """Ask eligibility: a job qualifies iff it has a generated ``clean.md``."""
    return job.clean_md.exists() and job.clean_md.is_file()


def guide_inventory(job: Job) -> dict:
    """Cheap summary of the generated guide (``clean.md``).

    Returns presence, character count, and a rough markdown-heading count. The
    guide BODY is never returned.
    """
    text = _read_text(job.clean_md)
    if text is None:
        return {"clean_md_present": False, "char_count": 0, "heading_count": 0}
    return {
        "clean_md_present": True,
        "char_count": len(text),
        "heading_count": len(_HEADING_RE.findall(text)),
    }


def source_inventory(job: Job) -> dict:
    """Cheap summary of extracted source text (``extracted.txt``).

    Returns presence, character count, and the ``## Page N`` anchor count (useful
    for future citation prep). The source BODY is never returned.
    """
    text = _read_text(job.extracted_txt)
    if text is None:
        return {
            "extracted_txt_present": False,
            "char_count": 0,
            "page_anchor_count": 0,
        }
    return {
        "extracted_txt_present": True,
        "char_count": len(text),
        "page_anchor_count": len(_PAGE_ANCHOR_RE.findall(text)),
    }
