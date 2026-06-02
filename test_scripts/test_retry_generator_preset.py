"""Regression test: retry preserves generator_preset (fix-rerender-generator-preset).

``retry_failed_job`` (api/server.py) rebuilds an LLM ``generate`` job from its saved
manifest. It already reproduced ``include_sections``/``output_depth``/``difficulty`` but
**dropped** ``generator_preset`` — so a job originally built with a generator preset was
retried through the DEFAULT prompt path, losing the preset system prompt and its tuned
sampling params.

This test stubs the generation/render boundary (no LLM call, no Chromium) and asserts:
  A. a manifest with a real preset id threads that id into ``generate_study_guide`` AND
     builds the provider config with the preset's sampling overrides;
  B. a manifest with no preset keeps the default path (no preset id, no sampling override);
  C. a manifest naming a since-removed preset degrades gracefully to the default path
     (the retry must not fail just because the id no longer resolves).

    python test_scripts/test_retry_generator_preset.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shutil  # noqa: E402

from api import server  # noqa: E402
from pipeline import generator_presets, run_markdown_job  # noqa: E402
from pipeline.job_manager import Job  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


class _FakeJob:
    """Minimal stand-in exposing only what retry_failed_job touches."""

    def __init__(self, manifest, tmp):
        self._manifest = manifest
        self.input_dir = tmp
        self.raw_md = tmp / "raw.md"

    def read_manifest(self):
        return dict(self._manifest)

    def set_status(self, *args, **kwargs):
        pass

    def save_text(self, path, text):
        return path

    def update(self, **fields):
        pass


def _run_retry(manifest):
    """Drive retry_failed_job with the heavy boundaries stubbed; capture kwargs."""
    tmp = Path(tempfile.mkdtemp(prefix="retry_preset_test_"))
    (tmp / "source.txt").write_text("Some source material.", encoding="utf-8")
    fake = _FakeJob(manifest, tmp)
    captured = {"bpc": []}

    def fake_generate_study_guide(source_text, **kwargs):
        captured["gsg"] = kwargs
        return "# Guide\n\nbody\n"

    def fake_build_provider_config(provider, model_choice, **kwargs):
        captured["bpc"].append(kwargs)
        return object()

    # Patch the generation + render boundary in the server namespace. The pipeline
    # runner is imported lazily inside the function, so patch it on its own module.
    server._get_job = lambda job_id: fake
    server.generate_study_guide = fake_generate_study_guide
    server.build_provider_config = fake_build_provider_config
    server.job_response = lambda job: {"ok": True}
    run_markdown_job.run_raw_markdown_pipeline = lambda *a, **k: None

    server.retry_failed_job("fake-job-id")
    return captured


def _base_manifest():
    return {
        "status": "failed",
        "path_mode": "generate",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "title": "T",
        "prompt_name": "basic_study_guide",
    }


def run():
    # Capture the real resolvers before any monkeypatching so case D can use them.
    orig_get_job = server._get_job
    orig_job_response = server.job_response

    preset_id = "claude_review"
    if not generator_presets.generator_preset_exists(preset_id):
        # Fall back to whatever the registry exposes first, so a rename doesn't break us.
        preset_id = generator_presets.list_generator_presets()[0]["id"]
    preset = generator_presets.get_generator_preset(preset_id)

    # A. preset preserved + sampling overrides applied
    m = _base_manifest()
    m["generator_preset"] = preset_id
    cap = _run_retry(m)
    check(
        "A: generator_preset threaded into generate_study_guide",
        cap["gsg"].get("generator_preset") == preset_id,
        f"got {cap['gsg'].get('generator_preset')!r}",
    )
    bpc = cap["bpc"][-1]
    check(
        "A: provider config built with preset sampling overrides",
        bpc.get("temperature_override") == preset["temperature"]
        and bpc.get("top_p") == preset["top_p"]
        and bpc.get("max_tokens") == preset["max_tokens"]
        and bpc.get("qwen_thinking_enabled") == preset["thinking"],
        f"bpc={bpc}",
    )

    # B. no preset → default path, no sampling override
    cap = _run_retry(_base_manifest())
    bpc = cap["bpc"][-1]
    check(
        "B: no preset → generator_preset is None",
        cap["gsg"].get("generator_preset") is None,
        f"got {cap['gsg'].get('generator_preset')!r}",
    )
    check(
        "B: no preset → no temperature override (default path)",
        "temperature_override" not in bpc and "top_p" not in bpc and "max_tokens" not in bpc,
        f"bpc={bpc}",
    )

    # C. unknown/stale preset id → graceful degrade to default path (must not raise)
    m = _base_manifest()
    m["generator_preset"] = "no_such_preset_xyz"
    cap = _run_retry(m)
    bpc = cap["bpc"][-1]
    check(
        "C: stale preset id degrades to default (generator_preset None)",
        cap["gsg"].get("generator_preset") is None,
        f"got {cap['gsg'].get('generator_preset')!r}",
    )
    check(
        "C: stale preset id → no sampling override",
        "temperature_override" not in bpc,
        f"bpc={bpc}",
    )

    # D. End-to-end on a REAL on-disk job through the real _get_job/Job path: a
    #    preset-built failed job is retried; afterwards the manifest STILL records the
    #    same generator_preset (identity survives the rebuild). Only the LLM + render
    #    boundary is stubbed; everything else is the real retry path.
    server._get_job = orig_get_job          # use the REAL job resolver
    server.job_response = orig_job_response  # and the real response builder
    server.generate_study_guide = lambda source_text, **kwargs: "# Guide\n\nbody\n"
    server.build_provider_config = lambda *a, **k: object()
    run_markdown_job.run_raw_markdown_pipeline = lambda *a, **k: None

    job = Job.create({
        "status": "failed",
        "path_mode": "generate",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "title": "T",
        "prompt_name": "basic_study_guide",
        "generator_preset": preset_id,
    })
    (job.input_dir / "source.txt").write_text("Some source material.", encoding="utf-8")
    try:
        server.retry_failed_job(job.id)
        after = job.read_manifest()
        check(
            "D: real retry preserves generator_preset in the on-disk manifest",
            after.get("generator_preset") == preset_id,
            f"manifest generator_preset={after.get('generator_preset')!r}",
        )
    finally:
        shutil.rmtree(job.dir, ignore_errors=True)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
