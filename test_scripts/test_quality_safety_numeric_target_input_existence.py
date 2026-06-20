"""Focused tests for the numeric-target input-existence classifier (revised 176D).

Synthetic, public-safe descriptors only — no raw source / OCR / table / guide text,
no formulas, no raw values, no fixture values, no answer strings. Verifies the
closed classification branches, the decision rule, totality on malformed input, the
closed-vocab contract, and the committed Ensemble hard-deck classification.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.quality_safety_numeric_target_input_existence import (  # noqa: E402
    ENSEMBLE_HARD_DECK_EVIDENCE,
    EVIDENCE_BASES,
    FUTURE_ACTIONS,
    NEXT_STEPS,
    RECONSTRUCTION_PRIORITIES,
    SOURCE_INPUT_EXISTENCE_STATUSES,
    STATUSES,
    WARNINGS,
    classify_ensemble_hard_deck,
    classify_numeric_target_input_existence,
    classify_target_input_existence,
)

_PASS = 0
_FAIL = 0


def check(label, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        print(f"  FAIL: {label}")


# ── Per-target branch coverage (synthetic public-safe descriptors) ───────────

def test_inputs_recovered_present():
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_gini",
            "target_family": "weighted_gini",
            "recompute_inputs_recovered_from_source": True,
        }
    )
    check("recovered → present", r["source_input_existence_status"] == "computation_input_present")
    check("recovered → reconstruct", r["future_action"] == "reconstruct_rows_cells")
    check("recovered → high priority", r["reconstruction_priority"] == "high")
    check("recovered not yet machine-consumable", r["machine_consumable_now"] is False)
    check("recovered → spot-check warning", "single_target_spot_check_only" in r["warnings"])
    check("recovered → sidecar basis", r["evidence_basis"] == "existing_recompute_sidecar")


def test_masked_passed_present_no_spotcheck_warning():
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_gini_proven",
            "target_family": "weighted_gini",
            "recompute_inputs_recovered_from_source": True,
            "masked_recompute_from_inputs_passed": True,
        }
    )
    check("masked-passed → present", r["source_input_existence_status"] == "computation_input_present")
    check("masked-passed drops spot-check warning", "single_target_spot_check_only" not in r["warnings"])


def test_parsed_record_machine_consumable():
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_done",
            "target_family": "total_error",
            "parsed_source_input_record_exists": True,
        }
    )
    check("parsed record → present", r["source_input_existence_status"] == "computation_input_present")
    check("parsed record → machine_consumable_now", r["machine_consumable_now"] is True)
    check("parsed record → defer", r["future_action"] == "defer")


def test_answer_matrix_only():
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_proximity",
            "target_family": "proximity",
            "reconstructed_grid_is_answer_matrix": True,
            "typed_candidate_region_count": 0,
        }
    )
    check("answer matrix → answer_output_only", r["source_input_existence_status"] == "answer_output_only")
    check("answer matrix → unverifiable", r["future_action"] == "mark_unverifiable_from_source")
    check("answer matrix → none priority", r["reconstruction_priority"] == "none")
    check("answer matrix → not machine-consumable", r["machine_consumable_now"] is False)
    check("answer matrix warning", "answer_matrix_not_input" in r["warnings"])
    check("answer matrix + manifest → mixed basis", r["evidence_basis"] == "mixed")


def test_answer_matrix_overridden_by_recovered_inputs():
    # If inputs are recovered elsewhere, an answer matrix does NOT downgrade to answer-only.
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_mixed",
            "target_family": "proximity",
            "reconstructed_grid_is_answer_matrix": True,
            "recompute_inputs_recovered_from_source": True,
        }
    )
    check("recovered beats answer-matrix", r["source_input_existence_status"] == "computation_input_present")
    check("recovered+matrix → mixed basis", r["evidence_basis"] == "mixed")


def test_searched_absent():
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_absent",
            "target_family": "other",
            "input_table_searched_and_absent": True,
            "typed_candidate_region_count": 0,
        }
    )
    check("searched-absent → absent_or_not_found", r["source_input_existence_status"] == "absent_or_not_found")
    check("absent → unverifiable", r["future_action"] == "mark_unverifiable_from_source")


def test_partial_inconclusive():
    r = classify_target_input_existence(
        {
            "target_id": "synthetic_partial",
            "target_family": "weighted_average",
            "recovery_partial": True,
        }
    )
    check("partial → inconclusive", r["source_input_existence_status"] == "inconclusive")
    check("partial → medium priority", r["reconstruction_priority"] == "medium")
    check("partial → inspect more", r["future_action"] == "inspect_more_closed_evidence")


def test_no_evidence_inconclusive():
    r = classify_target_input_existence({"target_id": "synthetic_blank", "target_family": "other"})
    check("no evidence → inconclusive", r["source_input_existence_status"] == "inconclusive")
    check("no evidence → no_closed_evidence basis", r["evidence_basis"] == "no_closed_evidence")
    check("no evidence → low priority", r["reconstruction_priority"] == "low")


def test_totality_on_malformed():
    for bad in [None, 42, "x", [], {"target_family": "not_a_family"}]:
        r = classify_target_input_existence(bad)
        check(f"malformed {bad!r} does not raise / stays closed",
              r["source_input_existence_status"] in SOURCE_INPUT_EXISTENCE_STATUSES)
        check(f"malformed {bad!r} family closed", r["target_family"] in
              {"weighted_gini", "total_error", "amount_of_say", "proximity", "weighted_average", "other"})


# ── Aggregate + decision rule ────────────────────────────────────────────────

def test_decision_rule_present_wins():
    summary = classify_numeric_target_input_existence(
        [
            {"target_id": "a", "target_family": "weighted_gini", "recompute_inputs_recovered_from_source": True},
            {"target_id": "b", "target_family": "proximity", "reconstructed_grid_is_answer_matrix": True},
        ]
    )
    check("≥1 present → reconstruct_present_input_target",
          summary["next_step"] == "reconstruct_present_input_target")
    check("present count", summary["computation_input_present_count"] == 1)
    check("answer-only count", summary["answer_output_only_count"] == 1)
    check("reconstruction candidate count", summary["reconstruction_candidate_count"] == 1)
    check("source unverifiable count", summary["source_unverifiable_count"] == 1)


def test_decision_rule_all_answer_only():
    summary = classify_numeric_target_input_existence(
        [
            {"target_id": "a", "target_family": "proximity", "reconstructed_grid_is_answer_matrix": True},
            {"target_id": "b", "target_family": "proximity", "input_table_searched_and_absent": True},
        ]
    )
    check("all answer/absent → not reconstruct_present",
          summary["next_step"] != "reconstruct_present_input_target")
    check("all answer/absent → pivot or mark-unverifiable",
          summary["next_step"] in {
              "mark_answer_only_targets_unverifiable",
              "pivot_table_reconstruction_to_student_visible_tables",
          })


def test_decision_rule_all_inconclusive():
    summary = classify_numeric_target_input_existence(
        [
            {"target_id": "a", "target_family": "other"},
            {"target_id": "b", "target_family": "other", "recovery_partial": True},
        ]
    )
    check("all inconclusive → improve evidence",
          summary["next_step"] == "improve_input_existence_evidence")


def test_empty_skipped():
    summary = classify_numeric_target_input_existence([])
    check("empty → skipped", summary["status"] == "skipped")
    check("empty → zero considered", summary["targets_considered_count"] == 0)


def test_provenance_flags_false():
    summary = classify_numeric_target_input_existence(
        [{"target_id": "a", "target_family": "weighted_gini", "recompute_inputs_recovered_from_source": True}]
    )
    for flag in (
        "used_fixture_values",
        "used_answer_strings",
        "used_generated_guide_text",
        "used_hand_authored_rows",
        "raw_text_committed",
        "raw_values_committed",
    ):
        check(f"provenance flag {flag} false", summary[flag] is False)
    check("judge_ready frozen false", summary["judge_ready"] is False)
    check("repair_ready frozen false", summary["repair_ready"] is False)


def test_closed_vocab_contract():
    summary = classify_ensemble_hard_deck()
    check("summary status closed", summary["status"] in STATUSES)
    check("summary next_step closed", summary["next_step"] in NEXT_STEPS)
    for t in summary["per_target"]:
        check("status closed", t["source_input_existence_status"] in SOURCE_INPUT_EXISTENCE_STATUSES)
        check("evidence_basis closed", t["evidence_basis"] in EVIDENCE_BASES)
        check("priority closed", t["reconstruction_priority"] in RECONSTRUCTION_PRIORITIES)
        check("future_action closed", t["future_action"] in FUTURE_ACTIONS)
        check("machine_consumable bool", isinstance(t["machine_consumable_now"], bool))
        for w in t["warnings"]:
            check(f"warning {w} closed", w in WARNINGS)


# ── Committed Ensemble hard-deck classification ──────────────────────────────

def test_ensemble_hard_deck_tallies():
    summary = classify_ensemble_hard_deck()
    check("ensemble source", summary["source_label"] == "ensemble")
    check("ensemble considered=7", summary["targets_considered_count"] == 7)
    check("ensemble fixture target count == 7", len(ENSEMBLE_HARD_DECK_EVIDENCE) == 7)
    check("ensemble present=5", summary["computation_input_present_count"] == 5)
    check("ensemble answer-only=1", summary["answer_output_only_count"] == 1)
    check("ensemble absent=0", summary["absent_or_not_found_count"] == 0)
    check("ensemble inconclusive=1", summary["inconclusive_count"] == 1)
    check("ensemble reconstruction candidates=5", summary["reconstruction_candidate_count"] == 5)
    check("ensemble source unverifiable=1", summary["source_unverifiable_count"] == 1)
    check("ensemble next_step=reconstruct_present_input_target",
          summary["next_step"] == "reconstruct_present_input_target")
    # No target is machine-consumable yet (no parsed source-input record committed).
    check("ensemble none machine-consumable now",
          all(t["machine_consumable_now"] is False for t in summary["per_target"]))


def test_ensemble_per_target_specifics():
    by_id = {t["target_id"]: t for t in classify_ensemble_hard_deck()["per_target"]}
    check("proximity_4_3 answer-only",
          by_id["proximity_4_3"]["source_input_existence_status"] == "answer_output_only")
    check("proximity_4_3 unverifiable",
          by_id["proximity_4_3"]["future_action"] == "mark_unverifiable_from_source")
    check("gini_weight_gt_176 present",
          by_id["gini_weight_gt_176"]["source_input_existence_status"] == "computation_input_present")
    check("gini_weight_gt_176 proven (no spot-check warning)",
          "single_target_spot_check_only" not in by_id["gini_weight_gt_176"]["warnings"])
    check("weighted_weight_impute inconclusive",
          by_id["weighted_weight_impute"]["source_input_existence_status"] == "inconclusive")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    total = _PASS + _FAIL
    print(f"\n{_PASS}/{total} checks passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
