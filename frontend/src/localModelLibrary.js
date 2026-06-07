// Pure helpers for the Local Model Manager Phase 2D library picker.
//
// The backend bridge already whitelists/redacts companion payloads. This module
// keeps the UI defensive: it accepts only display-safe model fields, rejects
// absolute/traversal paths, normalizes companion states, and stores no settings.

export const COMPANION_REACHABLE = "reachable";
export const COMPANION_UNCONFIGURED = "unconfigured";
export const COMPANION_OFFLINE = "offline";
export const COMPANION_AUTH_FAILED = "auth_failed";
export const COMPANION_ERROR = "error";
export const COMPANION_UNKNOWN = "unknown";

const SAFE_MODEL_FIELDS = new Set([
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
]);

const COMPANION_STATE_META = {
  [COMPANION_REACHABLE]: { label: "Reachable", tone: "reachable" },
  [COMPANION_UNCONFIGURED]: { label: "Unconfigured", tone: "neutral" },
  [COMPANION_OFFLINE]: { label: "Offline", tone: "offline" },
  [COMPANION_AUTH_FAILED]: { label: "Auth failed", tone: "error" },
  [COMPANION_ERROR]: { label: "Error", tone: "error" },
  [COMPANION_UNKNOWN]: { label: "Unavailable", tone: "neutral" },
};

export function companionState(status, library = null) {
  const source = status && typeof status === "object" ? status : library;
  if (!source || typeof source !== "object") return COMPANION_UNKNOWN;
  if (source.reachable === true) return COMPANION_REACHABLE;
  if (source.configured === false || source.error?.category === "companion_config") {
    return COMPANION_UNCONFIGURED;
  }
  if (source.error?.category === "companion_auth") return COMPANION_AUTH_FAILED;
  if (
    source.error?.category === "companion_offline" ||
    source.error?.category === "companion_timeout"
  ) {
    return COMPANION_OFFLINE;
  }
  if (typeof source.error?.category === "string" && source.error.category) {
    return COMPANION_ERROR;
  }
  return COMPANION_OFFLINE;
}

export function companionBadge(state) {
  return COMPANION_STATE_META[state] || COMPANION_STATE_META[COMPANION_UNKNOWN];
}

export function companionErrorMessage(status, library = null) {
  const fromStatus = status?.error?.message;
  if (typeof fromStatus === "string" && fromStatus) return fromStatus;
  const fromLibrary = library?.error?.message;
  return typeof fromLibrary === "string" && fromLibrary ? fromLibrary : null;
}

export function companionCapabilities(status) {
  const list = status?.capabilities;
  return Array.isArray(list) ? list.filter((v) => typeof v === "string" && v) : [];
}

function safeText(value, maxLen = 240) {
  if (typeof value !== "string") return null;
  const cleaned = value.replace(/\0/g, "").trim();
  return cleaned ? cleaned.slice(0, maxLen) : null;
}

