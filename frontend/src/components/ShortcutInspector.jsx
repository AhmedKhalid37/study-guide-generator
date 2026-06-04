import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  RefreshCw,
  Wrench,
  X,
} from "lucide-react";
import { applyShortcutRepair, inspectShortcut, previewShortcutRepair } from "../api/client";
import {
  countFindingsBySeverity,
  shortcutStatus,
  statusBadge,
} from "../shortcutStatus";
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
  REPAIR_REMOVABLE_FIELDS,
} from "../shortcutRepair";
import { TYPE_LABELS } from "../shortcutMeta";

// ── Shortcut Inspector with repair (Slice 3B) ────────────────────────────────
//
// Opens from a Home shortcut badge or the Customize modal. It calls the
// read-only GET /api/shortcuts/{id}/inspect (Slice 1) and renders the legacy
// valid/reason, the 3-tier validity status, every finding, and — when the
// shortcut is a repairable builder_setup — an explicit repair panel.
//
// SAFETY (enforced here):
//   - No repair API call on open (inspect is read-only).
//   - The repair draft starts EMPTY; nothing is sent until the user chooses an
//     action and clicks Preview.
//   - Apply is disabled until a SUCCESSFUL preview exists for the CURRENT draft;
//     editing the draft after a preview marks it stale and re-disables Apply.
//   - Apply requires an explicit confirmation click.
//   - No provider/model auto-switching; suggestions are never auto-applied.
//   - No raw keys: every candidate is the already-redacted backend list.

const TONE_CLASSES = {
  valid: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  degraded: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  broken: "border-red-400/30 bg-red-400/10 text-red-200",
};

const SEVERITY_META = {
  error: { Icon: AlertCircle, cls: "text-red-300", label: "Error" },
  warning: { Icon: AlertTriangle, cls: "text-amber-300", label: "Warning" },
  info: { Icon: Info, cls: "text-slate-400", label: "Info" },
};

// Human labels for the repair field keys (drives the control headings).
const FIELD_LABELS = {
  provider: "Provider",
  model: "Model",
  style: "Style",
  generator_preset: "Generator preset",
  output_depth: "Output depth",
  difficulty: "Difficulty",
  include_sections: "Included sections",
};

function StatusPill({ status }) {
  const badge = statusBadge(status);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
        TONE_CLASSES[badge.tone] || TONE_CLASSES.valid
      }`}
    >
      {badge.label}
    </span>
  );
}

function FindingRow({ finding }) {
  const meta = SEVERITY_META[finding?.severity] || SEVERITY_META.info;
  const { Icon } = meta;
  const candidateCount = Array.isArray(finding?.candidates) ? finding.candidates.length : 0;
  return (
    <li className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-start gap-2">
        <Icon size={15} className={`mt-0.5 shrink-0 ${meta.cls}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] text-slate-300">{finding?.code || "unknown"}</span>
            {finding?.field && (
              <span className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-400">
                {finding.field}
              </span>
            )}
            <span className={`text-[10px] uppercase tracking-wide ${meta.cls}`}>{meta.label}</span>
          </div>
          <p className="mt-1 text-xs text-slate-300">{finding?.message || "No description."}</p>
          {finding?.current_value !== undefined && finding?.current_value !== null && (
            <p className="mt-1 text-[11px] text-slate-500">
              Current: <span className="font-mono text-slate-400">{String(finding.current_value)}</span>
            </p>
          )}
          <p className="mt-1 text-[11px] text-slate-500">
            {finding?.repairable
              ? candidateCount > 0
                ? `Repairable — ${candidateCount} candidate${candidateCount === 1 ? "" : "s"} available`
                : "Repairable"
              : "Not automatically repairable"}
          </p>
        </div>
      </div>
    </li>
  );
}

