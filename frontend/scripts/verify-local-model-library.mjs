// Unit/static harness for Local Model Manager Phase 2D library picker.
//
// Plain Node, no new dependency. Imports the REAL pure helper module and reads
// source files to verify endpoint wiring and UI-safety invariants.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  COMPANION_AUTH_FAILED,
  COMPANION_OFFLINE,
  COMPANION_REACHABLE,
  COMPANION_UNCONFIGURED,
  companionBadge,
  companionCapabilities,
  companionErrorMessage,
  companionState,
  formatModelModifiedAt,
  formatModelSize,
  isSafeRelativePath,
  libraryModelCount,
  libraryModels,
  libraryRootsConfigured,
  librarySelectionPreview,
  librarySelectionStale,
  libraryWarnings,
  normalizeLibraryModel,
  normalizeLibrarySelection,
  selectedLibraryModel,
} from "../src/localModelLibrary.js";
import {
  SAFE_SERVER_DEFAULTS,
  SAFE_TEST_PROFILE_ID,
  buildLocalModelServerStartPayload,
  buildLocalModelServerStopPayload,
  localModelServerErrorMessage,
  localModelServerIsManagedRunning,
  localModelServerStatusLabel,
  normalizeLocalModelServerState,
} from "../src/localModelServer.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

const statusReachable = {
  ok: true,
  configured: true,
  reachable: true,
  capabilities: ["scan"],
  error: null,
};
const statusUnconfigured = {
  ok: true,
  configured: false,
  reachable: false,
  error: { category: "companion_config", message: "Local model companion is not configured." },
};
const statusOffline = {
  ok: true,
  configured: true,
  reachable: false,
  error: { category: "companion_offline", message: "Local model companion is not reachable." },
};
const statusAuth = {
  ok: true,
  configured: true,
  reachable: false,
  error: { category: "companion_auth", message: "Local model companion authentication failed." },
};
const model = {
  id: "gguf_1",
  display_name: "Gemma 4 Q4",
  filename: "gemma-4-q4.gguf",
  relative_path: "family/gemma-4-q4.gguf",
  root_id: "default",
  size_bytes: 5 * 1024 * 1024 * 1024,
  modified_at: "2026-06-06T00:00:00Z",
  family_hint: "gemma",
  quant_hint: "Q4_K_M",
  server_compatible: true,
  secret_value: "secret-do-not-render",
};
const unsafeUnixModelPath = `/${["blocked", "model.gguf"].join("/")}`;
const library = {
  ok: true,
  configured: true,
  reachable: true,
  models: [model, model],
  model_count: 99,
  roots_configured: 1,
  warnings: [
    {
      code: "root_missing",
      message: "approved root does not exist",
      root_id: "default",
      relative_path: "safe/model.gguf",
    },
    {
      code: "bad_path",
      message: "path hidden",
      relative_path: unsafeUnixModelPath,
    },
  ],
};

// State normalization.
check("reachable companion -> reachable", companionState(statusReachable) === COMPANION_REACHABLE);
check("unconfigured companion -> unconfigured", companionState(statusUnconfigured) === COMPANION_UNCONFIGURED);
check("offline companion -> offline", companionState(statusOffline) === COMPANION_OFFLINE);
check("auth companion -> auth_failed", companionState(statusAuth) === COMPANION_AUTH_FAILED);
check("library fallback state works", companionState(null, statusOffline) === COMPANION_OFFLINE);
check("reachable badge", companionBadge(COMPANION_REACHABLE).label === "Reachable");
check("auth badge", companionBadge(COMPANION_AUTH_FAILED).label === "Auth failed");
check("capabilities filters strings", companionCapabilities({ capabilities: ["scan", 4, ""] }).join(",") === "scan");
check("error message prefers status", companionErrorMessage(statusAuth, library) === statusAuth.error.message);

