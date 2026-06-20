"""Quality Safety **numeric-target input-existence classifier** (revised Slice 176D).

Prior slices classified *extraction / reconstruction behavior* (174A source-input
bridge, 175A machine-consumability proof, 176A focused table-structure attempt,
176C one-table-family row/cell reconstruction). None of them answered the question
this slice exists to answer:

    For each relevant hard-deck numeric target, does the **source** contain the
    computation **inputs**, or only the **answer / result**?

That distinction decides which targets are worth reconstructing (inputs present →
reconstruct rows/cells into a machine-consumable record) and which must be marked
**unverifiable-from-source** (answer-only → no amount of OCR / region detection
recovers an input that is not there). It exists to stop chasing input tables that
the source does not contain.

This module is a **pure, total, closed-vocabulary classifier**. It consumes closed
per-target *evidence descriptors* (booleans, closed tokens, and small counts that
summarize what already-committed closed slices established) and emits a closed
classification — never raw source / OCR / table / guide text, formulas, raw input
values, paths, filenames, hashes, or byte counts. It reads no files, opens no PDF,
runs no OCR, and reaches no network.

What this slice is **not**: a recoverability audit, a source-input bridge, numeric
plumbing, a prompt/generation slice, a visual-manifest rebuild, a generic table
framework, target-region detection improvement, generation wiring, a Layer-2 judge,
or repair. No Chandra; no cloud OCR. ``judge_ready=false``; ``repair_ready=false``.

Provenance discipline (non-negotiable): a target is only ``computation_input_present``
on the strength of *source-derived* closed evidence (recovered inputs / masked
recompute from recovered inputs / partial recovery). Fixture values, answer strings,
generated-guide candidate values, and hand-authored rows are **never** treated as
input-existence evidence and never enter this module.
"""
from __future__ import annotations

from typing import Any

VERSION = 1
KIND = "quality_safety_numeric_target_input_existence"
ARTIFACT_NAME = "quality_safety_numeric_target_input_existence"

SOURCE_LABEL_DEFAULT = "ensemble"

# ── Closed vocabularies (this module owns everything it emits) ───────────────
STATUSES = frozenset({"completed", "blocked", "skipped"})

TARGET_FAMILIES = frozenset(
    {
        "weighted_gini",
        "total_error",
        "amount_of_say",
        "proximity",
        "weighted_average",
        "other",
    }
)

SOURCE_INPUT_EXISTENCE_STATUSES = frozenset(
    {
        "computation_input_present",
        "answer_output_only",
        "absent_or_not_found",
        "inconclusive",
    }
)

EVIDENCE_BASES = frozenset(
    {
        "reconstructed_answer_matrix",
        "closed_candidate_manifest",
        "closed_region_metadata",
        "existing_recompute_sidecar",
        "existing_fact_sheet",
        "no_closed_evidence",
        "mixed",
    }
)

RECONSTRUCTION_PRIORITIES = frozenset({"high", "medium", "low", "none"})

FUTURE_ACTIONS = frozenset(
    {
        "reconstruct_rows_cells",
        "mark_unverifiable_from_source",
        "inspect_more_closed_evidence",
        "defer",
    }
)

NEXT_STEPS = frozenset(
    {
        "reconstruct_present_input_target",
        "mark_answer_only_targets_unverifiable",
        "pivot_table_reconstruction_to_student_visible_tables",
        "improve_input_existence_evidence",
        "stop_numeric_phase_no_machine_consumable_path",
    }
)

# Closed warning vocabulary (per-target). Only honest, non-leaking signals.
WARNINGS = frozenset(
    {
        "single_target_spot_check_only",
        "answer_matrix_not_input",
        "no_typed_candidate_region",
        "partial_recovery_only",
        "no_closed_evidence",
        "machine_consumable_record_absent",
    }
)


def _tok(value: Any, vocab: frozenset, default: str) -> str:
    """Coerce ``value`` into ``vocab`` or fall back to ``default`` (total)."""
    return value if isinstance(value, str) and value in vocab else default


def _b(value: Any) -> bool:
    return bool(value)


