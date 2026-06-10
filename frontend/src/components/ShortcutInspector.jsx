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

// Maps the status-badge tone to a semantic .sg-status-pill modifier.
const STATUS_TONE = { valid: "ok", degraded: "warn", broken: "bad" };

const SEVERITY_META = {
  error: { Icon: AlertCircle, cls: "sev-error", label: "Error" },
  warning: { Icon: AlertTriangle, cls: "sev-warn", label: "Warning" },
  info: { Icon: Info, cls: "sev-info", label: "Info" },
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
    <span className={`sg-status-pill ${STATUS_TONE[badge.tone] || "ok"}`}>
      {badge.label}
    </span>
  );
}

function FindingRow({ finding }) {
  const meta = SEVERITY_META[finding?.severity] || SEVERITY_META.info;
  const { Icon } = meta;
  const candidateCount = Array.isArray(finding?.candidates) ? finding.candidates.length : 0;
  return (
    <li className="sg-insp-card">
      <div className="sg-insp-find">
        <Icon className={meta.cls} />
        <div className="sg-insp-find-body">
          <div className="sg-insp-find-top">
            <span className="sg-insp-code">{finding?.code || "unknown"}</span>
            {finding?.field && <span className="sg-insp-fieldtag">{finding.field}</span>}
            <span className={`sg-insp-sev ${meta.cls}`}>{meta.label}</span>
          </div>
          <p className="sg-insp-msg">{finding?.message || "No description."}</p>
          {finding?.current_value !== undefined && finding?.current_value !== null && (
            <p className="sg-insp-sub">
              Current: <span className="v">{String(finding.current_value)}</span>
            </p>
          )}
          <p className="sg-insp-sub">
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
    <div className="sg-insp-card">
      <div className="sg-insp-ctl-top">
        <span className="sg-insp-ctl-label">{FIELD_LABELS[fieldKey] || fieldKey}</span>
        {current !== undefined && current !== null && current !== "" && (
          <span className="sg-insp-ctl-now">now: {String(current)}</span>
        )}
      </div>
      <div className="sg-insp-ctl-row">
        <select
          value={action}
          onChange={(e) => onChange(fieldKey, { action: e.target.value, value })}
          className="sg-insp-select"
        >
          <option value="keep">Keep current</option>
          <option value="replace">Replace with…</option>
          {removable && <option value="remove">Remove (use default)</option>}
        </select>
        {action === "replace" && (
          <select
            value={value}
            onChange={(e) => onChange(fieldKey, { action: "replace", value: e.target.value })}
            className="sg-insp-select grow"
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
        <p className="sg-insp-sub sev-warn">
          No replacement candidates are available for this field.
        </p>
      )}
    </div>
  );
}