// A single scalar-field repair control: Keep / Replace / Remove, plus a value
// select when Replace is chosen. `removable` decides whether Remove is offered.
function RepairFieldControl({ fieldKey, current, removable, options, entry, onChange }) {
  const action = entry?.action || "keep";
  const value = entry?.value ?? "";
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-200">{FIELD_LABELS[fieldKey] || fieldKey}</span>
        {current !== undefined && current !== null && current !== "" && (
          <span className="font-mono text-[10px] text-slate-500">now: {String(current)}</span>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <select
          value={action}
          onChange={(e) => onChange(fieldKey, { action: e.target.value, value })}
          className="h-8 rounded-lg border border-white/15 bg-[#0B0F19] px-2 text-xs text-slate-200"
        >
          <option value="keep">Keep current</option>
          <option value="replace">Replace with…</option>
          {removable && <option value="remove">Remove (use default)</option>}
        </select>
        {action === "replace" && (
          <select
            value={value}
            onChange={(e) => onChange(fieldKey, { action: "replace", value: e.target.value })}
            className="h-8 min-w-[8rem] flex-1 rounded-lg border border-white/15 bg-[#0B0F19] px-2 text-xs text-slate-200"
          >
            <option value="">Choose a replacement…</option>
            {options.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label || opt.id}
              </option>
            ))}
          </select>
        )}
      </div>
      {action === "replace" && options.length === 0 && (
        <p className="mt-1.5 text-[11px] text-amber-300">
          No replacement candidates are available for this field.
        </p>
      )}
    </div>
  );
}

