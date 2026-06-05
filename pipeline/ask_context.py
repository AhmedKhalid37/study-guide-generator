"""Context preparation / chunking + lexical index for Ask Your Guide.

Ask Slice 3 (backend context preparation). This module turns a job's *already
generated* artifacts — ``clean.md`` (the guide) and the optional
``extracted.txt`` (the source) — into a deterministic, citation-labelled chunk
index plus a dependency-free lexical index, and caches it per
``(job_id, content_hash)`` under the job tree. A later slice (retrieval / chat)
reads this cache; this slice never calls a model and never reads provider keys.

Hard constraints (see ``docs/ASK_YOUR_GUIDE_DESIGN.md`` §3.3 / §4 / §11):
  * read-only over the original artifacts — it never writes ``clean.md`` /
    ``extracted.txt`` / ``job.json``, never calls ``Job.save_clean_md``, never
    creates a job;
  * no model call, no local-model call, no provider/secret read;
  * no new dependency — chunking + index are pure Python (stdlib only);
  * the cache lives under ``jobs/<job_id>/ask/cache/`` and never escapes the job
    directory; writes are atomic (temp file + ``os.replace``);
  * guide/source text is treated as untrusted DATA — it is stored in the cache
    for later retrieval but never logged, executed, or treated as instructions.

The prepare endpoint returns counts + a citation summary only. The cache file
*may* contain chunk text (Slice 4 retrieval needs it) but never any secret,
key, base URL, host path, or unrelated manifest field — this module only ever
reads the two plain-text artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from pipeline.job_manager import Job

# Cache identity. ``INDEX_VERSION`` is bumped if the chunk/index *format* ever
# changes so a stale-format cache is treated as invalid and rebuilt. It is kept
# OUT of ``content_hash`` so the hash reflects guide/source content only.
CACHE_KIND = "ask_context_index"
INDEX_VERSION = 1

# Job-relative cache location (no host path is ever returned to a client).
_CACHE_SUBDIR = ("ask", "cache")
_INDEX_FILENAME = "context_index.json"
CACHE_RELPATH = "/".join((*_CACHE_SUBDIR, _INDEX_FILENAME))

# Approximate token budget per chunk (~500–800 tokens) using the chars/4
# heuristic — deliberately NO tokenizer dependency.
_CHARS_PER_TOKEN = 4
TARGET_CHARS = 650 * _CHARS_PER_TOKEN  # ~650 tokens
MAX_CHARS = 800 * _CHARS_PER_TOKEN     # ~800 tokens hard ceiling

# Bound on how many citation labels/pages the response summary samples.
_SUMMARY_SAMPLE = 24

# Markdown ATX heading: capture the heading TEXT (the citation label for guide
# chunks). Mirrors the read-only counter in ``ask_inventory`` but keeps text.
_GUIDE_HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$")
# Source page anchor emitted by PDF extraction, e.g. "## Page 12".
_PAGE_ANCHOR_RE = re.compile(r"^##[ \t]+Page[ \t]+(\d+)\b", re.IGNORECASE)
# Lexical terms: lowercased alphanumeric runs (length >= 2 to drop noise).
_TERM_RE = re.compile(r"[a-z0-9]{2,}")
# Paragraph boundary: one or more blank (whitespace-only) lines.
_PARA_SPLIT_RE = re.compile(r"\n[ \t]*\n")
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b")
_AUTH_RE = re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._\-]+")
_URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")


def _read_text(path: Path) -> str | None:
    """Read an artifact's text, or ``None`` if missing/unreadable."""
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _approx_tokens(char_count: int) -> int:
    """chars/4 heuristic, rounded up. No tokenizer dependency."""
    if char_count <= 0:
        return 0
    return (char_count + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


def _term_freqs(text: str) -> dict[str, int]:
    """Term-frequency map of lowercased alphanumeric terms for one chunk."""
    return dict(Counter(_TERM_RE.findall(text.lower())))


def _redact_chunk_text(text: str) -> str:
    """Mask obvious secrets/provider URLs before writing retrieval cache text."""
    text = _SK_RE.sub("[redacted-key]", text)
    text = _AUTH_RE.sub("[redacted-authorization]", text)
    return _URL_RE.sub("[redacted-url]", text)


def compute_content_hash(guide_text: str | None, source_text: str | None) -> str:
    """Stable sha256 over the guide + source *content* (not timestamps).

    A fixed namespace + length-delimited fields keep ``None`` (absent source)
    distinct from an empty string and prevent guide/source boundary ambiguity.
    """
    digest = hashlib.sha256()
    digest.update(b"ask-context\0")
    for label, text in ((b"guide", guide_text), (b"source", source_text)):
        digest.update(label)
        if text is None:
            digest.update(b"\0none\0")
        else:
            raw = text.encode("utf-8")
            digest.update(b"\0")
            digest.update(str(len(raw)).encode("ascii"))
            digest.update(b"\0")
            digest.update(raw)
    return digest.hexdigest()


def _segments(text: str, kind: str) -> list[tuple[str | None, int | None, str]]:
    """Split text into ``(label, page, body)`` segments on heading/page anchors.

    Each heading (guide) or ``## Page N`` anchor (source) starts a new segment
    whose label is the nearest such anchor; the anchor line is kept in the body
    so its terms are indexed and the chunk reads in context.
    """
    segments: list[tuple[str | None, int | None, str]] = []
    cur_label: str | None = None
    cur_page: int | None = None
    buf: list[str] = []

    def flush() -> None:
        if buf:
            body = "\n".join(buf).strip()
            if body:
                segments.append((cur_label, cur_page, body))
        buf.clear()

    for line in text.splitlines():
        if kind == "source":
            anchor = _PAGE_ANCHOR_RE.match(line)
            if anchor:
                flush()
                cur_page = int(anchor.group(1))
                cur_label = f"Page {cur_page}"
                buf.append(line)
                continue
        else:  # guide
            heading = _GUIDE_HEADING_RE.match(line)
            if heading:
                flush()
                cur_label = heading.group(1).strip()
                cur_page = None
                buf.append(line)
                continue
        buf.append(line)

    flush()
    return segments


def _split_body(body: str) -> list[str]:
    """Chunk one segment body deterministically on paragraph boundaries.

    Greedily packs paragraphs up to ``TARGET_CHARS``; a single oversized
    paragraph is hard-split at ``MAX_CHARS``. No overlap is used in v1 — chunk
    boundaries fall on paragraph/heading boundaries, which keeps the result
    deterministic and the citation label exact.
    """
    if len(body) <= MAX_CHARS:
        return [body]

    chunks: list[str] = []
    current = ""
    for para in _PARA_SPLIT_RE.split(body):
        para = para.strip()
        if not para:
            continue
        # Hard-split a paragraph that alone exceeds the ceiling.
        while len(para) > MAX_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:MAX_CHARS])
            para = para[MAX_CHARS:].lstrip()
        if not para:
            continue
        if current and len(current) + 2 + len(para) > TARGET_CHARS:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def _build_chunks(guide_text: str | None, source_text: str | None) -> list[dict]:
    """Deterministic, citation-labelled chunk records for guide + source."""
    chunks: list[dict] = []
    for kind, text in (("guide", guide_text), ("source", source_text)):
        if not text:
            continue
        seq = 0
        for label, page, body in _segments(text, kind):
            for piece in _split_body(body):
                piece = _redact_chunk_text(piece.strip())
                if not piece:
                    continue
                seq += 1
                char_count = len(piece)
                chunks.append(
                    {
                        "id": f"{kind}-{seq:04d}",
                        "source_type": kind,
                        "label": label,
                        "page": page,
                        "char_count": char_count,
                        "approx_tokens": _approx_tokens(char_count),
                        "terms": _term_freqs(piece),
                        "text": piece,
                    }
                )
    return chunks


