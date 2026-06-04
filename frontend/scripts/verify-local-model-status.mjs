// Unit harness for the read-only Local Models status helpers (LMM Slice 3).
//
// Mirrors the existing verify-shortcut-status.mjs pattern (plain node, no test
// runner, no new dependency). Imports the REAL src/localModelStatus.js — pure ESM
// with no React/JSX, so node loads it directly. Run:
//
//   node scripts/verify-local-model-status.mjs
//
// Proves: state normalization across reachable / offline / not-configured /
// error / missing-fields, badge label+tone mapping, model list count + display
// limit, latency/error/notes accessors, action enabled/disabled mapping, and the
// hard invariant that NO start/stop process-control action is ever enabled.

import {
  findAction,
  hasEnabledProcessControl,
  localServerState,
  modelChips,
  stateBadge,
  statusActions,
  statusBadge,
  statusErrorMessage,
  statusLatencyMs,
  statusModelCount,
  statusModels,
  statusNotes,
  STATE_ERROR,
  STATE_NOT_CONFIGURED,
  STATE_OFFLINE,
  STATE_REACHABLE,
  STATE_UNKNOWN,
} from "../src/localModelStatus.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// Representative DTOs mirroring pipeline/provider_config.get_local_model_status.
const reachable = {
  ok: true,
  provider: "local",
  configured: true,
  base_url_host: "host.docker.internal",
  base_url_configured: true,
  in_docker: true,
  reachable: true,
  models: ["gemma-4-it", "llama-3"],
  model_count: 2,
  default_model: "gemma-4-it",
  selected_model: "gemma-4-it",
  latency_ms: 42,
  error: null,
  actions: [
    { id: "open_provider_settings", label: "Edit local provider settings", enabled: true },
    { id: "copy_start_command", label: "Copy llama-server start command", enabled: false, reason: "Planned." },
  ],
  notes: [],
};
const offline = {
  ok: true,
  reachable: false,
  base_url_host: "host.docker.internal",
  base_url_configured: true,
  models: [],
  model_count: 0,
  latency_ms: null,
  error: { category: "local_offline", message: "Local model server is offline — start llama-server." },
  notes: ["Make sure llama-server binds --host 0.0.0.0 (not 127.0.0.1) so the container can reach it."],
};
const notConfigured = {
  ok: true,
  reachable: false,
  base_url_host: null,
  base_url_configured: false,
  models: [],
  model_count: 0,
  latency_ms: null,
  error: { category: "provider_config", message: "No local base URL is configured." },
  notes: [],
};
const errored = {
  ok: true,
  reachable: false,
  base_url_host: "host.docker.internal",
  base_url_configured: true,
  models: [],
  model_count: 0,
  latency_ms: null,
  error: { category: "provider_auth", message: "Authentication failed." },
  notes: [],
};

// ── state normalization ──────────────────────────────────────────────────────
check("reachable DTO -> reachable", localServerState(reachable) === STATE_REACHABLE);
check("offline DTO -> offline", localServerState(offline) === STATE_OFFLINE);
check("no base URL -> not_configured", localServerState(notConfigured) === STATE_NOT_CONFIGURED);
check("auth error -> error", localServerState(errored) === STATE_ERROR);
check(
  "provider_config category -> not_configured even if flag missing",
  localServerState({ reachable: false, error: { category: "provider_config" } }) === STATE_NOT_CONFIGURED
);
check(
  "not reachable, no error info -> offline (calm default)",
  localServerState({ reachable: false }) === STATE_OFFLINE
);

// ── missing-fields fallbacks ─────────────────────────────────────────────────
check("undefined status -> unknown (no crash)", localServerState(undefined) === STATE_UNKNOWN);
check("null status -> unknown", localServerState(null) === STATE_UNKNOWN);
check("non-object status -> unknown", localServerState("nope") === STATE_UNKNOWN);
check("empty object -> offline (reachable not true)", localServerState({}) === STATE_OFFLINE);

