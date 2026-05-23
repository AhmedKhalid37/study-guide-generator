from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.html_renderer import render_markdown_file


def render_pdf(
    markdown_path,
    output_pdf,
    backend: str = "chrome",
    theme: str = "claude_clean",
    strict_math: bool = True,
) -> Path:
    markdown = Path(markdown_path)
    pdf = Path(output_pdf)
    if backend != "chrome":
        raise ValueError(f"Unsupported PDF backend: {backend}")
    if not markdown.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown}")

    pdf.parent.mkdir(parents=True, exist_ok=True)
    html_path = pdf.with_suffix(".html")
    html = render_markdown_file(markdown, theme=theme, strict_math=strict_math)
    html_path.write_text(html, encoding="utf-8")
    _render_with_chromium(html_path, pdf)
    return pdf


def _render_with_chromium(html_path: Path, output_pdf: Path) -> None:
    chromium = _find_chromium()
    if chromium is None:
        raise RuntimeError(
            "Could not find a Chromium executable. Tried: chromium, chromium-browser, "
            "google-chrome, google-chrome-stable, chrome."
        )

    with tempfile.TemporaryDirectory(prefix="studyguide-chrome-") as profile_dir:
        command = [
            chromium,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-crash-reporter",
            "--disable-breakpad",
            # Prevent Chrome's default print header/footer from adding timestamps,
            # document titles, file:// paths, and browser page counts to PDFs.
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            f"--user-data-dir={profile_dir}",
            f"--print-to-pdf={output_pdf}",
            html_path.resolve().as_uri(),
        ]
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "Chromium failed to render the PDF.\n"
            f"command: {' '.join(command)}\n\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    if not output_pdf.exists() or output_pdf.stat().st_size == 0:
        raise RuntimeError(
            "Chromium exited successfully but did not create a non-empty PDF.\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


def _find_chromium() -> str | None:
    for candidate in (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
    ):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Markdown to PDF with headless Chromium.")
    parser.add_argument("markdown_path", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--backend", default="chrome")
    parser.add_argument("--theme", default="claude_clean")
    parser.add_argument(
        "--no-strict-math",
        action="store_true",
        help="Render invalid KaTeX expressions as error-marked HTML instead of failing.",
    )
    args = parser.parse_args(argv)

    try:
        pdf = render_pdf(
            args.markdown_path,
            args.output_pdf,
            backend=args.backend,
            theme=args.theme,
            strict_math=not args.no_strict_math,
        )
    except Exception as exc:
        print(f"PDF rendering failed: {exc}", file=sys.stderr)
        return 1

    print(f"Saved PDF: {pdf}")
    print(f"Saved HTML: {pdf.with_suffix('.html')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
