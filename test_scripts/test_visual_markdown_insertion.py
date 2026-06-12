#!/usr/bin/env python3
"""Focused tests for the minimal visual markdown image pilot (Slice 54).

Run with the flag OFF (default):

    python test_scripts/test_visual_markdown_insertion.py

Run a few flag-ON cases too:

    GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1 python test_scripts/test_visual_markdown_insertion.py

Slice 55 added a per-job opt-in (``visual_markdown_image_pilot``). Insertion now
requires BOTH the global env master switch AND the per-job opt-in. The truth-table
and opt-in unit checks below set/clear the env var themselves, so they run and pass
regardless of how this script is invoked; the legacy flag-ON cases assume an
opted-in job (the FakeJob default) so they still exercise selection/insertion.

The pilot helper is a near-pure function of an already-sanitized clean.md plus the
job's already-produced (sanitized) visual advisory artifacts. These tests feed it
tiny *handcrafted synthetic* manifests / plans and a temp job dir holding a tiny
real PNG written by the test (a 1x1 PNG byte literal) — no model dumps, private
documents, screenshots from the app, OCR text, image bytes from a provider, or
local host paths are used. The PNG bytes never appear in any assertion or output.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import types
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear anywhere in the inserted markdown.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

from pipeline import visual_markdown_insertion as vmi  # noqa: E402

# A minimal valid 1x1 PNG (transparent). Used only so the on-disk file gate has a
# real PNG to find; the bytes are never asserted on or emitted into any artifact.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


@dataclass(frozen=True)
class FakeJob:
    """Duck-typed stand-in exposing only what the pilot reads.

    ``opt_in`` (Slice 55) is surfaced as the persisted ``visual_markdown_image_pilot``
    job option the pilot AND-gates against the env master switch. It defaults to
    True so the legacy flag-ON selection/insertion cases stay meaningful; the
    truth-table cases pass it explicitly.
    """

    dir: Path
    opt_in: bool = True

    @property
    def visual_assets_manifest_json(self) -> Path:
        return self.dir / "visual_assets_manifest.json"

    @property
    def visual_replacement_plan_json(self) -> Path:
        return self.dir / "visual_replacement_plan.json"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"

    @property
    def visual_markdown_image_pilot(self) -> bool:
        return self.opt_in


def _figure_asset(asset_id: str, *, image_ref: str, page: int = 3, caption=None) -> dict:
    return {
        "asset_id": asset_id,
        "source_page": page,
        "asset_type": "extracted_figure",
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "caption": caption,
        "source_provider": "fitz_local",
        "image_ref": image_ref,
        "scores": {},
        "signals": {},
        "warnings": [],
    }


def _manifest(assets: list[dict]) -> dict:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "source": "extraction_metadata.json",
        "assets": assets,
        "summary": {"asset_count": len(assets)},
        "warnings": [],
    }


def _plan(items: list[dict]) -> dict:
    return {
        "version": 1,
        "kind": "visual_replacement_plan",
        "status": "completed",
        "source": "visual_asset_scoring.json",
        "items": items,
        "summary": {},
        "warnings": [],
    }


def _plan_item(asset_id: str, *, action="candidate_include_as_figure",
               provider="fitz_local", atype="extracted_figure", reasons=None) -> dict:
    return {
        "asset_id": asset_id,
        "source_page": 3,
        "source_provider": provider,
        "asset_type": atype,
        "priority": "high",
        "candidate_action": action,
        "placement": "source_page_reference",
        "reasons": reasons or ["score_high", "asset_type_figure"],
        "warnings": [],
    }


def _make_job(tmp: Path, *, assets: list[dict] | None = None, plan_items=None,
              png_names: list[str] | None = None, opt_in: bool = True) -> FakeJob:
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for name in (png_names or []):
        (job.assets_dir / name).write_bytes(_PNG_1x1)
    if assets is not None:
        job.visual_assets_manifest_json.write_text(
            json.dumps(_manifest(assets)) + "\n", encoding="utf-8"
        )
    if plan_items is not None:
        job.visual_replacement_plan_json.write_text(
            json.dumps(_plan(plan_items)) + "\n", encoding="utf-8"
        )
    return job


def _leak_scan(name: str, text: str) -> None:
    for label, pat in (
        ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
        ("socket", SOCKETLIKE), ("datauri", BASE64URI), ("gguf", GGUFLIKE),
    ):
        check(f"{name}.no_{label}", not pat.search(text), text[:120])


BASE_MD = "# Guide\n\nSome content.\n"


def _with_env(value, fn):
    """Run ``fn`` with the master-switch env var forced to ``value`` (None = unset).

    Saves/restores the prior value so the truth-table cases are deterministic no
    matter how the script was invoked.
    """
    old = os.environ.get(vmi.ENABLE_ENV)
    if value is None:
        os.environ.pop(vmi.ENABLE_ENV, None)
    else:
        os.environ[vmi.ENABLE_ENV] = value
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop(vmi.ENABLE_ENV, None)
        else:
            os.environ[vmi.ENABLE_ENV] = old


def run_truth_table() -> None:
    """Slice 55 gate: insertion requires BOTH the env master switch AND job opt-in.

    Runs all four (global, job) combinations explicitly. Only (on, on) may insert;
    crucially (off, on) proves a job opt-in can NEVER bypass the env master switch.
    """
    cases = [
        ("off_off", None, False),
        ("off_on", None, True),   # global OFF + job ON must still NOT insert
        ("on_off", "1", False),
        ("on_on", "1", True),     # only this one may insert
    ]
    for name, env, opt_in in cases:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            job = _make_job(
                tmp,
                assets=[_figure_asset("a1", image_ref="assets/a1.png")],
                plan_items=[_plan_item("a1")],
                png_names=["a1.png"],
                opt_in=opt_in,
            )
            out, info = _with_env(env, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
            if env == "1" and opt_in:
                check(f"truth.{name}.inserted",
                      info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
                _leak_scan(f"truth.{name}", out)
            else:
                check(f"truth.{name}.byte_identical", out == BASE_MD, repr(out[:60]))
                check(f"truth.{name}.no_image", "![" not in out)
                expected = vmi.SKIP_DISABLED if env != "1" else vmi.SKIP_JOB_OPT_OUT
                check(f"truth.{name}.reason", info.get("reason") == expected, str(info))

    # ---- is_job_visual_pilot_opt_in coercion (Slice 55) ----------------------
    optin = vmi.is_job_visual_pilot_opt_in
    check("optin.missing_false", optin(types.SimpleNamespace()) is False)
    check("optin.none_false", optin(types.SimpleNamespace(visual_markdown_image_pilot=None)) is False)
    check("optin.bool_true", optin(types.SimpleNamespace(visual_markdown_image_pilot=True)) is True)
    check("optin.bool_false", optin(types.SimpleNamespace(visual_markdown_image_pilot=False)) is False)
    check("optin.token_true", optin(types.SimpleNamespace(visual_markdown_image_pilot="true")) is True)
    check("optin.invalid_false", optin(types.SimpleNamespace(visual_markdown_image_pilot="banana")) is False)
    check("optin.int_false", optin(types.SimpleNamespace(visual_markdown_image_pilot=1)) is False)

    # Persisted-manifest read path (a real Job exposes read_manifest()).
    class ManifestJob:
        def read_manifest(self):
            return {"visual_markdown_image_pilot": True}

    class ManifestOffJob:
        # Old job created before the option existed → key absent → opt-out.
        def read_manifest(self):
            return {"theme": "claude_clean"}

    check("optin.manifest_true", optin(ManifestJob()) is True)
    check("optin.manifest_old_job_false", optin(ManifestOffJob()) is False)

    # A read_manifest that raises must degrade to False, never propagate.
    class BrokenManifestJob:
        def read_manifest(self):
            raise RuntimeError("boom")

    check("optin.manifest_error_false", optin(BrokenManifestJob()) is False)


def run() -> None:
    # ---- Slice 55 gate (flag-independent; always runs) -----------------------
    run_truth_table()

    # ---- flag gate -----------------------------------------------------------
    flag_on = vmi.is_visual_markdown_pilot_enabled()

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("s00_page_0003_figure_01", image_ref="assets/s00_page_0003_figure_01.png")],
            plan_items=[_plan_item("s00_page_0003_figure_01")],
            png_names=["s00_page_0003_figure_01.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        if not flag_on:
            check("flagoff.byte_identical", out == BASE_MD, repr(out[:80]))
            check("flagoff.reason_disabled", info.get("reason") == vmi.SKIP_DISABLED, str(info))
            check("flagoff.no_image", "![" not in out)
        else:
            check("flagon.inserted", info.get("status") == vmi.STATUS_INSERTED, str(info))
            check("flagon.has_image", "![" in out and "assets/s00_page_0003_figure_01.png" in out)

    # ---- validate_visual_asset_ref (pure, flag-independent) ------------------
    v = vmi.validate_visual_asset_ref
    check("ref.accepts_safe", v("assets/fig_01.png") == "assets/fig_01.png")
    check("ref.reject_absolute", v("/etc/passwd.png") is None)
    check("ref.reject_absolute_assets", v("/assets/fig.png") is None)
    check("ref.reject_dotdot", v("assets/../secret.png") is None)
    check("ref.reject_backslash", v("assets\\fig.png") is None)
    check("ref.reject_url", v("https://x/y.png") is None)
    check("ref.reject_datauri", v("data:image/png;base64,AAAA") is None)
    check("ref.reject_nonpng", v("assets/fig.jpg") is None)
    check("ref.reject_subdir", v("assets/sub/fig.png") is None)
    check("ref.reject_nonstr", v(None) is None and v(123) is None)
    check("ref.reject_empty", v("") is None)

    # ---- caption sanitization / length limit --------------------------------
    img = vmi.build_visual_markdown_image(
        {"asset_ref": "assets/fig_01.png", "source_page": 3, "caption": None}
    )
    check("caption.generic_default", img == "![Extracted figure from source page 3](assets/fig_01.png)", img)
    long_raw = "x" * 500 + "]](evil)(http://bad)"
    img2 = vmi.build_visual_markdown_image(
        {"asset_ref": "assets/fig_01.png", "source_page": 2, "caption": long_raw}
    )
    cap = img2[img2.index("[") + 1: img2.index("]")]
    check("caption.length_limited", len(cap) <= 80, str(len(cap)))
    check("caption.no_markup_chars", "]" not in cap and "[" not in cap, cap)
    check("caption.stripped_unsafe", "http" not in img2 and "evil" not in img2.split("](")[0])
    _leak_scan("caption", img2)

    # ---- the rest require the flag ON to exercise selection/insertion --------
    if not flag_on:
        # Prove flag-off does not insert even when artifacts + png exist.
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            job = _make_job(
                tmp,
                assets=[_figure_asset("a1", image_ref="assets/a1.png")],
                plan_items=[_plan_item("a1")],
                png_names=["a1.png"],
            )
            out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
            check("flagoff.artifacts_present_still_noop", out == BASE_MD)
        _summary()
        return

    # ===== flag-ON behaviour =====
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png")],
            plan_items=[_plan_item("a1")],
            png_names=["a1.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.single_image", out.count("![") == 1, str(out.count("![")))
        check("on.image_ref_shape", "(assets/a1.png)" in out)
        check("on.visual_reference_section", "## Visual Reference" in out)
        _leak_scan("on.output", out)

    # Multiple candidates → still only one image.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[
                _figure_asset("a1", image_ref="assets/a1.png"),
                _figure_asset("a2", image_ref="assets/a2.png"),
            ],
            plan_items=[_plan_item("a1"), _plan_item("a2")],
            png_names=["a1.png", "a2.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.only_one_of_many", out.count("![") == 1, str(out.count("![")))

    # Plan→manifest fallback: no plan file, first safe manifest figure used.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png")],
            plan_items=None,
            png_names=["a1.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.manifest_fallback", info.get("status") == vmi.STATUS_INSERTED and "assets/a1.png" in out, str(info))

    # Asset file missing on disk → degrade to original.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png")],
            plan_items=[_plan_item("a1")],
            png_names=[],  # no PNG written
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.missing_file_degrades", out == BASE_MD and info.get("status") == "skipped", str(info))

    # Reject Chandra-local candidate.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        chandra = _figure_asset("c1", image_ref="assets/c1.png")
        chandra["source_provider"] = "chandra_local"
        job = _make_job(tmp, assets=[chandra], plan_items=None, png_names=["c1.png"])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_chandra", out == BASE_MD, str(info))

    # Reject chandra_blocked marker even on a fitz asset.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        blocked = _figure_asset("c2", image_ref="assets/c2.png")
        blocked["reasons"] = ["chandra_blocked"]
        job = _make_job(tmp, assets=[blocked], plan_items=None, png_names=["c2.png"])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_chandra_blocked", out == BASE_MD, str(info))

    # Reject page_visual_signal (not an extracted_figure).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        sig = _figure_asset("p1", image_ref="assets/p1.png")
        sig["asset_type"] = "page_visual_signal"
        sig.pop("image_ref", None)
        job = _make_job(tmp, assets=[sig], plan_items=None, png_names=["p1.png"])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_page_signal", out == BASE_MD, str(info))

    # Reject unsafe image_ref on an otherwise-eligible figure.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        bad = _figure_asset("b1", image_ref="../../../etc/passwd.png")
        job = _make_job(tmp, assets=[bad], plan_items=None, png_names=[])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_bad_ref", out == BASE_MD, str(info))

    # Malformed manifest → degrade safely.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = FakeJob(dir=tmp)
        job.assets_dir.mkdir(parents=True, exist_ok=True)
        job.visual_assets_manifest_json.write_text("{not json", encoding="utf-8")
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.malformed_manifest_degrades", out == BASE_MD, str(info))

    # No artifacts at all (e.g. paste job) → degrade safely.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = FakeJob(dir=tmp)
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.no_artifacts_degrades", out == BASE_MD and info.get("reason") == vmi.SKIP_CANDIDATE_UNAVAILABLE, str(info))

    # Source-page anchor placement (deterministic marker present).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png", page=3)],
            plan_items=[_plan_item("a1")],
            png_names=["a1.png"],
        )
        md_with_anchor = "# Guide\n\n<!-- visual-anchor: source_page_0003 -->\n\nMore.\n"
        out, info = vmi.apply_visual_markdown_pilot(job, md_with_anchor)
        check("on.anchor_placement", info.get("placement") == vmi.PLACEMENT_SOURCE_PAGE_ANCHOR, str(info))
        check("on.anchor_no_extra_section", "## Visual Reference" not in out)
        # image must appear after the anchor marker
        check("on.anchor_after_marker", out.index("<!-- visual-anchor") < out.index("!["))

    # No mutation of source manifest / plan dicts.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        assets = [_figure_asset("a1", image_ref="assets/a1.png")]
        items = [_plan_item("a1")]
        man_before = json.dumps(_manifest(assets), sort_keys=True)
        plan_before = json.dumps(_plan(items), sort_keys=True)
        job = _make_job(tmp, assets=assets, plan_items=items, png_names=["a1.png"])
        manifest_obj = json.loads(job.visual_assets_manifest_json.read_text())
        plan_obj = json.loads(job.visual_replacement_plan_json.read_text())
        before_m = json.dumps(manifest_obj, sort_keys=True)
        before_p = json.dumps(plan_obj, sort_keys=True)
        vmi.select_visual_markdown_candidate(job, manifest=manifest_obj, replacement_plan=plan_obj)
        check("on.no_mutation_manifest", json.dumps(manifest_obj, sort_keys=True) == before_m)
        check("on.no_mutation_plan", json.dumps(plan_obj, sort_keys=True) == before_p)
        # artifacts on disk unchanged too
        check("on.disk_manifest_unchanged",
              json.dumps(json.loads(job.visual_assets_manifest_json.read_text()), sort_keys=True) == man_before)
        check("on.disk_plan_unchanged",
              json.dumps(json.loads(job.visual_replacement_plan_json.read_text()), sort_keys=True) == plan_before)

    _summary()


def _summary() -> None:
    print(f"\n{PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    run()