// Model safety and formatting.
const normalized = normalizeLibraryModel(model);
const safeKeys = [
  "id",
  "display_name",
  "filename",
  "relative_path",
  "root_id",
  "size_bytes",
  "modified_at",
  "family_hint",
  "quant_hint",
  "server_compatible",
];
check("valid model normalizes", normalized?.id === "gguf_1");
check("normalized model keys are whitelisted", Object.keys(normalized).every((k) => safeKeys.includes(k)), Object.keys(normalized).join(","));
check("unapproved fields are dropped", !JSON.stringify(normalized).includes("secret-do-not-render"));
check("absolute relative_path rejected", normalizeLibraryModel({ ...model, id: "abs", relative_path: unsafeUnixModelPath }).relative_path === undefined);
check("traversal relative_path rejected", isSafeRelativePath("../model.gguf") === false);
check("safe nested relative_path accepted", isSafeRelativePath("models/a.gguf") === true);
check("libraryModels dedupes", libraryModels(library).length === 1);
check("libraryModelCount prefers backend count", libraryModelCount(library) === 99);
check("libraryModelCount falls back", libraryModelCount({ models: [model] }) === 1);
check("libraryRootsConfigured reads count", libraryRootsConfigured(library) === 1);
check("warnings keep safe relative path", libraryWarnings(library)[0].relative_path === "safe/model.gguf");
check("warnings drop unsafe relative path", libraryWarnings(library)[1].relative_path === undefined);
check("selected model lookup uses current library", selectedLibraryModel(library, "gguf_1")?.display_name === "Gemma 4 Q4");
check("unknown selected model -> null", selectedLibraryModel(library, "missing") === null);
check("saved selection normalizes", normalizeLibrarySelection({ selected: { ...model, selected_at: "2026-06-06T00:00:00Z" } })?.id === "gguf_1");
check("saved selection stale detects missing model", librarySelectionStale({ models: [] }, normalized) === true);
check("saved selection stale detects current model", librarySelectionStale(library, normalized) === false);
check("future preview drops unsafe path", librarySelectionPreview({ future_launch_preview: { model_id: "gguf_1", filename: "m.gguf", relative_path: unsafeUnixModelPath, profile: "gpu_default" } }).relative_path === undefined);
check("size formatter", formatModelSize(5 * 1024 * 1024 * 1024) === "5 GB");
check("modified formatter tolerates garbage", formatModelModifiedAt("not-a-date") === "not-a-date");

// Managed server payload/status helpers.
const startPayload = buildLocalModelServerStartPayload(normalized);
check("start payload exists for saved selection", startPayload?.model_id === "gguf_1");
check("start payload uses safe test profile", startPayload?.profile_id === SAFE_TEST_PROFILE_ID && SAFE_TEST_PROFILE_ID === "fake_test");
check("start payload includes only allowed top-level fields", JSON.stringify(Object.keys(startPayload).sort()) === JSON.stringify(["model_id", "parameters", "profile_id"]));
check("start payload includes only allowed parameter fields", JSON.stringify(Object.keys(startPayload.parameters).sort()) === JSON.stringify(["ctx_size", "gpu_layers", "port", "threads"]));
check("start payload uses fixed defaults", JSON.stringify(startPayload.parameters) === JSON.stringify(SAFE_SERVER_DEFAULTS));
check("start payload rejects invalid selection", buildLocalModelServerStartPayload({ id: "../bad" }) === null);
check("stop payload is bounded grace only", JSON.stringify(buildLocalModelServerStopPayload()) === JSON.stringify({ grace_seconds: 5 }));
check("running status label", localModelServerStatusLabel({ configured: true, reachable: true, state: "running", managed: true }) === "Running");
check("already_running status label", localModelServerStatusLabel({ configured: true, reachable: true, state: "already_running", managed: true }) === "Already running");
check("stopped status label", localModelServerStatusLabel({ configured: true, reachable: true, state: "stopped", managed: false }) === "Stopped");
check("not_running status label", localModelServerStatusLabel({ configured: true, reachable: true, state: "not_running", managed: false }) === "Not running");
check("companion offline status label", localModelServerStatusLabel({ configured: true, reachable: false, error: { category: "companion_offline" } }) === "Companion offline");
check("companion auth status label", localModelServerStatusLabel({ configured: true, reachable: false, error: { category: "companion_auth" } }) === "Companion auth failed");
check("unknown state normalizes", normalizeLocalModelServerState({ state: "surprise" }) === "unknown");
check("managed running predicate", localModelServerIsManagedRunning({ state: "running", managed: true }) === true);
check("unmanaged running is not stoppable", localModelServerIsManagedRunning({ state: "running", managed: false }) === false);
check("port conflict error copy", localModelServerErrorMessage({ error: { category: "port_in_use" } }) === "The requested port is already in use.");
check("invalid params error copy", localModelServerErrorMessage({ error: { category: "invalid_parameters" } }) === "The launch parameters were rejected.");
check("unknown model error copy", localModelServerErrorMessage({ error: { category: "unknown_model" } }) === "The saved selected model is not available in the companion library.");
check("unknown profile error copy", localModelServerErrorMessage({ error: { category: "unknown_profile" } }) === "The test launch profile is not available.");