function DiffList({ diff }) {
  if (!Array.isArray(diff) || diff.length === 0) {
    return <p className="sg-insp-sub">No field changes.</p>;
  }
  const fmt = (v) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
  return (
    <ul className="sg-insp-diff">
      {diff.map((d, i) => (
        <li key={`${d?.field || "d"}-${i}`}>
          <span className="f">{d?.field}</span>
          <span className="from">{fmt(d?.from)}</span>
          <span className="arr">→</span>
          <span className="to">{fmt(d?.to)}</span>
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
    <div className="sg-drawer-root" style={{ zIndex: 80 }}>
      <button type="button" aria-label="Close inspector" className="sg-drawer-scrim" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Shortcut inspector"
        className="sg-drawer-sheet sg-insp"
      >
        <div className="sg-insp-head">
          <div className="sg-insp-titles">
            <div className="sg-insp-titlerow">
              <h2 className="sg-insp-title">{view?.name || "Shortcut"}</h2>
              <StatusPill status={status} />
            </div>
            <p className="sg-insp-eyebrow">{typeLabel}</p>
          </div>
          <button type="button" onClick={onClose} className="sg-drawer-close" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="sg-insp-body">
          {loading && (
            <div className="sg-insp-loading">
              <Loader2 className="sg-spin" /> Inspecting shortcut…
            </div>
          )}

          {notFound && (
            <div className="sg-insp-note warn">
              This shortcut no longer exists. It may have been deleted — close and refresh the list.
            </div>
          )}

          {error && <div className="sg-insp-note bad">{error}</div>}

          {applied && (
            <div className="sg-insp-banner">
              <CheckCircle2 />
              <div style={{ minWidth: 0 }}>
                <p className="sg-insp-banner-t">
                  {applied.mode === REPAIR_MODE_CLONE ? "Repaired copy created." : "Shortcut repaired."}
                </p>
                <p className="sg-insp-banner-d">
                  {applied.mode === REPAIR_MODE_CLONE
                    ? `New shortcut “${applied.name}” created; the original is unchanged.`
                    : "The saved shortcut was updated."}
                  {applied.status ? ` New status: ${applied.status}.` : ""}
                </p>
                {applied.warnings?.length > 0 && (
                  <p className="sg-insp-banner-w">{applied.warnings.join(" ")}</p>
                )}
              </div>
            </div>
          )}

          {!loading && !notFound && (
            <>
              {/* Legacy valid/reason, shown when relevant for transparency. */}
              {view?.valid === false && (
                <div className="sg-insp-note">
                  <span style={{ color: "var(--muted)" }}>Legacy check:</span> blocked
                  {view?.reason ? ` — ${view.reason}` : ""}
                </div>
              )}

              <section className="sg-insp-section">
                <div className="sg-insp-sec-head">
                  <h3>Findings</h3>
                  <span className="sg-insp-sec-meta">
                    {counts.error} error{counts.error === 1 ? "" : "s"} · {counts.warning} warning
                    {counts.warning === 1 ? "" : "s"} · {counts.info} info
                  </span>
                </div>
                {findings.length === 0 ? (
                  <p className="sg-insp-note ok">
                    No problems found. This shortcut resolves exactly as saved.
                  </p>
                ) : (
                  <ul className="sg-insp-list">
                    {findings.map((finding, index) => (
                      <FindingRow key={`${finding?.code || "f"}-${index}`} finding={finding} />
                    ))}
                  </ul>
                )}
              </section>

              {/* Repair panel — only for a repairable builder_setup with a
                  supported action. Otherwise a calm "nothing to do" note. */}
              <section className="sg-insp-section">
                <div className="sg-insp-sec-head">
                  <h3>Repair</h3>
                </div>

                {!panelEligible || !hasActionable ? (
                  <p className="sg-insp-note">
                    {findings.length === 0
                      ? "No repair needed."
                      : "No supported repair action for these findings."}
                  </p>
                ) : (
                  <div className="sg-insp-list">
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
                      <div className="sg-insp-card">
                        <span className="sg-insp-ctl-label">
                          {FIELD_LABELS.include_sections}
                        </span>
                        <p className="sg-insp-sub">
                          Remove sections that are no longer recognized.
                        </p>
                        <div className="sg-insp-opts">
                          {unknownSectionKeys.map((sectionKey) => (
                            <label key={sectionKey} className="sg-insp-opt">
                              <input
                                type="checkbox"
                                checked={(draft.removeSections || []).includes(sectionKey)}
                                onChange={() => toggleSectionRemoval(sectionKey)}
                              />
                              <span className="mono">{sectionKey}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Mode selector */}
                    <div className="sg-insp-card">
                      <span className="sg-insp-ctl-label">Apply mode</span>
                      <div className="sg-insp-opts">
                        <label className="sg-insp-opt">
                          <input
                            type="radio"
                            name="repair-mode"
                            checked={draft.mode === REPAIR_MODE_IN_PLACE}
                            onChange={() => setMode(REPAIR_MODE_IN_PLACE)}
                          />
                          Repair this shortcut (update in place)
                        </label>
                        <label className="sg-insp-opt">
                          <input
                            type="radio"
                            name="repair-mode"
                            checked={draft.mode === REPAIR_MODE_CLONE}
                            onChange={() => setMode(REPAIR_MODE_CLONE)}
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
                          className="sg-insp-input"
                        />
                      )}
                    </div>

                    {previewError && <div className="sg-insp-note bad">{previewError}</div>}

                    {/* Preview result + diff */}
                    {preview?.result && previewFresh && (
                      <div className="sg-insp-card accent">
                        <div className="sg-insp-ctl-top">
                          <span className="sg-insp-eyebrow" style={{ marginTop: 0, color: "#C7C9FB" }}>
                            Preview ({preview.result.mode})
                          </span>
                          <StatusPill status={preview.result?.proposed?.validity?.status || "valid"} />
                        </div>
                        <DiffList diff={preview.result.diff} />
                        {Array.isArray(preview.result.warnings) && preview.result.warnings.length > 0 && (
                          <p className="sg-insp-sub sev-warn">{preview.result.warnings.join(" ")}</p>
                        )}
                        <p className="sg-insp-sub">
                          The original is unchanged until you apply.
                        </p>
                      </div>
                    )}

                    {/* Stale-preview note */}
                    {preview?.result && !previewFresh && (
                      <p className="sg-insp-note warn">
                        Your choices changed — preview again before applying.
                      </p>
                    )}

                    {applyError && <div className="sg-insp-note bad">{applyError}</div>}

                    {/* Confirm step */}
                    {confirmOpen && (
                      <div className="sg-insp-card warn">
                        <p className="sg-insp-msg" style={{ marginTop: 0, color: "#F4C76B" }}>
                          {draft.mode === REPAIR_MODE_CLONE
                            ? "This will create a repaired copy and leave the original unchanged."
                            : "This will update the saved shortcut."}
                        </p>
                        <div className="sg-insp-ctl-row">
                          <button
                            type="button"
                            onClick={handleApply}
                            disabled={applying}
                            className="sg-act ok sm"
                          >
                            {applying ? <Loader2 size={13} className="sg-spin" /> : <CheckCircle2 size={13} />}
                            {draft.mode === REPAIR_MODE_CLONE ? "Create copy" : "Update shortcut"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmOpen(false)}
                            disabled={applying}
                            className="sg-act sm"
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
        <div className="sg-insp-foot">
          {panelEligible && hasActionable ? (
            <div className="sg-insp-foot-l">
              <button
                type="button"
                onClick={handlePreview}
                disabled={!canPreview}
                className="sg-act accent"
              >
                {previewing ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
                Preview repair
              </button>
              <button
                type="button"
                onClick={() => setConfirmOpen(true)}
                disabled={!canApply || confirmOpen}
                title={!previewFresh ? "Preview the repair first" : undefined}
                className="sg-act ok"
              >
                <Wrench size={14} />
                Apply…
              </button>
            </div>
          ) : (
            <span />
          )}
          <button type="button" onClick={onClose} className="sg-act">
            Close
          </button>
        </div>
      </aside>
    </div>
  );
}
