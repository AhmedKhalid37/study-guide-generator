// Single source of truth for the Builder's client-side attachment size policy.
//
// Slice 101 (emergency large-attachment support): the app must accept guide
// attachments around 100 MB. These constants mirror the backend default
// (GUIDEFORGE_MAX_ATTACHMENT_MB, default 150 MB). This is a pre-flight UX guard
// only — the backend re-enforces the real ceiling on every upload — so it never
// needs the file's *contents* or *name*: every function here reads `file.size`
// (a number) and nothing else. No filename, path, or source content is ever read
// or returned, keeping the no-leak invariant intact.

// Hard client ceiling. Kept in sync with the backend default; if the backend is
// configured higher via env, the server still accepts up to its own limit — this
// guard only ever rejects *before* the request, never loosens the server.
export const MAX_ATTACHMENT_MB = 150;
export const MAX_ATTACHMENT_BYTES = MAX_ATTACHMENT_MB * 1024 * 1024;

// At/above this size a file is still accepted, but warrants a calm heads-up that
// processing may take longer. This is the documented 100 MB target.
export const LARGE_ATTACHMENT_MB = 100;
export const LARGE_ATTACHMENT_BYTES = LARGE_ATTACHMENT_MB * 1024 * 1024;

// User-facing copy. Both strings are generic — they never embed a filename, a
// path, a byte count from a specific file, or any source content.
export const LARGE_FILE_NOTICE = "Large files may take longer to process.";
export const OVERSIZE_REJECTION = `Files larger than ${MAX_ATTACHMENT_MB} MB can't be uploaded.`;

// Coerce an arbitrary size value to a safe, non-negative byte count. A missing /
// non-finite / negative size degrades to 0 (treated as acceptable) so a flaky
// File object can never throw here.
function safeBytes(size) {
  return Number.isFinite(size) && size >= 0 ? size : 0;
}

// Classify a file purely by its byte size. Returns a small, content-free verdict:
//   { ok: boolean, large: boolean, reason: "too_large" | null }
// `ok:false` means it should be rejected before upload; `large:true` means it is
// accepted but large enough to warrant the LARGE_FILE_NOTICE copy.
export function classifyAttachmentSize(size) {
  const bytes = safeBytes(size);
  if (bytes > MAX_ATTACHMENT_BYTES) {
    return { ok: false, large: false, reason: "too_large" };
  }
  return { ok: true, large: bytes >= LARGE_ATTACHMENT_BYTES, reason: null };
}

// Convenience predicates over the same verdict, for call sites that only need a
// boolean. Deterministic and side-effect free.
export function isAttachmentSizeAccepted(size) {
  return classifyAttachmentSize(size).ok;
}

export function isLargeAttachment(size) {
  return classifyAttachmentSize(size).large;
}
