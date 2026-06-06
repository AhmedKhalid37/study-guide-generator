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
  libraryWarnings,
  normalizeLibraryModel,
  selectedLibraryModel,
} from "../src/localModelLibrary.js";

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
  transport: "unix_socket",
  socket_label: "configured",
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
  absolute_path: "/home/user/secret/gemma.gguf",
  token: "tok-secret-do-not-render",
  Authorization: "Bearer nope",
};
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
      relative_path: "/home/user/secret/model.gguf",
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
check("unsafe absolute fields are dropped", !JSON.stringify(normalized).includes("/home/user/secret") && !JSON.stringify(normalized).includes("tok-secret"));
check("absolute relative_path rejected", normalizeLibraryModel({ ...model, id: "abs", relative_path: "/tmp/model.gguf" }).relative_path === undefined);
check("traversal relative_path rejected", isSafeRelativePath("../model.gguf") === false);
check("safe nested relative_path accepted", isSafeRelativePath("models/a.gguf") === true);
check("libraryModels dedupes", libraryModels(library).length === 1);
check("libraryModelCount prefers backend count", libraryModelCount(library) === 99);
check("libraryModelCount falls back", libraryModelCount({ models: [model] }) === 1);
check("libraryRootsConfigured reads count", libraryRootsConfigured(library) === 1);
check("warnings keep safe relative path", libraryWarnings(library)[0].relative_path === "safe/model.gguf");
check("warnings drop unsafe relative path", libraryWarnings(library)[1].relative_path === undefined);
check("selected model is frontend-state lookup only", selectedLibraryModel(library, "gguf_1")?.display_name === "Gemma 4 Q4");
check("unknown selected model -> null", selectedLibraryModel(library, "missing") === null);
check("size formatter", formatModelSize(5 * 1024 * 1024 * 1024) === "5 GB");
check("modified formatter tolerates garbage", formatModelModifiedAt("not-a-date") === "not-a-date");

// API helper paths/methods.
const clientSource = fs.readFileSync(path.join(root, "src/api/client.js"), "utf8");
check("companion status helper path", /function getLocalModelCompanionStatus\(\)[\s\S]*requestJson\("\/api\/local-model\/companion\/status"\)/.test(clientSource));
check("library helper path", /function getLocalModelLibrary\(\)[\s\S]*requestJson\("\/api\/local-model\/library"\)/.test(clientSource));
check("scan helper path and POST", /function scanLocalModelLibrary\(\)[\s\S]*requestJson\("\/api\/local-model\/library\/scan", \{ method: "POST" \}\)/.test(clientSource));

// UI source invariants for the Phase 2D additions.
const panelSource = fs.readFileSync(path.join(root, "src/components/LocalModelsPanel.jsx"), "utf8");
const helperSource = fs.readFileSync(path.join(root, "src/localModelLibrary.js"), "utf8");
const librarySection = panelSource.slice(
  panelSource.indexOf("function ModelLibrarySection"),
  panelSource.indexOf("function Metric")
);
check("Model Library section is present", librarySection.includes("Model Library"));
check("scan button label is present", librarySection.includes("Scan approved folder(s)"));
check("scan flow calls local scan helper", panelSource.includes("scanLocalModelLibrary") && panelSource.includes("fetchLibrary(true)"));
check("selection uses React state only", panelSource.includes("selectedLibraryModelId") && !librarySection.includes("updateProviderSettings"));
check("no Provider Settings writes in panel", !/(updateProviderSettings|setDefaultProvider|clearProviderKey|testProviderSettings|fetchProviderModels)\s*\(/.test(panelSource));
check("no browser storage in new library files", !/(localStorage|sessionStorage)/.test(librarySection + helperSource));
check("no raw HTML rendering", !/(dangerouslySetInnerHTML)/.test(librarySection + helperSource));
check("no token/connection secret strings in new UI slice", !/(Authorization|Bearer|LMM_COMPANION|socket_path|token)/.test(librarySection + helperSource));
check("no process-control routes in frontend client", !/\/api\/local-model\/server\/(start|stop|restart)/.test(clientSource));
check("new library UI has no process-control labels", !/\b(Start|Stop|Restart)\b/.test(librarySection));

if (failed) {
  console.error(`\n${failed} local-model-library check(s) failed.`);
  process.exit(1);
}
console.log("\nAll local-model-library checks passed.");
