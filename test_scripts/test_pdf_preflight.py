#!/usr/bin/env python3
"""Focused test for the read-only PDF preflight slice (Slice 1).

Covers ``pipeline.extract.preflight_pdf`` + the ``POST /api/preflight/pdf``
endpoint WITHOUT needing an LLM provider, the Chromium renderer, or the OCR
stack. Preflight detects scanned pages purely by the *absence of a text layer*
(the same ``_is_meaningful_page_text`` gate the extractor uses), so blank /
text-layer-free pages stand in for scanned pages — no tesseract/Pillow required.

Cases:
  * small text PDF        -> verdict "ok", scanned_flag "text", mode "full"
  * image-heavy PDF       -> scanned_flag "image_heavy", verdict "warn"
  * mixed text/blank PDF  -> scanned_flag "mixed"
  * encrypted PDF         -> verdict "blocked" (if the fitz build supports it)
  * non-PDF upload        -> HTTP 400
  * corrupt ".pdf"        -> verdict "blocked"
  * oversize (threshold lowered via monkeypatch) -> HTTP 400
  * warn-by-page-count (threshold lowered)       -> verdict "warn" + first_n

No external APIs. SKIPS cleanly (exit 0) if PyMuPDF (fitz) is unavailable; the
endpoint cases additionally skip if FastAPI's TestClient is unavailable. Run
inside the Docker image for full coverage.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make the repo root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _skip(msg: str) -> "None":
    print(f"[SKIP] {msg}")
    sys.exit(0)


try:
    import fitz  # PyMuPDF
except ImportError:
    _skip("PyMuPDF (fitz) not installed — PDF preflight test needs it.")

from pipeline.extract import PdfEncryptedError, preflight_pdf

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} :: {detail}")


def _text_pdf(path: Path, pages: int) -> None:
    doc = fitz.open()
    for n in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Page {n + 1} carries real selectable embedded text about study guides.")
    doc.save(str(path))
    doc.close()


def _blank_pdf(path: Path, pages: int) -> None:
    """Pages with no text layer (stand-ins for scanned/image-only pages)."""
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    doc.save(str(path))
    doc.close()


def _mixed_pdf(path: Path, text_pages: int, blank_pages: int) -> None:
    doc = fitz.open()
    for n in range(text_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Text page {n + 1} with genuine embedded selectable content here.")
    for _ in range(blank_pages):
        doc.new_page(width=595, height=842)
    doc.save(str(path))
    doc.close()


def _encrypted_pdf(path: Path) -> bool:
    """Returns True if an encrypted PDF was written, False if unsupported."""
    try:
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), "Secret content behind a password.")
        doc.save(
            str(path),
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="user-secret",
        )
        doc.close()
        return True
    except Exception:
        return False


def test_helper() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)

        text_pdf = tmpd / "text.pdf"
        _text_pdf(text_pdf, 4)
        r = preflight_pdf(text_pdf)
        check("text PDF -> scanned_flag text", r.scanned_flag == "text", str(r))
        check("text PDF -> page_count 4", r.page_count == 4, str(r))
        check("text PDF -> all sampled meaningful", r.meaningful_pages == r.sampled_pages, str(r))

        img_pdf = tmpd / "image_heavy.pdf"
        _blank_pdf(img_pdf, 6)
        r = preflight_pdf(img_pdf)
        check("image-heavy PDF -> scanned_flag image_heavy", r.scanned_flag == "image_heavy", str(r))
        check("image-heavy PDF -> image_ratio ~1.0", r.image_ratio >= 0.85, str(r))

        mixed_pdf = tmpd / "mixed.pdf"
        _mixed_pdf(mixed_pdf, 3, 3)
        r = preflight_pdf(mixed_pdf)
        check("mixed PDF -> scanned_flag mixed", r.scanned_flag == "mixed", str(r))

        big = tmpd / "big.pdf"
        _text_pdf(big, 60)
        r = preflight_pdf(big, sample_pages=20)
        check("sampling is bounded", r.sampled_pages <= 20, str(r))
        check("60-page doc still counted", r.page_count == 60, str(r))

        enc = tmpd / "encrypted.pdf"
        if _encrypted_pdf(enc):
            try:
                preflight_pdf(enc)
                check("encrypted PDF -> PdfEncryptedError", False, "no error raised")
            except PdfEncryptedError:
                check("encrypted PDF -> PdfEncryptedError", True)
            except Exception as exc:
                check("encrypted PDF -> PdfEncryptedError", False, f"wrong error {type(exc).__name__}")
        else:
            print("[SKIP] encrypted-PDF helper case — this fitz build can't encrypt")


def test_endpoint() -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # noqa: BLE001
        print(f"[SKIP] endpoint cases — TestClient unavailable: {exc}")
        return
    try:
        from api import server
    except Exception as exc:  # noqa: BLE001
        print(f"[SKIP] endpoint cases — could not import app: {exc}")
        return

    client = TestClient(server.app)

    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)

        text_pdf = tmpd / "text.pdf"
        _text_pdf(text_pdf, 3)
        resp = client.post(
            "/api/preflight/pdf",
            files={"file": ("text.pdf", text_pdf.read_bytes(), "application/pdf")},
        )
        ok = resp.status_code == 200
        body = resp.json() if ok else {}
        check("endpoint text PDF -> 200 ok verdict", ok and body.get("verdict") == "ok", f"{resp.status_code} {body}")
        check("endpoint text PDF -> recommended full", body.get("recommended_mode") == "full", str(body))
        check("endpoint text PDF -> allowed_actions [continue]", body.get("allowed_actions") == ["continue"], str(body))
        check("endpoint text PDF -> limits echoed", isinstance(body.get("limits"), dict) and "warn_pages" in body["limits"], str(body))
        # No secrets / host paths leaked in the response.
        flat = str(body)
        check("endpoint response has no temp path leak", "preflight-" not in flat and "/tmp" not in flat, flat)

        img_pdf = tmpd / "image_heavy.pdf"
        _blank_pdf(img_pdf, 5)
        resp = client.post(
            "/api/preflight/pdf",
            files={"file": ("scan.pdf", img_pdf.read_bytes(), "application/pdf")},
        )
        body = resp.json()
        check("endpoint image-heavy -> warn", body.get("verdict") == "warn", str(body))
        check("endpoint image-heavy -> flag image_heavy", body.get("scanned_flag") == "image_heavy", str(body))
        check(
            "endpoint image-heavy -> offers process_first_n",
            "process_first_n" in body.get("allowed_actions", []),
            str(body),
        )
        check("endpoint never offers split (deferred)", "split_automatically" not in body.get("allowed_actions", []), str(body))

        # Non-PDF upload -> 400.
        resp = client.post(
            "/api/preflight/pdf",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        check("endpoint non-PDF -> 400", resp.status_code == 400, f"{resp.status_code} {resp.text}")

        # Corrupt ".pdf" -> blocked verdict (request still ok).
        resp = client.post(
            "/api/preflight/pdf",
            files={"file": ("broken.pdf", b"%PDF-1.4 not really a pdf at all", "application/pdf")},
        )
        ok = resp.status_code == 200
        body = resp.json() if ok else {}
        check("endpoint corrupt PDF -> blocked", ok and body.get("verdict") == "blocked", f"{resp.status_code} {body}")
        check("endpoint corrupt PDF -> only remove_file", body.get("allowed_actions") == ["remove_file"], str(body))

        # Oversize guard (lower the ceiling, restore after).
        saved_max = server.MAX_LLM_ATTACHMENT_BYTES
        try:
            server.MAX_LLM_ATTACHMENT_BYTES = 16  # bytes — any real PDF exceeds this
            resp = client.post(
                "/api/preflight/pdf",
                files={"file": ("text.pdf", text_pdf.read_bytes(), "application/pdf")},
            )
            check("endpoint oversize -> 400", resp.status_code == 400, f"{resp.status_code} {resp.text}")
        finally:
            server.MAX_LLM_ATTACHMENT_BYTES = saved_max

        # Warn-by-page-count (lower the page threshold, restore after).
        many = tmpd / "many.pdf"
        _text_pdf(many, 5)
        saved_pages = server.PREFLIGHT_WARN_PAGES
        try:
            server.PREFLIGHT_WARN_PAGES = 2
            resp = client.post(
                "/api/preflight/pdf",
                files={"file": ("many.pdf", many.read_bytes(), "application/pdf")},
            )
            body = resp.json()
            check("endpoint warn-by-pages -> warn", body.get("verdict") == "warn", str(body))
            check("endpoint warn-by-pages -> recommended first_n", body.get("recommended_mode") == "first_n", str(body))
        finally:
            server.PREFLIGHT_WARN_PAGES = saved_pages


def main() -> None:
    test_helper()
    test_endpoint()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
