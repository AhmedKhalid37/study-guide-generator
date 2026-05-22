from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.job_manager import Job
from pipeline.llm_client import LLMConfig, MissingLLMConfigError
from pipeline.orchestrator import generate_study_guide
from pipeline.run_markdown_job import MarkdownJobError, run_raw_markdown_pipeline


class LLMJobError(RuntimeError):
    def __init__(self, message: str, job: Job | None = None) -> None:
        super().__init__(message)
        self.job = job


def run_llm_job(
    source_text: str,
    *,
    title: str,
    mode: str = "exam",
    theme: str = "claude_clean",
    strict_math: bool = True,
    config: LLMConfig | None = None,
) -> Job:
    resolved_config = config or LLMConfig.from_env()
    job = Job.create(
        {
            "path_mode": "generate",
            "input_type": "text",
            "title": title,
            "mode": mode,
            "theme": theme,
            "strict_math": strict_math,
            "provider": "openai_compatible",
            "model": resolved_config.model,
        }
    )

    print(f"Job id: {job.id}")
    print(f"Job dir: {job.dir}")

    try:
        job.set_status("saving_input")
        source_path = job.input_dir / "source.txt"
        job.save_text(source_path, source_text)
        job.update(input_path=str(source_path))

        job.set_status("generating")
        raw_markdown = generate_study_guide(
            source_text,
            title=title,
            mode=mode,
            config=resolved_config,
        )
        job.save_text(job.raw_md, raw_markdown)
        job.update(raw_md=str(job.raw_md))

        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except MarkdownJobError as exc:
        raise LLMJobError(str(exc), exc.job) from exc
    except Exception as exc:
        message = f"LLM job failed: {exc}"
        job.set_status("failed", message)
        raise LLMJobError(message, job) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a study guide with an OpenAI-compatible LLM.")
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--mode", default="exam")
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
