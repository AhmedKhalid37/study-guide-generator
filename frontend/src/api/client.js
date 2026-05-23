const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

async function requestJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
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

export function artifactUrl(jobId, artifactName) {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(
    artifactName
  )}`;
}