// API helper paths/methods.
const clientSource = fs.readFileSync(path.join(root, "src/api/client.js"), "utf8");
check("companion status helper path", /function getLocalModelCompanionStatus\(\)[\s\S]*requestJson\("\/api\/local-model\/companion\/status"\)/.test(clientSource));
check("library helper path", /function getLocalModelLibrary\(\)[\s\S]*requestJson\("\/api\/local-model\/library"\)/.test(clientSource));
check("scan helper path and POST", /function scanLocalModelLibrary\(\)[\s\S]*requestJson\("\/api\/local-model\/library\/scan", \{ method: "POST" \}\)/.test(clientSource));
check("selection GET helper path", /function getLocalModelLibrarySelection\(\)[\s\S]*requestJson\("\/api\/local-model\/library\/selection"\)/.test(clientSource));
check("selection POST helper path and method", /function saveLocalModelLibrarySelection\(selection\)[\s\S]*requestJson\("\/api\/local-model\/library\/selection", \{[\s\S]*method: "POST"/.test(clientSource));
check("selection DELETE helper path and method", /function clearLocalModelLibrarySelection\(\)[\s\S]*requestJson\("\/api\/local-model\/library\/selection", \{ method: "DELETE" \}\)/.test(clientSource));
check("server status helper path", /function getLocalModelServerStatus\(\)[\s\S]*requestJson\("\/api\/local-model\/server\/status"\)/.test(clientSource));
check("server start helper path and POST", /function startLocalModelServer\(payload\)[\s\S]*requestJson\("\/api\/local-model\/server\/start", \{[\s\S]*method: "POST"/.test(clientSource));
check("server stop helper path and POST", /function stopLocalModelServer\(payload\)[\s\S]*requestJson\("\/api\/local-model\/server\/stop", \{[\s\S]*method: "POST"/.test(clientSource));
check("server restart helper path and POST", /function restartLocalModelServer\(payload\)[\s\S]*requestJson\("\/api\/local-model\/server\/restart", \{[\s\S]*method: "POST"/.test(clientSource));

// UI source invariants for the Phase 2D additions.
const panelSource = fs.readFileSync(path.join(root, "src/components/LocalModelsPanel.jsx"), "utf8");
const helperSource = fs.readFileSync(path.join(root, "src/localModelLibrary.js"), "utf8");
const serverHelperSource = fs.readFileSync(path.join(root, "src/localModelServer.js"), "utf8");
const librarySection = panelSource.slice(
  panelSource.indexOf("function ModelLibrarySection"),
  panelSource.indexOf("function Metric")
);
const managedServerSection = panelSource.slice(
  panelSource.indexOf("function ManagedServerSection"),
  panelSource.indexOf("function CompanionStateIcon")
);
check("Model Library section is present", librarySection.includes("Model Library"));
check("scan button label is present", librarySection.includes("Scan approved folder(s)"));
check("scan flow calls local scan helper", panelSource.includes("scanLocalModelLibrary") && panelSource.includes("fetchLibrary(true)"));
check("selected model UI state exists", panelSource.includes("selectedLibraryModelId") && panelSource.includes("setSelectedLibraryModelId"));
check("persisted selected model display exists", librarySection.includes("Chosen library model") && librarySection.includes("Remember selected model"));
check("stale selected model display exists", librarySection.includes("Saved but not in current library") && librarySection.includes("Scan approved folder(s) again"));
check("clear selection flow exists", librarySection.includes("Clear selection") && panelSource.includes("clearLocalModelLibrarySelection"));
check("selection save flow calls selection API", panelSource.includes("saveLocalModelLibrarySelection") && panelSource.includes("model_id: librarySelectedModel.id"));
check("saved selection preview exists", librarySection.includes("Saved selection preview"));
check("no Provider Settings writes in panel", !/(updateProviderSettings|setDefaultProvider|clearProviderKey|testProviderSettings|fetchProviderModels)\s*\(/.test(panelSource));
check("no Provider Settings calls in managed server section", !/(updateProviderSettings|setDefaultProvider|clearProviderKey|testProviderSettings|fetchProviderModels)\s*\(/.test(managedServerSection));
check("no Ask calls in managed server section", !/\/api\/ask|sendAskSessionMessage|createAskSession|prepareAskJobContext/.test(managedServerSection + serverHelperSource));
check("no browser storage in new library/server files", !/(localStorage|sessionStorage)/.test(librarySection + managedServerSection + helperSource + serverHelperSource));
check("no raw HTML rendering", !/(dangerouslySetInnerHTML)/.test(librarySection + managedServerSection + helperSource + serverHelperSource));
check("no connection detail strings in new UI slice", !/(Authorization|Bearer|LMM_COMPANION|socket|token)/.test(librarySection + managedServerSection + helperSource + serverHelperSource));
check("no free-form command args UI", !/(textarea|argv|args|shell flags|arbitrary JSON)/.test(managedServerSection + serverHelperSource));
check("managed server section is present", managedServerSection.includes("Managed Server"));
check("start disabled without selected model", managedServerSection.includes("!hasSelection") && managedServerSection.includes("disabled={!canStart}"));
check("manual helper fallback remains", panelSource.includes("How to start llama-server (manual)") && panelSource.includes("CommandHelper"));
check("stop copy says companion-managed only", managedServerSection.includes("Stops only the companion-managed server."));
check("provider settings unchanged copy present", managedServerSection.includes("Provider Settings are not changed."));
check("start copy says companion-managed only", managedServerSection.includes("Starts companion-managed server only."));
check("restart uses explicit selected-model payload", panelSource.includes("call = restartLocalModelServer") && panelSource.includes("payload = startPayload") && !managedServerSection.includes("reuse_last"));
check("start payload is built from saved selection", panelSource.includes("savedServerSelection = normalizeLibrarySelection(librarySelectionData)") && panelSource.includes("buildLocalModelServerStartPayload(savedServerSelection)"));
check("start payload JSON has no unsafe fields", !/(executable|model_path|command|args|--|absolute_path|secret_value)/.test(JSON.stringify(startPayload)));
check("no raw absolute path rendering", !/\/home\/|\/tmp\/|[A-Za-z]:\\\\/.test(managedServerSection + serverHelperSource));

if (failed) {
  console.error(`\n${failed} local-model-library check(s) failed.`);
  process.exit(1);
}
console.log("\nAll local-model-library checks passed.");
