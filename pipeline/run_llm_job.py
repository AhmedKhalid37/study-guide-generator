from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.job_manager import Job, JobCancelled
from pipeline.extract import ExtractionError, extract_file
from pipeline.extraction_metadata import (
    pdf_source_metadata,
    write_extraction_metadata,
    write_skipped_extraction_metadata,
)
from pipeline.source_coverage_artifact import write_source_coverage_report
from pipeline.page_selection_model import (
    apply_material_selection_to_page_universe,
    normalize_page_selection,
)
from pipeline.visual_assets_manifest import write_visual_assets_manifest
from pipeline.visual_asset_scoring import write_visual_asset_scoring_report
from pipeline.visual_replacement_planner import write_visual_replacement_plan_report
from pipeline.visual_asset_extractor import (
    MAX_FIGURES_PER_JOB,
    extract_local_figures,
    local_figure_extraction_enabled,
)
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
    output_depth: str | None = None,
    difficulty: str | None = None,
    theme: str = "claude_clean",
    strict_math: bool = True,
    config: LLMConfig | None = None,
    attachments: list[AttachmentSource] | None = None,
    page_selections: dict[str, list[list[int]]] | None = None,
    material_page_selection: dict[str, Any] | None = None,
    material_page_selections: dict[str, Any] | None = None,
    enable_visual_references: bool = False,
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
            # Global generation-directive axes (C2), persisted so rerender
            # reproduces the same depth/difficulty. Unset stays None.
            "output_depth": output_depth,
            "difficulty": difficulty,
            # Optional per-file PDF page selection. Persisted so a future
            # retry/rerender preserves it, and (Slice 4) consumed by extraction:
            # matching PDF attachments are restricted to the selected original
            # pages. Empty / absent => all pages => unchanged behaviour.
            "page_selections": page_selections or {},
            # Slice 79 (Full Material Coverage): normalized page/slide
            # inclusion-exclusion model (Slice 78 page_selection_model shape),
            # already normalized at the API handler. Persisted so a future
            # retry/rerender and later application slices preserve it. SEPARATE from
            # the page_selections PDF page-range field above and consumed by NOTHING
            # yet — no extraction/content/visual/render/export/prompt change. Absent
            # => {} => default "all" resolved by the safe reader on read.
            "material_page_selection": material_page_selection or {},
            # Slice 80 (Full Material Coverage): PER-ATTACHMENT material selections
            # envelope {version, attachments:{attachment_<i>: model}, warnings},
            # already normalized at the API handler with SAFE attachment_<index>
            # keys (never filenames/paths). Preferred per-attachment intent; the
            # top-level material_page_selection stays as the global fallback.
            # Persisted so retry/rerender and later application slices preserve it;
            # consumed by NOTHING yet. Absent => {} resolved by the safe reader.
            "material_page_selections": material_page_selections or {},
            # Slice 55: per-job opt-in for the off-by-default visual markdown image
            # pilot. Persisted so the pilot (apply_visual_markdown_pilot, read in
            # run_raw_markdown_pipeline) can AND it with the global env master
            # switch. Coerced to a strict bool here; default False keeps every
            # existing/non-opted-in job byte-identical. The env switch still wins —
            # this flag alone never enables insertion.
            "visual_markdown_image_pilot": bool(enable_visual_references),
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
        job.raise_if_cancelled()
        attachment_report: dict[str, Any] = {
            "files": [],
            "warnings": [],
            "total_extracted_chars": 0,
        }
        augmented_source = source_text
        if attachments:
            job.set_stage("extracting")
            augmented_source, attachment_report = _attach_sources(
                job,
                source_text,
                attachments,
                generator_preset=generator_preset,
                page_selections=page_selections,
                material_page_selection=material_page_selection,
                material_page_selections=material_page_selections,
            )

        source_path = job.input_dir / "source.txt"
        job.save_text(source_path, augmented_source)
        job.update(
            input_path=str(source_path),
            attachments=attachment_report["files"],
            extraction_warnings=attachment_report["warnings"],
            total_extracted_chars=attachment_report["total_extracted_chars"],
        )

        # Best early-exit checkpoint: bail before the expensive, uninterruptible
        # LLM call rather than after paying for it.
        job.raise_if_cancelled()
        job.set_status("generating")
        raw_markdown = generate_study_guide(
            augmented_source,
            title=title,
            mode=mode,
            prompt_name=prompt_name,
            generator_preset=generator_preset,
            include_sections=include_sections,
            output_depth=output_depth,
            difficulty=difficulty,
            config=resolved_config,
            on_stage=job.set_stage,
        )
        job.save_text(job.raw_md, raw_markdown)
        job.update(raw_md=str(job.raw_md))

        # The LLM call has returned; bail before the render phase so a cancel
        # requested during generation skips the Chromium PDF render.
        job.raise_if_cancelled()
        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except JobCancelled as exc:
        # Cooperative cancel observed at a safe boundary: stop cleanly, preserve
        # whatever partial input/source was written, and end in a non-failure
        # terminal status. Clear the marker so a later retry isn't auto-cancelled.
        exc.job.clear_cancel_request()
        exc.job.set_status("cancelled")
        return exc.job
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
    page_selections: dict[str, list[list[int]]] | None = None,
    material_page_selection: dict[str, Any] | None = None,
    material_page_selections: dict[str, Any] | None = None,
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
    extraction_metadata_sources: list[dict[str, Any]] = []
    # Slice 40: saved PDF path + page set per metadata source, kept in lockstep with
    # extraction_metadata_sources so the gated local figure extractor can re-open the
    # exact same PDFs/pages. Only used when extraction is enabled (off by default).
    pdf_extraction_inputs: list[dict[str, Any]] = []
    # Slice 82: per-metadata-source visual-manifest page filter, kept in lockstep
    # with extraction_metadata_sources. Each entry is the EFFECTIVE post-material
    # allowed page set when a material selection was APPLIED for that attachment, or
    # None (no active material filter ⇒ existing visual-manifest behaviour). Passed
    # to write_visual_assets_manifest so excluded pages contribute no visual records.
    visual_page_filters: list[set[int] | None] = []
    pdf_metadata_unavailable = False
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
        # Page selections are keyed by the ORIGINAL upload filename (the same value
        # stored as `original_filename` in this attachment's metadata, set by the
        # frontend / `_save_llm_attachments`). They apply to PDFs only; a selection
        # for a non-PDF attachment is ignored. `extract_file` itself also ignores
        # `pages` for non-PDFs, so this guard is just to skip needless work.
        selected_pages: set[int] | None = None
        if page_selections and saved_path.suffix.lower() == ".pdf":
            ranges = page_selections.get(attachment.filename)
            if ranges:
                selected_pages = _expand_page_ranges(ranges)

        # Slice 81: apply the Full Material Coverage page/slide selection to which
        # pages are extracted. Precedence per attachment: per-attachment
        # material_page_selections[attachment_<i>] > global material_page_selection >
        # default-all. A material selection can only FURTHER FILTER the existing
        # page_selections universe (above); it never expands extraction beyond it.
        # Non-PDF attachments are ignored (page semantics not implemented).
        # Degrade-never-fail: an unresolvable selection (exclude/all with no known
        # universe) leaves extraction unchanged and records a closed warning.
        is_pdf = saved_path.suffix.lower() == ".pdf"
        # Slice 82: the effective post-material allowed page set when a material
        # selection is APPLIED to this PDF, else None (no active visual-manifest
        # filter for this source — existing behaviour preserved).
        material_visual_filter: set[int] | None = None
        material_selection = _resolve_material_selection(
            f"attachment_{index - 1}", material_page_selections, material_page_selection
        )
        if material_selection is not None:
            if not is_pdf:
                entry["material_selection"] = {
                    "status": "not_applicable",
                    "warnings": ["material_selection_non_pdf_ignored"],
                }
            else:
                existing_universe = sorted(selected_pages) if selected_pages else None
                outcome = apply_material_selection_to_page_universe(
                    material_selection, existing_allowed_pages=existing_universe
                )
                if outcome["resolved"]:
                    selected_pages = set(outcome["included_pages"])
                    # Same effective set drives extraction (above) and the visual
                    # manifest (below), so a visual record can never survive on a
                    # page extraction already excluded.
                    material_visual_filter = set(selected_pages)
                    entry["material_selection"] = {
                        "status": "applied",
                        "warnings": [*outcome["warnings"], "material_selection_applied"],
                    }
                else:
                    entry["material_selection"] = {
                        "status": "deferred",
                        "warnings": outcome["warnings"],
                    }

        try:
            result = extract_file(saved_path, pages=selected_pages)
            extracted_text = result.text.strip()
            entry["mode"] = result.mode
            entry["warnings"] = result.warnings

            if saved_path.suffix.lower() == ".pdf":
                try:
                    source_metadata = pdf_source_metadata(
                        filename=safe_name,
                        content_type=_content_type_for(saved_path),
                        extraction_metadata=result.metadata,
                    )
                    if source_metadata is None:
                        pdf_metadata_unavailable = True
                    else:
                        extraction_metadata_sources.append(source_metadata)
                        pdf_extraction_inputs.append(
                            {
                                "path": saved_path,
                                "pages": set(selected_pages) if selected_pages else None,
                            }
                        )
                        # Slice 82: keep the visual-manifest page filter in lockstep
                        # with the metadata source just appended.
                        visual_page_filters.append(material_visual_filter)
                except Exception as exc:
                    pdf_metadata_unavailable = True
                    print(
                        f"Extraction metadata source skipped ({type(exc).__name__}); job continues.",
                        file=sys.stderr,
                    )

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
            if saved_path.suffix.lower() == ".pdf":
                pdf_metadata_unavailable = True

        files.append(entry)

    if pdf_metadata_unavailable:
        write_skipped_extraction_metadata(job)
        _write_source_coverage_report_safely(
            job,
            {
                "version": 2,
                "kind": "extraction_metadata",
                "status": "skipped",
                "reason": "metadata_unavailable",
                "safe_message": "Extraction metadata could not be collected.",
            },
        )
    elif extraction_metadata_sources:
        write_extraction_metadata(job, extraction_metadata_sources)
        # Slice 38: derive the provider-agnostic visual-assets manifest from the
        # same sanitized sources. Advisory-only and wrapped; it is written exactly
        # when extraction metadata exists, and never gates or fails the job. Non-PDF
        # jobs / unavailable metadata simply omit the artifact (no call here).
        #
        # Slice 40: when the gated local figure extractor is enabled, additionally
        # crop real figure regions from the same PDFs and merge them (re-sanitised)
        # into the manifest as `extracted_figure` assets. Off by default → this
        # branch is skipped and the manifest is byte-identical to Slice 38.
        extracted_assets = _extract_local_figures(job, pdf_extraction_inputs)
        # Slice 82: apply the same Full Material Coverage page selection to the
        # visual manifest. `visual_page_filters` is aligned by index with
        # `extraction_metadata_sources`; excluded pages contribute no visual
        # candidates. None entries (no active material selection) preserve behaviour.
        write_visual_assets_manifest(
            job,
            extraction_metadata_sources,
            extracted_assets,
            page_filters=visual_page_filters,
        )
        # Slice 47: persist the advisory visual-asset SCORING report derived from
        # the manifest we just wrote. Reads only the persisted (sanitized) manifest
        # object, never mutates it, and is degrade-not-fail — it never gates or
        # fails the job. Written exactly when the manifest is written; non-PDF jobs
        # with no extraction metadata simply omit these artifacts (no call here).
        visual_manifest_obj = _read_visual_manifest_for_scoring(job)
        _write_source_coverage_report_safely(
            job,
            {
                "version": 2,
                "kind": "extraction_metadata",
                "status": "completed",
                "sources": extraction_metadata_sources,
            },
            visual_manifest=visual_manifest_obj,
        )
        scoring_report = write_visual_asset_scoring_report(job, visual_manifest_obj)
        # Slice 49: persist the advisory visual REPLACEMENT PLAN derived from the
        # scoring report we just wrote; the manifest is passed only for a
        # presence-only asset-id cross-check. Degrade-not-fail — it never gates or
        # fails the job, never mutates the scoring report or manifest, makes no
        # production include/omit decision, and never embeds visuals. If scoring was
        # skipped/unavailable, a safe skipped plan is written for consistency.
        write_visual_replacement_plan_report(
            job, scoring_report, manifest=visual_manifest_obj
        )

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


