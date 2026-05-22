from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from pipeline.input_handler import accept_markdown_upload, needs_extraction
from pipeline.job_manager import Job
from pipeline.markdown_sanitizer import sanitize
from pipeline.math_validator import validate
from pipeline.pdf_renderer import render_pdf


class MarkdownJobError(RuntimeError):
    def __init__(self, message: str, job: Job) -> None:
        super().__init__(message)
        self.job = job


def run_markdown_job(
    input_path: Path,
    *,
    theme: str = "claude_clean",
    strict_math: bool = True,
) -> Job:
    source = input_path.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Markdown input not found: {source}")
    if needs_extraction(source):
        raise ValueError(f"Expected Markdown input, got extractable file: {source}")

    job = Job.create(
        {
            "path_mode": "have_markdown",
            "input_type": source.suffix.lower().lstrip("."),
            "source_path": str(source),
            "theme": theme,
            "strict_math": strict_math,
        }
    )

    print(f"Job id: {job.id}")
    print(f"Job dir: {job.dir}")

    try:
        job.set_status("saving_input")
        saved_input = accept_markdown_upload(job, source)
        shutil.copy2(saved_input, job.raw_md)
        job.update(input_path=str(saved_input), raw_md=str(job.raw_md))

        job.set_status("sanitizing")
        raw = job.raw_md.read_text(encoding="utf-8", errors="replace")
        job.save_text(job.clean_md, sanitize(raw))
        job.update(clean_md=str(job.clean_md))
        print(f"clean.md: {job.clean_md}")

        job.set_status("validating")
        validation_path = job.logs_dir / "validation.json"
        result = validate(job.clean_md, output_json=validation_path)
        job.update(
            validation_json=str(validation_path),
            math_validation={
                "ok": result.ok,
                "display_blocks": result.display_blocks,
                "inline_formulas": result.inline_formulas,
                "errors": len(result.errors),
            },
        )
        if not result.ok:
            message = _validation_error_message(result)
            job.set_status("validation_failed", message)
            print(f"Validation failed. Details saved to: {validation_path}", file=sys.stderr)
            print(message, file=sys.stderr)
            raise MarkdownJobError(message, job)

        job.set_status("rendering")
        try:
            render_pdf(job.clean_md, job.final_pdf, theme=theme, strict_math=strict_math)
        except Exception as exc:
            message = f"Rendering failed: {exc}"
            job.save_text(job.render_log, message + "\n")
            job.set_status("render_failed", message)
            print(f"Rendering failed. Details saved to: {job.render_log}", file=sys.stderr)
            print(message, file=sys.stderr)
            raise MarkdownJobError(message, job) from exc

        job.save_text(job.render_log, f"Rendered PDF: {job.final_pdf}\nRendered HTML: {job.final_html}\n")
        job.update(final_html=str(job.final_html), final_pdf=str(job.final_pdf))
        job.set_status("done")

        print(f"final.html: {job.final_html}")
        print(f"final.pdf: {job.final_pdf}")
        return job
    except MarkdownJobError:
        raise
    except Exception as exc:
        message = f"Markdown job failed: {exc}"
        job.set_status("failed", message)
        raise MarkdownJobError(message, job) from exc


def _validation_error_message(result) -> str:
    if not result.errors:
        return "Math validation failed."
    lines = [f"Math validation failed with {len(result.errors)} error(s):"]
    for index, error in enumerate(result.errors, start=1):
        mode = "display" if error.display_mode else "inline"
        lines.append(f"{index}. {mode}: {error.expr}")
        lines.append(f"   {error.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Markdown-to-PDF backend job pipeline.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--theme", default="claude_clean")
    parser.add_argument(
        "--no-strict-math",
        action="store_true",
        help="Render invalid KaTeX expressions as error-marked HTML instead of failing.",
    )
    args = parser.parse_args(argv)

    try:
        job = run_markdown_job(
            args.input_path,
            theme=args.theme,
            strict_math=not args.no_strict_math,
        )
    except MarkdownJobError as exc:
        print(f"Job id: {exc.job.id}", file=sys.stderr)
        print(f"Job dir: {exc.job.dir}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Job failed before creation: {exc}", file=sys.stderr)
        return 1

    print(f"Status: done")
    print(f"Job manifest: {job.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