// ── badge label + tone mapping ───────────────────────────────────────────────
check("badge(reachable) label/tone", stateBadge(STATE_REACHABLE).label === "Reachable" && stateBadge(STATE_REACHABLE).tone === "reachable");
check("badge(offline) label/tone", stateBadge(STATE_OFFLINE).label === "Offline" && stateBadge(STATE_OFFLINE).tone === "offline");
check("badge(not_configured) label/tone", stateBadge(STATE_NOT_CONFIGURED).label === "Not configured" && stateBadge(STATE_NOT_CONFIGURED).tone === "neutral");
check("badge(error) label/tone", stateBadge(STATE_ERROR).label === "Error" && stateBadge(STATE_ERROR).tone === "error");
check("badge(unknown) label/tone", stateBadge(STATE_UNKNOWN).label === "Status unavailable" && stateBadge(STATE_UNKNOWN).tone === "neutral");
check("badge(garbage) defaults to unknown", stateBadge("???").label === "Status unavailable");
check("statusBadge resolves through state", statusBadge(reachable).label === "Reachable");

// ── model list helpers ───────────────────────────────────────────────────────
check("statusModels returns the ids", statusModels(reachable).join(",") === "gemma-4-it,llama-3");
check("statusModels tolerates missing", statusModels({}).length === 0);
check("statusModels filters non-strings", statusModels({ models: ["a", 5, null, "b"] }).join(",") === "a,b");
check("statusModelCount prefers backend count", statusModelCount(reachable) === 2);
check("statusModelCount falls back to length", statusModelCount({ models: ["a", "b", "c"] }) === 3);
check("statusModelCount of empty is 0 (no NaN)", statusModelCount({}) === 0);

const many = { models: Array.from({ length: 30 }, (_, i) => `m${i}`), model_count: 30 };
const chips = modelChips(many, 12);
check("modelChips limits shown to 12", chips.shown.length === 12, JSON.stringify(chips.shown.length));
check("modelChips reports overflow", chips.overflow === 18, String(chips.overflow));
check("modelChips no overflow when under limit", modelChips(reachable, 12).overflow === 0);

// ── latency / error / notes accessors ────────────────────────────────────────
check("latency for reachable is the int", statusLatencyMs(reachable) === 42);
check("latency for offline is null", statusLatencyMs(offline) === null);
check("latency tolerates garbage", statusLatencyMs({ latency_ms: "soon" }) === null);
check("errorMessage for offline", statusErrorMessage(offline) === offline.error.message);
check("errorMessage for reachable is null", statusErrorMessage(reachable) === null);
check("errorMessage tolerates missing", statusErrorMessage({}) === null);
check("notes returns the array", statusNotes(offline).length === 1);
check("notes tolerates missing", statusNotes(reachable).length === 0);
check("notes tolerates non-array", statusNotes({ notes: "x" }).length === 0);

// ── action enabled/disabled mapping ──────────────────────────────────────────
const acts = statusActions(reachable);
check("statusActions returns both descriptors", acts.length === 2);
check("open_provider_settings enabled", findAction(reachable, "open_provider_settings").enabled === true);
check("copy_start_command disabled", findAction(reachable, "copy_start_command").enabled === false);
check("copy_start_command carries reason", findAction(reachable, "copy_start_command").reason === "Planned.");
check("findAction unknown id -> null", findAction(reachable, "nope") === null);
check("statusActions tolerates missing", statusActions({}).length === 0);
check(
  "enabled defaults false unless explicitly true",
  statusActions({ actions: [{ id: "x" }, { id: "y", enabled: "yes" }] }).every((a) => a.enabled === false)
);
check(
  "malformed action entries dropped",
  statusActions({ actions: [null, { label: "no id" }, { id: "ok" }] }).length === 1
);

// ── hard invariant: NO enabled process control, ever ─────────────────────────
check("reachable DTO has no enabled process control", hasEnabledProcessControl(reachable) === false);
check("offline DTO has no enabled process control", hasEnabledProcessControl(offline) === false);
check(
  "a disabled start_server is still NOT enabled control",
  hasEnabledProcessControl({ actions: [{ id: "start_server", enabled: false }] }) === false
);
check(
  "an enabled start_server WOULD be flagged (guard works)",
  hasEnabledProcessControl({ actions: [{ id: "start_server", enabled: true }] }) === true
);

if (failed) {
  console.error(`\n${failed} local-model-status check(s) failed.`);
  process.exit(1);
}
console.log("\nAll local-model-status checks passed.");