def _resolve_material_selection(
    attachment_key: str,
    per_attachment: dict[str, Any] | None,
    global_selection: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve the ACTIVE material page selection for one attachment (Slice 81).

    Precedence: a per-attachment entry (``material_page_selections.attachments
    [attachment_<i>]``) wins outright when present — even if it is default-all, in
    which case the global selection is intentionally NOT consulted. Otherwise the
    global ``material_page_selection`` is the fallback. Returns the normalized model
    only when it would actually filter pages (an "active" selection); a default-all
    / absent selection returns ``None`` so extraction stays byte-identical.
    """
    selection: Any = None
    used_per_attachment = False
    if isinstance(per_attachment, dict):
        attachments = per_attachment.get("attachments")
        if isinstance(attachments, dict) and attachment_key in attachments:
            selection = attachments[attachment_key]
            used_per_attachment = True
    if not used_per_attachment and isinstance(global_selection, dict) and global_selection:
        selection = global_selection
    if not isinstance(selection, dict):
        return None
    normalized = normalize_page_selection(selection)
    if not _is_active_material_selection(normalized):
        return None
    return normalized


def _is_active_material_selection(normalized: dict[str, Any]) -> bool:
    """True when a normalized selection would change the extracted page set.

    ``include`` always restricts (even an empty include => no pages). ``all`` /
    ``exclude`` only restrict when there is at least one excluded page; a bare
    ``all`` with no exclusions is a no-op and is treated as absent.
    """
    if normalized.get("mode") == "include":
        return True
    return bool(normalized.get("exclude_pages"))


def _expand_page_ranges(ranges: list[list[int]]) -> set[int]:
    """Expand normalized 1-based inclusive ``[[start, end], ...]`` ranges to a set
    of page numbers. Ranges arrive already validated/merged by the API's
    ``_normalize_page_selections`` (positive ints, ``start <= end``); this only
    flattens them. Extraction validates the result against the real page count.
    """
    pages: set[int] = set()
    for pair in ranges:
        start, end = int(pair[0]), int(pair[1])
        pages.update(range(start, end + 1))
    return pages


def _read_visual_manifest_for_scoring(job: Job) -> dict[str, Any] | None:
    """Read back the just-written ``visual_assets_manifest.json`` for scoring.

    Best-effort and total: returns ``None`` on any read/parse error so the advisory
    scoring writer degrades to a safe skipped report. Never raises, never mutates.
    """
    try:
        path = job.visual_assets_manifest_json
        if not path.exists():
            return None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def _write_source_coverage_report_safely(
    job: Job,
    extraction_metadata: Any,
    *,
    visual_manifest: Any = None,
) -> None:
    """Best-effort source coverage artifact write; never gates generation."""
    try:
        write_source_coverage_report(
            job,
            extraction_metadata,
            visual_manifest=visual_manifest,
        )
    except Exception as exc:
        print(
            f"Source coverage report skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )


def _extract_local_figures(
    job: Job,
    pdf_inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run the gated local figure extractor over the job's saved PDFs (Slice 40).

    Returns an empty list (no work, no ``assets/`` dir) unless the
    ``GUIDEFORGE_LOCAL_FIGURE_EXTRACTION`` flag is on, so the default job is
    byte-identical to Slice 38. Advisory-only and fully wrapped: a failure here
    never propagates — it just yields fewer/zero figures.
    """
    if not local_figure_extraction_enabled() or not pdf_inputs:
        return []

    extracted: list[dict[str, Any]] = []
    for source_index, item in enumerate(pdf_inputs):
        remaining = MAX_FIGURES_PER_JOB - len(extracted)
        if remaining <= 0:
            break
        try:
            extracted.extend(
                extract_local_figures(
                    item["path"],
                    assets_dir=job.assets_dir,
                    source_index=source_index,
                    pages=item.get("pages"),
                    remaining_budget=remaining,
                )
            )
        except Exception as exc:  # belt-and-braces; extractor already wraps
            print(
                f"Local figure extraction skipped ({type(exc).__name__}); job continues.",
                file=sys.stderr,
            )
    return extracted


def _safe_filename(filename: str, *, fallback: str) -> str:
    name = Path(filename or fallback).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or fallback


def _content_type_for(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    return guessed or "application/octet-stream"


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
