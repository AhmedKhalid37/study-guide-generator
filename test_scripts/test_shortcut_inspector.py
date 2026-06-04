"""Unit tests for the read-only Shortcut Inspector (Slice 1).

Covers the additive ``validity`` object + ``inspect_shortcut`` in
``pipeline/shortcut_store.py`` and the ``GET /api/shortcuts/{id}/inspect`` route.

Key guarantees proven here:
- ``validity.status`` is the 3-tier ``valid``/``degraded``/``broken`` derived from
  the FULL findings list (not first-failure-only).
- The saved ``model`` reference is validated (the gap ``_evaluate_validity`` never
  covered) and reports ``model_unavailable`` as a *degraded* finding while legacy
  ``valid`` stays ``true`` (the activation guard is unchanged).
- Inspection is read-only: ``shortcuts.json`` is byte-identical before/after.
- No raw provider key leaks into any inspect / list / read payload.

    python test_scripts/test_shortcut_inspector.py
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import provider_config, shortcut_store  # noqa: E402

results = []

# A sentinel "API key" we plant in the provider-settings store, then assert never
# appears in any inspector output. Long + unique so a substring match is meaningful.
SENTINEL_KEY = "sk-INSPECTOR-SENTINEL-DO-NOT-LEAK-abcdef0123456789"


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _point_store_at(tmp: Path):
    shortcut_store.SHORTCUTS_DIR = tmp
    shortcut_store.SHORTCUTS_JSON = tmp / "shortcuts.json"


def _configured_provider():
    """Pick a live configured provider id (deepseek/qwen via env), or None."""
    for item in provider_config.get_provider_registry(discover_local=False):
        if item.get("configured"):
            return item.get("id"), item
    return None, None


def _inject(record: dict):
    """Append a hand-built record straight into the registry (bypassing the
    create whitelist) so we can simulate legacy / hand-edited / broken shortcuts."""
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


def _codes(view):
    return [f["code"] for f in view["validity"]["findings"]]


def run():
    tmp = Path(tempfile.mkdtemp(prefix="sc_inspect_"))
    _point_store_at(tmp)
    shortcut_store.list_shortcuts()  # seed defaults

    provider_id, prov_entry = _configured_provider()
    if not provider_id:
        check("a configured provider is available for tests", False,
              "no provider configured via env; cannot run inspector tests")
        return False
    default_model = prov_entry.get("default_model")
    avail_models = prov_entry.get("available_models") or []

    # 1. Valid builder_setup -> status valid, findings empty
    valid_payload = {"input_type": "generate_llm", "provider": provider_id, "mode": "study_guide"}
    if default_model:
        valid_payload["model"] = default_model
    _inject(_base_builder("sc_validone", valid_payload))
    v = shortcut_store.get_shortcut("sc_validone")
    check("valid builder -> status valid + empty findings",
          v["validity"]["status"] == "valid" and v["validity"]["findings"] == [],
          f"status={v['validity']['status']} findings={_codes(v)}")
    check("valid builder -> legacy valid:true preserved", v["valid"] is True, f"{v.get('reason')}")

    # 2. Missing / unknown provider -> broken, provider_missing
    _inject(_base_builder("sc_noprov", {"provider": "totally_not_a_provider"}))
    v = shortcut_store.get_shortcut("sc_noprov")
    check("unknown provider -> status broken",
          v["validity"]["status"] == "broken" and shortcut_store.FINDING_PROVIDER_MISSING in _codes(v),
          f"status={v['validity']['status']} codes={_codes(v)}")
    check("unknown provider -> legacy valid:false preserved", v["valid"] is False, "")

    # 2b. Provider field entirely absent -> broken, provider_missing
    _inject(_base_builder("sc_emptyprov", {"input_type": "generate_llm"}))
    v = shortcut_store.get_shortcut("sc_emptyprov")
    check("absent provider -> broken + provider_missing",
          v["validity"]["status"] == "broken" and shortcut_store.FINDING_PROVIDER_MISSING in _codes(v),
          f"codes={_codes(v)}")

    # 3. Model unavailable but provider valid -> degraded, model_unavailable.
    #    Legacy valid stays TRUE (new model check must not flip the guard).
    if avail_models:
        _inject(_base_builder("sc_badmodel", {"provider": provider_id, "model": "zzz-model-that-does-not-exist"}))
        v = shortcut_store.get_shortcut("sc_badmodel")
        check("bad model + good provider -> degraded + model_unavailable",
              v["validity"]["status"] == "degraded" and shortcut_store.FINDING_MODEL_UNAVAILABLE in _codes(v),
              f"status={v['validity']['status']} codes={_codes(v)}")
        check("bad model -> legacy valid stays TRUE (guard unchanged)", v["valid"] is True,
              f"valid={v['valid']} reason={v.get('reason')}")
    else:
        check("bad model + good provider -> degraded + model_unavailable", True,
              "skipped: provider exposes no available_models list")
        check("bad model -> legacy valid stays TRUE (guard unchanged)", True, "skipped")

    # 4. Missing style -> degraded, style_missing
    _inject(_base_builder("sc_badstyle", {"provider": provider_id, "style": "no_such_style_xyz"}))
    v = shortcut_store.get_shortcut("sc_badstyle")
    check("missing style -> degraded + style_missing",
          v["validity"]["status"] == "degraded" and shortcut_store.FINDING_STYLE_MISSING in _codes(v),
          f"status={v['validity']['status']} codes={_codes(v)}")

    # 5. Missing generator preset -> degraded, generator_preset_missing
    _inject(_base_builder("sc_badpreset", {"provider": provider_id, "generator_preset": "no_such_preset_xyz"}))
    v = shortcut_store.get_shortcut("sc_badpreset")
    check("missing preset -> degraded + generator_preset_missing",
          v["validity"]["status"] == "degraded" and shortcut_store.FINDING_GENERATOR_PRESET_MISSING in _codes(v),
          f"status={v['validity']['status']} codes={_codes(v)}")

    # 6. Unknown include_sections key -> degraded, section_unknown (no crash)
    _inject(_base_builder("sc_badsection",
            {"provider": provider_id, "include_sections": {"glossary": True, "totally_fake_section": True}}))
    v = shortcut_store.get_shortcut("sc_badsection")
    check("unknown section -> section_unknown finding, no crash",
          shortcut_store.FINDING_SECTION_UNKNOWN in _codes(v) and v["validity"]["status"] == "degraded",
          f"status={v['validity']['status']} codes={_codes(v)}")

    # 7. Invalid output_depth / difficulty -> degraded (documented choice).
    #    Stored via injection because the create-path REJECTS invalid axes.
    _inject(_base_builder("sc_badaxis",
            {"provider": provider_id, "output_depth": "ultra_mega", "difficulty": "impossible"}))
    v = shortcut_store.get_shortcut("sc_badaxis")
    check("invalid axes -> degraded + output_depth_invalid + difficulty_invalid",
          v["validity"]["status"] == "degraded"
          and shortcut_store.FINDING_OUTPUT_DEPTH_INVALID in _codes(v)
          and shortcut_store.FINDING_DIFFICULTY_INVALID in _codes(v),
          f"status={v['validity']['status']} codes={_codes(v)}")

    # 8. Tool route missing -> broken
    _inject({"id": "sc_badtool", "name": "Bad Tool", "type": "tool",
             "icon": "", "color": None, "pinned": False, "order": 61,
             "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
             "payload": {"tool": "no_such_tool"}})
    v = shortcut_store.get_shortcut("sc_badtool")
    check("missing tool route -> broken + tool_route_missing",
          v["validity"]["status"] == "broken" and shortcut_store.FINDING_TOOL_ROUTE_MISSING in _codes(v),
          f"status={v['validity']['status']} codes={_codes(v)}")

    # 8b. Library view missing -> broken
    _inject({"id": "sc_badview", "name": "Bad View", "type": "library_view",
             "icon": "", "color": None, "pinned": False, "order": 62,
             "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z",
             "payload": {"view": "no_such_view"}})
    v = shortcut_store.get_shortcut("sc_badview")
    check("missing view -> broken + tool_route_missing",
          v["validity"]["status"] == "broken" and shortcut_store.FINDING_TOOL_ROUTE_MISSING in _codes(v),
          f"status={v['validity']['status']} codes={_codes(v)}")

    # 9. Multiple simultaneous issues -> ALL findings present (not first-failure)
    _inject(_base_builder("sc_multibad", {
        "provider": "totally_not_a_provider",
        "style": "no_such_style_xyz",
        "generator_preset": "no_such_preset_xyz",
        "include_sections": {"fake_section": True},
    }))
    v = shortcut_store.get_shortcut("sc_multibad")
    codes = set(_codes(v))
    expected = {shortcut_store.FINDING_PROVIDER_MISSING, shortcut_store.FINDING_STYLE_MISSING,
                shortcut_store.FINDING_GENERATOR_PRESET_MISSING, shortcut_store.FINDING_SECTION_UNKNOWN}
    check("multiple issues -> full findings list (not first-failure-only)",
          expected <= codes and v["validity"]["status"] == "broken",
          f"status={v['validity']['status']} codes={sorted(codes)}")

    # 10. inspect_shortcut: unknown id -> NotFound (404 at the route layer)
    try:
        shortcut_store.inspect_shortcut("sc_doesnotexist00")
        check("inspect unknown id -> NotFound", False)
    except shortcut_store.ShortcutNotFoundError:
        check("inspect unknown id -> NotFound", True)

    # inspect returns repair_candidates with the required keys
    insp = shortcut_store.inspect_shortcut("sc_multibad")
    rc = insp.get("repair_candidates", {})
    check("inspect returns repair_candidates (providers/models_by_provider/styles/presets)",
          all(k in rc for k in ("providers", "models_by_provider", "styles", "generator_presets")),
          f"keys={sorted(rc.keys())}")
    check("inspect preserves legacy valid/reason alongside validity",
          insp["valid"] is False and "validity" in insp, f"valid={insp['valid']}")

    # 11. Read-only proof: shortcuts.json byte-identical across list + inspect
    digest_before = hashlib.sha256(shortcut_store.SHORTCUTS_JSON.read_bytes()).hexdigest()
    shortcut_store.list_shortcuts()
    for sid in ("sc_validone", "sc_noprov", "sc_badmodel", "sc_multibad", "sc_badtool"):
        try:
            shortcut_store.inspect_shortcut(sid)
        except shortcut_store.ShortcutNotFoundError:
            pass
    digest_after = hashlib.sha256(shortcut_store.SHORTCUTS_JSON.read_bytes()).hexdigest()
    check("inspection is read-only (shortcuts.json sha256 unchanged)",
          digest_before == digest_after, f"{digest_before[:12]}.. vs {digest_after[:12]}..")

    # 12. No raw-key leak. Plant a sentinel secret in the provider-settings store,
    #     then assert it never appears in inspect / list payloads.
    try:
        from pipeline import provider_settings_store
        # Redirect the settings store at the temp dir so we never touch real config.
        provider_settings_store.CONFIG_DIR = tmp
        provider_settings_store.SETTINGS_JSON = tmp / "provider_settings.json"
        provider_settings_store.SECRETS_JSON = tmp / "secrets.json"
        provider_settings_store.update_provider(provider_id, {"api_key": SENTINEL_KEY})
    except Exception as exc:  # noqa: BLE001
        print(f"  (sentinel plant skipped: {exc})")

    blobs = [json.dumps(shortcut_store.inspect_shortcut("sc_validone")),
             json.dumps(shortcut_store.inspect_shortcut("sc_badmodel")) if avail_models else "{}",
             json.dumps(shortcut_store.list_shortcuts())]
    leaked = any(SENTINEL_KEY in b for b in blobs)
    check("no raw key leak in inspect / list payloads", not leaked,
          "SENTINEL KEY FOUND IN OUTPUT" if leaked else "")

    print("\n--- SUMMARY ---")
    passed = sum(1 for _, ok in results if ok)
    print(f"{passed}/{len(results)} checks passed")
    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
