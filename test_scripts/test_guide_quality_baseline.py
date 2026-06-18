#!/usr/bin/env python3
"""Focused tests for the measured guide-quality baseline aggregator (Slice 149).

Run with:

    python test_scripts/test_guide_quality_baseline.py

The baseline aggregator (`pipeline/guide_quality_baseline.py`) reuses the
existing wired artifacts (math verification, guide-quality contract lint, QA
gate, report v2, source coverage, rubric) and a committed closed golden spec to
emit a closed aggregate baseline record. It is a measurement/diff harness, not a
new evaluator: it reruns none of those checks, reads no PDFs/guides/clean.md,
and calls no provider/model/cloud/local LLM. It copies only known integer
counts, booleans, and closed status tokens out of its inputs — never an excerpt,
heading, formula, value, table/caption/OCR text, filename, path, or raw artifact
body — so hostile canaries cannot survive into the closed record. Synthetic
artifact JSON in temp dirs only; nothing is written to the repo.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|[A-Za-z]:\\\\)")

CANARY_PATH = "/home/operator/private_iris_deck.pdf"
CANARY_KEY = "Bearer sk-secret-aaaaaaaaaaaaaaaaaaaa"
CANARY_TEXT = "the iris softmax probability for setosa equals 0.97"

REQUIRED_FAMILIES = (
    "reasoning_leak_status",
    "numeric_math_status",
    "guide_quality_qa_gate_status",
    "source_coverage_status",
    "structure_contract_status",
    "reference_relative_completeness_status",
    "figure_handling_status",
    "artifact_existence_status",
)


def check(label: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


# --- imports under test (kept after the harness counters) -------------------
from pipeline import guide_quality_baseline as gqb  # noqa: E402


# --- synthetic artifact builders --------------------------------------------


def _write(directory: Path, name: str, payload: Any) -> None:
    (directory / name).write_text(
        payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
    )


def _good_contract_lint(leak: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "guide_quality_report",
        "status": "completed",
        "summary": {
            "reasoning_leak_count": leak,
            "required_section_count": 4,
            "required_section_present_count": 4,
            "warning_count": 0,
            "source_name": CANARY_PATH,  # unread field carrying a canary
        },
        "checks": [{"instruction": CANARY_TEXT}],
    }


def _good_qa_gate(status: str = "passed", warnings: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "guide_quality_gate",
        "status": status,
        "summary": {"check_count": 6, "passed_count": 6 - warnings, "warning_count": warnings, "unknown_count": 0},
    }


def _math(total: int = 5, ok: int = 5, mismatch: int = 0, unparseable: int = 0) -> dict:
    return {
        "version": 1,
        "source_name": CANARY_PATH,
        "summary": {"total": total, "ok": ok, "mismatch": mismatch, "unparseable": unparseable},
        "claims": [{"text": CANARY_TEXT, "claimed": CANARY_KEY}],
    }


def _source_coverage(status: str = "complete") -> dict:
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "status": status,
        "summary": {"source_count": 1, "complete_source_count": 1, "visual_candidate_pages": 2},
    }


def _all_clean(directory: Path) -> None:
    _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
    _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
    _write(directory, "math_verification.json", _math())
    _write(directory, "source_coverage_report.json", _source_coverage())


# --- golden spec ------------------------------------------------------------


def _golden_spec() -> dict:
    return {
        "version": 1,
        "kind": "guide_quality_baseline_golden_spec",
        "fixture_id": "nn_iris_local_golden_spec",
        "fixture_mode": "local_gitignored_source",
        "source_material_committed": False,
        "generated_guide_committed": False,
        "required_concepts": ["neural_network_forward_pass", "softmax_output"],
        "key_facts": ["softmax_outputs_probabilities"],
        "known_numbers": [],
        "must_not_claim": ["unsupported_exact_accuracy_claim"],
        "expected_sections": ["concept_overview", "worked_example"],
        "expected_figures_or_diagrams": [
            {"id": "nn_architecture_diagram", "expected_status": "expected_or_explained_missing"}
        ],
        "warnings": ["source_material_local_gitignored"],
    }


# --- tests ------------------------------------------------------------------


def test_golden_spec_loader_accepts_closed_spec() -> None:
    spec = gqb.normalize_guide_quality_baseline_golden_spec(_golden_spec())
    check("golden spec valid", spec["valid"] is True)
    check("golden spec fixture id", spec["fixture_id"] == "nn_iris_local_golden_spec")
    check("golden concepts retained", "neural_network_forward_pass" in spec["required_concepts"])
    check("golden figures retained", spec["expected_figures_or_diagrams"][0]["id"] == "nn_architecture_diagram")


def test_golden_spec_strips_unsafe_path_like_strings() -> None:
    data = _golden_spec()
    data["required_concepts"] = ["valid_concept", CANARY_PATH, "/etc/passwd", "data:text/plain;base64,AAA"]
    data["key_facts"] = ["softmax_outputs_probabilities", "leaked.pdf"]
    spec = gqb.normalize_guide_quality_baseline_golden_spec(data)
    serialized = json.dumps(spec)
    check("unsafe path stripped from concepts", CANARY_PATH not in serialized)
    check("etc passwd stripped", "/etc/passwd" not in serialized)
    check("data uri stripped", "data:text/plain" not in serialized)
    check("pdf-like label stripped", "leaked.pdf" not in serialized)
    check("valid concept retained", "valid_concept" in spec["required_concepts"])
    check("entries-dropped warning recorded", any("entries_dropped" in w for w in spec["normalization_warnings"]))


def test_golden_spec_rejects_non_mapping() -> None:
    spec = gqb.normalize_guide_quality_baseline_golden_spec(["not", "a", "dict"])
    check("non-mapping invalid", spec["valid"] is False)
    check("non-mapping warning", "golden_spec_not_a_mapping" in spec["normalization_warnings"])


def test_collector_reads_exact_name_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        check("contract lint present", arts["guide_quality_contract_lint"]["presence"] == "present")
        check("qa gate present", arts["guide_quality_qa_gate"]["presence"] == "present")
        check("math present", arts["math_verification"]["presence"] == "present")
        check("source coverage present", arts["source_coverage_report"]["presence"] == "present")
        check(
            "contract lint leak count extracted",
            arts["guide_quality_contract_lint"]["counts"].get("reasoning_leak_count") == 0,
        )
        check("math total extracted", arts["math_verification"]["counts"].get("total") == 5)


def test_collector_does_not_return_dir_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        serialized = json.dumps(arts)
        check("collector hides dir path", str(directory) not in serialized)
        check("collector hides no path marker", not PATHLIKE.search(serialized))


def test_missing_artifacts_produce_missing_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        # only contract lint present; rest missing
        _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        check("present one", arts["guide_quality_contract_lint"]["presence"] == "present")
        check("missing math", arts["math_verification"]["presence"] == "missing")
        check("missing qa gate", arts["guide_quality_qa_gate"]["presence"] == "missing")
        check("missing optional rubric", arts["guide_quality_rubric_score"]["presence"] == "missing")


def test_malformed_artifacts_produce_malformed_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "math_verification.json", "{not valid json")
        _write(directory, "guide_quality_qa_gate.json", "[1, 2, 3]")  # valid json, wrong shape (list)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        check("malformed math", arts["math_verification"]["presence"] == "malformed")
        check("non-dict qa gate malformed", arts["guide_quality_qa_gate"]["presence"] == "malformed")


def test_record_includes_all_metric_families() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        for family in REQUIRED_FAMILIES:
            check(f"metric family present: {family}", family in record["metrics"])
        check("metric families match module list", tuple(record["metrics"].keys()) == REQUIRED_FAMILIES)
        check("record kind", record["kind"] == "guide_quality_measured_baseline_record")
        check("local run defaults not_run", record["local_operator_run"] == "not_run")


def test_reasoning_leak_first_class_from_contract_lint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        metric = record["metrics"]["reasoning_leak_status"]
        check("leak pass when zero", metric["status"] == "pass")
        check("leak source contract lint", metric["source"] == "guide_quality_contract_lint")


def test_reasoning_leak_fails_when_leak_present() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "guide_quality_contract_lint.json", _good_contract_lint(leak=3))
        _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
        _write(directory, "math_verification.json", _math())
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check("leak fail when present", record["metrics"]["reasoning_leak_status"]["status"] == "fail")
        check("overall failed on leak", record["status"] == "failed")


def test_reasoning_leak_falls_back_to_qa_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        # No contract lint; QA gate carries the signal.
        _write(directory, "guide_quality_qa_gate.json", _good_qa_gate(status="passed", warnings=0))
        _write(directory, "math_verification.json", _math())
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        metric = record["metrics"]["reasoning_leak_status"]
        check("leak fallback source qa gate", metric["source"] == "guide_quality_qa_gate")
        check("leak fallback pass", metric["status"] == "pass")


def test_numeric_math_from_math_verification() -> None:
    cases = [
        (_math(total=5, ok=5), "pass"),
        (_math(total=5, ok=4, mismatch=1), "fail"),
        (_math(total=5, ok=4, unparseable=1), "warning"),
        (_math(total=0, ok=0), "not_observed"),
    ]
    for math_payload, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
            _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
            _write(directory, "math_verification.json", math_payload)
            arts = gqb.collect_guide_quality_baseline_artifacts(directory)
            record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
            check(f"numeric status {expected}", record["metrics"]["numeric_math_status"]["status"] == expected)
    # known_numbers empty -> spec-relative numeric scoring deferred via warning
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check(
            "numeric spec-relative deferred warning",
            "numeric_spec_relative_scoring_needs_future_metric" in record["warnings"],
        )


def test_qa_gate_status_derivation() -> None:
    for gate_status, expected in (("passed", "pass"), ("warning", "warning"), ("partial", "warning"), ("skipped", "not_observed")):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
            _write(directory, "guide_quality_qa_gate.json", _good_qa_gate(status=gate_status, warnings=1 if gate_status == "warning" else 0))
            _write(directory, "math_verification.json", _math())
            arts = gqb.collect_guide_quality_baseline_artifacts(directory)
            record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
            check(f"qa gate status {expected}", record["metrics"]["guide_quality_qa_gate_status"]["status"] == expected)


def test_source_coverage_status_derivation() -> None:
    for cov_status, expected in (("complete", "pass"), ("partial", "warning"), ("unreadable", "fail"), ("skipped", "not_observed")):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _all_clean(directory)
            _write(directory, "source_coverage_report.json", _source_coverage(status=cov_status))
            arts = gqb.collect_guide_quality_baseline_artifacts(directory)
            record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
            check(f"source coverage {expected}", record["metrics"]["source_coverage_status"]["status"] == expected)
    # missing coverage -> not_available
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
        _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
        _write(directory, "math_verification.json", _math())
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check("source coverage missing -> not_available", record["metrics"]["source_coverage_status"]["status"] == "not_available")


def test_structure_status_from_contract_lint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        lint = _good_contract_lint()
        lint["summary"]["required_section_present_count"] = 2  # < required 4
        _write(directory, "guide_quality_contract_lint.json", lint)
        _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
        _write(directory, "math_verification.json", _math())
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check("structure warning when sections missing", record["metrics"]["structure_contract_status"]["status"] == "warning")


def test_reference_relative_completeness_needs_future_metric() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        metric = record["metrics"]["reference_relative_completeness_status"]
        check("reference completeness deferred", metric["status"] == "needs_future_metric")
        check("reference completeness source golden", metric["source"] == "golden_spec")


def test_figure_handling_needs_future_metric() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        metric = record["metrics"]["figure_handling_status"]
        check("figure handling deferred", metric["status"] == "needs_future_metric")


def test_artifact_existence_status() -> None:
    # all required present -> pass
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check("artifact existence pass", record["metrics"]["artifact_existence_status"]["status"] == "pass")
    # some required missing -> warning + overall partial
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
        _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check("artifact existence warning", record["metrics"]["artifact_existence_status"]["status"] == "warning")
        check("overall partial when required missing", record["status"] == "partial")
    # all required missing -> fail + overall skipped
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        check("artifact existence fail", record["metrics"]["artifact_existence_status"]["status"] == "fail")
        check("overall skipped when none present", record["status"] == "skipped")


def test_trend_comparison() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        current = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)

    check("no previous", gqb.compare_guide_quality_baseline_records(current, None)["status"] == "no_previous")

    worse = json.loads(json.dumps(current))
    worse["metrics"]["reasoning_leak_status"] = {"status": "fail", "source": "guide_quality_contract_lint"}
    improved = gqb.compare_guide_quality_baseline_records(current, worse)
    check("improved vs worse prior", improved["status"] == "improved")
    check("improved count", improved["improved_metric_count"] == 1)

    better = json.loads(json.dumps(current))
    # Make every currently-pass metric still pass but flip one to fail in current copy.
    regressed_current = json.loads(json.dumps(current))
    regressed_current["metrics"]["numeric_math_status"] = {"status": "fail", "source": "math_verification"}
    regressed = gqb.compare_guide_quality_baseline_records(regressed_current, better)
    check("regressed vs better prior", regressed["status"] == "regressed")

    unchanged = gqb.compare_guide_quality_baseline_records(current, json.loads(json.dumps(current)))
    check("unchanged vs identical", unchanged["status"] == "unchanged")


def test_deterministic_serialization() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record_a = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        record_b = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        s_a = gqb.serialize_guide_quality_baseline_record(record_a)
        s_b = gqb.serialize_guide_quality_baseline_record(record_b)
        check("deterministic serialization", s_a == s_b)
        check("serialization sorted", gqb.serialize_guide_quality_baseline_record({"b": 1, "a": 2}) == '{"a":2,"b":1}')


def test_no_forbidden_canary_survives() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        arts = gqb.collect_guide_quality_baseline_artifacts(directory)
        record = gqb.build_guide_quality_baseline_record(_golden_spec(), arts)
        serialized = gqb.serialize_guide_quality_baseline_record(record)
        check("path canary stripped", CANARY_PATH not in serialized)
        check("key canary stripped", CANARY_KEY not in serialized)
        check("text canary stripped", CANARY_TEXT not in serialized)
        check("no keylike in record", not KEYLIKE.search(serialized))
        check("no pathlike in record", not PATHLIKE.search(serialized))
        # Collector output must also be content-free.
        coll = json.dumps(arts)
        check("path canary not in collector", CANARY_PATH not in coll)
        check("text canary not in collector", CANARY_TEXT not in coll)


def test_no_files_written_outside_temp() -> None:
    # Build a record without any directory at all; nothing should be written.
    record = gqb.build_guide_quality_baseline_record(_golden_spec(), {})
    check("no-dir build skipped status", record["status"] == "skipped")
    # Collector with a non-existent dir is tolerated and writes nothing.
    arts = gqb.collect_guide_quality_baseline_artifacts("/nonexistent/path/should/not/exist")
    check("nonexistent dir -> all missing", all(v["presence"] == "missing" for v in arts.values()))


def _load_validator():
    sys.path.insert(0, str(REPO / "test_scripts"))
    import validate_guide_quality_baseline_harness as v  # noqa: WPS433

    return v


def _temp_golden_spec(directory: Path) -> Path:
    spec_path = directory / "golden_spec.json"
    spec_path.write_text(json.dumps(_golden_spec()), encoding="utf-8")
    return spec_path


def test_local_mode_accepts_temp_dir_and_hides_path() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        spec_path = _temp_golden_spec(directory)
        summary = v.run_local_baseline(spec_path, directory, "app_run_synthetic")
        rendered = json.dumps(summary, sort_keys=True)
        check("local mode harness ok", summary["baseline_harness_status"] == "ok")
        check("local mode run flag closed", summary["local_operator_baseline_run"] == "closed_summary_only")
        check("local mode run label preserved", summary["run_label"] == "app_run_synthetic")
        check("local mode validation id", summary["validation_id"] == "guide_quality_baseline_local_operator_run")
        check("local mode hides temp dir path", str(directory) not in rendered)
        check("local mode hides spec path", str(spec_path) not in rendered)
        check("local mode no pathlike", not PATHLIKE.search(rendered))
        # First-class headline metric is present as a flat closed status.
        check("local mode reasoning_leak first-class", summary["reasoning_leak_status"] == "pass")
        for family in REQUIRED_FAMILIES:
            check(f"local mode flat metric present: {family}", family in summary)


def test_local_mode_does_not_leak_raw_artifact_body_or_canary() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        spec_path = _temp_golden_spec(directory)
        summary = v.run_local_baseline(spec_path, directory, "app_run_canary")
        rendered = json.dumps(summary, sort_keys=True)
        check("local mode no path canary", CANARY_PATH not in rendered)
        check("local mode no key canary", CANARY_KEY not in rendered)
        check("local mode no text canary", CANARY_TEXT not in rendered)
        check("local mode no keylike", not KEYLIKE.search(rendered))


def test_local_mode_missing_optional_is_closed_warning_not_crash() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        # Required present, all optional missing.
        _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
        _write(directory, "guide_quality_qa_gate.json", _good_qa_gate())
        _write(directory, "math_verification.json", _math())
        spec_path = _temp_golden_spec(directory)
        summary = v.run_local_baseline(spec_path, directory, "app_run_opt_missing")
        check("local mode optional-missing stays ok", summary["baseline_harness_status"] == "ok")
        check("local mode optional-missing has source_coverage status", summary["source_coverage_status"] == "not_available")
        check("local mode optional-missing baseline not crashed", summary["baseline_status"] in {"ok", "warning", "partial", "failed", "skipped"})


def test_local_mode_missing_core_is_closed_status_not_exception() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        # Empty dir: no core artifacts at all.
        spec_path = _temp_golden_spec(directory)
        summary = v.run_local_baseline(spec_path, directory, "app_run_empty")
        check("local mode empty dir harness ok", summary["baseline_harness_status"] == "ok")
        check("local mode empty dir baseline skipped", summary["baseline_status"] == "skipped")
        check("local mode empty dir artifact_existence fail", summary["artifact_existence_status"] == "fail")


def test_local_mode_partial_core_is_closed_partial() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        # Only one core artifact present.
        _write(directory, "guide_quality_contract_lint.json", _good_contract_lint())
        spec_path = _temp_golden_spec(directory)
        summary = v.run_local_baseline(spec_path, directory, "app_run_partial")
        check("local mode partial harness ok", summary["baseline_harness_status"] == "ok")
        check("local mode partial baseline partial", summary["baseline_status"] == "partial")
        check("local mode partial artifact_existence warning", summary["artifact_existence_status"] == "warning")


def test_local_mode_harness_error_on_bad_spec_and_missing_dir() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        # Unreadable golden spec -> harness error.
        bad = v.run_local_baseline(directory / "does_not_exist.json", directory, "app_run_badspec")
        check("local mode bad spec is error", bad["baseline_harness_status"] == "error")
        check("local mode bad spec reason", bad.get("error") == "golden_spec_unreadable")
        # Missing artifact dir -> harness error.
        spec_path = _temp_golden_spec(directory)
        missing = v.run_local_baseline(spec_path, directory / "no_such_dir", "app_run_nodir")
        check("local mode missing dir is error", missing["baseline_harness_status"] == "error")
        check("local mode missing dir reason", missing.get("error") == "artifact_dir_not_found")


def test_local_mode_run_label_sanitized() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        spec_path = _temp_golden_spec(directory)
        # A path-like label must be rejected, not echoed.
        summary = v.run_local_baseline(spec_path, directory, "/home/operator/secret_run")
        check("local mode rejects path-like label", summary["run_label"] == "local")
        check("local mode sanitized label no path", "/home/" not in json.dumps(summary))


def test_local_mode_deterministic() -> None:
    v = _load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _all_clean(directory)
        spec_path = _temp_golden_spec(directory)
        a = v.run_local_baseline(spec_path, directory, "app_run_det")
        b = v.run_local_baseline(spec_path, directory, "app_run_det")
        check("local mode deterministic", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))


def test_module_is_stdlib_only() -> None:
    source = (REPO / "pipeline" / "guide_quality_baseline.py").read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    allowed_modules = {"__future__", "json", "os", "typing"}
    for line in import_lines:
        # Each import must resolve to a stdlib module on the allowed list.
        module = line.split()[1].split(".")[0]
        check(f"import is stdlib-only: {line}", module in allowed_modules)
    forbidden_substrings = (
        "fastapi",
        "requests",
        "httpx",
        "anthropic",
        "openai",
        "run_markdown_job",
        "job_manager",
        "subprocess",
    )
    for token in forbidden_substrings:
        in_imports = any(token in line for line in import_lines)
        check(f"no forbidden import: {token}", not in_imports)


def main() -> int:
    print("Guide quality baseline aggregator tests (Slice 149)\n")
    test_golden_spec_loader_accepts_closed_spec()
    test_golden_spec_strips_unsafe_path_like_strings()
    test_golden_spec_rejects_non_mapping()
    test_collector_reads_exact_name_artifacts()
    test_collector_does_not_return_dir_path()
    test_missing_artifacts_produce_missing_status()
    test_malformed_artifacts_produce_malformed_status()
    test_record_includes_all_metric_families()
    test_reasoning_leak_first_class_from_contract_lint()
    test_reasoning_leak_fails_when_leak_present()
    test_reasoning_leak_falls_back_to_qa_gate()
    test_numeric_math_from_math_verification()
    test_qa_gate_status_derivation()
    test_source_coverage_status_derivation()
    test_structure_status_from_contract_lint()
    test_reference_relative_completeness_needs_future_metric()
    test_figure_handling_needs_future_metric()
    test_artifact_existence_status()
    test_trend_comparison()
    test_deterministic_serialization()
    test_no_forbidden_canary_survives()
    test_no_files_written_outside_temp()
    test_local_mode_accepts_temp_dir_and_hides_path()
    test_local_mode_does_not_leak_raw_artifact_body_or_canary()
    test_local_mode_missing_optional_is_closed_warning_not_crash()
    test_local_mode_missing_core_is_closed_status_not_exception()
    test_local_mode_partial_core_is_closed_partial()
    test_local_mode_harness_error_on_bad_spec_and_missing_dir()
    test_local_mode_run_label_sanitized()
    test_local_mode_deterministic()
    test_module_is_stdlib_only()
    print(f"\nGuide quality baseline tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