def _i(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if n >= 0 else 0


def classify_target_input_existence(evidence: Any) -> dict[str, Any]:
    """Classify ONE target's source-input existence from a closed evidence descriptor.

    ``evidence`` is a mapping of closed fields (all optional, all closed-vocab /
    bool / small-count) summarizing prior committed closed findings:

      * ``target_id`` / ``target_family``
      * ``parsed_source_input_record_exists`` — a machine-consumable record already
        parsed from extraction output exists (origin ``parsed_from_extraction_output``).
      * ``recompute_inputs_recovered_from_source`` — closed recoverability evidence
        that the per-target computation inputs are present/recovered in the source.
      * ``masked_recompute_from_inputs_passed`` — a masked recompute (answer hidden)
        from those recovered inputs reproduced the fixture within tolerance.
      * ``recovery_partial`` — inputs partially recovered (neither clean present nor
        proven absent).
      * ``reconstructed_grid_is_answer_matrix`` — the only reconstructable grid is the
        answer/output matrix (176C shape), not inputs.
      * ``typed_candidate_region_count`` — typed table-candidate regions seen in the
        closed candidate manifest (0 ⇒ none surfaced).
      * ``input_table_searched_and_absent`` — affirmative closed evidence the input
        table was searched for and is not present.

    Returns a closed per-target record (no raw values).
    """
    ev = evidence if isinstance(evidence, dict) else {}

    target_id = ev.get("target_id") if isinstance(ev.get("target_id"), str) else "unknown_target"
    family = _tok(ev.get("target_family"), TARGET_FAMILIES, "other")

    parsed_record = _b(ev.get("parsed_source_input_record_exists"))
    inputs_recovered = _b(ev.get("recompute_inputs_recovered_from_source"))
    masked_passed = _b(ev.get("masked_recompute_from_inputs_passed"))
    partial = _b(ev.get("recovery_partial"))
    is_answer_matrix = _b(ev.get("reconstructed_grid_is_answer_matrix"))
    typed_regions = _i(ev.get("typed_candidate_region_count"))
    searched_absent = _b(ev.get("input_table_searched_and_absent"))
    manifest_checked = "typed_candidate_region_count" in ev

    warnings: list[str] = []

    # Decision order (most-decisive evidence first). machine_consumable_now is true
    # ONLY when an actual parsed computation-input record already exists.
    if parsed_record:
        status = "computation_input_present"
        basis = "existing_fact_sheet"
        priority = "none"
        future = "defer"
        machine_consumable = True
    elif masked_passed or inputs_recovered:
        # Inputs are present in source (recoverability proven). Not yet parsed into a
        # machine-consumable record → reconstruction is the worthwhile next work.
        status = "computation_input_present"
        basis = "mixed" if is_answer_matrix else "existing_recompute_sidecar"
        priority = "high"
        future = "reconstruct_rows_cells"
        machine_consumable = False
        warnings.append("machine_consumable_record_absent")
        if inputs_recovered and not masked_passed:
            warnings.append("single_target_spot_check_only")
    elif is_answer_matrix:
        # The only reconstructable grid is the answer/output matrix → answer-only.
        status = "answer_output_only"
        basis = "mixed" if manifest_checked else "reconstructed_answer_matrix"
        priority = "none"
        future = "mark_unverifiable_from_source"
        machine_consumable = False
        warnings.append("answer_matrix_not_input")
        if manifest_checked and typed_regions == 0:
            warnings.append("no_typed_candidate_region")
    elif searched_absent:
        status = "absent_or_not_found"
        basis = "closed_candidate_manifest" if manifest_checked else "closed_region_metadata"
        priority = "none"
        future = "mark_unverifiable_from_source"
        machine_consumable = False
        if manifest_checked and typed_regions == 0:
            warnings.append("no_typed_candidate_region")
    elif partial:
        status = "inconclusive"
        basis = "existing_recompute_sidecar"
        priority = "medium"
        future = "inspect_more_closed_evidence"
        machine_consumable = False
        warnings.append("partial_recovery_only")
    else:
        # No positive evidence either way: cannot prove presence OR absence.
        status = "inconclusive"
        basis = "no_closed_evidence"
        priority = "low"
        future = "inspect_more_closed_evidence"
        machine_consumable = False
        warnings.append("no_closed_evidence")
        if manifest_checked and typed_regions == 0:
            warnings.append("no_typed_candidate_region")

    # Closed-vocab filter on warnings (defensive; everything appended is already closed).
    safe_warnings = [w for w in warnings if w in WARNINGS]

    return {
        "target_id": target_id,
        "target_family": family,
        "source_input_existence_status": status,
        "evidence_basis": _tok(basis, EVIDENCE_BASES, "no_closed_evidence"),
        "reconstruction_priority": _tok(priority, RECONSTRUCTION_PRIORITIES, "none"),
        "future_action": _tok(future, FUTURE_ACTIONS, "defer"),
        "machine_consumable_now": bool(machine_consumable),
        "warnings": safe_warnings,
    }


def _decide_next_step(per_target: list[dict[str, Any]]) -> str:
    """Apply the Part 1F decision rule over the classified targets (closed)."""
    statuses = [t["source_input_existence_status"] for t in per_target]
    n = len(statuses) or 1
    present = statuses.count("computation_input_present")
    answer_only = statuses.count("answer_output_only")
    absent = statuses.count("absent_or_not_found")
    inconclusive = statuses.count("inconclusive")

    any_answer_matrix = any("answer_matrix_not_input" in t["warnings"] for t in per_target)

    # A. At least one target has inputs present → reconstruct a present-input target.
    if present >= 1:
        return "reconstruct_present_input_target"
    # E. No present inputs and nothing reconstructable at all → stop the numeric phase.
    if present == 0 and (answer_only + absent) == 0 and inconclusive == n:
        return "improve_input_existence_evidence"
    # C. Answer/result tables reconstructable but inputs mostly absent → pivot to
    #    student-visible table insertion.
    if any_answer_matrix and (answer_only + absent) >= max(1, present + 1):
        return "pivot_table_reconstruction_to_student_visible_tables"
    # B. Proximity and most/all hard-deck targets answer-only/absent → mark unverifiable.
    if (answer_only + absent) >= (n + 1) // 2:
        return "mark_answer_only_targets_unverifiable"
    # D. Evidence too weak to classify.
    if inconclusive >= (n + 1) // 2:
        return "improve_input_existence_evidence"
    return "improve_input_existence_evidence"


def classify_numeric_target_input_existence(
    evidences: Any,
    *,
    source_label: str = SOURCE_LABEL_DEFAULT,
) -> dict[str, Any]:
    """Classify a list of target evidence descriptors → closed summary + per-target.

    Pure and total. Never raises on malformed input (each malformed descriptor
    degrades to an ``inconclusive`` / ``no_closed_evidence`` record).
    """
    items = evidences if isinstance(evidences, list) else []
    per_target = [classify_target_input_existence(ev) for ev in items]

    statuses = [t["source_input_existence_status"] for t in per_target]
    present = statuses.count("computation_input_present")
    answer_only = statuses.count("answer_output_only")
    absent = statuses.count("absent_or_not_found")
    inconclusive = statuses.count("inconclusive")

    reconstruction_candidates = sum(
        1 for t in per_target if t["future_action"] == "reconstruct_rows_cells"
    )
    source_unverifiable = answer_only + absent

    status = "completed" if per_target else "skipped"

    return {
        "version": VERSION,
        "kind": KIND,
        "artifact_name": ARTIFACT_NAME,
        "status": status,
        "source_label": _tok(source_label, frozenset({"ensemble", "nn3"}), "ensemble"),
        "targets_considered_count": len(per_target),
        "computation_input_present_count": present,
        "answer_output_only_count": answer_only,
        "absent_or_not_found_count": absent,
        "inconclusive_count": inconclusive,
        "reconstruction_candidate_count": reconstruction_candidates,
        "source_unverifiable_count": source_unverifiable,
        # Provenance discipline flags — this module never consumes any of these.
        "used_fixture_values": False,
        "used_answer_strings": False,
        "used_generated_guide_text": False,
        "used_hand_authored_rows": False,
        "raw_text_committed": False,
        "raw_values_committed": False,
        "next_step": _decide_next_step(per_target),
        "judge_ready": False,
        "repair_ready": False,
        "per_target": per_target,
    }


# ── Committed closed evidence vector for the Ensemble hard deck ──────────────
# Each entry encodes ONLY closed findings already committed by prior slices
# (closed booleans / tokens / small counts). No raw values, formulas, answer
# strings, fixture values, or guide candidates. Source-slice attribution in
# comments so the classification is auditable against committed history.
#
#  - 173C Ensemble recoverability report: computation_input_present_count=5,
#    computation_input_partial_count=2 (targets_considered=7); high-risk Gini
#    masked-recompute spot-check passed for gini_weight_gt_176 only.
#  - 174A: proximity_4_3 & weighted_weight_impute method-gated → source_input_missing
#    after methods added (no source-derived structured records).
#  - 175A / 176A: no machine-consumable parsed source-input record exists for any
#    target (machine_consumable=0).
#  - 176C: proximity_4_3 source region reconstructs to the ANSWER MATRIX, not inputs;
#    closed candidate manifest surfaced 0 typed regions for it (176D-region probe).
ENSEMBLE_HARD_DECK_EVIDENCE: tuple[dict[str, Any], ...] = (
    {
        "target_id": "gini_chest_pain",
        "target_family": "weighted_gini",
        "recompute_inputs_recovered_from_source": True,
        "masked_recompute_from_inputs_passed": False,
    },
    {
        "target_id": "gini_blocked_arteries",
        "target_family": "weighted_gini",
        "recompute_inputs_recovered_from_source": True,
        "masked_recompute_from_inputs_passed": False,
    },
    {
        "target_id": "gini_weight_gt_176",
        "target_family": "weighted_gini",
        "recompute_inputs_recovered_from_source": True,
        "masked_recompute_from_inputs_passed": True,
    },
    {
        "target_id": "total_error_stump_1",
        "target_family": "total_error",
        "recompute_inputs_recovered_from_source": True,
        "masked_recompute_from_inputs_passed": False,
    },
    {
        "target_id": "amount_of_say_half_ln_7",
        "target_family": "amount_of_say",
        "recompute_inputs_recovered_from_source": True,
        "masked_recompute_from_inputs_passed": False,
    },
    {
        "target_id": "proximity_4_3",
        "target_family": "proximity",
        "reconstructed_grid_is_answer_matrix": True,
        "typed_candidate_region_count": 0,
    },
    {
        "target_id": "weighted_weight_impute",
        "target_family": "weighted_average",
        "recovery_partial": True,
    },
)


def classify_ensemble_hard_deck() -> dict[str, Any]:
    """Run the classifier over the committed Ensemble hard-deck evidence vector."""
    return classify_numeric_target_input_existence(
        list(ENSEMBLE_HARD_DECK_EVIDENCE), source_label="ensemble"
    )


if __name__ == "__main__":  # pragma: no cover - manual closed inspection only
    import json

    print(json.dumps(classify_ensemble_hard_deck(), indent=2))
