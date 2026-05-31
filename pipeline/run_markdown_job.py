from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from pipeline.input_handler import accept_markdown_upload, accept_paste, needs_extraction
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
        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except MarkdownJobError:
        raise
    except Exception as exc:
        from pipeline.errors import classify_exception
        category, user_message = classify_exception(exc)
        job.set_status("failed", user_message, error_category=category)
        raise MarkdownJobError(user_message, job) from exc


def run_pasted_text_job(
    text: str,
    *,
    theme: str = "claude_clean",
    strict_math: bool = True,
) -> Job:
    job = Job.create(
        {
            "path_mode": "have_markdown",
            "input_type": "paste",
            "theme": theme,
            "strict_math": strict_math,
        }
    )

    print(f"Job id: {job.id}")
    print(f"Job dir: {job.dir}")

    try:
        job.set_status("saving_input")
        pasted = accept_paste(job, text)
        job.save_text(job.raw_md, text)
        job.update(input_path=str(pasted), raw_md=str(job.raw_md))
        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except MarkdownJobError:
        raise
    except Exception as exc:
        from pipeline.errors import classify_exception
        category, user_message = classify_exception(exc)
        job.set_status("failed", user_message, error_category=category)
        raise MarkdownJobError(user_message, job) from exc


def run_raw_markdown_pipeline(job: Job, *, theme: str, strict_math: bool) -> Job:
    job.set_status("sanitizing")
    raw = job.raw_md.read_text(encoding="utf-8", errors="replace")
    job.save_clean_md(sanitize(raw), "generated")
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
        # Graceful degradation: a single malformed LaTeX expression must NOT
        # destroy the whole guide. Record the failed expressions, then render
        # anyway with KaTeX throwOnError=false (below) so bad math becomes a
        # visible error-marked span the user can fix in the Markdown editor.
        # ``strict_math`` now means "flag and mark bad math", not "abort the job".
        message = _validation_error_message(result)
        job.update(
            math_warnings=message,
            math_failures=[
                {
                    "expr": error.expr,
                    "display_mode": error.display_mode,
                    "message": error.message,
                }
                for error in result.errors
            ],
        )
        print(
            f"Math validation found {len(result.errors)} issue(s); rendering with "
            f"error-marked spans instead of failing. Details: {validation_path}",
            file=sys.stderr,
        )

    job.set_status("rendering")
    # When math validation failed we must render with throwOnError=false so the
    # bad expressions degrade to error spans rather than aborting the render.
    # Valid-math jobs keep their original strict_math (output is byte-identical
    # for valid expressions, so this is a no-op for the normal case).
    render_strict = strict_math and result.ok
    try:
        render_pdf(job.clean_md, job.final_pdf, theme=theme, strict_math=render_strict)
    except Exception as exc:
        message = f"PDF rendering failed: {exc}"
        job.save_text(job.render_log, message + "\n")
        job.set_status("failed", message, error_category="pdf", log_path=str(job.render_log))
        print(f"PDF rendering failed. Details: {job.render_log}", file=sys.stderr)
        print(message, file=sys.stderr)
        raise MarkdownJobError(message, job) from exc

    job.save_text(job.render_log, f"Rendered PDF: {job.final_pdf}\nRendered HTML: {job.final_html}\n")
    job.update(final_html=str(job.final_html), final_pdf=str(job.final_pdf))
    # A usable guide was produced. Use a non-fatal terminal status when math was
    # degraded so the UI can show a "fix these expressions" notice without
    # presenting a failure state.
    job.set_status("done" if result.ok else "completed_with_warnings")

    print(f"final.html: {job.final_html}")
    print(f"final.pdf: {job.final_pdf}")
    return job


def rerender_job(job: Job, *, theme: str | None = None, strict_math: bool | None = None) -> Job:
    """Re-render final.pdf/final.html from an existing clean.md.

    This is a render-only operation: it never re-runs the LLM, re-sanitizes, or
    touches the raw source / prompt. Use it when the theme or render CSS changed
    and the existing clean Markdown should be re-rendered. The job's stored
    ``theme``/``strict_math`` are reused unless overridden.
    """
    if not job.clean_md.exists():
        raise MarkdownJobError("clean.md is missing; nothing to re-render.", job)

    manifest = job.read_manifest()
    use_theme = theme or manifest.get("theme") or "claude_clean"
    use_strict = bool(manifest.get("strict_math", True)) if strict_math is None else bool(strict_math)

    job.set_status("rendering")
    try:
        render_pdf(job.clean_md, job.final_pdf, theme=use_theme, strict_math=use_strict)
    except Exception as exc:
        message = f"PDF rendering failed: {exc}"
        job.save_text(job.render_log, message + "\n")
        job.set_status("failed", message, error_category="pdf", log_path=str(job.render_log))
        raise MarkdownJobError(message, job) from exc

    job.save_text(job.render_log, f"Re-rendered PDF: {job.final_pdf}\nRe-rendered HTML: {job.final_html}\n")
    job.update(theme=use_theme, final_html=str(job.final_html), final_pdf=str(job.final_pdf))
    job.set_status("done")
    return job


def _run_raw_markdown_pipeline(job: Job, *, theme: str, strict_math: bool) -> Job:
    return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)


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
    parser.add_argument("input_path", type=Path, nargs="?")
    parser.add_argument("--paste-file", type=Path)
    parser.add_argument("--theme", default="claude_clean")
    parser.add_argument(
        "--no-strict-math",
        action="store_true",
        help="Render invalid KaTeX expressions as error-marked HTML instead of failing.",
    )
    args = parser.parse_args(argv)

    try:
        if args.paste_file:
            if args.input_path is not None:
                parser.error("Provide either input_path or --paste-file, not both.")
            text = args.paste_file.read_text(encoding="utf-8", errors="replace")
            job = run_pasted_text_job(
                text,
                theme=args.theme,
                strict_math=not args.no_strict_math,
            )
        else:
            if args.input_path is None:
                parser.error("input_path is required unless --paste-file is used.")
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