export function isSafeRelativePath(value) {
  const text = safeText(value, 500);
  if (!text) return false;
  const normalized = text.replace(/\\/g, "/");
  if (normalized.startsWith("/") || /^[A-Za-z]:\//.test(normalized)) return false;
  const parts = normalized.split("/");
  return parts.every((part) => part && part !== "." && part !== "..");
}

export function normalizeLibraryModel(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = safeText(raw.id, 500);
  if (!id) return null;

  const model = { id };
  for (const field of SAFE_MODEL_FIELDS) {
    if (field === "id") continue;
    const value = raw[field];
    if (field === "relative_path") {
      if (isSafeRelativePath(value)) model.relative_path = safeText(value, 500).replace(/\\/g, "/");
      continue;
    }
    if (field === "size_bytes") {
      if (Number.isSafeInteger(value) && value >= 0) model.size_bytes = value;
      continue;
    }
    if (field === "server_compatible") {
      if (typeof value === "boolean") model.server_compatible = value;
      continue;
    }
    const text = safeText(value, field === "filename" ? 500 : 240);
    if (text) model[field] = text;
  }
  return model;
}

export function libraryModels(data) {
  const list = data?.models;
  if (!Array.isArray(list)) return [];
  const seen = new Set();
  const models = [];
  for (const raw of list) {
    const model = normalizeLibraryModel(raw);
    if (!model || seen.has(model.id)) continue;
    seen.add(model.id);
    models.push(model);
  }
  return models;
}

export function libraryModelCount(data) {
  const count = data?.model_count;
  if (Number.isSafeInteger(count) && count >= 0) return count;
  return libraryModels(data).length;
}

export function libraryRootsConfigured(data) {
  const count = data?.roots_configured;
  return Number.isSafeInteger(count) && count >= 0 ? count : 0;
}

export function libraryRootSummaries(data) {
  const list = data?.roots;
  if (!Array.isArray(list)) return [];
  const seen = new Set();
  const roots = [];
  for (const item of list) {
    if (!item || typeof item !== "object") continue;
    const id = safeText(item.id, 120);
    if (!id || !/^[A-Za-z0-9._:-]+$/.test(id) || seen.has(id)) continue;
    seen.add(id);
    const summary = {
      id,
      recursive: item.recursive === true,
    };
    if (Number.isSafeInteger(item.model_count) && item.model_count >= 0) {
      summary.model_count = item.model_count;
    }
    roots.push(summary);
  }
  return roots;
}

export function libraryWarnings(data) {
  const list = data?.warnings;
  if (!Array.isArray(list)) return [];
  return list
    .filter((item) => item && typeof item === "object")
    .map((item) => {
      const warning = {};
      const code = safeText(item.code, 80);
      const message = safeText(item.message, 240);
      const rootId = safeText(item.root_id, 120);
      const relativePath = isSafeRelativePath(item.relative_path)
        ? safeText(item.relative_path, 500).replace(/\\/g, "/")
        : null;
      if (code) warning.code = code;
      if (message) warning.message = message;
      if (rootId) warning.root_id = rootId;
      if (relativePath) warning.relative_path = relativePath;
      if (Number.isSafeInteger(item.count) && item.count >= 0) warning.count = item.count;
      return warning;
    })
    .filter((item) => Object.keys(item).length > 0);
}

export function formatModelSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "Unknown size";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1;
  const formatted = value.toFixed(digits).replace(/\.0$/, "");
  return `${formatted} ${units[unit]}`;
}

export function formatModelModifiedAt(value) {
  const text = safeText(value, 80);
  if (!text) return "Modified date unknown";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function selectedLibraryModel(data, selectedId) {
  if (typeof selectedId !== "string" || !selectedId) return null;
  return libraryModels(data).find((model) => model.id === selectedId) || null;
}

export function normalizeLibrarySelection(data) {
  const selected = data?.selected;
  if (!selected || typeof selected !== "object") return null;
  const model = normalizeLibraryModel(selected);
  if (!model) return null;
  const selectedAt = safeText(selected.selected_at, 80);
  if (selectedAt) model.selected_at = selectedAt;
  return model;
}

export function librarySelectionPreview(data) {
  const preview = data?.future_launch_preview;
  if (!preview || typeof preview !== "object") return null;
  const out = {};
  const profile = safeText(preview.profile, 120);
  const modelId = safeText(preview.model_id, 500);
  const filename = safeText(preview.filename, 500);
  const relativePath = isSafeRelativePath(preview.relative_path)
    ? safeText(preview.relative_path, 500).replace(/\\/g, "/")
    : null;
  const rootId = safeText(preview.root_id, 120);
  const resolver = safeText(preview.resolver, 120);
  if (profile) out.profile = profile;
  if (modelId) out.model_id = modelId;
  if (filename) out.filename = filename;
  if (relativePath) out.relative_path = relativePath;
  if (rootId) out.root_id = rootId;
  if (resolver) out.resolver = resolver;
  out.runnable_command = preview.runnable_command === true;
  return Object.keys(out).length ? out : null;
}

export function librarySelectionStale(library, selected) {
  if (!selected?.id || !library || typeof library !== "object") return false;
  return !libraryModels(library).some((model) => model.id === selected.id);
}
