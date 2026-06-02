const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = (
  RAW_API_BASE_URL === undefined ? DEFAULT_API_BASE_URL : RAW_API_BASE_URL
).replace(/\/+$/, "");

async function requestJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    let message = `API request failed: ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (data.detail?.message) {
        message = data.detail.message;
      }
    } catch {
      // Keep the status-based fallback when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

export function getHealth() {
  return requestJson("/api/health");
}

export function getOptions() {
  return requestJson("/api/options");
}

export function getJobs() {
  return requestJson("/api/jobs");
}

export function getPresets() {
  return requestJson("/api/presets");
}

export function applyPreset(presetId) {
  return requestJson(`/api/presets/${encodeURIComponent(presetId)}/apply`, {
    method: "POST"
  });
}

export function setJobFavorite(jobId, value) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/favorite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value })
  });
}

export function trashJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/trash`, {
    method: "POST"
  });
}

export function restoreJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/restore`, {
    method: "POST"
  });
}

export function getTrash() {
  return requestJson("/api/jobs/trash");
}

export function purgeTrashedJob(jobId) {
  return requestJson(`/api/jobs/trash/${encodeURIComponent(jobId)}`, {
    method: "DELETE"
  });
}

export function emptyTrash() {
  return requestJson("/api/jobs/trash", {
    method: "DELETE"
  });
}

export function getStyles() {
  return requestJson("/api/styles");
}

export function getStyle(styleId) {
  return requestJson(`/api/styles/${encodeURIComponent(styleId)}`);
}

export function createStyle({ name, description = "", content, baseStyle = null, tags = [] }) {
  return requestJson("/api/styles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, content, base_style: baseStyle, tags })
  });
}

export function updateStyle(styleId, { name, description, content, tags }) {
  const body = {};
  if (name !== undefined) body.name = name;
  if (description !== undefined) body.description = description;
  if (content !== undefined) body.content = content;
  if (tags !== undefined) body.tags = tags;
  return requestJson(`/api/styles/${encodeURIComponent(styleId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export function deleteStyle(styleId) {
  return requestJson(`/api/styles/${encodeURIComponent(styleId)}`, {
    method: "DELETE"
  });
}

export function generateStyle({ description, baseStyle = null, provider = null, model = null }) {
  return requestJson("/api/styles/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, base_style: baseStyle, provider, model })
  });
}

export function getLibrary(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, String(value));
    }
  });
  const suffix = query.toString();
  return requestJson(`/api/library${suffix ? `?${suffix}` : ""}`);
}

export function getFolders() {
  return requestJson("/api/library/folders");
}

export function createFolder({ name, color = null }) {
  return requestJson("/api/library/folders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, color })
  });
}

export function updateFolder(folderId, { name, color, sort_order } = {}) {
  const body = {};
  if (name !== undefined) body.name = name;
  if (color !== undefined) body.color = color;
  if (sort_order !== undefined) body.sort_order = sort_order;
  return requestJson(`/api/library/folders/${encodeURIComponent(folderId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export function deleteFolder(folderId) {
  return requestJson(`/api/library/folders/${encodeURIComponent(folderId)}`, {
    method: "DELETE"
  });
}

export function moveJobToFolder(jobId, folderId) {
  return requestJson(`/api/library/jobs/${encodeURIComponent(jobId)}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_id: folderId })
  });
}

// ── Bulk job actions (canonical /api/jobs/bulk/* family) ─────────────────────
// All three return the partial-success batch contract:
//   { results: [{ id, status: "ok"|"skipped"|"error", detail? }], ok_count, fail_count }
// A whole-request failure (e.g. bulk move to an unknown folder → 404) rejects
// via requestJson with the server's `detail`.

export function bulkDeleteJobs(ids) {
  return requestJson("/api/jobs/bulk/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids })
  });
}

export function bulkRestoreJobs(ids) {
  return requestJson("/api/jobs/bulk/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids })
  });
}

// Canonical batch move (replaces the older POST /api/library/jobs/move). Sends
// `folder_id` (NOT `folder`); pass "unfiled" to remove the folder assignment.
export function bulkMoveJobs(ids, folderId) {
  return requestJson("/api/jobs/bulk/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, folder_id: folderId })
  });
}

// Bulk PERMANENT delete. Each id must already be in the trash; loops the same
// guarded single-job purge server-side. Irreversible — confirm strongly first.
export function bulkPurgeJobs(ids) {
  return requestJson("/api/jobs/bulk/purge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids })
  });
}

export function generateOutline({ sourceText = "", title = "", provider = null, model = null }) {
  return requestJson("/api/outline/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_text: sourceText, title, provider, model })
  });
}

export function getExports(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, String(value));
    }
  });
  const suffix = query.toString();
  return requestJson(`/api/exports${suffix ? `?${suffix}` : ""}`);
}

// Downloads a ZIP bundle of selected artifacts for the given jobs. Streams the
// binary response into a browser download (cannot use requestJson — it's JSON).
export async function downloadExportBundle(jobIds, artifacts) {
  const response = await fetch(`${API_BASE_URL}/api/exports/bundle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds, artifacts })
  });
  if (!response.ok) {
    let message = `Bundle failed: ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (data.detail?.message) message = data.detail.message;
    } catch {
      // keep status-based fallback
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "study-guides-export.zip";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return { filename };
}

export function rerenderJob(jobId, { theme } = {}) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/rerender`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(theme ? { theme } : {})
  });
}

export function retryJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
}

// Request cooperative cancellation of a running generation. The running job
// stops at its next safe stage boundary and ends in status "cancelled"; this
// never kills a process. Safe no-op for already-finished jobs.
export function cancelJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
}

export function getJobError(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/error`);
}

