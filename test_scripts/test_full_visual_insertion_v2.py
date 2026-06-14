"""Slice 90 — full non-table figure insertion v2.

Synthetic, offline regression for the plan-driven full insertion path
(``pipeline.visual_markdown_insertion._apply_full_visual_insertion`` /
``select_full_visual_markdown_candidates``). It proves that, when the visual gate
AND the Slice 90 mode switch are on, the generator inserts *every* useful planned
non-table figure from included pages — not the legacy top-1/top-2 cap — while
still skipping table-like / decorative / tiny / blank / unsafe / unmappable
records, de-duplicating, ordering deterministically, using only safe source-page
captions and safe ``assets/<slug>.png`` refs, and never failing a job.

Everything here is synthetic: a temp job dir, a hand-built sanitized manifest, and
minimal 1x1 PNG bytes that exist only so the on-disk asset-file gate has a real
file to find. No real PDF/image/DOCX, no provider/model/cloud call, no private
source text, and no path/filename/ref is asserted on or emitted.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import visual_markdown_insertion as vmi  # noqa: E402
from pipeline.visual_inclusion_planner import (  # noqa: E402
    build_visual_inclusion_plan,
    candidate_id_for_manifest_position,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


# A minimal valid 1x1 PNG. Bytes are never asserted on or emitted anywhere.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Leak canary patterns — the generated Markdown must match NONE of these.
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATAURI = re.compile(r"(data:|base64,)")
GGUFLIKE = re.compile(r"(\.gguf|mmproj|llama-server|\.sock)")
# A synthetic "private" canary stuffed into every record's leaky fields; it must
# never survive into the generated guide or the public plan.
CANARY = "PRIVATE_SOURCE_CANARY_quarterly_plan"


@dataclass(frozen=True)
class FakeJob:
    dir: Path
    opt_in: bool = True

    @property
    def visual_assets_manifest_json(self) -> Path:
        return self.dir / "visual_assets_manifest.json"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"

    @property
    def visual_markdown_image_pilot(self) -> bool:
        return self.opt_in


def _leaky() -> dict:
    """Fields a hostile manifest might carry; read for decisions, never echoed."""
    return {
        "caption": f"{CANARY} caption text",
        "title": f"{CANARY} title",
        "ocr_text": "raw OCR dump",
        "table_text": "table cell text",
        "source_path": "/home/secret/private-source.pdf",
        "source_filename": "private-source.pdf",
        "url": "https://example.test/secret",
        "api_key": "sk_fullinsertcanary1234567890",
        "data_uri": "data:image/png;base64,QQQQ",
    }


def _figure(asset_id: str, *, source_index: int, source_page: int, image_ref: str) -> dict:
    rec = _leaky()
    rec.update(
        {
            "asset_id": asset_id,
            "asset_type": "extracted_figure",
            "source_provider": "fitz_local",
            "source_index": source_index,
            "source_page": source_page,
            "image_ref": image_ref,
            "bbox": [0.0, 0.0, 200.0, 200.0],
            "signals": {"crop_width_px": 200, "crop_height_px": 200},
            "warnings": [],
        }
    )
    return rec


def _table(asset_id: str, *, source_index: int, source_page: int) -> dict:
    rec = _figure(asset_id, source_index=source_index, source_page=source_page,
                  image_ref=f"assets/{asset_id}.png")
    rec["visual_kind"] = "table"
    return rec


def _decorative(asset_id: str, *, source_index: int, source_page: int, kind: str) -> dict:
    rec = _figure(asset_id, source_index=source_index, source_page=source_page,
                  image_ref=f"assets/{asset_id}.png")
    rec["visual_kind"] = kind
    return rec


def _tiny(asset_id: str, *, source_index: int, source_page: int) -> dict:
    rec = _figure(asset_id, source_index=source_index, source_page=source_page,
                  image_ref=f"assets/{asset_id}.png")
    rec["signals"] = {"crop_width_px": 8, "crop_height_px": 8}
    return rec


def _blank(asset_id: str, *, source_index: int, source_page: int) -> dict:
    rec = _figure(asset_id, source_index=source_index, source_page=source_page,
                  image_ref=f"assets/{asset_id}.png")
    rec["signals"] = {"classification": "blank_or_low_text"}
    return rec


def _unsafe(asset_id: str, *, source_index: int, source_page: int) -> dict:
    rec = _figure(asset_id, source_index=source_index, source_page=source_page,
                  image_ref=f"assets/{asset_id}.png")
    rec["unsafe"] = True
    return rec


def _page_signal(asset_id: str, *, source_index: int, source_page: int) -> dict:
    rec = _leaky()
    rec.update(
        {
            "asset_id": asset_id,
            "asset_type": "page_visual_signal",
            "source_provider": "fitz_local",
            "source_index": source_index,
            "source_page": source_page,
            "signals": {"has_drawings": True},
            "warnings": [],
        }
    )
    return rec


def _manifest(assets: list[dict], status: str = "completed") -> dict:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": status,
        "assets": assets,
        "summary": {"asset_count": len(assets)},
        "warnings": [],
    }


def _make_job(tmp: Path, assets: list[dict], *, png_slugs: list[str], opt_in: bool = True) -> FakeJob:
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for slug in png_slugs:
        (job.assets_dir / f"{slug}.png").write_bytes(_PNG_1x1)
    job.visual_assets_manifest_json.write_text(json.dumps(_manifest(assets)) + "\n", encoding="utf-8")
    return job


def _full_env(fn):
    """Run ``fn`` with BOTH the visual master switch and the Slice 90 mode switch on."""
    saved = {k: os.environ.get(k) for k in (vmi.ENABLE_ENV, vmi.FULL_INSERTION_ENABLE_ENV)}
    os.environ[vmi.ENABLE_ENV] = "1"
    os.environ[vmi.FULL_INSERTION_ENABLE_ENV] = "1"
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _legacy_env(fn):
    """Master switch on, Slice 90 mode switch OFF (legacy capped pilot)."""
    saved = {k: os.environ.get(k) for k in (vmi.ENABLE_ENV, vmi.FULL_INSERTION_ENABLE_ENV)}
    os.environ[vmi.ENABLE_ENV] = "1"
    os.environ.pop(vmi.FULL_INSERTION_ENABLE_ENV, None)
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


BASE_MD = "# Guide\n\nSome content.\n"


def _leak_scan(name: str, text: str) -> None:
    check(f"{name}.no_canary", CANARY not in text, text[:160])
    check(f"{name}.no_key", not KEYLIKE.search(text))
    check(f"{name}.no_hostpath", not PATHLIKE.search(text.replace("assets/", "")))
    check(f"{name}.no_url", not URLLIKE.search(text))
    check(f"{name}.no_datauri", not DATAURI.search(text))
    check(f"{name}.no_gguf", not GGUFLIKE.search(text))
    check(f"{name}.no_filename", "private-source.pdf" not in text)


def _count_images(text: str) -> int:
    return len(re.findall(r"!\[[^\]]*\]\(assets/[A-Za-z0-9_]+\.png\)", text))


# ── Tests ────────────────────────────────────────────────────────────────────


def test_inserts_all_five_not_capped() -> None:
    slugs = [f"s00_page_{p:04d}_figure_01" for p in (2, 3, 4, 5, 6)]
    assets = [_figure(s, source_index=0, source_page=p, image_ref=f"assets/{s}.png")
              for s, p in zip(slugs, (2, 3, 4, 5, 6))]
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), assets, png_slugs=slugs)
        out, info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("five.status_inserted", info.get("status") == vmi.STATUS_INSERTED, str(info))
        check("five.mode_full", info.get("mode") == vmi.MODE_FULL_INSERTION, str(info))
        check("five.count_5", info.get("inserted_visual_count") == 5, str(info))
        check("five.markdown_has_5_images", _count_images(out) == 5, str(_count_images(out)))
        for s in slugs:
            check(f"five.has_{s}", f"assets/{s}.png" in out)
        _leak_scan("five", out)
        # Legacy capped pilot on the SAME job inserts at most 2 — proving the cap is bypassed.
        legacy_out, legacy_info = _legacy_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("five.legacy_capped", _count_images(legacy_out) <= vmi._HARD_MAX_IMAGES, str(legacy_info))


def test_table_like_not_inserted_as_screenshot() -> None:
    fig = _figure("s00_page_0002_figure_01", source_index=0, source_page=2,
                  image_ref="assets/s00_page_0002_figure_01.png")
    tab = _table("s00_page_0003_table_01", source_index=0, source_page=3)
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [fig, tab],
                        png_slugs=["s00_page_0002_figure_01", "s00_page_0003_table_01"])
        out, info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("table.only_figure_inserted", _count_images(out) == 1, str(_count_images(out)))
        check("table.figure_present", "assets/s00_page_0002_figure_01.png" in out)
        check("table.table_absent", "s00_page_0003_table_01.png" not in out)


def test_decorative_tiny_blank_unsafe_skipped() -> None:
    good = _figure("s00_page_0002_figure_01", source_index=0, source_page=2,
                   image_ref="assets/s00_page_0002_figure_01.png")
    junk = [
        _decorative("logo_01", source_index=0, source_page=3, kind="logo"),
        _decorative("header_01", source_index=0, source_page=4, kind="header"),
        _decorative("bg_01", source_index=0, source_page=5, kind="background"),
        _tiny("tiny_01", source_index=0, source_page=6),
        _blank("blank_01", source_index=0, source_page=7),
        _unsafe("unsafe_01", source_index=0, source_page=8),
    ]
    slugs = ["s00_page_0002_figure_01", "logo_01", "header_01", "bg_01",
             "tiny_01", "blank_01", "unsafe_01"]
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [good, *junk], png_slugs=slugs)
        out, info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("junk.only_good_inserted", _count_images(out) == 1, str(_count_images(out)))
        for s in ("logo_01", "header_01", "bg_01", "tiny_01", "blank_01", "unsafe_01"):
            check(f"junk.{s}_absent", f"assets/{s}.png" not in out)


def test_excluded_pages_absent_because_manifest_filtered() -> None:
    # The manifest is already page-filtered upstream (Slice 82): an excluded page
    # simply contributes no record, so its figure can never be inserted.
    keep = _figure("s00_page_0002_figure_01", source_index=0, source_page=2,
                   image_ref="assets/s00_page_0002_figure_01.png")
    with tempfile.TemporaryDirectory() as d:
        # Note: no record for page 9 exists, and no png for it either.
        job = _make_job(Path(d), [keep], png_slugs=["s00_page_0002_figure_01"])
        out, _info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("excluded.kept_page_present", "assets/s00_page_0002_figure_01.png" in out)
        check("excluded.no_phantom_page9", "page_0009" not in out)


def test_deterministic_order() -> None:
    # Two sources, pages out of order in the manifest; result must be ordered by
    # source_index then source_page then manifest position.
    assets = [
        _figure("s01_page_0005_figure_01", source_index=1, source_page=5,
                image_ref="assets/s01_page_0005_figure_01.png"),
        _figure("s00_page_0004_figure_01", source_index=0, source_page=4,
                image_ref="assets/s00_page_0004_figure_01.png"),
        _figure("s00_page_0002_figure_01", source_index=0, source_page=2,
                image_ref="assets/s00_page_0002_figure_01.png"),
    ]
    slugs = ["s01_page_0005_figure_01", "s00_page_0004_figure_01", "s00_page_0002_figure_01"]
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), assets, png_slugs=slugs)
        cands = _full_env(lambda: vmi.select_full_visual_markdown_candidates(job))
        order = [c["asset_id"] for c in cands]
        expected = ["s00_page_0002_figure_01", "s00_page_0004_figure_01", "s01_page_0005_figure_01"]
        check("order.deterministic", order == expected, str(order))
        # Repeated call is identical.
        again = [c["asset_id"] for c in _full_env(lambda: vmi.select_full_visual_markdown_candidates(job))]
        check("order.repeatable", again == expected, str(again))


def test_safe_candidate_mapping_is_deterministic() -> None:
    assets = [
        _figure("a1", source_index=0, source_page=2, image_ref="assets/a1.png"),
        _figure("a2", source_index=0, source_page=3, image_ref="assets/a2.png"),
    ]
    plan = build_visual_inclusion_plan(_manifest(assets))
    ids = [it["candidate_id"] for it in plan["items"]]
    check("map.ids_present", all(isinstance(i, str) and i.startswith("visual_candidate_") for i in ids), str(ids))
    check("map.id_first", candidate_id_for_manifest_position(0) == "visual_candidate_0001")
    check("map.id_zeropad", candidate_id_for_manifest_position(11) == "visual_candidate_0012")
    check("map.id_negative_none", candidate_id_for_manifest_position(-1) is None)
    check("map.id_bool_none", candidate_id_for_manifest_position(True) is None)


def test_unmappable_candidate_degrades_safely() -> None:
    fig = _figure("a1", source_index=0, source_page=2, image_ref="assets/a1.png")
    sig = _page_signal("sig1", source_index=0, source_page=3)
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [fig, sig], png_slugs=["a1"])
        # A hand-built plan with a bogus candidate_id (no manifest record) + the
        # page-signal candidate (record exists but is not an insertable figure) +
        # the good figure. Generation must not fail; only the good figure inserts.
        plan = {
            "version": 1, "kind": "visual_inclusion_plan", "status": "completed",
            "summary": {}, "warnings": [],
            "items": [
                {"plan_index": 1, "candidate_id": "visual_candidate_9999",
                 "source_index": 0, "source_page": 9, "visual_kind": "figure",
                 "inclusion_role": "primary_visual", "reason": "x", "warnings": []},
                {"plan_index": 2, "candidate_id": candidate_id_for_manifest_position(1),
                 "source_index": 0, "source_page": 3, "visual_kind": "diagram",
                 "inclusion_role": "supporting_visual", "reason": "x", "warnings": []},
                {"plan_index": 3, "candidate_id": candidate_id_for_manifest_position(0),
                 "source_index": 0, "source_page": 2, "visual_kind": "figure",
                 "inclusion_role": "primary_visual", "reason": "x", "warnings": []},
            ],
        }
        cands = _full_env(lambda: vmi.select_full_visual_markdown_candidates(job, plan=plan))
        check("unmappable.only_good_mapped", [c["asset_id"] for c in cands] == ["a1"], str(cands))
        out, info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("unmappable.job_not_broken", info.get("status") == vmi.STATUS_INSERTED, str(info))
        check("unmappable.one_image", _count_images(out) == 1)


def test_all_unmappable_degrades_to_skip() -> None:
    # A manifest of only page signals (no insertable figure) → safe skip, original text.
    sigs = [_page_signal(f"sig{p}", source_index=0, source_page=p) for p in (2, 3)]
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), sigs, png_slugs=[])
        out, info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("allunmap.skipped", info.get("status") == "skipped", str(info))
        check("allunmap.reason_unmappable", info.get("reason") == vmi.SKIP_PLAN_UNMAPPABLE, str(info))
        check("allunmap.text_unchanged", out == BASE_MD)


def test_duplicate_records_deduped() -> None:
    fig = _figure("dup", source_index=0, source_page=2, image_ref="assets/dup.png")
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [fig], png_slugs=["dup"])
        # Plan with duplicate candidate_ids AND another item resolving to the same slug.
        cid = candidate_id_for_manifest_position(0)
        plan = {
            "version": 1, "kind": "visual_inclusion_plan", "status": "completed",
            "summary": {}, "warnings": [],
            "items": [
                {"plan_index": 1, "candidate_id": cid, "source_index": 0, "source_page": 2,
                 "visual_kind": "figure", "inclusion_role": "primary_visual", "reason": "x", "warnings": []},
                {"plan_index": 2, "candidate_id": cid, "source_index": 0, "source_page": 2,
                 "visual_kind": "figure", "inclusion_role": "primary_visual", "reason": "x", "warnings": []},
            ],
        }
        cands = _full_env(lambda: vmi.select_full_visual_markdown_candidates(job, plan=plan))
        check("dedupe.one_candidate", len(cands) == 1, str(cands))


def test_captions_are_safe_source_page_only() -> None:
    fig = _figure("s00_page_0003_figure_01", source_index=0, source_page=3,
                  image_ref="assets/s00_page_0003_figure_01.png")
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [fig], png_slugs=["s00_page_0003_figure_01"])
        out, _info = _full_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("caption.page_phrase", "Source visual, page 3." in out, out[-200:])
        check("caption.alt_safe", "source page 3" in out, out[-200:])
        _leak_scan("caption", out)


def test_public_plan_artifact_sanitized() -> None:
    assets = [_figure("a1", source_index=0, source_page=2, image_ref="assets/a1.png"),
              _table("t1", source_index=0, source_page=3)]
    plan = build_visual_inclusion_plan(_manifest(assets))
    blob = json.dumps(plan)
    check("plan.no_canary", CANARY not in blob)
    check("plan.no_filename", "private-source.pdf" not in blob)
    check("plan.no_assetref", "assets/a1.png" not in blob and "image_ref" not in blob)
    check("plan.no_key", not KEYLIKE.search(blob))
    check("plan.no_path", not PATHLIKE.search(blob))
    check("plan.candidate_id_safe", "visual_candidate_0001" in blob)
    # Table-like record is planned-out (not inserted, not reconstructed).
    check("plan.table_excluded", plan["summary"]["table_like_skipped_count"] == 1, str(plan["summary"]))
    check("plan.no_reconstruction_field", "reconstructed_table" not in blob and "table_markdown" not in blob)


def test_mode_switch_off_uses_legacy_path() -> None:
    fig = _figure("a1", source_index=0, source_page=3, image_ref="assets/a1.png")
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [fig], png_slugs=["a1"])
        _out, info = _legacy_env(lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("modeoff.not_full_mode", info.get("mode") != vmi.MODE_FULL_INSERTION, str(info))


def test_no_provider_or_cloud_imports() -> None:
    # Import-statement hygiene (not bare-word): the safety prose legitimately names
    # "Chandra"/"Mistral" while forbidding them — what must never appear is an actual
    # import of a provider/cloud/network client.
    src = (ROOT / "pipeline" / "visual_markdown_insertion.py").read_text(encoding="utf-8")
    planner_src = (ROOT / "pipeline" / "visual_inclusion_planner.py").read_text(encoding="utf-8")
    for name in ("openai", "anthropic", "mistralai", "google.generativeai", "google",
                 "chandra", "requests", "httpx", "urllib.request", "socket"):
        for label, blob in (("insertion", src), ("planner", planner_src)):
            ok = f"import {name}" not in blob and f"from {name}" not in blob
            check(f"noprovider.{label}_no_import_{name}", ok)


def main() -> int:
    test_inserts_all_five_not_capped()
    test_table_like_not_inserted_as_screenshot()
    test_decorative_tiny_blank_unsafe_skipped()
    test_excluded_pages_absent_because_manifest_filtered()
    test_deterministic_order()
    test_safe_candidate_mapping_is_deterministic()
    test_unmappable_candidate_degrades_safely()
    test_all_unmappable_degrades_to_skip()
    test_duplicate_records_deduped()
    test_captions_are_safe_source_page_only()
    test_public_plan_artifact_sanitized()
    test_mode_switch_off_uses_legacy_path()
    test_no_provider_or_cloud_imports()
    print(f"\nFull visual insertion v2 tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
