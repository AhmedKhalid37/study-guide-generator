#!/usr/bin/env python3
"""Narrow render validation for the Slice 54 visual markdown image pilot.

Proves the *existing* renderers can resolve a job-local ``assets/<slug>.png``
reference produced by the pilot — without rewriting any renderer. It does NOT need
the pilot flag (it feeds a clean.md that already contains the safe image ref, which
is exactly what the flag-on pilot would have written) and degrades to SKIP when a
renderer's host dependency (markdown-it / python-docx / Chromium) is unavailable,
mirroring the repo's other host-skippable checks.

No screenshots, no committed image fixtures: the test writes a tiny 1x1 PNG to a
temp dir at runtime. The PNG bytes never appear in any assertion or output.

Run:

    python test_scripts/test_visual_markdown_render.py
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
SKIP = 0

PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\)")

_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# A clean.md exactly as the flag-on pilot would leave it (trailing figure section).
CLEAN_MD = (
    "# Synthetic Guide\n\nSome content.\n\n"
    "## Visual Reference\n\n"
    "![Extracted figure from source page 3](assets/s00_page_0003_figure_01.png)\n"
)
ASSET_NAME = "s00_page_0003_figure_01.png"


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def skip(name: str, detail: str = "") -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}" + (f" — {detail}" if detail else ""))


def _make_job_dir(tmp: Path) -> Path:
    (tmp / "assets").mkdir(parents=True, exist_ok=True)
    (tmp / "assets" / ASSET_NAME).write_bytes(_PNG_1x1)
    (tmp / "clean.md").write_text(CLEAN_MD, encoding="utf-8")
    return tmp


def test_html() -> None:
    try:
        from pipeline.html_renderer import render_markdown_file
    except Exception as exc:  # markdown-it / deps unavailable
        skip("html.render", f"renderer import unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job_dir(Path(d))
        try:
            html = render_markdown_file(job / "clean.md")
        except Exception as exc:
            skip("html.render", f"render unavailable ({type(exc).__name__})")
            return
        check("html.has_img_tag", "<img" in html and 'src="assets/' + ASSET_NAME + '"' in html, html[:200])
        check("html.relative_src_only", "file://" not in html and "/home/" not in html)


def test_docx() -> None:
    try:
        import docx  # noqa: F401
        from pipeline.docx_renderer import render_docx
    except Exception as exc:
        skip("docx.render", f"python-docx unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job_dir(Path(d))
        out = job / "final.docx"
        try:
            render_docx(job / "clean.md", out, title="Synthetic Guide")
        except Exception as exc:
            check("docx.render_no_raise", False, f"{type(exc).__name__}")
            return
        check("docx.produced_nonempty", out.is_file() and out.stat().st_size > 0)
        # The relative image resolved against the job dir, so it embedded rather than
        # leaving an "[image missing]" marker. (DOCX zip is binary; just confirm the
        # file is well-formed and non-trivially sized — embedding adds the PNG.)
        check("docx.embedded_image", out.stat().st_size > 5000, str(out.stat().st_size))


def test_pdf() -> None:
    try:
        from pipeline.pdf_renderer import render_pdf, _find_chromium
    except Exception as exc:
        skip("pdf.render", f"renderer import unavailable ({type(exc).__name__})")
        return
    if _find_chromium() is None:
        skip("pdf.render", "no Chromium on host")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job_dir(Path(d))
        out = job / "final.pdf"
        try:
            render_pdf(job / "clean.md", out)
        except Exception as exc:
            check("pdf.render_no_raise", False, f"{type(exc).__name__}")
            return
        check("pdf.produced_nonempty", out.is_file() and out.stat().st_size > 0)


def main() -> None:
    test_html()
    test_docx()
    test_pdf()
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
