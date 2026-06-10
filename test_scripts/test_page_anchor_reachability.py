#!/usr/bin/env python3
"""Focused proof for Slice 23A: page anchors reach LLM prompt assembly.

This is intentionally a measurement test, not a generation-behavior test. It
proves that source text containing extraction-style ``## Page N`` anchors
survives into the model-facing user message assembled by ``pipeline.orchestrator``
without enabling citation directives or assuming rendered guide citations exist.

    python test_scripts/test_page_anchor_reachability.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.job_manager import Job  # noqa: E402
from pipeline.orchestrator import (  # noqa: E402
    build_messages,
    build_messages_for_preset,
)
from pipeline.run_llm_job import AttachmentSource, _attach_sources  # noqa: E402

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "page_anchor_reachability"
    / "extracted_pages.txt"
)

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _user(messages: list[dict]) -> str:
    return next(message["content"] for message in messages if message["role"] == "user")


def _system(messages: list[dict]) -> str:
    return next(message["content"] for message in messages if message["role"] == "system")


def test_direct_template_prompt_preserves_anchors() -> None:
    source = (
        "## Page 1\n"
        "Alpha lecture text about entropy.\n\n"
        "## Page 2\n"
        "Beta lecture text about enthalpy."
    )
    messages = build_messages(source, title="Anchor Proof", prompt_name="basic_study_guide")
    user_content = _user(messages)
    system_content = _system(messages)

    check("direct/template: user message contains Page 1 anchor", "## Page 1" in user_content)
    check("direct/template: user message contains Page 2 anchor", "## Page 2" in user_content)
    check(
        "direct/template: lecture text around anchors is preserved",
        "Alpha lecture text about entropy." in user_content
        and "Beta lecture text about enthalpy." in user_content,
    )
    check(
        "direct/template: anchor order survives",
        user_content.find("## Page 1") < user_content.find("## Page 2"),
    )
    check(
        "direct/template: no page-citation directive enabled by default",
        "Do not invent page numbers" not in system_content
        and "(page N)" not in system_content,
    )
    check(
        "direct/template: no generated citation is assumed",
        "(page 1)" not in user_content
        and "(pages 1-2)" not in user_content
        and "[Source Page 1]" not in user_content,
    )


def test_fixture_text_with_surrounding_lecture_content_preserves_anchors() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    messages = build_messages(source, title="Fixture Anchor Proof")
    user_content = _user(messages)

    check("fixture/template: Page 1 anchor reaches user message", "## Page 1" in user_content)
    check("fixture/template: Page 2 anchor reaches user message", "## Page 2" in user_content)
    check(
        "fixture/template: pre-anchor lecture text reaches user message",
        "Lecture overview before the anchors." in user_content,
    )
    check(
        "fixture/template: between-anchor lecture text reaches user message",
        "Instructor note between pages" in user_content,
    )
    check(
        "fixture/template: post-anchor lecture text reaches user message",
        "Intermediate gradients are reused" in user_content,
    )


def test_attachment_augmented_source_reaches_template_prompt() -> None:
    job: Job | None = None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            job = Job("anchor-attach-proof", root=Path(tmp))
            job.input_dir.mkdir(parents=True, exist_ok=False)
            augmented, report = _attach_sources(
                job,
                "Base typed source before attachments.",
                [AttachmentSource(path=FIXTURE, filename="lecture anchors.txt")],
            )
            messages = build_messages(augmented, title="Attachment Anchor Proof")
            user_content = _user(messages)

            check("attachment: fixture extracted successfully", report["files"][0]["status"] == "extracted")
            check("attachment: attached source section present", "## Attached Sources" in user_content)
            check("attachment: sanitized attachment heading present", "### lecture_anchors.txt" in user_content)
            check("attachment: Page 1 anchor reaches model-facing user message", "## Page 1" in user_content)
            check("attachment: Page 2 anchor reaches model-facing user message", "## Page 2" in user_content)
            check(
                "attachment: base typed source remains before attached source",
                user_content.find("Base typed source before attachments.")
                < user_content.find("## Attached Sources")
                < user_content.find("## Page 1")
                < user_content.find("## Page 2"),
            )
        finally:
            if job is not None:
                shutil.rmtree(job.dir, ignore_errors=True)


def test_preset_prompt_uses_source_as_user_message_verbatim() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    messages = build_messages_for_preset(source, system_prompt="Preset system prompt.")
    user_content = _user(messages)
    system_content = _system(messages)

    check("preset: user message is exactly the source text", user_content == source)
    check("preset: Page 1 anchor reaches user message", "## Page 1" in user_content)
    check("preset: Page 2 anchor reaches user message", "## Page 2" in user_content)
    check(
        "preset: no page-citation directive enabled by default",
        "Do not invent page numbers" not in system_content
        and "(page N)" not in system_content,
    )


def run() -> bool:
    test_direct_template_prompt_preserves_anchors()
    test_fixture_text_with_surrounding_lecture_content_preserves_anchors()
    test_attachment_augmented_source_reaches_template_prompt()
    test_preset_prompt_uses_source_as_user_message_verbatim()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
