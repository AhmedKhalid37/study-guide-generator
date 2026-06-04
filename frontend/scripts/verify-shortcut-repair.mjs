// Unit harness for the Shortcut Inspector repair draft/payload helpers (Slice 3B).
//
// Mirrors verify-shortcut-status.mjs (plain node, no test runner, no new
// dependency). Imports the REAL src/shortcutRepair.js — pure ESM, no React/JSX.
//
//   node scripts/verify-shortcut-repair.mjs
//
// Proves: empty draft sends nothing, the request payload shape for
// provider/model/style/preset/axes/remove-fields/include_sections, clone
// name/default, model candidate filtering by provider, effective-provider
// selection, and the staleness signature (Apply disabled before preview;
// changing the draft after preview marks it stale).

import {
  buildRepairPayload,
  defaultCloneName,
  draftHasChanges,
  draftSignature,
  effectiveProvider,
  emptyRepairDraft,
  modelCandidatesForProvider,
  repairFieldKey,
  REPAIR_MODE_CLONE,
  REPAIR_MODE_IN_PLACE,
} from "../src/shortcutRepair.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ── empty draft sends nothing (Apply must stay disabled before any choice) ───
const empty = emptyRepairDraft();
check("empty draft has no changes", draftHasChanges(empty) === false);
check(
  "empty draft payload is {mode:in_place, changes:{}}",
  eq(buildRepairPayload(empty), { mode: REPAIR_MODE_IN_PLACE, changes: {} })
);

// ── provider replacement ─────────────────────────────────────────────────────
const provDraft = {
  ...empty,
  fields: { provider: { action: "replace", value: "qwen" } },
};
check("provider replace -> changes.provider", buildRepairPayload(provDraft).changes.provider === "qwen");
check("provider replace counts as a change", draftHasChanges(provDraft) === true);

// ── an empty replace value is ignored (forces an explicit choice) ────────────
const provEmpty = { ...empty, fields: { provider: { action: "replace", value: "" } } };
check("replace with empty value sends nothing", draftHasChanges(provEmpty) === false);

// ── model: replace filtered + remove ─────────────────────────────────────────
const modelReplace = { ...empty, fields: { model: { action: "replace", value: "qwen3.7-plus" } } };
check("model replace -> changes.model", buildRepairPayload(modelReplace).changes.model === "qwen3.7-plus");
const modelRemove = { ...empty, fields: { model: { action: "remove" } } };
check(
  "model remove -> remove_fields:['model']",
  eq(buildRepairPayload(modelRemove).changes.remove_fields, ["model"])
);

// ── style / preset / axes ────────────────────────────────────────────────────
const styleRemove = { ...empty, fields: { style: { action: "remove" } } };
check("style remove -> remove_fields:['style']", eq(buildRepairPayload(styleRemove).changes.remove_fields, ["style"]));
const presetReplace = { ...empty, fields: { generator_preset: { action: "replace", value: "claude_cram" } } };
check("preset replace -> changes.generator_preset", buildRepairPayload(presetReplace).changes.generator_preset === "claude_cram");
const axisDraft = {
  ...empty,
  fields: {
    output_depth: { action: "replace", value: "balanced" },
    difficulty: { action: "remove" },
  },
};
const axisPayload = buildRepairPayload(axisDraft);
check("axis replace -> changes.output_depth", axisPayload.changes.output_depth === "balanced");
check("axis remove -> remove_fields includes difficulty", axisPayload.changes.remove_fields.includes("difficulty"));

// ── include_sections remove (drop unknown keys) ──────────────────────────────
const secDraft = { ...empty, removeSections: ["totally_fake_section", "another_dead_key"] };
check(
  "removeSections -> include_sections.remove",
  eq(buildRepairPayload(secDraft).changes.include_sections, {
    remove: ["totally_fake_section", "another_dead_key"],
  })
);

