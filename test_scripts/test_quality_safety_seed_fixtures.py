#!/usr/bin/env python3
"""Tests for Slice 109 quality-safety seed fixtures.

The committed fixtures are sanitized synthetic JSON specs only. They are not a
real golden corpus and do not include source decks, reference guides, generated
guides, paths, filenames, evidence quotes, snippets, OCR/table/caption text,
provider payloads, PDFs, images, DOCX, ZIPs, or runtime eval outputs.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO / "test_scripts" / "fixtures" / "quality_safety"
EXPECTED_FIXTURES = (
    "ambiguous_ensemble_synthetic.json",
    "clean_neural_networks_synthetic.json",
)

sys.path.insert(0, str(REPO))

from pipeline.quality_safety_eval_harness import (  # noqa: E402
    build_quality_safety_regression_record,
    load_quality_safety_fixture_spec,
    run_quality_safety_layer1_checks,
)

PASS = 0
FAIL = 0

BINARY_SUFFIXES = {".pdf", ".docx", ".zip", ".png", ".jpg", ".jpeg", ".webp"}
FORBIDDEN_KEYS = {
    "source_deck",
    "claude_reference",
    "source_path",
    "reference_path",
    "file_path",
    "path",
    "filename",
    "evidence_quote",
    "evidence_quotes",
    "raw_evidence_quote",
    "raw_evidence",
    "guide_snippet",
    "source_snippet",
    "snippet",
    "snippets",
    "guide_text",
    "source_text",
    "raw_text",
    "page_text",
    "table_text",
    "ocr_text",
    "raw_ocr",
    "caption",
    "captions",
    "table_rows",
}
FORBIDDEN_KEY_PARTS = ("path", "filename", "quote", "snippet", "ocr", "caption")
HOSTILE_CANARIES = (
    "/home/private/seed-fixture.pdf",
    "C:\\private\\seed-fixture.docx",
    "https://private.invalid/uploaded-quality-spec",
    "Authorization: Bearer sk_qualitysafetyseed1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_SEED_MARKER",
    "TABLE_TEXT_PRIVATE_SEED_MARKER",
    "CAPTION_PRIVATE_SEED_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_SEED_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MARKER",
)
LEAK_PATTERNS = (
    re.compile(r"/home/private"),
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"https?://"),
    re.compile(r"Authorization", re.IGNORECASE),
    re.compile(r"Bearer", re.IGNORECASE),
    re.compile(r"sk_qualitysafetyseed"),
    re.compile(r"data:image", re.IGNORECASE),
    re.compile(r"base64", re.IGNORECASE),
    re.compile(r"OCR_PRIVATE_SEED_MARKER"),
    re.compile(r"TABLE_TEXT_PRIVATE_SEED_MARKER"),
    re.compile(r"CAPTION_PRIVATE_SEED_MARKER"),
    re.compile(r"PROVIDER_PAYLOAD_PRIVATE_SEED_MARKER"),
    re.compile(r"UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME"),
    re.compile(r"EVIDENCE_QUOTE_PRIVATE_MARKER"),
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {name}{suffix}")


def raw_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def loaded_fixture(name: str) -> dict[str, Any]:
    return load_quality_safety_fixture_spec(raw_fixture(name))


def seed_fixture_items() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    return [(name, raw_fixture(name), loaded_fixture(name)) for name in EXPECTED_FIXTURES]


def deep_items(node: Any) -> list[tuple[str | None, Any]]:
    found: list[tuple[str | None, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.append((str(key), value))
            found.extend(deep_items(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(deep_items(value))
    return found


def serialized(node: Any) -> str:
    return json.dumps(node, sort_keys=True)


def assert_no_leak(name: str, node: Any) -> None:
    blob = serialized(node)
    found = ""
    for canary in HOSTILE_CANARIES:
        if canary in blob:
            found = canary
            break
    if not found:
        for pattern in LEAK_PATTERNS:
            if pattern.search(blob):
                found = pattern.pattern
                break
    check(f"{name}: no hostile canary", not found, found)


def assert_safe_fixture_fields(name: str, data: dict[str, Any]) -> None:
    bad_keys: list[str] = []
    for key, _value in deep_items(data):
        if key is None:
            continue
        lower = key.lower()
        if lower in FORBIDDEN_KEYS or any(part in lower for part in FORBIDDEN_KEY_PARTS):
            bad_keys.append(key)
    check(f"{name}: no forbidden fixture fields", bad_keys == [], str(bad_keys))


def check_report_blocking_statuses(report: dict[str, Any], expected_ids: set[str]) -> None:
    by_id = {item.get("id"): item.get("status") for item in report.get("checks", []) if isinstance(item, dict)}
    observed = {check_id for check_id, status in by_id.items() if status == "failed"}
    check("failing report closed blocking ids", expected_ids.issubset(set(report.get("blocking_failures", []))), str(report.get("blocking_failures")))
    check("failing report closed failed statuses", expected_ids.issubset(observed), str(by_id))


def clean_candidate() -> str:
    return "\n".join(
        [
            "# Clean Neural Networks Synthetic Candidate",
            "The activation function feeds the forward pass.",
            "The softmax output is used with cross entropy loss.",
            "The training pipeline remains synthetic and deterministic.",
            "synthetic_forward_output: 0.86",
            "synthetic_cross_entropy: 0.56",
            "## Worked Answer",
            "Solution: substitute the synthetic values and finish with 0.86 and 0.56.",
            "## Mock Question 1: Which step uses the activation function?",
            "Answer: the forward pass.",
            "## Mock Question 2: Which output is normalized?",
            "Answer: softmax output.",
            "## Practice Question 3: Which loss is paired with it?",
            "Answer: cross entropy loss.",
        ]
    )


def ambiguous_candidate() -> str:
    return "\n".join(
        [
            "# Ambiguous Ensemble Synthetic Candidate",
            "Voting methods compare models after bagging.",
            "The out of bag estimate supports model comparison.",
            "Stump selection uses weighted error before voting.",
            "synthetic_stump_choice_score: 0.20",
            "synthetic_weighted_error: 0.125",
            "synthetic_vote_margin: 0.80",
            "## Worked Answer",
            "Solution: use the synthetic target values and select the stable stump.",
            "## Mock Question 1: Which methods combine outputs?",
            "Answer: voting methods.",
            "## Mock Question 2: Which process resamples examples?",
            "Answer: bagging.",
            "## Practice Question 3: Which estimate is held out?",
            "Answer: out of bag estimate.",
            "## Practice Question 4: Which comparison is made?",
            "Answer: model comparison.",
        ]
    )


def ambiguous_failing_candidate() -> str:
    return "\n".join(
        [
            "# Ambiguous Ensemble Synthetic Candidate",
            "Wait, the ensemble explanation keeps a synthetic uncertainty marker.",
            "Voting methods, bagging, out of bag estimate, stump selection, weighted error, and model comparison are present.",
            "synthetic_stump_choice_score: 0.50",
            "synthetic_weighted_error: 0.125",
            "synthetic_vote_margin: 0.80",
            "## Worked Answer",
            "Solution: use the synthetic target values and finish with the stated vote margin.",
            "## Mock Question 1: Which methods combine outputs?",
            "Answer: voting methods.",
            "## Mock Question 2: Which process resamples examples?",
            "Answer: bagging.",
            "## Practice Question 3: Which estimate is held out?",
            "Answer: out of bag estimate.",
            "## Practice Question 4: Which comparison is made?",
            "Answer: model comparison.",
        ]
    )


def test_fixture_files_exist() -> None:
    check("fixture directory exists", FIXTURE_DIR.is_dir(), str(FIXTURE_DIR))
    names = sorted(path.name for path in FIXTURE_DIR.iterdir()) if FIXTURE_DIR.is_dir() else []
    for name in EXPECTED_FIXTURES:
        check(f"fixture exists: {name}", (FIXTURE_DIR / name).is_file())
    non_json = [name for name in names if not name.endswith(".json")]
    binary = [name for name in names if Path(name).suffix.lower() in BINARY_SUFFIXES]
    check("no non-json fixtures", non_json == [], str(non_json))
    check("no binary fixtures", binary == [], str(binary))


def test_fixture_files_are_safe() -> None:
    for name, raw, loaded in seed_fixture_items():
        assert_safe_fixture_fields(f"{name} raw", raw)
        assert_safe_fixture_fields(f"{name} loaded", loaded)
        assert_no_leak(f"{name} raw fixture", raw)
        assert_no_leak(f"{name} loaded fixture", loaded)


def test_fixture_loader_accepts_seed_files() -> None:
    for name, _raw, loaded in seed_fixture_items():
        check(f"{name}: fixture kind", loaded["kind"] == "quality_safety_fixture")
        check(f"{name}: no loader warnings", loaded["warnings"] == [], str(loaded["warnings"]))
        check(f"{name}: expected topics present", len(loaded["expected_topics"]) > 0)
        check(f"{name}: numeric targets present", len(loaded["ground_truth_numerics"]) > 0)
        check(f"{name}: min mock questions positive", loaded["min_mock_questions"] > 0)
        tiers = loaded.get("tier_targets", {})
        check(f"{name}: tier targets numeric", all(isinstance(tiers.get(key), float) for key in ("premium", "local")), str(tiers))


def test_harness_passes_synthetic_candidates() -> None:
    clean = run_quality_safety_layer1_checks(clean_candidate(), loaded_fixture("clean_neural_networks_synthetic.json"))
    ambiguous = run_quality_safety_layer1_checks(ambiguous_candidate(), loaded_fixture("ambiguous_ensemble_synthetic.json"))
    check("clean fixture candidate passes", clean["shippable"] is True and clean["status"] == "passed", str(clean))
    check("ambiguous fixture candidate passes", ambiguous["shippable"] is True and ambiguous["status"] == "passed", str(ambiguous))
    assert_no_leak("clean passing report", clean)
    assert_no_leak("ambiguous passing report", ambiguous)


def test_harness_catches_failing_ambiguous_candidate() -> None:
    report = run_quality_safety_layer1_checks(
        ambiguous_failing_candidate(),
        loaded_fixture("ambiguous_ensemble_synthetic.json"),
    )
    check("ambiguous failing candidate not shippable", report["shippable"] is False, str(report))
    check_report_blocking_statuses(report, {"leaked_reasoning", "numeric_correctness"})
    numeric = next(item for item in report["checks"] if item["id"] == "numeric_correctness")
    check("failing numeric values only", numeric["targets"][0]["found_values"] == [0.5], str(numeric))
    check("failing report no snippets", not any(term in serialized(report) for term in ("Wait, the ensemble", "stated vote margin", "synthetic_stump_choice_score:")))
    assert_no_leak("ambiguous failing report", report)


def test_deterministic_serialization() -> None:
    first_loaded = [loaded_fixture(name) for name in EXPECTED_FIXTURES]
    second_loaded = [loaded_fixture(name) for name in EXPECTED_FIXTURES]
    check("fixture loading deterministic", serialized(first_loaded) == serialized(second_loaded))

    first_reports = [
        run_quality_safety_layer1_checks(clean_candidate(), first_loaded[1]),
        run_quality_safety_layer1_checks(ambiguous_failing_candidate(), first_loaded[0]),
    ]
    second_reports = [
        run_quality_safety_layer1_checks(clean_candidate(), second_loaded[1]),
        run_quality_safety_layer1_checks(ambiguous_failing_candidate(), second_loaded[0]),
    ]
    check("fixture reports deterministic", serialized(first_reports) == serialized(second_reports))


def test_no_leak_sweep() -> None:
    hostile_candidate = "\n".join(
        [
            *HOSTILE_CANARIES,
            "Wait, synthetic_stump_choice_score: 0.50",
            "synthetic_weighted_error: 0.125",
            "synthetic_vote_margin: 0.80",
        ]
    )
    loaded = loaded_fixture("ambiguous_ensemble_synthetic.json")
    report = run_quality_safety_layer1_checks(hostile_candidate, loaded)
    record = build_quality_safety_regression_record(
        run_id=HOSTILE_CANARIES[0],
        git_sha=HOSTILE_CANARIES[1],
        model=HOSTILE_CANARIES[2],
        preset=HOSTILE_CANARIES[3],
        lecture_id=HOSTILE_CANARIES[4],
        tier="premium",
        layer1_report=report,
    )
    fixtures = [raw_fixture(name) for name in EXPECTED_FIXTURES]
    assert_no_leak("fixture raw no-leak sweep", fixtures)
    assert_no_leak("fixture loaded no-leak sweep", [loaded_fixture(name) for name in EXPECTED_FIXTURES])
    assert_no_leak("hostile report no-leak sweep", report)
    assert_no_leak("hostile record no-leak sweep", record)


def test_import_hygiene() -> None:
    source_path = REPO / "pipeline" / "quality_safety_eval_harness.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                calls.append(func.attr)
            elif isinstance(func, ast.Name):
                calls.append(func.id)
    forbidden_import_prefixes = (
        "api",
        "frontend",
        "requests",
        "urllib",
        "httpx",
        "openai",
        "anthropic",
        "google",
        "boto",
        "chandra",
        "mistral",
        "gemini",
        "pipeline.provider",
        "pipeline.llm",
        "pipeline.ocr",
        "pipeline.pdf_renderer",
        "pipeline.docx_renderer",
        "pipeline.html_renderer",
        "pipeline.run_llm_job",
    )
    bad_imports = [name for name in imports if name.startswith(forbidden_import_prefixes)]
    check("import hygiene no forbidden imports", bad_imports == [], str(bad_imports))
    forbidden_calls = {"urlopen", "post", "socket", "create_connection"}
    bad_calls = sorted(set(calls) & forbidden_calls)
    check("import hygiene no network calls", bad_calls == [], str(bad_calls))


def run() -> int:
    test_fixture_files_exist()
    test_fixture_files_are_safe()
    test_fixture_loader_accepts_seed_files()
    test_harness_passes_synthetic_candidates()
    test_harness_catches_failing_ambiguous_candidate()
    test_deterministic_serialization()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_seed_fixtures: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
