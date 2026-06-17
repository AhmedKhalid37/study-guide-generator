from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from pipeline.input_handler import accept_markdown_upload, accept_paste, needs_extraction
from pipeline.job_manager import Job, JobCancelled
from pipeline.markdown_sanitizer import sanitize
from pipeline.math_validator import validate
from pipeline.pdf_renderer import render_pdf
from pipeline.visual_markdown_insertion import apply_visual_markdown_pilot


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
        job.set_stage("preparing")
        saved_input = accept_markdown_upload(job, source)
        shutil.copy2(saved_input, job.raw_md)
        job.update(input_path=str(saved_input), raw_md=str(job.raw_md))
        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except JobCancelled:
        job.clear_cancel_request()
        job.set_status("cancelled")
        return job
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
        job.set_stage("preparing")
        pasted = accept_paste(job, text)
        job.save_text(job.raw_md, text)
        job.update(input_path=str(pasted), raw_md=str(job.raw_md))
        return run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
    except JobCancelled:
        job.clear_cancel_request()
        job.set_status("cancelled")
        return job
    except MarkdownJobError:
        raise
    except Exception as exc:
        from pipeline.errors import classify_exception
        category, user_message = classify_exception(exc)
        job.set_status("failed", user_message, error_category=category)
        raise MarkdownJobError(user_message, job) from exc


def run_raw_markdown_pipeline(job: Job, *, theme: str, strict_math: bool) -> Job:
    # Cooperative cancel checkpoint at the phase boundary (before sanitize).
    job.raise_if_cancelled()
    job.set_status("sanitizing")
    job.set_stage("cleaning")
    raw = job.raw_md.read_text(encoding="utf-8", errors="replace")
    clean = sanitize(raw)
    # Slice 54: off-by-default minimal V4/V5 visual pilot. When the flag is unset
    # this returns `clean` unchanged (byte-identical, no artifact reads); when on it
    # may insert at most one existing fitz_local extracted figure as a standard
    # Markdown image. Degrade-never-fail — it never raises and never blocks the job,
    # and clean.md still flows through the single save_clean_md chokepoint below.
    clean, _visual_pilot = apply_visual_markdown_pilot(job, clean)
    job.save_clean_md(clean, "generated")
    job.update(clean_md=str(job.clean_md))
    print(f"clean.md: {job.clean_md}")

    job.set_status("validating")
    job.set_stage("checking_math")
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

    # Slice 21: persist a per-job math_verification.json sibling artifact from the
    # final, sanitized clean.md. Advisory-only and fully defensive - it never
    # changes job status, never blocks the render below, and never fails the job.
    _write_math_verification(job)

    # Slice 27: persist a per-job guide_lint.json sibling artifact from the same
    # final, sanitized clean.md. Same advisory contract as math verification:
    # never changes job status, never blocks the render, never fails the job.
    _write_guide_lint(job)

    # Slice 96: persist a per-job guide_quality_report_v2.json sibling artifact that
    # measures whether the generated clean.md appears to reflect the Slices 82–95
    # coverage signals. Same advisory contract: it scans clean.md for safe COUNTS
    # ONLY (no excerpt persisted), reads only the already-sanitized coverage
    # artifacts, calls no LLM, inspects no PDF/image, reconstructs no table, never
    # changes job status, never blocks the render, and never fails the job.
    _write_guide_quality_report_v2(job)

    # Slice 102: persist a per-job guide_quality_contract_lint.json sibling artifact.
    # It scans the generated clean.md for safe COUNTS ONLY (reasoning-leak signatures,
    # required-section presence, exam-alert/table counts — no excerpt/phrase/heading/
    # number persisted) and is flag-only: same advisory contract as the others — it
    # calls no LLM, inspects no PDF/image, reconstructs no table, never changes job
    # status, never blocks the render, and never fails the job.
    _write_guide_quality_contract_lint(job)

    # Slice 103: persist a per-job guide_quality_qa_gate.json sibling artifact. It
    # combines the already-sanitized contract lint, guide quality report v2, source
    # coverage report, and the existing numeric math verification (written just above)
    # into one advisory pass/warning/skipped summary (counts + closed tokens only).
    # Same advisory contract: it calls no LLM, reruns no math verification, inspects
    # no PDF/image, reconstructs no table, never changes job status, never blocks the
    # render, and never fails the job. ``blocking`` is always false (flag-only v1).
    _write_guide_quality_qa_gate(job)

    # Slice 105: persist a per-job guide_quality_rubric_score.json sibling artifact.
    # It converts the already-sanitized guide-quality artifacts into a closed,
    # advisory rubric scorecard. Unsupported semantic axes stay unknown instead of
    # being fake-scored. Same advisory contract: no LLM/provider/model/cloud calls,
    # no PDF/image/OCR/table inspection, no prompt/render/export changes, no status
    # changes, no blocking, and no job failure.
    _write_guide_quality_rubric_score(job)

    # Slice 118: persist a per-job quality_safety_unified_qa.json sibling artifact.
    # It is advisory-only and deterministic: it scans the final, sanitized clean.md
    # only as input to the safe leak scanner, uses structured extraction bundles
    # only when such a safe bundle exists, stores closed counts/tokens only, calls
    # no provider/model/cloud service, never changes prompts, never rewrites or
    # repairs guide content, never changes job status, never blocks render/export,
    # and never fails the job.
    _write_quality_safety_unified_qa(job)

    # Last safe checkpoint before the uninterruptible Chromium render: a cancel
    # requested up to here skips the render entirely. Once render_pdf starts we
    # let it finish (no process killing).
    job.raise_if_cancelled()
    job.set_status("rendering")
    job.set_stage("rendering")
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

    # PDF + HTML are written; finalize the artifact records (docx stays lazy).
    job.set_stage("exporting")
    job.save_text(job.render_log, f"Rendered PDF: {job.final_pdf}\nRendered HTML: {job.final_html}\n")
    job.update(final_html=str(job.final_html), final_pdf=str(job.final_pdf))
    # A usable guide was produced. Use a non-fatal terminal status when math was
    # degraded so the UI can show a "fix these expressions" notice without
    # presenting a failure state.
    job.set_status("done" if result.ok else "completed_with_warnings")
    job.set_stage("complete")

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