// ── combined payload shape (provider+model+style+preset+axes+sections) ───────
const combined = {
  mode: REPAIR_MODE_IN_PLACE,
  cloneName: "",
  fields: {
    provider: { action: "replace", value: "qwen" },
    model: { action: "replace", value: "qwen3.7-plus" },
    style: { action: "remove" },
    generator_preset: { action: "replace", value: "claude_cram" },
    output_depth: { action: "remove" },
    difficulty: { action: "keep" },
  },
  removeSections: ["dead_key"],
};
check(
  "combined payload shape",
  eq(buildRepairPayload(combined), {
    mode: "in_place",
    changes: {
      provider: "qwen",
      model: "qwen3.7-plus",
      generator_preset: "claude_cram",
      include_sections: { remove: ["dead_key"] },
      remove_fields: ["style", "output_depth"],
    },
  })
);

// ── clone mode + clone name ──────────────────────────────────────────────────
const cloneNamed = {
  ...empty,
  mode: REPAIR_MODE_CLONE,
  cloneName: "My fixed copy",
  fields: { provider: { action: "replace", value: "qwen" } },
};
const cloneNamedPayload = buildRepairPayload(cloneNamed);
check("clone mode -> mode:clone", cloneNamedPayload.mode === REPAIR_MODE_CLONE);
check("clone name forwarded when set", cloneNamedPayload.clone_name === "My fixed copy");
const cloneNoName = { ...cloneNamed, cloneName: "" };
check("clone with empty name omits clone_name", buildRepairPayload(cloneNoName).clone_name === undefined);
check('defaultCloneName -> "{name} (repaired copy)"', defaultCloneName("Cram Mode") === "Cram Mode (repaired copy)");
check("defaultCloneName tolerates empty name", defaultCloneName("") === "Shortcut (repaired copy)");

// ── model candidate filtering by provider ────────────────────────────────────
const candidates = {
  providers: [
    { id: "deepseek", label: "DeepSeek", configured: true },
    { id: "qwen", label: "Qwen", configured: true },
  ],
  models_by_provider: {
    deepseek: ["deepseek-chat", "deepseek-reasoner"],
    qwen: ["qwen3.7-max", "qwen3.7-plus"],
  },
};
check("models filter by provider (qwen)", eq(modelCandidatesForProvider(candidates, "qwen"), ["qwen3.7-max", "qwen3.7-plus"]));
check("models filter by provider (deepseek)", eq(modelCandidatesForProvider(candidates, "deepseek"), ["deepseek-chat", "deepseek-reasoner"]));
check("models for unknown provider -> []", eq(modelCandidatesForProvider(candidates, "nope"), []));
check("models tolerates missing candidates -> []", eq(modelCandidatesForProvider(null, "qwen"), []));

// effective provider: a chosen replacement wins over the saved provider.
check("effectiveProvider: replacement wins", effectiveProvider(provDraft, "deepseek") === "qwen");
check("effectiveProvider: falls back to current", effectiveProvider(empty, "deepseek") === "deepseek");
check("effectiveProvider: null-safe", effectiveProvider(empty, null) === null);

// ── staleness signature: Apply disabled before preview, stale after edit ─────
const draftA = { ...empty, fields: { provider: { action: "replace", value: "qwen" } } };
const sigA = draftSignature(draftA);
check("equal drafts -> equal signature", draftSignature({ ...draftA }) === sigA);
const draftB = { ...empty, fields: { provider: { action: "replace", value: "deepseek" } } };
check("changing a value changes the signature (stale)", draftSignature(draftB) !== sigA);
const draftAClone = { ...draftA, mode: REPAIR_MODE_CLONE, cloneName: "x" };
check("changing mode/clone-name changes the signature (stale)", draftSignature(draftAClone) !== sigA);

// ── finding.field -> repair key mapping ──────────────────────────────────────
check("repairFieldKey provider", repairFieldKey("payload.provider") === "provider");
check("repairFieldKey include_sections", repairFieldKey("payload.include_sections") === "include_sections");
check("repairFieldKey unsupported (modules) -> null", repairFieldKey("payload.modules") === null);
check("repairFieldKey unsupported (tool) -> null", repairFieldKey("payload.tool") === null);

if (failed) {
  console.error(`\n${failed} shortcut-repair check(s) failed.`);
  process.exit(1);
}
console.log("\nAll shortcut-repair checks passed.");