def _citation_summary(chunks: list[dict]) -> dict:
    """Bounded, body-free citation/source summary for the prepare response."""
    guide_labels: list[str] = []
    seen_labels: set[str] = set()
    pages: list[int] = []
    seen_pages: set[int] = set()
    for chunk in chunks:
        if chunk["source_type"] == "guide":
            label = chunk.get("label")
            if label and label not in seen_labels:
                seen_labels.add(label)
                guide_labels.append(label)
        else:
            page = chunk.get("page")
            if isinstance(page, int) and page not in seen_pages:
                seen_pages.add(page)
                pages.append(page)
    pages.sort()
    return {
        "guide": {
            "heading_count": len(guide_labels),
            "headings_sample": guide_labels[:_SUMMARY_SAMPLE],
        },
        "source": {
            "page_count": len(pages),
            "page_numbers_sample": pages[:_SUMMARY_SAMPLE],
        },
    }


def _build_index(
    job: Job, guide_text: str | None, source_text: str | None, content_hash: str
) -> dict:
    """Assemble the full cache index (includes chunk text for Slice 4)."""
    chunks = _build_chunks(guide_text, source_text)
    guide_count = sum(1 for c in chunks if c["source_type"] == "guide")
    source_count = sum(1 for c in chunks if c["source_type"] == "source")

    doc_freq: Counter[str] = Counter()
    for chunk in chunks:
        for term in chunk["terms"]:
            doc_freq[term] += 1

    return {
        "kind": CACHE_KIND,
        "version": INDEX_VERSION,
        "job_id": job.id,
        "content_hash": content_hash,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "guide_present": guide_text is not None,
        "source_present": source_text is not None,
        "guide_chunk_count": guide_count,
        "source_chunk_count": source_count,
        "total_chunk_count": len(chunks),
        "doc_freq": dict(doc_freq),
        "citation_summary": _citation_summary(chunks),
        "chunks": chunks,
    }


