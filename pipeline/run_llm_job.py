from __future__ import annotations

import argparse
import os
import re
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.job_manager import Job
from pipeline.extract import ExtractionError, extract_file
from pipeline.llm_client import LLMConfig, LLMProviderError, MissingLLMConfigError
from pipeline.orchestrator import generate_study_guide
from pipeline.run_markdown_job import MarkdownJobError, run_raw_markdown_pipeline

MAX_ATTACHMENT_CHARS = int(os.getenv("MAX_ATTACHMENT_CHARS", "200000"))
MAX_TOTAL_ATTACHMENT_CHARS = int(os.getenv("MAX_TOTAL_ATTACHMENT_CHARS", "600000"))


class LLMJobError(RuntimeError):
    def __init__(self, message: str, job: Job | None = None) -> None:
        super().__init__(message)
        self.job = job


@dataclass(frozen=True)
class AttachmentSource:
    path: Path
    filename: str


def run_llm_job(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    prompt_name: str = "basic_study_guide",
    generator_preset: str | None = None,
    include_sections: dict[str, bool] | None = None,
    theme: str = "claude_clean",
    strict_math: bool = True,
    config: LLMConfig | None = None,
    attachments: list[AttachmentSource] | None = None,
) -> Job:
    resolved_config = config or LLMConfig.from_env()
    job = Job.create(
        {
            "path_mode": "generate",
            "input_type": "text",
            "title": title,
            "mode": mode,
            "prompt_name": prompt_name,
            "generator_preset": generator_preset,
            # Persisted so rerender reproduces the same requested output sections.
            "include_sections": include_sections or {},
            "theme": theme,
            "strict_math": strict_math,
            "provider": resolved_config.provider,
            "model": resolved_config.model,
        }
    )

    print(f"Job id: {job.id}")
    print(f"Job dir: {job.dir}")

    try:
        job.set_status("saving_input")
        job.set_stage("preparing")
        attachment_report: dict[str, Any] = {
            "files": [],
            "warnings": [],
            "total_extracted_chars": 0,
        }
        augmented_source = source_text
        if attachments:
            job.set_stage("extracting")
            augmented_source, attachment_report = _attach_sources(
                job, source_text, attachments, generator_preset=generator_preset
            )

        source_path = job.input_dir / "source.txt"
        job.save_text(source_path, augmented_source)
        job.update(
            input_path=str(source_path),
            attachments=attachment_report["files"],
            extraction_warnings=attachment_report["warnings"],
            total_extracted_chars=attachment_report["total_extracted_chars"],
        )

        job.set_status("generating")
        raw_markdown = generate_study_guide(
            augmented_source,
            title=title,
            mode=mode,
            prompt_name=prompt_name,
            generator_preset=generator_preset,
            include_sections=include_sections,
            config=resolved_config,
            on_stage=job.set_stage,
        )
        job.save_text(job.raw_md, raw_markdown)
        job.update(raw_md=str(job.raw_md))

        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except LLMProviderError as exc:
        job.set_status("failed", str(exc), error_category=exc.category, log_path=str(job.render_log))
        raise LLMJobError(str(exc), job) from exc
    except MarkdownJobError as exc:
        # category already set in run_raw_markdown_pipeline
        raise LLMJobError(str(exc), exc.job) from exc
    except Exception as exc:
        from pipeline.errors import classify_exception
        category, user_message = classify_exception(
            exc, base_url=getattr(resolved_config, "base_url", None)
        )
        job.set_status("failed", user_message, error_category=category, log_path=str(job.render_log))
        raise LLMJobError(user_message, job) from exc