function DiffList({ diff }) {
  if (!Array.isArray(diff) || diff.length === 0) {
    return <p className="text-[11px] text-slate-500">No field changes.</p>;
  }
  const fmt = (v) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
  return (
    <ul className="flex flex-col gap-1">
      {diff.map((d, i) => (
        <li key={`${d?.field || "d"}-${i}`} className="flex flex-wrap items-center gap-1 text-[11px]">
          <span className="font-mono text-slate-400">{d?.field}</span>
          <span className="font-mono text-slate-500">{fmt(d?.from)}</span>
          <span className="text-slate-500">→</span>
          <span className="font-mono text-emerald-300">{fmt(d?.to)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function ShortcutInspector({ shortcut, onClose, onRepaired }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);

  // Repair draft + flow state.
  const [draft, setDraft] = useState(emptyRepairDraft);
  const [preview, setPreview] = useState(null); // { result, signature }
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applied, setApplied] = useState(null); // { mode, status, name, newId }

  // The current saved payload (the list view carries it). Updated from an
  // in-place apply response so the model filter stays accurate after a repair.
  const [livePayload, setLivePayload] = useState(shortcut?.payload || null);

  const shortcutId = shortcut?.id;

  const loadInspect = useCallback(() => {
    if (!shortcutId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);
    inspectShortcut(shortcutId)
      .then((result) => {
        if (cancelled) return;
        setData(result);
      })
      .catch((err) => {
        if (cancelled) return;
        const message = err?.message || "Could not inspect this shortcut.";
        if (/not found/i.test(message) || /404/.test(message)) setNotFound(true);
        else setError(message);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [shortcutId]);

  // Inspect on open / id change; reset all repair state for the new shortcut.
  useEffect(() => {
    setDraft(emptyRepairDraft());
    setPreview(null);
    setPreviewError(null);
    setApplyError(null);
    setConfirmOpen(false);
    setApplied(null);
    setLivePayload(shortcut?.payload || null);
    return loadInspect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shortcutId]);

  // Seed header fields from the list view while the fetch is in flight, then
  // prefer the authoritative inspect response once it arrives.
  const view = data || shortcut || {};
  const status = shortcutStatus(view);
  const findings = Array.isArray(view?.validity?.findings) ? view.validity.findings : [];
  const counts = countFindingsBySeverity(findings);
  const typeLabel = TYPE_LABELS[view?.type] || view?.type || "Shortcut";

  const candidates = data?.repair_candidates || null;
  const isBuilder = view?.type === "builder_setup";
  const validityRepairable = view?.validity?.repairable === true;
  const anyFindingRepairable = findings.some((f) => f?.repairable === true);
  const panelEligible = isBuilder && (validityRepairable || anyFindingRepairable);

  // The repairable fields actually supported in this slice, derived from the
  // findings (legacy modules / tool / view findings map to no control).
  const findingByKey = useMemo(() => {
    const map = {};
    for (const f of findings) {
      if (!f?.repairable) continue;
      const key = repairFieldKey(f.field);
      if (key && key !== "include_sections" && !map[key]) map[key] = f;
    }
    return map;
  }, [findings]);

  const unknownSectionKeys = useMemo(
    () =>
      findings
        .filter((f) => f?.repairable && f?.field === "payload.include_sections")
        .map((f) => f?.current_value)
        .filter((v) => v !== undefined && v !== null && v !== ""),
    [findings]
  );

  const actionableKeys = Object.keys(findingByKey);
  const hasActionable = actionableKeys.length > 0 || unknownSectionKeys.length > 0;

  const currentProvider = effectiveProvider(draft, livePayload?.provider);

  // Candidate options per field key (model is filtered by the effective provider).
  const optionsFor = useCallback(
    (key) => {
      if (key === "model") {
        return modelCandidatesForProvider(candidates, currentProvider).map((m) => ({ id: m, label: m }));
      }
      if (key === "provider") {
        const list = (candidates?.providers || []).filter((p) => p?.configured);
        return list.length ? list : Array.isArray(findingByKey.provider?.candidates) ? findingByKey.provider.candidates : [];
      }
      const finding = findingByKey[key];
      return Array.isArray(finding?.candidates) ? finding.candidates : [];
    },
    [candidates, currentProvider, findingByKey]
  );

  const onFieldChange = useCallback((key, next) => {
    setDraft((d) => {
      const fields = { ...d.fields, [key]: next };
      // If the provider replacement changes, a previously-chosen model may no
      // longer belong to it — reset the model action so we never send a stale pair.
      if (key === "provider" && fields.model && fields.model.action === "replace") {
        fields.model = { action: "keep", value: "" };
      }
      return { ...d, fields };
    });
  }, []);

  const toggleSectionRemoval = useCallback((sectionKey) => {
    setDraft((d) => {
      const set = new Set(d.removeSections || []);
      if (set.has(sectionKey)) set.delete(sectionKey);
      else set.add(sectionKey);
      return { ...d, removeSections: [...set] };
    });
  }, []);

  const setMode = useCallback(
    (mode) => {
      setDraft((d) => {
        const next = { ...d, mode };
        if (mode === REPAIR_MODE_CLONE && !d.cloneName) {
          next.cloneName = defaultCloneName(view?.name);
        }
        return next;
      });
    },
    [view?.name]
  );

  const currentSignature = draftSignature(draft);
  const previewFresh = preview && preview.signature === currentSignature;
  const canPreview = hasActionable && draftHasChanges(draft) && !previewing;
  const canApply = Boolean(previewFresh) && !applying;

  const handlePreview = useCallback(() => {
    if (!shortcutId) return;
    setPreviewing(true);
    setPreviewError(null);
    setApplyError(null);
    const signature = draftSignature(draft);
    previewShortcutRepair(shortcutId, buildRepairPayload(draft))
      .then((result) => setPreview({ result, signature }))
      .catch((err) => {
        // Keep the draft; just surface a safe error and drop any stale preview.
        setPreview(null);
        setPreviewError(err?.message || "Could not preview this repair.");
      })
      .finally(() => setPreviewing(false));
  }, [shortcutId, draft]);

  const handleApply = useCallback(() => {
    if (!shortcutId || !previewFresh) return;
    setApplying(true);
    setApplyError(null);
    applyShortcutRepair(shortcutId, buildRepairPayload(draft))
      .then((res) => {
        const repaired = res?.shortcut || {};
        setApplied({
          mode: res?.mode || draft.mode,
          status: repaired?.validity?.status || null,
          name: repaired?.name || null,
          newId: res?.mode === REPAIR_MODE_CLONE ? repaired?.id || null : null,
          warnings: Array.isArray(res?.warnings) ? res.warnings : [],
        });
        // For in-place, the saved payload changed — track it for model filtering.
        if (res?.mode !== REPAIR_MODE_CLONE && repaired?.payload) {
          setLivePayload(repaired.payload);
        }
        // Reset the draft + preview, refresh the parent list, and re-inspect so
        // the findings/status update in place.
        setDraft(emptyRepairDraft());
        setPreview(null);
        setConfirmOpen(false);
        onRepaired?.();
        loadInspect();
      })
      .catch((err) => {
        setConfirmOpen(false);
        setApplyError(err?.message || "Could not apply this repair.");
      })
      .finally(() => setApplying(false));
  }, [shortcutId, previewFresh, draft, onRepaired, loadInspect]);

  return (
    <div className="fixed inset-0 z-[80] flex justify-end">
      <button type="button" aria-label="Close inspector" className="absolute inset-0 cursor-default bg-black/60" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Shortcut inspector"
        className="relative flex h-full w-full max-w-md flex-col border-l border-white/10 bg-[#0B0F19] shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-white/10 px-5 py-3.5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-sm font-bold text-white">{view?.name || "Shortcut"}</h2>
              <StatusPill status={status} />
            </div>
            <p className="mt-0.5 text-[11px] uppercase tracking-wide text-slate-500">{typeLabel}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-white">
            <X size={16} />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Loader2 size={14} className="animate-spin" /> Inspecting shortcut…
            </div>
          )}

          {notFound && (
            <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
              This shortcut no longer exists. It may have been deleted — close and refresh the list.
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
              {error}
            </div>
          )}

          {applied && (
            <div className="flex items-start gap-2 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100">
              <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-300" />
              <div className="min-w-0">
                <p className="font-semibold">
                  {applied.mode === REPAIR_MODE_CLONE ? "Repaired copy created." : "Shortcut repaired."}
                </p>
                <p className="mt-0.5 text-emerald-200/80">
                  {applied.mode === REPAIR_MODE_CLONE
                    ? `New shortcut “${applied.name}” created; the original is unchanged.`
                    : "The saved shortcut was updated."}
                  {applied.status ? ` New status: ${applied.status}.` : ""}
                </p>
                {applied.warnings?.length > 0 && (
                  <p className="mt-0.5 text-amber-200/90">{applied.warnings.join(" ")}</p>
                )}
              </div>
            </div>
          )}

          {!loading && !notFound && (
            <>
              {/* Legacy valid/reason, shown when relevant for transparency. */}
              {view?.valid === false && (
                <div className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-300">
                  <span className="text-slate-500">Legacy check:</span> blocked
                  {view?.reason ? ` — ${view.reason}` : ""}
                </div>
              )}

              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Findings</h3>
                  <span className="text-[11px] text-slate-500">
                    {counts.error} error{counts.error === 1 ? "" : "s"} · {counts.warning} warning
                    {counts.warning === 1 ? "" : "s"} · {counts.info} info
                  </span>
                </div>
                {findings.length === 0 ? (
                  <p className="rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2 text-xs text-emerald-200">
                    No problems found. This shortcut resolves exactly as saved.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {findings.map((finding, index) => (
                      <FindingRow key={`${finding?.code || "f"}-${index}`} finding={finding} />
                    ))}
                  </ul>
                )}
              </section>

              {/* Repair panel — only for a repairable builder_setup with a
                  supported action. Otherwise a calm "nothing to do" note. */}
              <section>
                <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-slate-400">Repair</h3>

                {!panelEligible || !hasActionable ? (
                  <p className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-400">
                    {findings.length === 0
                      ? "No repair needed."
                      : "No supported repair action for these findings."}
                  </p>
                ) : (
                  <div className="flex flex-col gap-3">
                    {actionableKeys.map((key) => (
                      <RepairFieldControl
                        key={key}
                        fieldKey={key}
                        current={livePayload?.[key]}
                        removable={REPAIR_REMOVABLE_FIELDS.includes(key)}
                        options={optionsFor(key)}
                        entry={draft.fields[key]}
                        onChange={onFieldChange}
                      />
                    ))}

                    {unknownSectionKeys.length > 0 && (
                      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                        <span className="text-xs font-semibold text-slate-200">
                          {FIELD_LABELS.include_sections}
                        </span>
                        <p className="mt-0.5 text-[11px] text-slate-500">
                          Remove sections that are no longer recognized.
                        </p>
                        <div className="mt-2 flex flex-col gap-1.5">
                          {unknownSectionKeys.map((sectionKey) => (
                            <label key={sectionKey} className="flex items-center gap-2 text-xs text-slate-300">
                              <input
                                type="checkbox"
                                checked={(draft.removeSections || []).includes(sectionKey)}
                                onChange={() => toggleSectionRemoval(sectionKey)}
                                className="h-3.5 w-3.5 accent-emerald-400"
                              />
                              <span className="font-mono text-[11px]">{sectionKey}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Mode selector */}
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                      <span className="text-xs font-semibold text-slate-200">Apply mode</span>
                      <div className="mt-2 flex flex-col gap-1.5 text-xs text-slate-300">
                        <label className="flex items-center gap-2">
                          <input
                            type="radio"
                            name="repair-mode"
                            checked={draft.mode === REPAIR_MODE_IN_PLACE}
                            onChange={() => setMode(REPAIR_MODE_IN_PLACE)}
                            className="accent-sky-400"
                          />
                          Repair this shortcut (update in place)
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="radio"
                            name="repair-mode"
                            checked={draft.mode === REPAIR_MODE_CLONE}
                            onChange={() => setMode(REPAIR_MODE_CLONE)}
                            className="accent-sky-400"
                          />
                          Create a repaired copy (keep the original)
                        </label>
                      </div>
                      {draft.mode === REPAIR_MODE_CLONE && (
                        <input
                          type="text"
                          value={draft.cloneName}
                          onChange={(e) => setDraft((d) => ({ ...d, cloneName: e.target.value }))}
                          placeholder={defaultCloneName(view?.name)}
                          className="mt-2 h-8 w-full rounded-lg border border-white/15 bg-[#0B0F19] px-2 text-xs text-slate-200"
                        />
                      )}
                    </div>

                    {previewError && (
                      <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
                        {previewError}
                      </div>
                    )}

                    {/* Preview result + diff */}
                    {preview?.result && previewFresh && (
                      <div className="rounded-xl border border-sky-400/20 bg-sky-400/[0.06] p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-bold uppercase tracking-wide text-sky-200">
                            Preview ({preview.result.mode})
                          </span>
                          <StatusPill status={preview.result?.proposed?.validity?.status || "valid"} />
                        </div>
                        <div className="mt-2">
                          <DiffList diff={preview.result.diff} />
                        </div>
                        {Array.isArray(preview.result.warnings) && preview.result.warnings.length > 0 && (
                          <p className="mt-2 text-[11px] text-amber-300">{preview.result.warnings.join(" ")}</p>
                        )}
                        <p className="mt-2 text-[11px] text-slate-400">
                          The original is unchanged until you apply.
                        </p>
                      </div>
                    )}

                    {/* Stale-preview note */}
                    {preview?.result && !previewFresh && (
                      <p className="rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-[11px] text-amber-200">
                        Your choices changed — preview again before applying.
                      </p>
                    )}

                    {applyError && (
                      <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
                        {applyError}
                      </div>
                    )}

                    {/* Confirm step */}
                    {confirmOpen && (
                      <div className="rounded-xl border border-amber-400/30 bg-amber-400/[0.08] p-3">
                        <p className="text-xs text-amber-100">
                          {draft.mode === REPAIR_MODE_CLONE
                            ? "This will create a repaired copy and leave the original unchanged."
                            : "This will update the saved shortcut."}
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <button
                            type="button"
                            onClick={handleApply}
                            disabled={applying}
                            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-emerald-400/40 bg-emerald-400/15 px-3 text-xs font-bold text-emerald-100 hover:bg-emerald-400/25 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {applying ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                            {draft.mode === REPAIR_MODE_CLONE ? "Create copy" : "Update shortcut"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmOpen(false)}
                            disabled={applying}
                            className="inline-flex h-8 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3 text-xs font-semibold text-slate-200 hover:bg-white/[0.08]"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>
            </>
          )}
        </div>

        {/* Footer actions: Preview + Apply (only when a repair panel is shown). */}
        <div className="flex items-center justify-between gap-2 border-t border-white/10 px-5 py-3">
          {panelEligible && hasActionable ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handlePreview}
                disabled={!canPreview}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-sky-400/40 bg-sky-400/15 px-3.5 text-sm font-semibold text-sky-100 hover:bg-sky-400/25 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.03] disabled:text-slate-500"
              >
                {previewing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Preview repair
              </button>
              <button
                type="button"
                onClick={() => setConfirmOpen(true)}
                disabled={!canApply || confirmOpen}
                title={!previewFresh ? "Preview the repair first" : undefined}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-emerald-400/40 bg-emerald-400/15 px-3.5 text-sm font-bold text-emerald-100 hover:bg-emerald-400/25 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.03] disabled:text-slate-500"
              >
                <Wrench size={14} />
                Apply…
              </button>
            </div>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 hover:bg-white/[0.08]"
          >
            Close
          </button>
        </div>
      </aside>
    </div>
  );
}