def _cache_dir(job: Job) -> Path:
    return job.dir.joinpath(*_CACHE_SUBDIR)


def _index_path(job: Job) -> Path:
    return _cache_dir(job) / _INDEX_FILENAME


def _ensure_fenced(job: Job, path: Path) -> None:
    """Defensive: refuse to read/write outside the job directory."""
    root = job.dir.resolve()
    target = path.resolve()
    if target != root and not target.is_relative_to(root):
        raise ValueError("ask context cache path escapes the job directory")


def _read_cache(path: Path) -> dict | None:
    """Load a cached index, or ``None`` if missing / corrupt / not a dict."""
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _cache_valid(cache: dict, content_hash: str) -> bool:
    return (
        cache.get("kind") == CACHE_KIND
        and cache.get("version") == INDEX_VERSION
        and cache.get("content_hash") == content_hash
        and isinstance(cache.get("chunks"), list)
    )


def _write_index(path: Path, index: dict) -> None:
    """Atomically write the index JSON (temp file + ``os.replace``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(index, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _summary(index: dict, *, cache_status: str) -> dict:
    """Body-free prepare result. NEVER includes chunk text or doc_freq."""
    return {
        "ready": True,
        "cache_status": cache_status,
        "content_hash": index["content_hash"],
        "guide_chunk_count": index["guide_chunk_count"],
        "source_chunk_count": index["source_chunk_count"],
        "total_chunk_count": index["total_chunk_count"],
        "citation_summary": index["citation_summary"],
        "cache_relpath": CACHE_RELPATH,
    }


def load_index(job: Job) -> dict | None:
    """Read-only loader for a prepared index (used by Slice 4 retrieval)."""
    path = _index_path(job)
    _ensure_fenced(job, path)
    return _read_cache(path)


def prepare_context(job: Job) -> dict:
    """Build or reuse the chunk index for ``job`` (idempotent, content-hashed).

    Returns a body-free summary dict. ``ready`` is ``False`` (with a ``reason``)
    when the job has no generated guide. Otherwise ``cache_status`` is one of
    ``hit`` (valid cache reused, nothing written), ``built`` (no prior cache),
    or ``rebuilt`` (a stale/corrupt cache was replaced).
    """
    guide_text = _read_text(job.clean_md)
    if guide_text is None:
        return {
            "ready": False,
            "cache_status": "skipped",
            "reason": "No generated guide (clean.md) is available for this job yet.",
        }

    source_text = _read_text(job.extracted_txt)  # optional
    content_hash = compute_content_hash(guide_text, source_text)

    cache_path = _index_path(job)
    _ensure_fenced(job, cache_path)

    had_file = cache_path.exists()
    existing = _read_cache(cache_path)
    if existing is not None and _cache_valid(existing, content_hash):
        return _summary(existing, cache_status="hit")

    index = _build_index(job, guide_text, source_text, content_hash)
    _write_index(cache_path, index)
    return _summary(index, cache_status="rebuilt" if had_file else "built")
