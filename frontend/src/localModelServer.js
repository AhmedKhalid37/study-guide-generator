// Pure helpers for Local Model Manager Phase 2G4 managed-server controls.
//
// This frontend slice builds only a safe companion-bridge payload from the saved
// selected library model plus fixed typed defaults. It never accepts runnable
// binary details, filesystem locations, free-form process flags, raw connection
// details, or arbitrary browser JSON.

export const SERVER_STOPPED = "stopped";
export const SERVER_RUNNING = "running";
export const SERVER_ALREADY_RUNNING = "already_running";
export const SERVER_NOT_RUNNING = "not_running";
export const SERVER_STARTING = "starting";
export const SERVER_STOPPING = "stopping";
export const SERVER_CRASHED = "crashed";
export const SERVER_ERROR = "error";
export const SERVER_UNKNOWN = "unknown";

export const SAFE_TEST_PROFILE_ID = "fake_test";

export const SAFE_SERVER_DEFAULTS = Object.freeze({
  port: 18080,
  ctx_size: 2048,
  gpu_layers: 0,
  threads: 2,
});

const KNOWN_STATES = new Set([
  SERVER_STOPPED,
  SERVER_RUNNING,
  SERVER_ALREADY_RUNNING,
  SERVER_NOT_RUNNING,
  SERVER_STARTING,
  SERVER_STOPPING,
  SERVER_CRASHED,
  SERVER_ERROR,
  SERVER_UNKNOWN,
]);

const ERROR_LABELS = {
  not_running: "No companion-managed server is running.",
  already_running: "A companion-managed server is already running.",
  port_in_use: "The requested port is already in use.",
  invalid_parameters: "The launch parameters were rejected.",
  unknown_model: "The saved selected model is not available in the companion library.",
  unknown_profile: "The test launch profile is not available.",
  executable_missing: "The configured server executable was not found.",
  permission_denied: "The configured server executable is not runnable.",
  companion_config: "Companion is not configured.",
  companion_offline: "Companion is offline.",
  companion_timeout: "Companion did not respond in time.",
  companion_auth: "Companion authentication failed.",
  model_load_failed: "The selected model could not be loaded.",
  model_may_be_too_large: "The selected model may be too large for available memory.",
  readiness_timeout: "The managed server did not become ready in time.",
  process_start_failed: "The companion-managed process did not start.",
  process_crashed: "The companion-managed process exited unexpectedly.",
  process_error: "Companion process state is unavailable.",
};

function safeIdentifier(value, maxLen = 240) {
  if (typeof value !== "string") return null;
  const text = value.replace(/\0/g, "").trim();
  if (!text || text.length > maxLen) return null;
  if (!/^[A-Za-z0-9._:-]+$/.test(text)) return null;
  return text;
}

function boundedInt(value, fallback, min, max) {
  if (typeof value !== "number" || !Number.isInteger(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}

export function buildLocalModelServerStartPayload(selection, overrides = {}) {
  const modelId = safeIdentifier(selection?.id || selection?.model_id);
  if (!modelId) return null;
  const defaults = SAFE_SERVER_DEFAULTS;
  return {
    model_id: modelId,
    profile_id: SAFE_TEST_PROFILE_ID,
    parameters: {
      port: boundedInt(overrides.port, defaults.port, 1024, 65535),
      ctx_size: boundedInt(overrides.ctx_size, defaults.ctx_size, 512, 131072),
      gpu_layers: boundedInt(overrides.gpu_layers, defaults.gpu_layers, 0, 999),
      threads: boundedInt(overrides.threads, defaults.threads, 1, 256),
    },
  };
}

export function buildLocalModelServerStopPayload() {
  return { grace_seconds: 5 };
}

export function normalizeLocalModelServerState(status) {
  const state = typeof status?.state === "string" ? status.state : SERVER_UNKNOWN;
  return KNOWN_STATES.has(state) ? state : SERVER_UNKNOWN;
}

export function localModelServerIsManagedRunning(status) {
  const state = normalizeLocalModelServerState(status);
  return status?.managed === true && (state === SERVER_RUNNING || state === SERVER_ALREADY_RUNNING);
}

export function localModelServerStatusLabel(status) {
  if (!status || typeof status !== "object") return "Status unavailable";
  if (status.configured === false) return "Companion unconfigured";
  if (status.reachable === false) {
    const category = status.error?.category;
    if (category === "companion_auth") return "Companion auth failed";
    return "Companion offline";
  }
  const state = normalizeLocalModelServerState(status);
  const labels = {
    [SERVER_STOPPED]: "Stopped",
    [SERVER_RUNNING]: "Running",
    [SERVER_ALREADY_RUNNING]: "Already running",
    [SERVER_NOT_RUNNING]: "Not running",
    [SERVER_STARTING]: "Starting",
    [SERVER_STOPPING]: "Stopping",
    [SERVER_CRASHED]: "Crashed",
    [SERVER_ERROR]: "Error",
    [SERVER_UNKNOWN]: "Unknown",
  };
  return labels[state] || labels[SERVER_UNKNOWN];
}

export function localModelServerErrorMessage(status) {
  const error = status?.error;
  if (!error || typeof error !== "object") return null;
  const category = typeof error.category === "string" ? error.category : "";
  const label = ERROR_LABELS[category];
  if (label) return label;
  return typeof error.message === "string" && error.message ? error.message : "Managed server status error.";
}
