// Pure helpers for Local Model Manager Phase 2G6 managed-server controls.
//
// This frontend slice builds only a safe companion-bridge payload from the saved
// selected library model plus backend-sanitized profile schemas. It never accepts
// runnable binary details, filesystem locations, free-form process flags, raw
// connection details, or arbitrary browser JSON.

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
  ctx_size: 4096,
  gpu_layers: 0,
  threads: 8,
});

export const SAFE_PARAMETER_NAMES = Object.freeze([
  "port",
  "ctx_size",
  "gpu_layers",
  "threads",
  "parallel",
  "cache_type_k",
  "cache_type_v",
  "flash_attention",
  "mmap",
]);

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
  unknown_profile: "The launch profile is not available.",
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

function safeText(value, fallback = "", maxLen = 240) {
  if (typeof value !== "string") return fallback;
  return value.replace(/\0/g, "").trim().slice(0, maxLen) || fallback;
}

function normalizeParameterSchema(name, schema) {
  if (!SAFE_PARAMETER_NAMES.includes(name) || !schema || typeof schema !== "object") return null;
  const type = schema.type;
  if (!["integer", "boolean", "enum"].includes(type)) return null;
  const normalized = {
    name,
    type,
    label: safeText(schema.label, name.replaceAll("_", " "), 120),
    help: safeText(schema.help, "", 500),
    required: schema.required === true,
  };
  if (type === "integer") {
    if (!Number.isInteger(schema.min) || !Number.isInteger(schema.max) || schema.min > schema.max) return null;
    if (!Number.isInteger(schema.default) || schema.default < schema.min || schema.default > schema.max) return null;
    normalized.min = schema.min;
    normalized.max = schema.max;
    normalized.default = schema.default;
    return normalized;
  }
  if (type === "boolean") {
    if (typeof schema.default !== "boolean") return null;
    normalized.default = schema.default;
    return normalized;
  }
  const allowed = Array.isArray(schema.allowed_values)
    ? schema.allowed_values.filter((item) => typeof item === "string" && /^[A-Za-z0-9_.:-]{1,40}$/.test(item))
    : [];
  if (!allowed.includes(schema.default)) return null;
  normalized.allowed_values = allowed;
  normalized.default = schema.default;
  return normalized;
}

export function normalizeLocalModelServerProfile(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = safeIdentifier(raw.id, 80);
  if (!id) return null;
  const rawParameters = raw.parameters && typeof raw.parameters === "object" ? raw.parameters : {};
  const parameters = {};
  for (const name of SAFE_PARAMETER_NAMES) {
    const schema = normalizeParameterSchema(name, rawParameters[name]);
    if (schema) parameters[name] = schema;
  }
  if (Object.keys(parameters).length === 0) return null;
  return {
    id,
    display_name: safeText(raw.display_name, id, 120),
    description: safeText(raw.description, "", 500),
    type: raw.type === "fake_test" ? "fake_test" : raw.type === "llama_server" ? "llama_server" : "unknown",
    test_profile: raw.test_profile === true,
    runnable: raw.runnable === true,
    runnable_reason: typeof raw.runnable_reason === "string" ? raw.runnable_reason : null,
    default_parameters: localModelServerProfileDefaults({ parameters }),
    parameters,
    warnings: Array.isArray(raw.warnings)
      ? raw.warnings.filter((item) => typeof item === "string" && item.trim()).map((item) => safeText(item, "", 500)).slice(0, 8)
      : [],
  };
}

export function localModelServerProfiles(data) {
  if (!data || typeof data !== "object" || !Array.isArray(data.profiles)) return [];
  const seen = new Set();
  const profiles = [];
  for (const item of data.profiles) {
    const profile = normalizeLocalModelServerProfile(item);
    if (!profile || seen.has(profile.id)) continue;
    seen.add(profile.id);
    profiles.push(profile);
  }
  return profiles;
}

export function localModelServerProfileDefaults(profile) {
  const defaults = {};
  const parameters = profile?.parameters && typeof profile.parameters === "object" ? profile.parameters : {};
  for (const name of SAFE_PARAMETER_NAMES) {
    if (parameters[name]) defaults[name] = parameters[name].default;
  }
  return defaults;
}

export function safestRunnableServerProfile(profiles) {
  const list = Array.isArray(profiles) ? profiles : [];
  const runnable = list.filter((profile) => profile?.runnable === true);
  return (
    runnable.find((profile) => profile.id === "cpu_safe") ||
    runnable.find((profile) => !profile.test_profile) ||
    runnable.find((profile) => profile.id === SAFE_TEST_PROFILE_ID) ||
    null
  );
}

export function profileById(profiles, profileId) {
  const id = safeIdentifier(profileId, 80);
  if (!id || !Array.isArray(profiles)) return null;
  return profiles.find((profile) => profile.id === id) || null;
}

export function coerceProfileParameterValue(schema, value) {
  if (!schema || typeof schema !== "object") return undefined;
  if (value === undefined || value === null || value === "") return schema.default;
  if (schema.type === "integer") {
    const parsed = typeof value === "number" ? value : Number(value);
    if (!Number.isInteger(parsed)) return schema.default;
    return boundedInt(parsed, schema.default, schema.min, schema.max);
  }
  if (schema.type === "boolean") return value === true;
  if (schema.type === "enum") return schema.allowed_values.includes(value) ? value : schema.default;
  return undefined;
}

export function buildLocalModelServerStartPayload(selection, profile, overrides = {}) {
  const modelId = safeIdentifier(selection?.id || selection?.model_id);
  if (!modelId) return null;
  const selectedProfile = normalizeLocalModelServerProfile(profile);
  if (!selectedProfile || !selectedProfile.runnable) return null;
  const parameters = {};
  for (const name of SAFE_PARAMETER_NAMES) {
    const schema = selectedProfile.parameters[name];
    if (!schema) continue;
    parameters[name] = coerceProfileParameterValue(schema, overrides[name]);
  }
  return {
    model_id: modelId,
    profile_id: selectedProfile.id,
    parameters,
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