def _write_math_verification(job: Job) -> None:
    """Persist a per-job ``math_verification.json`` sibling artifact (Slice 21).

    Runs the deterministic Slice 18 numeric verifier
    (:func:`pipeline.math_verifier.verify_math_claims`) against the final,
    sanitized ``clean.md`` and records its report. This is **advisory only**:

      * It NEVER fails the job, NEVER changes the visible job status, and NEVER
        blocks PDF/HTML/DOCX rendering.
      * Zero extracted claims is a normal ``completed`` result (summary total 0).
      * Mismatched / unparseable claims are recorded; they do not fail the job.
      * Any unexpected error degrades to a small ``skipped`` artifact carrying a
        safe message and NO traceback. Tracebacks/expression bodies are never
        written to the artifact, and only the exception *type name* is logged.

    The verifier (``math_verifier``) is the numeric-correctness checker and is
    deliberately distinct from ``math_validator`` (KaTeX render validation, whose
    ``validation.json`` schema is untouched by this artifact).
    """
    artifact_path = job.math_verification_json
    try:
        from pipeline.math_verifier import verify_math_claims

        text = job.clean_md.read_text(encoding="utf-8", errors="replace")
        report = verify_math_claims(text, source_name="clean.md")
        payload = {
            "version": 1,
            "kind": "math_verification",
            "status": "completed",
            "source": "clean.md",
            "report": report.to_dict(),
        }
        job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
    except Exception as exc:  # never let verification break a job
        try:
            payload = {
                "version": 1,
                "kind": "math_verification",
                "status": "skipped",
                "reason": "verifier_error",
                "safe_message": "Math verification could not be completed.",
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise
        # Log only the exception TYPE - never its message/args, which could echo
        # guide content or a path - so the artifact and logs stay clean.
        print(
            f"Math verification skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )


def _write_guide_lint(job: Job) -> None:
    """Persist a per-job ``guide_lint.json`` sibling artifact (Slice 27).

    Runs the deterministic Slice 19 structural advisory core
    (:func:`pipeline.guide_lint.lint_guide_markdown`) against the final,
    sanitized ``clean.md`` and records its report. This is **advisory only**,
    mirroring the math-verification artifact contract:

      * It NEVER fails the job, NEVER changes the visible job status, and NEVER
        blocks PDF/HTML/DOCX rendering.
      * Zero findings is a normal ``completed`` result (summary total 0).
      * Structural findings (empty headings, broken tables, unbalanced math,
        KaTeX render issues) are recorded; they do not fail the job.
      * Any unexpected error degrades to a small ``skipped`` artifact carrying a
        safe message and NO traceback. Tracebacks/expression bodies are never
        written to the artifact, and only the exception *type name* is logged.

    Lint scope choices for this slice (kept deliberately small):

      * ``expected_sections`` is NOT passed. The job manifest only stores
        canonical section-toggle keys (e.g. ``key_concepts``), not the actual
        heading text the LLM emits, so feeding them to the heading matcher would
        produce unreliable / noisy ``missing_section`` findings. Wiring real
        expected headings is left to a later slice.
      * ``available_source_pages`` is NOT passed. Source page anchors are not
        reliably available here without invasive source-text plumbing (and are
        absent for paste / Markdown-upload jobs), so the optional page-citation
        check is left disabled to keep this slice non-invasive.

    The guide-lint core (``guide_lint``) is the structural checker and is
    deliberately distinct from ``math_validator`` (KaTeX render validation, whose
    ``validation.json`` schema is untouched by this artifact) and from
    ``math_verifier`` (numeric ``math_verification.json``).
    """
    artifact_path = job.guide_lint_json
    try:
        from pipeline.guide_lint import lint_guide_markdown

        text = job.clean_md.read_text(encoding="utf-8", errors="replace")
        report = lint_guide_markdown(text, source_name="clean.md")
        payload = {
            "version": 1,
            "kind": "guide_lint",
            "status": "completed",
            "source": "clean.md",
            "report": report.to_dict(),
        }
        job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
    except Exception as exc:  # never let linting break a job
        try:
            payload = {
                "version": 1,
                "kind": "guide_lint",
                "status": "skipped",
                "reason": "lint_error",
                "safe_message": "Guide lint could not be completed.",
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise


def _read_json_artifact(path: Path) -> dict | None:
    """Best-effort read of an already-sanitized sibling JSON artifact.

    Returns the parsed dict when present and well-formed, else ``None``. Never
    raises; a missing/unreadable/non-dict artifact simply contributes no signal.
    """
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_guide_quality_report_v2(job: Job) -> None:
    """Persist a per-job ``guide_quality_report_v2.json`` sibling artifact (Slice 96).

    Builds the deterministic, sanitized guide quality report
    (:func:`pipeline.guide_quality_report_v2.build_guide_quality_report_v2`) from the
    generated ``clean.md`` (scanned for safe COUNTS ONLY — no excerpt is ever
    persisted) plus the already-sanitized sibling coverage artifacts. The optional
    missing-material and coverage-aware contexts are rebuilt from those same
    sanitized artifacts via the existing pure builders so the report can note whether
    the guide reflected that guidance.

    Same advisory contract as math verification / guide lint:

      * It NEVER fails the job, NEVER changes the visible job status, and NEVER
        blocks PDF/HTML/DOCX rendering.
      * It calls no LLM/provider, inspects no PDF/image, OCRs nothing, and
        reconstructs no table.
      * A missing/unreadable ``clean.md`` degrades to a safe ``skipped`` report
        rather than failing the job.
      * Any unexpected error degrades to a small ``skipped`` artifact carrying a
        safe message and NO traceback.

    The artifact is reached only by its exact filename (not added to the generic
    ARTIFACTS list / generic UI rows / export selectors).
    """
    artifact_path = job.guide_quality_report_v2_json
    try:
        from pipeline.guide_quality_report_v2 import build_guide_quality_report_v2
        from pipeline.visual_markdown_insertion import is_full_visual_insertion_enabled

        try:
            clean_markdown = job.clean_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            clean_markdown = None

        source_coverage_report = _read_json_artifact(job.source_coverage_report_json)
        visual_inclusion_plan = _read_json_artifact(job.visual_inclusion_plan_json)
        table_candidates_manifest = _read_json_artifact(job.table_candidates_manifest_json)
        table_reconstruction_policy = _read_json_artifact(job.table_reconstruction_policy_json)

        # Rebuild the Slice 94 missing-material context and the Slice 95 coverage-aware
        # context from the same sanitized artifacts (pure / degrade-not-fail builders)
        # so the report can compare observed guidance phrases against expected signals.
        missing_material_context = _build_missing_material_context_for_report(
            visual_inclusion_plan, table_candidates_manifest, table_reconstruction_policy
        )
        coverage_aware_context = _build_coverage_aware_context_for_report(
            source_coverage_report,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            missing_material_context,
        )

        report = build_guide_quality_report_v2(
            clean_markdown,
            source_coverage_report=source_coverage_report,
            visual_inclusion_plan=visual_inclusion_plan,
            table_candidates_manifest=table_candidates_manifest,
            table_reconstruction_policy=table_reconstruction_policy,
            missing_material_context=missing_material_context,
            coverage_aware_context=coverage_aware_context,
            full_visual_insertion_enabled=is_full_visual_insertion_enabled(),
        )
        job.save_text(artifact_path, json.dumps(report, indent=2) + "\n")
    except Exception:  # never let the quality report break a job
        try:
            payload = {
                "version": 2,
                "kind": "guide_quality_report",
                "status": "skipped",
                "reason": "report_error",
                "safe_message": "Guide quality report could not be completed.",
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise


def _write_guide_quality_contract_lint(job: Job) -> None:
    """Persist a per-job ``guide_quality_contract_lint.json`` sibling artifact (Slice 102).

    Builds the deterministic, sanitized, flag-only guide-quality contract lint
    (:func:`pipeline.guide_quality_contract_lint.build_guide_quality_contract_lint_report`)
    from the generated ``clean.md`` (scanned for safe COUNTS ONLY — no excerpt,
    phrase, heading text, table content, formula, example, or number is ever
    persisted). The ``comprehensive`` flag is inferred from the job's saved request
    signals (depth axis / generator preset / style) using the same rule the prompt
    contract uses, so the structural checks match what the guide was asked to be.

    Same advisory contract as math verification / guide lint / quality report v2:

      * It is FLAG-ONLY — it never rewrites, regenerates, rejects, changes the
        visible job status, blocks the render, or fails the job.
      * It calls no LLM/provider, inspects no PDF/image, OCRs nothing, and
        reconstructs no table.
      * A missing/unreadable ``clean.md`` degrades to a safe ``skipped`` report.
      * Any unexpected error degrades to a small ``skipped`` artifact carrying a
        safe message and NO traceback.

    The artifact is reached only by its exact filename (not added to the generic
    ARTIFACTS list / generic UI rows / export selectors).
    """
    artifact_path = job.guide_quality_contract_lint_json
    try:
        from pipeline.guide_quality_contract_lint import (
            build_guide_quality_contract_lint_report,
        )
        from pipeline.guide_quality_prompt_contract import infer_comprehensive

        try:
            clean_markdown = job.clean_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            clean_markdown = None

        try:
            manifest = job.read_manifest()
        except Exception:
            manifest = {}
        comprehensive = infer_comprehensive(
            manifest.get("output_depth"),
            manifest.get("generator_preset"),
            manifest.get("prompt_name"),
            manifest.get("mode"),
        )

        report = build_guide_quality_contract_lint_report(
            clean_markdown, comprehensive=comprehensive
        )
        job.save_text(artifact_path, json.dumps(report, indent=2) + "\n")
    except Exception:  # never let the contract lint break a job
        try:
            payload = {
                "version": 1,
                "kind": "guide_quality_contract_lint",
                "status": "skipped",
                "reason": "lint_error",
                "safe_message": "Guide quality contract lint could not be completed.",
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise


def _write_guide_quality_qa_gate(job: Job) -> None:
    """Persist a per-job ``guide_quality_qa_gate.json`` sibling artifact (Slice 103).

    Builds the deterministic, sanitized, advisory guide-quality QA gate
    (:func:`pipeline.guide_quality_qa_gate.build_guide_quality_qa_gate`) by combining
    the already-written, already-sanitized sibling artifacts: the guide-quality
    contract lint, the guide quality report v2, the source coverage report, and the
    existing numeric math verification (``math_verification.json``, written just above
    in this pipeline). It copies no string out of those artifacts — only known integer
    counts and closed status tokens — so no excerpt, phrase, heading, formula, value,
    table content, caption, OCR text, or source text is ever persisted. The
    ``comprehensive`` flag is inferred from the saved request signals using the same
    rule the prompt contract / contract lint use.

    Same advisory contract as the other quality siblings:

      * It is FLAG-ONLY — ``blocking`` is always ``False``; it never rewrites,
        regenerates, rejects, changes the visible job status, blocks the render, or
        fails the job.
      * It calls no LLM/provider, reruns no math verification, inspects no PDF/image,
        OCRs nothing, and reconstructs no table.
      * Missing/unreadable input artifacts degrade to ``unknown`` checks and a
        ``skipped``/``partial`` gate, never a failure.
      * Any unexpected error degrades to a small ``skipped`` artifact carrying a safe
        message and NO traceback.

    The artifact is reached only by its exact filename (not added to the generic
    ARTIFACTS list / generic UI rows / export selectors).
    """
    artifact_path = job.guide_quality_qa_gate_json
    try:
        from pipeline.guide_quality_qa_gate import build_guide_quality_qa_gate
        from pipeline.guide_quality_prompt_contract import infer_comprehensive

        try:
            manifest = job.read_manifest()
        except Exception:
            manifest = {}
        comprehensive = infer_comprehensive(
            manifest.get("output_depth"),
            manifest.get("generator_preset"),
            manifest.get("prompt_name"),
            manifest.get("mode"),
        )

        gate = build_guide_quality_qa_gate(
            guide_quality_contract_lint=_read_json_artifact(job.guide_quality_contract_lint_json),
            guide_quality_report_v2=_read_json_artifact(job.guide_quality_report_v2_json),
            source_coverage_report=_read_json_artifact(job.source_coverage_report_json),
            math_verification=_read_json_artifact(job.math_verification_json),
            math_validation=_read_json_artifact(job.logs_dir / "validation.json"),
            comprehensive=comprehensive,
        )
        job.save_text(artifact_path, json.dumps(gate, indent=2) + "\n")
    except Exception:  # never let the QA gate break a job
        try:
            payload = {
                "version": 1,
                "kind": "guide_quality_qa_gate",
                "status": "skipped",
                "reason": "gate_error",
                "safe_message": "Guide quality QA gate could not be completed.",
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise


def _write_guide_quality_rubric_score(job: Job) -> None:
    """Persist a per-job ``guide_quality_rubric_score.json`` artifact (Slice 105).

    Builds the deterministic, sanitized, advisory rubric score
    (:func:`pipeline.guide_quality_rubric_score.build_guide_quality_rubric_score`)
    by combining only already-written sibling JSON artifacts. It copies no strings
    out of those artifacts: only known counts and closed status tokens influence
    closed-axis scores. Semantic axes that need human judgment remain unknown.

    Same advisory contract as the other guide-quality siblings:

      * It never rewrites, regenerates, rejects, changes job status, blocks render
        or export, or fails the job. ``blocking`` is always ``False``.
      * It calls no LLM/provider/model/cloud service, inspects no PDF/image/OCR,
        reads no source documents, and reconstructs no table.
      * Missing/unreadable input artifacts degrade to unknown axes and closed
        warnings.
      * Any unexpected error degrades to a small skipped artifact with no raw
        exception string.

    The artifact is reached only by its exact filename (not added to generic
    artifact UI rows or export selectors).
    """
    artifact_path = job.guide_quality_rubric_score_json
    try:
        from pipeline.guide_quality_prompt_contract import infer_comprehensive
        from pipeline.guide_quality_rubric_score import build_guide_quality_rubric_score

        try:
            manifest = job.read_manifest()
        except Exception:
            manifest = {}
        comprehensive = infer_comprehensive(
            manifest.get("output_depth"),
            manifest.get("generator_preset"),
            manifest.get("prompt_name"),
            manifest.get("mode"),
        )

        score = build_guide_quality_rubric_score(
            qa_gate=_read_json_artifact(job.guide_quality_qa_gate_json),
            contract_lint=_read_json_artifact(job.guide_quality_contract_lint_json),
            guide_quality_report_v2=_read_json_artifact(job.guide_quality_report_v2_json),
            source_coverage_report=_read_json_artifact(job.source_coverage_report_json),
            math_verification=_read_json_artifact(job.math_verification_json),
            validation=_read_json_artifact(job.logs_dir / "validation.json"),
            visual_inclusion_plan=_read_json_artifact(job.visual_inclusion_plan_json),
            table_candidates_manifest=_read_json_artifact(job.table_candidates_manifest_json),
            table_reconstruction_policy=_read_json_artifact(job.table_reconstruction_policy_json),
            comprehensive=comprehensive,
        )
        job.save_text(artifact_path, json.dumps(score, indent=2) + "\n")
    except Exception:  # never let the rubric score break a job
        try:
            payload = {
                "version": 1,
                "kind": "guide_quality_rubric_score",
                "status": "skipped",
                "blocking": False,
                "summary": {
                    "score_total": 0,
                    "score_possible": 0,
                    "known_axis_count": 0,
                    "unknown_axis_count": 0,
                    "warning_axis_count": 0,
                    "rubric_axis_count": 0,
                },
                "axes": [],
                "warnings": ["malformed_input_degraded"],
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise


def _read_job_json_artifact(job: Job, attr: str) -> dict | None:
    """Read a safe sibling JSON artifact dict by Job path attribute; never raise.

    Returns ``None`` when the attribute is absent, the file is missing, the JSON
    is malformed, or the top-level value is not a dict. Read-only; touches only an
    exact-name artifact the job already produced.
    """
    path = getattr(job, attr, None)
    if path is None:
        return None
    try:
        artifact_path = Path(path)
        if not artifact_path.exists():
            return None
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_quality_safety_unified_qa(job: Job) -> None:
    """Persist ``quality_safety_unified_qa.json`` as an advisory-only job artifact."""
    artifact_path = job.quality_safety_unified_qa_json
    try:
        from pipeline.quality_safety_job_artifact import (
            build_quality_safety_job_artifact_payload,
            read_quality_safety_numeric_extraction_records,
            read_quality_safety_safe_numeric_candidates,
            read_quality_safety_structured_numeric_candidates,
        )

        try:
            clean_markdown = job.clean_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            clean_markdown = None

        artifact_parent = Path(job.quality_safety_unified_qa_json).parent

        # Slice 126: optionally consume a safe numeric extraction records sidecar
        # if a future numeric extractor has already dropped it next to the
        # artifact (read-only; never created here). Absent today, so the numeric
        # leg degrades honestly to component_missing/skipped.
        numeric_extraction_records = read_quality_safety_numeric_extraction_records(
            artifact_parent
        )

        # Slice 130: optionally consume a safe numeric candidate sidecar (read-only;
        # never created here). When present (and no explicit numeric records sidecar
        # exists) its sanitized candidates feed the Slice 129 safe numeric extractor,
        # whose records drive the same recompute leg. Absent today, so the safe leg
        # degrades honestly to skipped. No OCR/table/source parsing; no clean.md
        # numeric read; no job-folder scan; numbers are never fabricated from
        # structural coverage.
        safe_numeric_candidates = read_quality_safety_safe_numeric_candidates(
            artifact_parent
        )

        # Slice 134: optionally consume a future structured numeric candidate
        # sidecar (read-only; never created here). It feeds only adapter -> safe
        # extractor when explicit records and safe candidates are both absent.
        # No OCR/table/source parsing; no clean.md numeric read; no job-folder
        # scan; numeric facts are never fabricated from structural coverage.
        structured_numeric_candidates = read_quality_safety_structured_numeric_candidates(
            artifact_parent
        )

        # Slice 122: feed the advisory structural extraction-coverage leg from
        # already-produced, already-sanitized sibling JSON artifacts (read-only).
        # This is advisory transparency only — it never feeds the concept/fact
        # producer, never becomes numeric recompute evidence, and never upgrades
        # shippable / safety_floor_green.
        payload = build_quality_safety_job_artifact_payload(
            candidate_markdown=clean_markdown,
            numeric_extraction_records=numeric_extraction_records,
            safe_numeric_candidates=safe_numeric_candidates,
            structured_numeric_candidates=structured_numeric_candidates,
            source_coverage_report=_read_job_json_artifact(job, "source_coverage_report_json"),
            extraction_metadata=_read_job_json_artifact(job, "extraction_metadata_json"),
            visual_inclusion_plan=_read_job_json_artifact(job, "visual_inclusion_plan_json"),
            table_candidates_manifest=_read_job_json_artifact(job, "table_candidates_manifest_json"),
            table_reconstruction_policy=_read_job_json_artifact(job, "table_reconstruction_policy_json"),
        )
        job.save_text(artifact_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except Exception:  # never let the advisory artifact break a job
        try:
            from pipeline.quality_safety_job_artifact import (
                ARTIFACT_NAME,
                KIND,
                SOURCE,
                VERSION,
            )

            payload = {
                "version": VERSION,
                "kind": KIND,
                "artifact_name": ARTIFACT_NAME,
                "advisory": True,
                "source": SOURCE,
                "status": "skipped",
                "shippable": False,
                "safety_floor_green": False,
                "component_statuses": {
                    "layer1": "unknown",
                    "recompute": "unknown",
                    "canonical": "skipped",
                    "leak": "unknown",
                },
                "deterministic_axes_0_5": {
                    "accuracy": None,
                    "coverage": None,
                    "solved_problem": None,
                    "clarity": None,
                },
                "summary": {
                    "blocking_failure_count": 0,
                    "quality_safety_warning_count": 0,
                    "component_missing_count": 4,
                    "deterministic_axis_count": 0,
                    "job_artifact_warning_count": 1,
                },
                "blocking_failures": [],
                "warnings": ["artifact_write_failed"],
                "extraction_coverage_status": "skipped",
                "extraction_coverage_summary": {
                    "source_count": 0,
                    "page_count": 0,
                    "selected_page_count": None,
                    "visual_count": 0,
                    "table_count": 0,
                    "coverage_item_count": 0,
                    "numeric_observation_count": 0,
                },
                "extraction_coverage_bundle": {
                    "version": 1,
                    "kind": "quality_safety_extraction_coverage_bundle",
                    "status": "skipped",
                    "source_quality": "unknown",
                    "summary": {
                        "source_count": 0,
                        "page_count": 0,
                        "selected_page_count": None,
                        "visual_count": 0,
                        "table_count": 0,
                        "coverage_item_count": 0,
                        "numeric_observation_count": 0,
                    },
                    "coverage_records": [],
                    "numeric_observations": [],
                    "warnings": ["component_missing"],
                },
                "numeric_extraction_status": "skipped",
                "numeric_extraction_summary": {
                    "record_count": 0,
                    "numeric_fact_count": 0,
                    "computation_record_count": 0,
                    "supported_method_count": 0,
                    "unsupported_method_count": 0,
                },
                "numeric_extraction_warnings": ["component_missing"],
                "numeric_extraction_bundle": {
                    "version": 1,
                    "kind": "quality_safety_numeric_extraction_bundle",
                    "status": "skipped",
                    "source_quality": "unknown",
                    "summary": {
                        "record_count": 0,
                        "numeric_fact_count": 0,
                        "computation_record_count": 0,
                        "bare_numeric_observation_count": 0,
                        "supported_method_count": 0,
                        "unsupported_method_count": 0,
                    },
                    "numeric_records": [],
                    "warnings": ["component_missing"],
                },
                "structured_numeric_candidate_adapter_status": "skipped",
                "structured_numeric_candidate_adapter_summary": {
                    "input_candidate_count": 0,
                    "output_candidate_count": 0,
                    "supported_method_count": 0,
                    "unsupported_method_count": 0,
                    "dropped_candidate_count": 0,
                },
                "structured_numeric_candidate_adapter_warnings": [
                    "structured_numeric_candidates_missing"
                ],
                "safe_numeric_extractor_status": "skipped",
                "safe_numeric_extractor_summary": {
                    "candidate_count": 0,
                    "record_count": 0,
                    "supported_method_count": 0,
                    "unsupported_method_count": 0,
                    "dropped_candidate_count": 0,
                },
                "safe_numeric_extractor_warnings": [],
                "quality_safety_unified_qa": {
                    "version": 1,
                    "kind": "quality_safety_unified_qa",
                    "status": "skipped",
                    "shippable": False,
                    "safety_floor_green": False,
                    "blocking": False,
                    "summary": {
                        "blocking_failure_count": 0,
                        "warning_count": 0,
                        "layer1_blocking_failure_count": 0,
                        "numeric_blocking_failure_count": 0,
                        "leak_blocking_failure_count": 0,
                        "coverage_warning_count": 0,
                        "mock_question_warning_count": 0,
                        "verified_recompute_count": 0,
                        "verified_canonical_count": 0,
                        "failed_recompute_count": 0,
                        "failed_canonical_count": 0,
                        "unverified_fact_count": 0,
                        "unknown_context_leak_count": 0,
                        "deterministic_axis_count": 0,
                    },
                    "deterministic_axes_0_5": {
                        "accuracy": None,
                        "coverage": None,
                        "solved_problem": None,
                        "clarity": None,
                    },
                    "component_statuses": {
                        "layer1": "unknown",
                        "recompute": "unknown",
                        "canonical": "skipped",
                        "leak": "unknown",
                    },
                    "component_summaries": {},
                    "blocking_failures": [],
                    "warnings": [],
                },
            }
            job.save_text(artifact_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        except Exception:
            pass  # writing the degraded artifact must itself never raise


def _build_missing_material_context_for_report(
    visual_inclusion_plan: dict | None,
    table_candidates_manifest: dict | None,
    table_reconstruction_policy: dict | None,
) -> dict | None:
    """Rebuild the sanitized Slice 94 missing-material context (or ``None``)."""
    try:
        from pipeline.missing_material_explainer import (
            build_missing_material_explainer_context,
        )
        from pipeline.visual_markdown_insertion import is_full_visual_insertion_enabled

        context = build_missing_material_explainer_context(
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            full_visual_insertion_enabled=is_full_visual_insertion_enabled(),
        )
        return context if isinstance(context, dict) else None
    except Exception:
        return None


def _build_coverage_aware_context_for_report(
    source_coverage_report: dict | None,
    visual_inclusion_plan: dict | None,
    table_candidates_manifest: dict | None,
    table_reconstruction_policy: dict | None,
    missing_material_context: dict | None,
) -> dict | None:
    """Rebuild the sanitized Slice 95 coverage-aware context (or ``None``)."""
    try:
        from pipeline.coverage_aware_prompt_context import (
            build_coverage_aware_prompt_context,
        )
        from pipeline.visual_markdown_insertion import is_full_visual_insertion_enabled

        context = build_coverage_aware_prompt_context(
            source_coverage_report=source_coverage_report,
            visual_inclusion_plan=visual_inclusion_plan,
            table_candidates_manifest=table_candidates_manifest,
            table_reconstruction_policy=table_reconstruction_policy,
            missing_material_context=missing_material_context,
            full_visual_insertion_enabled=is_full_visual_insertion_enabled(),
        )
        return context if isinstance(context, dict) else None
    except Exception:
        return None
        # Log only the exception TYPE - never its message/args, which could echo
        # guide content or a path - so the artifact and logs stay clean.
        print(
            f"Guide lint skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )


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
