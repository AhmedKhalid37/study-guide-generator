"""Tests for the Slice 176M frame-redundancy detector + frame_dedup_mode resolver.

All fixtures here are SYNTHETIC 64-bit hash sequences (made-up bit patterns) — never
a real deck, never a rendered image, never source content. They prove:

  * an animation-like sequence (runs of near-identical hashes) → slide_redundancy=high;
  * a normal varied sequence → slide_redundancy=low;
  * a repetitive-template-but-distinct sequence → low/medium and resolved OFF
    (the false-positive guard);
  * frame_dedup_mode defaults to auto, force_on/force_off override, unknown → off;
  * the closed summary is closed-vocab only with no raw images / thumbnails / source;
  * the expensive frame-selection pipeline is neither invoked nor present.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.slide_redundancy_detector as det
from pipeline.slide_redundancy_detector import (
    FrameRedundancyConfig,
    build_closed_redundancy_summary,
    compute_adjacent_metrics,
    derive_slide_redundancy,
    resolve_frame_dedup,
    run_slide_redundancy_detection,
)

_FAILURES: list[str] = []
_FULL = (1 << 64) - 1


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


def _flip_bits(base: int, n: int, start: int = 0) -> int:
    """Flip ``n`` bits of ``base`` starting at bit ``start`` (deterministic)."""
    out = base
    for i in range(n):
        out ^= 1 << ((start + i) % 64)
    return out


def _animation_like_sequence() -> list[int]:
    """Runs of near-identical frames: a few distinct slides, each held for several
    build-step frames that differ by only 0-1 bits (a video-export deck)."""
    seq: list[int] = []
    base = 0x0F0F0F0F0F0F0F0F
    for slide in range(5):  # 5 real slides
        anchor = _flip_bits(base, 24, start=slide * 7)  # distinct per slide
        seq.append(anchor)
        for step in range(5):  # 5 near-identical animation frames each
            seq.append(_flip_bits(anchor, 1, start=step))  # 1-bit drift → sim ~0.984
    return seq


def _normal_varied_sequence() -> list[int]:
    """Every slide visually distinct (~30-bit hamming apart) → low redundancy."""
    return [_flip_bits(0xAAAAAAAAAAAAAAAA, 30, start=i * 31) for i in range(20)]


def _repetitive_template_sequence() -> list[int]:
    """Shared template but distinct body: ~8-bit hamming apart (sim ~0.875) — below
    the 0.92 near-duplicate threshold, so each slide is its own cluster."""
    base = 0x3333333333333333
    return [_flip_bits(base, 8, start=i * 11) for i in range(16)]


def test_animation_like_is_high() -> None:
    metrics = compute_adjacent_metrics(_animation_like_sequence())
    redundancy, confidence = derive_slide_redundancy(metrics)
    _check("animation -> high redundancy", redundancy == "high")
    _check("animation confidence not low", confidence in {"medium", "high"})
    res = resolve_frame_dedup(redundancy, "auto")
    _check("animation auto -> on", res["resolved_frame_dedup"] == "on")
    _check("animation reason detector_high", res["resolution_reason"] == "detector_high")


def test_normal_varied_is_low() -> None:
    metrics = compute_adjacent_metrics(_normal_varied_sequence())
    redundancy, _ = derive_slide_redundancy(metrics)
    _check("normal -> low redundancy", redundancy == "low")
    res = resolve_frame_dedup(redundancy, "auto")
    _check("normal auto -> off", res["resolved_frame_dedup"] == "off")


def test_repetitive_template_is_not_high() -> None:
    # The false-positive guard: template-similar but content-distinct must NOT flag high.
    metrics = compute_adjacent_metrics(_repetitive_template_sequence())
    redundancy, _ = derive_slide_redundancy(metrics)
    _check("repetitive template not high", redundancy in {"low", "medium"})
    res = resolve_frame_dedup(redundancy, "auto")
    _check("repetitive template auto -> off", res["resolved_frame_dedup"] == "off")


def test_resolver_modes() -> None:
    _check("default mode auto", FrameRedundancyConfig().frame_dedup_mode == "auto")
    # force_on overrides a low detector
    r1 = resolve_frame_dedup("low", "force_on")
    _check("force_on overrides low -> on", r1["resolved_frame_dedup"] == "on")
    _check("force_on reason", r1["resolution_reason"] == "user_force_on")
    # force_off overrides a high detector
    r2 = resolve_frame_dedup("high", "force_off")
    _check("force_off overrides high -> off", r2["resolved_frame_dedup"] == "off")
    _check("force_off reason", r2["resolution_reason"] == "user_force_off")
    # auto + high -> on
    _check("auto high -> on", resolve_frame_dedup("high", "auto")["resolved_frame_dedup"] == "on")
    # auto + medium -> off (conservative)
    _check("auto medium -> off", resolve_frame_dedup("medium", "auto")["resolved_frame_dedup"] == "off")
    # auto + unknown -> off
    r3 = resolve_frame_dedup("unknown", "auto")
    _check("auto unknown -> off", r3["resolved_frame_dedup"] == "off")
    _check("auto unknown reason", r3["resolution_reason"] == "detector_unknown_default_off")
    # garbage mode coerces to auto
    _check("garbage mode -> auto", resolve_frame_dedup("high", "nonsense")["frame_dedup_mode"] == "auto")


def test_closed_summary_is_safe_and_closed() -> None:
    metrics = compute_adjacent_metrics(_animation_like_sequence())
    summary = build_closed_redundancy_summary(
        status="completed", source_label="synthetic_anim", metrics=metrics
    )
    _check("artifact_name", summary["artifact_name"] == "slide_redundancy_detection")
    _check("slide_redundancy high", summary["slide_redundancy"] == "high")
    _check("raw_images_committed False", summary["raw_images_committed"] is False)
    _check("thumbnails_committed False", summary["thumbnails_committed"] is False)
    _check("source_pdf_committed False", summary["source_pdf_committed"] is False)
    for key in (
        "page_count_bucket",
        "mean_adjacent_similarity_bucket",
        "high_similarity_pair_ratio_bucket",
        "distinct_visual_cluster_count_bucket",
        "cluster_to_page_ratio_bucket",
    ):
        _check(f"{key} in closed bucket set", summary[key] in det._BUCKET)
    _check("slide_redundancy closed", summary["slide_redundancy"] in det._REDUNDANCY)
    _check("detector_confidence closed", summary["detector_confidence"] in det._CONFIDENCE)
    _check("warnings closed", all(w in det._WARNINGS for w in summary["warnings"]))
    # Counts are the only ints; no string field carries a digit.
    ok = True
    for key, value in summary.items():
        if key in {"pages_sampled_count", "adjacent_pairs_sampled_count"}:
            continue
        if isinstance(value, str) and any(ch.isdigit() for ch in value):
            ok = False
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and any(ch.isdigit() for ch in item):
                    ok = False
    _check("no raw values in closed tokens", ok)


def test_runner_end_to_end_from_hashes() -> None:
    cfg = FrameRedundancyConfig(
        source_label="synthetic", page_hashes=_animation_like_sequence(), frame_dedup_mode="auto"
    )
    out = run_slide_redundancy_detection(cfg)
    _check("runner has detection", isinstance(out.get("detection"), dict))
    _check("runner has resolution", isinstance(out.get("resolution"), dict))
    _check("runner detection high", out["detection"]["slide_redundancy"] == "high")
    _check("runner auto resolves on", out["resolution"]["resolved_frame_dedup"] == "on")
    _check("runner status completed", out["detection"]["status"] == "completed")


def test_runner_blocks_without_pages() -> None:
    out = run_slide_redundancy_detection(FrameRedundancyConfig(source_label="empty"))
    _check("empty -> blocked", out["detection"]["status"] == "blocked")
    _check("empty -> unknown redundancy", out["detection"]["slide_redundancy"] == "unknown")
    _check("empty auto -> off", out["resolution"]["resolved_frame_dedup"] == "off")


def test_too_few_pages_degrades() -> None:
    out = run_slide_redundancy_detection(
        FrameRedundancyConfig(source_label="tiny", page_hashes=[1, 2])
    )
    _check("two pages -> degraded", out["detection"]["status"] == "degraded")
    _check("two pages -> not high", out["detection"]["slide_redundancy"] in {"low", "medium", "unknown"})


def test_selection_pipeline_not_implemented() -> None:
    # The expensive frame-selection branch must NOT exist in this slice.
    for forbidden in (
        "phash_collapse",
        "select_terminal_frames",
        "coverage_coupled_selection",
        "vlm_classify_survivors",
        "run_frame_selection_pipeline",
    ):
        _check(f"no {forbidden}", not hasattr(det, forbidden))


def main() -> int:
    print("test_slide_redundancy_detector:")
    test_animation_like_is_high()
    test_normal_varied_is_low()
    test_repetitive_template_is_not_high()
    test_resolver_modes()
    test_closed_summary_is_safe_and_closed()
    test_runner_end_to_end_from_hashes()
    test_runner_blocks_without_pages()
    test_too_few_pages_degrades()
    test_selection_pipeline_not_implemented()
    if _FAILURES:
        print(f"test_slide_redundancy_detector: FAILED ({len(_FAILURES)})")
        return 1
    print("test_slide_redundancy_detector: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
