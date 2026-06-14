// Per-attachment material page/slide exclusions (Slice 87).
//
// Pure, React-free helpers that turn the Builder's per-attachment "exclude
// pages/slides" text inputs into the backend `material_page_selections` envelope
// that Slices 79–86 already persist + apply server-side. The backend
// (`api/server.py::_normalize_material_page_selections` + the Slice 78 page model)
// remains the final normalizer / source of truth — these helpers only shape a
// safe, deterministic request and surface local UI hints.
//
// Safety invariants (must hold):
//   * Persisted attachment keys are ALWAYS `attachment_<index>` by upload order —
//     never a filename, path, or title.
//   * Raw invalid tokens the user typed are NEVER copied into the payload or its
//     warnings; only closed-vocabulary warning tokens are emitted, and locally.
//   * Output is deterministic: pages are deduped + ascending, warnings collapse to
//     a fixed canonical order.

export const MATERIAL_PAGE_SELECTIONS_VERSION = 1;

// Closed-vocabulary local UI warning tokens. These never carry the offending raw
// token value and are not sent to the backend payload.
export const WARN_TOKEN_INVALID = "page_token_invalid";
export const WARN_RANGE_INVALID = "page_range_invalid";
export const WARN_RANGE_REVERSED = "page_range_reversed";
export const WARN_NUMBER_INVALID = "page_number_invalid";

// Canonical order used to dedupe/sort emitted warnings for determinism.
const WARNING_ORDER = [
  WARN_TOKEN_INVALID,
  WARN_RANGE_INVALID,
  WARN_RANGE_REVERSED,
  WARN_NUMBER_INVALID
];

function dedupeWarnings(warnings) {
  return WARNING_ORDER.filter((token) => warnings.includes(token));
}

// Parse a user-typed exclusion spec like "2, 4-6, 10" into ascending, deduped,
// positive 1-based page numbers. Invalid tokens are dropped with a closed warning
// token (never the raw value). Returns { pages, warnings }.
export function parsePageListInput(input) {
  const warnings = [];
  const pageSet = new Set();
  const tokens = String(input ?? "")
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean);

  for (const token of tokens) {
    const range = token.match(/^(\d+)\s*-\s*(\d+)$/);
    const single = token.match(/^(\d+)$/);
    if (range) {
      const start = parseInt(range[1], 10);
      const end = parseInt(range[2], 10);
      if (start < 1 || end < 1) {
        warnings.push(WARN_RANGE_INVALID);
        continue;
      }
      if (start > end) {
        warnings.push(WARN_RANGE_REVERSED);
        continue;
      }
      for (let page = start; page <= end; page += 1) pageSet.add(page);
    } else if (single) {
      const page = parseInt(single[1], 10);
      if (page < 1) {
        warnings.push(WARN_NUMBER_INVALID);
        continue;
      }
      pageSet.add(page);
    } else if (token.includes("-")) {
      // Looks like a range but failed the strict digit-dash-digit shape.
      warnings.push(WARN_RANGE_INVALID);
    } else {
      warnings.push(WARN_TOKEN_INVALID);
    }
  }

  const pages = Array.from(pageSet).sort((a, b) => a - b);
  return { pages, warnings: dedupeWarnings(warnings) };
}

// Build a single per-attachment exclude model from already-parsed pages. Mirrors
// the Slice 78 page-selection model shape the backend re-normalizes.
function buildExcludeModel(pages) {
  return {
    version: MATERIAL_PAGE_SELECTIONS_VERSION,
    mode: "exclude",
    include_pages: [],
    exclude_pages: pages,
    warnings: []
  };
}

// Build the `material_page_selections` envelope from per-attachment raw exclusion
// inputs given IN UPLOAD ORDER. The array index becomes the safe `attachment_<i>`
// key — filenames/paths are intentionally never accepted here. Attachments with no
// active exclusions are omitted entirely (keeps a default request byte-equivalent).
export function buildMaterialPageSelections(orderedInputs) {
  const inputs = Array.isArray(orderedInputs) ? orderedInputs : [];
  const attachments = {};
  inputs.forEach((raw, index) => {
    const { pages } = parsePageListInput(raw);
    if (pages.length === 0) return;
    attachments[`attachment_${index}`] = buildExcludeModel(pages);
  });
  return {
    version: MATERIAL_PAGE_SELECTIONS_VERSION,
    attachments,
    warnings: []
  };
}

// True when the envelope carries at least one active per-attachment exclusion —
// the gate the Builder uses to decide whether to send the field at all.
export function hasActiveMaterialSelections(envelope) {
  return Boolean(
    envelope &&
      envelope.attachments &&
      Object.keys(envelope.attachments).length > 0
  );
}
