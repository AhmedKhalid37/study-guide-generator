// Pure status helpers for the read-only Local Models panel (LMM Slice 3).
//
// These normalize the detection-only status DTO from the backend
// (GET /api/local-model/status, POST /api/local-model/check — LMM Slice 2,
// pipeline/provider_config.get_local_model_status) into a small, stable state
// vocabulary the UI maps to pills + copy. They are PURE functions (no React, no
// imports) so a node harness can unit-test them, and so every surface derives
// state the SAME way. The backend owns the truth; this layer only SHAPES it and
// must tolerate missing/garbage fields (old backend, partial payloads) without
// throwing. It never reconstructs a full URL and never surfaces a raw key — it
// only reads the already-safe fields the backend chose to expose.

export const STATE_REACHABLE = "reachable";
export const STATE_OFFLINE = "offline";
export const STATE_NOT_CONFIGURED = "not_configured";
export const STATE_ERROR = "error";
export const STATE_UNKNOWN = "unknown"; // no/garbage status (e.g. old backend)

// Derive the panel state from a status DTO. Order matters:
//   * reachable === true                      -> reachable (server answered)
//   * no base URL configured                  -> not_configured
//   * connection failure (local_offline)      -> offline
//   * auth/model/other classified error       -> error
//   * not reachable, no error info            -> offline (calm default)
// A missing/non-object status (failed request, old backend) -> unknown.
export function localServerState(status) {
  if (!status || typeof status !== "object") return STATE_UNKNOWN;
  if (status.reachable === true) return STATE_REACHABLE;
  if (status.base_url_configured === false) return STATE_NOT_CONFIGURED;

  const category = status.error?.category;
  if (category === "provider_config") return STATE_NOT_CONFIGURED;
  if (category === "local_offline") return STATE_OFFLINE;
  if (typeof category === "string" && category) return STATE_ERROR;

  // Not reachable with no usable error info: treat as a calm offline rather than
  // a scary error — the server simply did not answer.
  return STATE_OFFLINE;
}

// Display metadata per state. `tone` is a stable, CSS-agnostic key the UI maps to
// colours (mirrors shortcutStatus.js). Copy is calm and non-alarming.
const STATE_META = {
  [STATE_REACHABLE]: { label: "Reachable", tone: "reachable" },
  [STATE_OFFLINE]: { label: "Offline", tone: "offline" },
  [STATE_NOT_CONFIGURED]: { label: "Not configured", tone: "neutral" },
  [STATE_ERROR]: { label: "Error", tone: "error" },
  [STATE_UNKNOWN]: { label: "Status unavailable", tone: "neutral" },
};

export function stateBadge(state) {
  return STATE_META[state] || STATE_META[STATE_UNKNOWN];
}

// Convenience: the badge for a whole status DTO.
export function statusBadge(status) {
  return stateBadge(localServerState(status));
}

// Safe accessor for the discovered model id list (tolerates missing/non-array).
export function statusModels(status) {
  const list = status?.models;
  return Array.isArray(list) ? list.filter((m) => typeof m === "string" && m) : [];
}

// Model count: prefer the backend's count, fall back to the array length. Never
// NaN — an absent/garbage count degrades to the visible list length.
export function statusModelCount(status) {
  const n = status?.model_count;
  if (Number.isFinite(n) && n >= 0) return n;
  return statusModels(status).length;
}

// Compact display split for the model chips: the first `limit` ids plus an
// overflow count, so the panel never renders an unbounded wall of chips.
export function modelChips(status, limit = 12) {
  const models = statusModels(status);
  const max = Number.isFinite(limit) && limit > 0 ? limit : models.length;
  return { shown: models.slice(0, max), overflow: Math.max(0, models.length - max) };
}

// Latency, only when it is a real measurement (reachable probes). Offline /
// unconfigured states return null and the UI shows an em dash.
export function statusLatencyMs(status) {
  const ms = status?.latency_ms;
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

// The already-redacted error message, if any. Never a stack trace, full URL, or
// key — the backend caps + redacts it; this only passes it through safely.
export function statusErrorMessage(status) {
  const msg = status?.error?.message;
  return typeof msg === "string" && msg ? msg : null;
}

// Backend notes array (e.g. the --host 0.0.0.0 gotcha), tolerating missing data.
export function statusNotes(status) {
  const list = status?.notes;
  return Array.isArray(list) ? list.filter((n) => typeof n === "string" && n) : [];
}

// Normalize the action descriptors into a stable, render-safe shape. Unknown /
// malformed entries are dropped. `enabled` defaults to true ONLY when the field
// is explicitly true — anything else (false, missing, non-bool) is disabled, so
// a planned-but-not-built action can never render as an enabled control.
export function statusActions(status) {
  const list = status?.actions;
  if (!Array.isArray(list)) return [];
  return list
    .filter((a) => a && typeof a.id === "string" && a.id)
    .map((a) => ({
      id: a.id,
      label: typeof a.label === "string" && a.label ? a.label : a.id,
      enabled: a.enabled === true,
      reason: typeof a.reason === "string" && a.reason ? a.reason : null,
    }));
}

// Find a single action by id (or null). Used to wire the "Edit local provider
// settings" link without hardcoding its position in the array.
export function findAction(status, id) {
  return statusActions(status).find((a) => a.id === id) || null;
}

// Ids that would START / STOP / control a host process. This slice is
// detection-only: NONE of these may ever be enabled. The helper exists so the
// harness can assert that invariant against any status payload.
const PROCESS_CONTROL_IDS = new Set([
  "start_server",
  "stop_server",
  "restart_server",
]);

export function hasEnabledProcessControl(status) {
  return statusActions(status).some(
    (a) => a.enabled && PROCESS_CONTROL_IDS.has(a.id)
  );
}
