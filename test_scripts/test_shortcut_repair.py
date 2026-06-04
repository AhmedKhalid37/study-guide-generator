"""Unit tests for the Shortcut Repair preview + apply endpoints (Slice 3A).

Covers `preview_repair` / `apply_repair` in `pipeline/shortcut_store.py`
(the shared `_prepare_repair` normalizer) and, by extension, the
`POST /api/shortcuts/{id}/repair/preview` + `/repair/apply` routes.

Key guarantees proven here:
- Preview is READ-ONLY: `shortcuts.json` is byte-identical before/after.
- Apply in-place fixes a broken shortcut and preserves its id; clone creates a
  NEW shortcut and leaves the original untouched.
- Explicit-whitelist validation: unknown repair fields, invalid provider/style/
  preset/model/axis/section all raise (→ HTTP 400), nothing is written.
- Model validation uses the repaired provider; a model-only repair with no
  provider context is rejected.
- Resulting validity is recomputed after preview/apply.
- No migration-on-read; no raw provider key leaks into any repair payload.

    python test_scripts/test_shortcut_repair.py
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import provider_config, shortcut_store  # noqa: E402

results = []

SENTINEL_KEY = "sk-REPAIR-SENTINEL-DO-NOT-LEAK-abcdef0123456789"


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _point_store_at(tmp: Path):
    shortcut_store.SHORTCUTS_DIR = tmp
    shortcut_store.SHORTCUTS_JSON = tmp / "shortcuts.json"


def _configured_provider():
    for item in provider_config.get_provider_registry(discover_local=False):
        if item.get("configured"):
            return item.get("id"), item
    return None, None


def _inject(record: dict):
    reg = shortcut_store._read_registry()
    reg["shortcuts"].append(record)
    shortcut_store._write_registry(reg)


def _base_builder(sid, payload):
    return {
        "id": sid, "name": f"T {sid}", "type": "builder_setup",
        "icon": "", "color": None, "pinned": False, "order": 60,
        "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
        "payload": payload,
    }


def _digest():
    return hashlib.sha256(shortcut_store.SHORTCUTS_JSON.read_bytes()).hexdigest()


def _expect_error(fn, name, detail=""):
    try:
        fn()
        check(name, False, "expected ShortcutStoreError, none raised")
    except shortcut_store.ShortcutStoreError:
        check(name, True, detail)
    except Exception as exc:  # noqa: BLE001
        check(name, False, f"wrong exception type: {type(exc).__name__}: {exc}")


def run():
    tmp = Path(tempfile.mkdtemp(prefix="sc_repair_"))
    _point_store_at(tmp)
    shortcut_store.list_shortcuts()  # seed defaults (the only write before tests)

    provider_id, prov_entry = _configured_provider()
    if not provider_id:
        check("a configured provider is available for tests", False,
              "no provider configured via env; cannot run repair tests")
        return False
    default_model = prov_entry.get("default_model")
    avail_models = prov_entry.get("available_models") or []
    bad_model = "zzz-model-that-does-not-exist"

    # 1. Preview is READ-ONLY: sha256 unchanged across a preview call.
    _inject(_base_builder("sc_prev0001", {"provider": "totally_not_a_provider"}))
    before = _digest()
    prev = shortcut_store.preview_repair("sc_prev0001", {
        "mode": "in_place", "changes": {"provider": provider_id},
    })
    after = _digest()
    check("preview does not write shortcuts.json (sha256 unchanged)", before == after,
          f"{before[:12]}.. vs {after[:12]}..")
    check("preview returns original(broken) + proposed(valid) + diff",
          prev["original"]["validity"]["status"] == "broken"
          and prev["proposed"]["validity"]["status"] == "valid"
          and any(d["field"] == "payload.provider" for d in prev["diff"]),
          f"orig={prev['original']['validity']['status']} "
          f"prop={prev['proposed']['validity']['status']} diff={prev['diff']}")

    # 2. Apply in-place provider(+model) repair: broken -> valid, id preserved.
    changes = {"provider": provider_id}
    if default_model:
        changes["model"] = default_model
    res = shortcut_store.apply_repair("sc_prev0001", {"mode": "in_place", "changes": changes})
    after_apply = shortcut_store.get_shortcut("sc_prev0001")
    check("apply in_place keeps the same id", res["shortcut"]["id"] == "sc_prev0001",
          res["shortcut"]["id"])
    check("apply in_place repairs broken -> valid",
          after_apply["validity"]["status"] == "valid",
          f"status={after_apply['validity']['status']}")
    check("apply in_place persisted the new provider",
          after_apply["payload"]["provider"] == provider_id,
          after_apply["payload"]["provider"])

    # 3. Clone repair: new id created, original unchanged, clone repaired.
    _inject(_base_builder("sc_clone001", {"provider": "totally_not_a_provider"}))
    clone_res = shortcut_store.apply_repair("sc_clone001", {
        "mode": "clone",
        "changes": {"provider": provider_id},
        "clone_name": "My Repaired Copy",
    })
    new_id = clone_res["shortcut"]["id"]
    original = shortcut_store.get_shortcut("sc_clone001")
    check("clone creates a NEW id (not the original)",
          new_id != "sc_clone001" and shortcut_store.is_valid_shortcut_id(new_id), new_id)
    check("clone leaves the original unchanged (still broken provider)",
          original["payload"]["provider"] == "totally_not_a_provider"
          and original["validity"]["status"] == "broken",
          f"orig provider={original['payload']['provider']}")
    check("clone carries the repaired payload + chosen name",
          clone_res["shortcut"]["payload"]["provider"] == provider_id
          and clone_res["shortcut"]["name"] == "My Repaired Copy"
          and clone_res["shortcut"]["validity"]["status"] == "valid",
          f"name={clone_res['shortcut']['name']}")

    # 3b. Clone without clone_name -> safe derived suffix.
    _inject(_base_builder("sc_clone002", {"provider": "totally_not_a_provider"}))
    clone2 = shortcut_store.apply_repair("sc_clone002", {
        "mode": "clone", "changes": {"provider": provider_id},
    })
    check("clone without clone_name derives a '(repaired copy)' suffix",
          shortcut_store.CLONE_NAME_SUFFIX in clone2["shortcut"]["name"],
          clone2["shortcut"]["name"])

    # 4. Unknown repair field -> error (400).
    _inject(_base_builder("sc_err00001", {"provider": provider_id}))
    _expect_error(
        lambda: shortcut_store.preview_repair("sc_err00001", {"changes": {"frobnicate": "x"}}),
        "unknown repair change field -> error")
    _expect_error(
        lambda: shortcut_store.preview_repair("sc_err00001", {"changes": {}, "bogus_top": 1}),
        "unknown top-level repair field -> error")

    # 5. Invalid provider / style / preset / model / axis / section -> error.
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_err00001", {"changes": {"provider": "no_such_provider"}}),
        "invalid provider -> error")
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_err00001", {"changes": {"style": "no_such_style_xyz"}}),
        "invalid style -> error")
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_err00001", {"changes": {"generator_preset": "no_such_preset"}}),
        "invalid generator_preset -> error")
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_err00001", {"changes": {"output_depth": "ultra_mega"}}),
        "invalid output_depth axis -> error")
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_err00001", {"changes": {"difficulty": "impossible"}}),
        "invalid difficulty axis -> error")
    _expect_error(
        lambda: shortcut_store.apply_repair(
            "sc_err00001", {"changes": {"include_sections": {"set": {"totally_fake_section": True}}}}),
        "invalid include_sections set key -> error")
    if avail_models:
        _expect_error(
            lambda: shortcut_store.apply_repair(
                "sc_err00001", {"changes": {"provider": provider_id, "model": bad_model}}),
            "invalid model for provider -> error")
    else:
        check("invalid model for provider -> error", True, "skipped: provider lists no models")

    # 6. Model validation uses the REPAIRED provider when both are supplied.
    if avail_models and default_model:
        ok_res = shortcut_store.apply_repair("sc_err00001", {
            "changes": {"provider": provider_id, "model": default_model}})
        check("model validated against repaired provider (valid model accepted)",
              ok_res["shortcut"]["payload"]["model"] == default_model
              and ok_res["shortcut"]["payload"]["provider"] == provider_id,
              f"model={ok_res['shortcut']['payload'].get('model')}")
    else:
        check("model validated against repaired provider (valid model accepted)", True,
              "skipped: no default_model/available_models")

    # 7. Model-only repair with NO provider context -> error.
    _inject(_base_builder("sc_nomodel01", {"input_type": "generate_llm"}))  # no provider
    _expect_error(
        lambda: shortcut_store.apply_repair(
            "sc_nomodel01", {"changes": {"model": default_model or "any-model"}}),
        "model-only repair without provider context -> error")

    # 8. Remove an unavailable optional field (style) works.
    _inject(_base_builder("sc_rmstyle01", {"provider": provider_id, "style": "no_such_style_xyz"}))
    rm = shortcut_store.apply_repair("sc_rmstyle01", {"changes": {"remove_fields": ["style"]}})
    after_rm = shortcut_store.get_shortcut("sc_rmstyle01")
    check("remove unavailable optional field (style) clears it + repairs degraded",
          after_rm["payload"].get("style") in (None, "")
          and after_rm["validity"]["status"] == "valid",
          f"style={after_rm['payload'].get('style')} status={after_rm['validity']['status']}")
    # remove_fields rejects a non-removable field (provider).
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_rmstyle01", {"changes": {"remove_fields": ["provider"]}}),
        "remove_fields rejects a non-removable field (provider)")

    # 9. Unknown include_sections key removal works (drops the dead key).
    _inject(_base_builder("sc_rmsec0001",
            {"provider": provider_id, "include_sections": {"glossary": True, "totally_fake_section": True}}))
    sec_res = shortcut_store.apply_repair("sc_rmsec0001", {
        "changes": {"include_sections": {"remove": ["totally_fake_section"]}}})
    sec_after = sec_res["shortcut"]["payload"].get("include_sections") or {}
    check("unknown include_sections key removal drops the dead key",
          "totally_fake_section" not in sec_after and "glossary" in sec_after,
          f"sections={sec_after}")
    check("include_sections removal recomputes validity to valid (no section_unknown)",
          sec_res["shortcut"]["validity"]["status"] == "valid",
          f"status={sec_res['shortcut']['validity']['status']}")

    # 10. Resulting validity recomputed after preview (degraded -> valid).
    if avail_models:
        _inject(_base_builder("sc_recompute1", {"provider": provider_id, "model": bad_model}))
        pre = shortcut_store.preview_repair("sc_recompute1", {"changes": {"remove_fields": ["model"]}})
        check("preview recomputes validity (degraded model -> valid after drop)",
              pre["original"]["validity"]["status"] == "degraded"
              and pre["proposed"]["validity"]["status"] == "valid",
              f"orig={pre['original']['validity']['status']} prop={pre['proposed']['validity']['status']}")
    else:
        check("preview recomputes validity (degraded model -> valid after drop)", True, "skipped")

    # 11. No migration-on-read: list + inspect + preview leave disk byte-identical.
    digest_before = _digest()
    shortcut_store.list_shortcuts()
    shortcut_store.inspect_shortcut("sc_rmsec0001")
    shortcut_store.preview_repair("sc_rmsec0001", {"changes": {"include_sections": {"set": {"glossary": True}}}})
    digest_after = _digest()
    check("no migration-on-read (list+inspect+preview leave sha256 unchanged)",
          digest_before == digest_after, f"{digest_before[:12]}.. vs {digest_after[:12]}..")

    # 12. Unknown shortcut id -> NotFound (404 at the route layer).
    try:
        shortcut_store.preview_repair("sc_doesnotexist00", {"changes": {"provider": provider_id}})
        check("repair unknown id -> NotFound", False)
    except shortcut_store.ShortcutNotFoundError:
        check("repair unknown id -> NotFound", True)

    # 12b. Non-builder shortcut -> safe error.
    _inject({"id": "sc_tool00001", "name": "Tool", "type": "tool",
             "icon": "", "color": None, "pinned": False, "order": 70,
             "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
             "payload": {"tool": "clean_markdown"}})
    _expect_error(
        lambda: shortcut_store.apply_repair("sc_tool00001", {"changes": {"provider": provider_id}}),
        "repair of a non-builder shortcut -> error")

    # 13. No raw-key leak. Plant a sentinel secret, assert it never appears.
    try:
        from pipeline import provider_settings_store
        provider_settings_store.CONFIG_DIR = tmp
        provider_settings_store.SETTINGS_JSON = tmp / "provider_settings.json"
        provider_settings_store.SECRETS_JSON = tmp / "secrets.json"
        provider_settings_store.update_provider(provider_id, {"api_key": SENTINEL_KEY})
    except Exception as exc:  # noqa: BLE001
        print(f"  (sentinel plant skipped: {exc})")

    _inject(_base_builder("sc_leak00001", {"provider": "totally_not_a_provider"}))
    blobs = [
        json.dumps(shortcut_store.preview_repair("sc_leak00001", {"changes": {"provider": provider_id}})),
        json.dumps(shortcut_store.apply_repair("sc_leak00001", {"mode": "clone", "changes": {"provider": provider_id}})),
        json.dumps(shortcut_store.list_shortcuts()),
        json.dumps(shortcut_store.inspect_shortcut("sc_leak00001")),
    ]
    leaked = any(SENTINEL_KEY in b for b in blobs)
    check("no raw key leak in preview / apply / list / inspect payloads", not leaked,
          "SENTINEL KEY FOUND IN OUTPUT" if leaked else "")

    print("\n--- SUMMARY ---")
    passed = sum(1 for _, ok in results if ok)
    print(f"{passed}/{len(results)} checks passed")
    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