export function getJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}`);
}

// Coarse, pollable generation progress: { status, stage, stage_label, progress }.
// status is the terminal-state source of truth; stop polling once it is terminal.
export function getJobProgress(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/progress`);
}

export function createPasteJob({ text, theme = "claude_clean", strictMath = true, folderId = null }) {
  return requestJson("/api/jobs/paste", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text,
      theme,
      strict_math: strictMath,
      folder_id: folderId
    })
  });
}

export function createUploadMarkdownJob({ file, theme = "claude_clean", strictMath = true, folderId = null }) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("theme", theme);
  formData.append("strict_math", String(strictMath));
  if (folderId) {
    formData.append("folder_id", folderId);
  }

  return requestJson("/api/jobs/upload-markdown", {
    method: "POST",
    body: formData
  });
}

export function createLlmJob(payload) {
  const attachments = payload.attachments ?? [];
  if (attachments.length > 0) {
    const formData = new FormData();
    Object.entries(payload).forEach(([key, value]) => {
      if (key === "attachments" || value === null || value === undefined) {
        return;
      }
      if ((key === "outline" || key === "include_sections") && typeof value === "object") {
        formData.append(key, JSON.stringify(value));
        return;
      }
      formData.append(key, String(value));
    });
    attachments.forEach((file) => {
      formData.append("attachments", file);
    });
    return requestJson("/api/jobs/llm", {
      method: "POST",
      body: formData
    });
  }

  return requestJson("/api/jobs/llm", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

// Read-only large-PDF preflight (see docs/LARGE_PDF_PREFLIGHT_DESIGN.md). Posts
// a single PDF as multipart and returns the inspection report
// ({ verdict: "ok"|"warn"|"blocked", warnings[], allowed_actions[], page_count,
// file_size_mb, scanned_flag, ... }). Creates no job and persists nothing. A
// non-PDF / oversize file rejects via requestJson with the server's `detail`;
// callers treat any failure as a soft warning and do NOT block generation.
export function preflightPdf(file) {
  const formData = new FormData();
  formData.append("file", file);
  return requestJson("/api/preflight/pdf", {
    method: "POST",
    body: formData
  });
}

export function getJobVersions(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/versions`);
}

export async function getCleanMd(jobId) {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/clean_md`);
  if (!response.ok) {
    throw new Error(`Failed to load markdown: ${response.status}`);
  }
  return response.text();
}

export function putCleanMd(jobId, text) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/clean_md`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  });
}

export async function getVersionCleanMd(jobId, version) {
  const response = await fetch(
    `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/versions/${version}/clean_md`
  );
  if (!response.ok) {
    throw new Error(`Failed to load version ${version}: ${response.status}`);
  }
  return response.text();
}

export function revertJobVersion(jobId, version) {
  return requestJson(
    `/api/jobs/${encodeURIComponent(jobId)}/revert/${version}`,
    { method: "POST" }
  );
}

export function getJobSections(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/sections`);
}

export function getOutlineCompliance(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/outline_compliance`);
}

export function regenerateSection(jobId, sectionIndex, { action, instruction = "", provider = null, model = null, qwenThinking = true } = {}) {
  return requestJson(
    `/api/jobs/${encodeURIComponent(jobId)}/sections/${sectionIndex}/regenerate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, instruction, provider, model, qwen_thinking: qwenThinking })
    }
  );
}

export function generateQuiz(jobId, { questionTypes, count, difficulty, focus, sectionIndices = null, provider = null, model = null, qwenThinking = true } = {}) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/quiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_types: questionTypes,
      count,
      difficulty,
      focus,
      section_indices: sectionIndices,
      provider,
      model,
      qwen_thinking: qwenThinking,
    }),
  });
}

export function listQuizzes(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/quizzes`);
}

export function getQuiz(jobId, quizN) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}/quizzes/${quizN}`);
}

export function quizExportUrl(jobId, quizN, format) {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/quizzes/${quizN}/export?format=${encodeURIComponent(format)}`;
}

// ── Shortcuts (Home launcher registry) ──────────────────────────────────────

export function listShortcuts() {
  return requestJson("/api/shortcuts");
}

export function getShortcut(shortcutId) {
  return requestJson(`/api/shortcuts/${encodeURIComponent(shortcutId)}`);
}

export function createShortcut(shortcut) {
  return requestJson("/api/shortcuts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(shortcut),
  });
}

export function updateShortcut(shortcutId, patch) {
  return requestJson(`/api/shortcuts/${encodeURIComponent(shortcutId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export function deleteShortcut(shortcutId) {
  return requestJson(`/api/shortcuts/${encodeURIComponent(shortcutId)}`, {
    method: "DELETE",
  });
}

export function reorderShortcuts(items) {
  return requestJson("/api/shortcuts/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
}

export function resetShortcutDefaults() {
  return requestJson("/api/shortcuts/defaults/reset", { method: "POST" });
}

export function previewImportShortcuts(data, overwrite = false) {
  const body = Array.isArray(data) ? data : { ...data, overwrite };
  return requestJson("/api/shortcuts/import/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function importShortcuts(data, overwrite = false) {
  const body = Array.isArray(data) ? data : { ...data, overwrite };
  return requestJson("/api/shortcuts/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function exportShortcutUrl(shortcutId) {
  return `${API_BASE_URL}/api/shortcuts/${encodeURIComponent(shortcutId)}/export`;
}

export function exportShortcutsUrl() {
  return `${API_BASE_URL}/api/shortcuts/export`;
}

export function artifactUrl(jobId, artifactName) {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(
    artifactName
  )}`;
}

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

export function previewApiUrl(path) {
  const url = apiUrl(path);
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}disposition=inline`;
}