def _attach_sources(
    job: Job,
    source_text: str,
    attachments: list[AttachmentSource],
    *,
    generator_preset: str | None = None,
) -> tuple[str, dict[str, Any]]:
    attachment_dir = job.input_dir / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)

    # When a generator preset is active its prompt promises to "cover the whole
    # deck", so any truncation/skip silently breaks that promise. Make those
    # warnings explicit so the user knows to raise the cap or split the deck.
    preset_note = (
        f" The '{generator_preset}' preset aims to cover the whole deck, so this "
        "truncation compromises that goal — raise MAX_ATTACHMENT_CHARS / "
        "MAX_TOTAL_ATTACHMENT_CHARS or split the deck."
        if generator_preset
        else ""
    )

    sections: list[str] = []
    files: list[dict[str, Any]] = []
    warnings: list[str] = []
    total_chars = 0

    for index, attachment in enumerate(attachments, start=1):
        safe_name = _safe_filename(attachment.filename, fallback=f"attachment-{index}{attachment.path.suffix}")
        saved_path = attachment_dir / safe_name
        shutil.copy2(attachment.path, saved_path)

        entry: dict[str, Any] = {
            "filename": safe_name,
            "original_filename": attachment.filename,
            "path": str(saved_path),
            "status": "pending",
            "mode": None,
            "extracted_chars": 0,
            "truncated": False,
            "warnings": [],
        }
        try:
            result = extract_file(saved_path)
            extracted_text = result.text.strip()
            entry["mode"] = result.mode
            entry["warnings"] = result.warnings

            remaining = max(MAX_TOTAL_ATTACHMENT_CHARS - total_chars, 0)
            if not extracted_text:
                warning = f"{safe_name}: no text could be extracted."
                warnings.append(warning)
                entry["warnings"] = [*entry["warnings"], warning]
                entry["status"] = "warning"
            elif remaining <= 0:
                warning = f"{safe_name}: skipped because the attachment text limit was reached.{preset_note}"
                warnings.append(warning)
                entry["warnings"] = [*entry["warnings"], warning]
                entry["status"] = "skipped"
            else:
                limit = min(MAX_ATTACHMENT_CHARS, remaining)
                clipped_text = extracted_text[:limit]
                truncated = len(extracted_text) > limit
                if truncated:
                    warning = f"{safe_name}: extracted text was truncated to {limit} characters.{preset_note}"
                    warnings.append(warning)
                    entry["warnings"] = [*entry["warnings"], warning]
                sections.append(f"### {safe_name}\n{clipped_text}")
                total_chars += len(clipped_text)
                entry["status"] = "extracted"
                entry["extracted_chars"] = len(clipped_text)
                entry["truncated"] = truncated

            warnings.extend(result.warnings)
        except ExtractionError as exc:
            warning = f"Couldn't read {safe_name}: the file may be corrupt or an unreadable scan. ({exc})"
            warnings.append(warning)
            entry["status"] = "failed"
            entry["warnings"] = [warning]

        files.append(entry)

    if not sections:
        return source_text, {
            "files": files,
            "warnings": _dedupe(warnings),
            "total_extracted_chars": total_chars,
        }

    attached_text = "\n\n## Attached Sources\n\n" + "\n\n".join(sections)
    return source_text.rstrip() + attached_text, {
        "files": files,
        "warnings": _dedupe(warnings),
        "total_extracted_chars": total_chars,
    }


def _safe_filename(filename: str, *, fallback: str) -> str:
    name = Path(filename or fallback).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or fallback


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a study guide with an OpenAI-compatible LLM.")
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--mode", default="exam")
    parser.add_argument("--prompt-name", default="basic_study_guide")
    parser.add_argument(
        "--generator-preset",
        default=None,
        help="Generator preset id (e.g. claude_exam); overrides --prompt-name when set.",
    )
    parser.add_argument("--theme", default="claude_clean")
    parser.add_argument(
        "--no-strict-math",
        action="store_true",
        help="Render invalid KaTeX expressions as error-marked HTML instead of failing.",
    )
    args = parser.parse_args(argv)

    try:
        config = LLMConfig.from_env()
        source_text = args.source_file.read_text(encoding="utf-8", errors="replace")
        job = run_llm_job(
            source_text,
            title=args.title,
            mode=args.mode,
            prompt_name=args.prompt_name,
            generator_preset=args.generator_preset,
            theme=args.theme,
            strict_math=not args.no_strict_math,
            config=config,
        )
    except MissingLLMConfigError as exc:
        print(f"LLM configuration error: {exc}", file=sys.stderr)
        return 2
    except LLMJobError as exc:
        print(str(exc), file=sys.stderr)
        if exc.job is not None:
            print(f"Job id: {exc.job.id}", file=sys.stderr)
            print(f"Job dir: {exc.job.dir}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"LLM job failed before creation: {exc}", file=sys.stderr)
        return 1

    print("Status: done")
    print(f"Job manifest: {job.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
