#!/usr/bin/env python3
"""Focused tests for the emergency large-attachment support slice (Slice 101).

Covers the single env-tunable upload ceiling
(``GUIDEFORGE_MAX_ATTACHMENT_MB``, default 150 MB) and the streaming attachment
save guard, WITHOUT an LLM provider, the Chromium renderer, or the OCR stack:

  * ``_resolve_max_attachment_mb`` resolution matrix: default, valid override,
    missing/invalid/out-of-range values all degrade to the safe default; the
    accepted band is floored at 100 MB and capped at 1024 MB.
  * the module ceiling accepts at least 100 MB (the slice goal).
  * ``_save_llm_attachments`` accepts a ~100 MB stream (driven through a stub
    UploadFile — no committed fixture, the temp file is removed afterwards).
  * an over-ceiling stream is rejected with HTTP 413 and a GENERIC,
    filename-free detail (no-leak): no filename / path / content / raw exception.

No real PDFs/images/DOCX are read or written; the only bytes are zero-filled
chunks streamed through a stub. SKIPS cleanly (exit 0) if FastAPI is unavailable
in host Python — run inside the Docker image for full coverage.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0

MB = 1024 * 1024

# A sensitive filename + path that must NEVER appear in any rejection detail or
# response surface. Purely synthetic canaries.
CANARY_FILENAME = "private-source.pdf"
CANARY_PATH = "/home/example/private-source.pdf"
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|llm-attachment-|preflight-)")


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} :: {detail}")


def _skip(msg: str) -> "None":
    print(f"[SKIP] {msg}")
    sys.exit(0)


try:
    from api import server  # noqa: E402
except Exception as exc:  # noqa: BLE001 — FastAPI (or a dep) unavailable on host.
    _skip(f"could not import api.server (FastAPI unavailable?): {exc}")

from fastapi import HTTPException  # noqa: E402


class _StubUpload:
    """Minimal async stand-in for Starlette's UploadFile.

    Streams ``total_bytes`` of zero bytes in <=1 MiB chunks. Holds no large
    buffer in memory and reads no real file — it exists only to drive the
    server's streaming size guard.
    """

    def __init__(self, filename: str, total_bytes: int, chunk: int = MB) -> None:
        self.filename = filename
        self._remaining = total_bytes
        self._chunk = chunk
        self.closed = False

    async def read(self, n: int) -> bytes:
        if self._remaining <= 0:
            return b""
        take = min(n, self._chunk, self._remaining)
        self._remaining -= take
        return b"\0" * take

    async def close(self) -> None:
        self.closed = True


def _resolve_with_env(value: object) -> int:
    """Call _resolve_max_attachment_mb with GUIDEFORGE_MAX_ATTACHMENT_MB set to
    ``value`` (or unset when ``value is None``), restoring the prior env after."""
    key = "GUIDEFORGE_MAX_ATTACHMENT_MB"
    saved = os.environ.get(key)
    try:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
        return server._resolve_max_attachment_mb()
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved


def test_resolution_matrix() -> None:
    check("unset env -> default 150", _resolve_with_env(None) == 150)
    check("valid override 200 honored", _resolve_with_env(200) == 200)
    check("valid override 100 (floor) honored", _resolve_with_env(100) == 100)
    check("valid override 1024 (cap) honored", _resolve_with_env(1024) == 1024)
    # Out of range -> default.
    check("below-floor 50 degrades to default", _resolve_with_env(50) == 150)
    check("zero degrades to default", _resolve_with_env(0) == 150)
    check("negative degrades to default", _resolve_with_env(-10) == 150)
    check("above-cap 99999 degrades to default", _resolve_with_env(99999) == 150)
    # Hostile / malformed -> default (never raises).
    check("non-numeric degrades to default", _resolve_with_env("not-a-number") == 150)
    check("empty string degrades to default", _resolve_with_env("") == 150)
    check("float-ish string degrades to default", _resolve_with_env("150.5") == 150)
    check("whitespace tolerated ' 200 '", _resolve_with_env(" 200 ") == 200)


def test_module_ceiling_accepts_100mb() -> None:
    check(
        "module ceiling >= 100 MB",
        server.MAX_LLM_ATTACHMENT_BYTES >= 100 * MB,
        str(server.MAX_LLM_ATTACHMENT_BYTES),
    )
    check(
        "default module ceiling is 150 MB",
        server.MAX_LLM_ATTACHMENT_MB == 150 or os.environ.get("GUIDEFORGE_MAX_ATTACHMENT_MB"),
        str(server.MAX_LLM_ATTACHMENT_MB),
    )


def test_save_accepts_100mb_stream() -> None:
    """A ~100 MB stream passes the app-level guard at the default ceiling.

    Uses a stub stream (no committed fixture); the temp file the server writes is
    removed here so nothing large persists.
    """
    saved = server.MAX_LLM_ATTACHMENT_BYTES
    try:
        server.MAX_LLM_ATTACHMENT_BYTES = 150 * MB
        stub = _StubUpload(CANARY_FILENAME, 100 * MB)
        attachments = asyncio.run(server._save_llm_attachments([stub]))
        try:
            check("100 MB stream accepted (one attachment)", len(attachments) == 1)
            path = attachments[0].path if attachments else None
            check(
                "saved temp file is ~100 MB",
                path is not None and path.exists() and path.stat().st_size == 100 * MB,
                str(path.stat().st_size if path and path.exists() else "missing"),
            )
            check("stub upload was closed", stub.closed is True)
        finally:
            for att in attachments:
                att.path.unlink(missing_ok=True)
    finally:
        server.MAX_LLM_ATTACHMENT_BYTES = saved


def test_save_rejects_oversize_generically() -> None:
    """An over-ceiling stream is rejected with 413 and a filename-free detail."""
    saved = server.MAX_LLM_ATTACHMENT_BYTES
    try:
        server.MAX_LLM_ATTACHMENT_BYTES = 2 * MB  # tiny ceiling for a fast test
        stub = _StubUpload(CANARY_FILENAME, 3 * MB)
        raised: HTTPException | None = None
        try:
            asyncio.run(server._save_llm_attachments([stub]))
        except HTTPException as exc:
            raised = exc
        check("oversize stream raises HTTPException", raised is not None)
        if raised is not None:
            check("oversize status is 413", raised.status_code == 413, str(raised.status_code))
            detail = str(raised.detail)
            check("rejection omits the filename", CANARY_FILENAME not in detail, detail)
            check("rejection omits any path", not PATHLIKE.search(detail), detail)
            check("rejection mentions a MB limit", "MB" in detail, detail)
        check("stub upload was closed after rejection", stub.closed is True)
    finally:
        server.MAX_LLM_ATTACHMENT_BYTES = saved


def test_preflight_limits_echo() -> None:
    limits = server._preflight_limits()
    check(
        "preflight limits echo max_upload_mb >= 100",
        isinstance(limits.get("max_upload_mb"), int) and limits["max_upload_mb"] >= 100,
        str(limits.get("max_upload_mb")),
    )


def main() -> None:
    test_resolution_matrix()
    test_module_ceiling_accepts_100mb()
    test_save_accepts_100mb_stream()
    test_save_rejects_oversize_generically()
    test_preflight_limits_echo()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
