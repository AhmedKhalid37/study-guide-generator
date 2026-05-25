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

export function getJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function createPasteJob({ text, theme = "claude_clean", strictMath = true }) {
  return requestJson("/api/jobs/paste", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      text,
      theme,
      strict_math: strictMath
    })
  });
}

export function createUploadMarkdownJob({ file, theme = "claude_clean", strictMath = true }) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("theme", theme);
  formData.append("strict_math", String(strictMath));

  return requestJson("/api/jobs/upload-markdown", {
    method: "POST",
    body: formData
  });
}

export function createLlmJob(payload) {
  return requestJson("/api/jobs/llm", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
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
