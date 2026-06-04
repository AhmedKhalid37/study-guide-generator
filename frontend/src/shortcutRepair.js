// Pure draft/payload helpers for the Shortcut Inspector repair UI (Slice 3B).
//
// These mirror the Slice 3A backend repair contract in
// pipeline/shortcut_store.py (_prepare_repair / _apply_repair_changes). They are
// PURE functions (no React, no imports) so a node harness can unit-test them and
// so the Inspector component builds the request payload + computes preview
// staleness the SAME way everywhere. The backend owns validation — these helpers
// only assemble the explicit, whitelisted patch the backend already enforces.
//
// SAFETY: a draft starts EMPTY (every field "keep"); nothing is sent until the
// user explicitly chooses a replace/remove action and previews. buildRepairPayload
// drops empty "replace" values so a half-finished choice never mutates anything.

export const REPAIR_MODE_IN_PLACE = "in_place";
export const REPAIR_MODE_CLONE = "clone";

// Scalar builder fields a repair may REPLACE. `provider` is the only one that is
// NOT removable (a generation shortcut needs a provider) — the backend rejects a
// provider in remove_fields, so the UI never offers a Remove action for it.
export const REPAIR_SCALAR_FIELDS = [
  "provider",
  "model",
  "style",
  "generator_preset",
  "output_depth",
  "difficulty",
];
export const REPAIR_REMOVABLE_FIELDS = [
  "model",
  "style",
  "generator_preset",
  "output_depth",
  "difficulty",
];

export const CLONE_NAME_SUFFIX = "(repaired copy)";

// Map a finding.field (dotted path, e.g. "payload.provider") to the short repair
// key the draft uses, or null when the field has no supported repair action in
// this slice (legacy modules, tool/view, type/payload shape errors).
const FIELD_KEY_BY_PATH = {
  "payload.provider": "provider",
  "payload.model": "model",
  "payload.style": "style",
  "payload.generator_preset": "generator_preset",
  "payload.output_depth": "output_depth",
  "payload.difficulty": "difficulty",
  "payload.include_sections": "include_sections",
};

export function repairFieldKey(findingField) {
  return FIELD_KEY_BY_PATH[findingField] || null;
}

// The default clone name the UI prefills: "{name} (repaired copy)" — matches the
// backend's CLONE_NAME_SUFFIX derivation when clone_name is omitted.
export function defaultCloneName(name) {
  const base = (name && String(name).trim()) || "Shortcut";
  return `${base} ${CLONE_NAME_SUFFIX}`;
}

// An empty repair draft: in_place mode, no per-field actions, no section removals.
export function emptyRepairDraft() {
  return {
    mode: REPAIR_MODE_IN_PLACE,
    cloneName: "",
    // { provider: { action: "keep"|"replace", value }, model: { action:"remove" } … }
    fields: {},
    // unknown include_sections keys the user chose to drop
    removeSections: [],
  };
}

// Build the explicit backend request payload from a draft:
//   { mode, changes: {…}, clone_name? }
// - "replace" with a non-empty value -> changes[field] = value
// - "replace" with an empty value    -> ignored (no change yet; forces a choice)
// - "remove" of a removable field    -> changes.remove_fields += field
// - chosen section keys              -> changes.include_sections = { remove: [...] }
export function buildRepairPayload(draft) {
  const changes = {};
  const removeFields = [];
  const fields = (draft && draft.fields) || {};

  for (const key of REPAIR_SCALAR_FIELDS) {
    const entry = fields[key];
    if (!entry || entry.action === "keep") continue;
    if (entry.action === "remove") {
      if (REPAIR_REMOVABLE_FIELDS.includes(key)) removeFields.push(key);
    } else if (entry.action === "replace") {
      const value = entry.value;
      if (value !== undefined && value !== null && value !== "") {
        changes[key] = value;
      }
    }
  }

  const removeSections = Array.isArray(draft && draft.removeSections)
    ? draft.removeSections.filter(Boolean)
    : [];
  if (removeSections.length > 0) {
    changes.include_sections = { remove: [...removeSections] };
  }

  if (removeFields.length > 0) {
    changes.remove_fields = removeFields;
  }

  const mode = draft && draft.mode === REPAIR_MODE_CLONE
    ? REPAIR_MODE_CLONE
    : REPAIR_MODE_IN_PLACE;
  const payload = { mode, changes };

  if (mode === REPAIR_MODE_CLONE) {
    const name = (draft && draft.cloneName && String(draft.cloneName).trim()) || "";
    // Only send clone_name when non-empty; otherwise the backend derives the
    // "(repaired copy)" suffix itself.
    if (name) payload.clone_name = name;
  }

  return payload;
}

// True when the draft would actually change something (so Preview is meaningful
// and the Preview button can enable).
export function draftHasChanges(draft) {
  const payload = buildRepairPayload(draft);
  return Object.keys(payload.changes).length > 0;
}

// A STABLE signature of the request a draft would send. Used for preview
// staleness: after a successful preview we remember the signature; if the draft
// changes (any action/value/mode/clone-name that affects the payload), the
// signature changes and the prior preview is marked stale, re-disabling Apply.
// buildRepairPayload emits keys in a deterministic order, so equal drafts give
// equal signatures.
export function draftSignature(draft) {
  return JSON.stringify(buildRepairPayload(draft));
}

// Models available for a provider, from the inspect repair_candidates
// (models_by_provider). Tolerates missing candidates / unknown provider -> [].
export function modelCandidatesForProvider(candidates, providerId) {
  if (!candidates || !providerId) return [];
  const map = candidates.models_by_provider || {};
  const list = map[providerId];
  return Array.isArray(list) ? list : [];
}

// The effective provider used to filter the model list: a chosen replacement
// provider wins, else the shortcut's current saved provider.
export function effectiveProvider(draft, currentProvider) {
  const entry = draft && draft.fields && draft.fields.provider;
  if (entry && entry.action === "replace" && entry.value) return entry.value;
  return currentProvider || null;
}
