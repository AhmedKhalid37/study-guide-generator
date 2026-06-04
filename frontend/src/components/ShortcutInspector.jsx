import React, { useEffect, useMemo, useState } from "react";
import { AlertCircle, AlertTriangle, Info, Loader2, Lock, X } from "lucide-react";
import { inspectShortcut } from "../api/client";
import {
  countFindingsBySeverity,
  shortcutStatus,
  statusBadge,
} from "../shortcutStatus";
import { TYPE_LABELS } from "../shortcutMeta";

// ── Read-only Shortcut Inspector (Slice 2) ───────────────────────────────────
//
// Opens from a Home shortcut badge or the Customize modal. It calls the Slice 1
// read-only GET /api/shortcuts/{id}/inspect and renders: the legacy valid/reason,
// the 3-tier validity status, every finding, and a summary of the safe repair
// CANDIDATES the backend offers. It NEVER mutates a shortcut — there is no
// Save/Apply/Repair action in this slice. Repair preview + apply land in Slice 3.

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

function CandidatesSummary({ candidates }) {
  const rows = useMemo(() => {
    if (!candidates || typeof candidates !== "object") return [];
    const out = [];
    const providers = Array.isArray(candidates.providers) ? candidates.providers : [];
    const configured = providers.filter((p) => p?.configured).length;
    out.push({ key: "providers", label: "Providers", value: `${configured} configured / ${providers.length} total` });

    const modelsByProvider = candidates.models_by_provider || {};
    const modelLines = Object.entries(modelsByProvider)
      .map(([pid, models]) => `${pid}: ${Array.isArray(models) ? models.length : 0}`)
      .join(" · ");
    out.push({ key: "models", label: "Models", value: modelLines || "none" });

    out.push({ key: "styles", label: "Styles", value: String((candidates.styles || []).length) });
    out.push({ key: "presets", label: "Generator presets", value: String((candidates.generator_presets || []).length) });
    out.push({ key: "sections", label: "Sections", value: String((candidates.sections || []).length) });
    out.push({
      key: "axes",
      label: "Depth / difficulty",
      value: `${(candidates.output_depth || []).length} / ${(candidates.difficulty || []).length}`,
    });
    return out;
  }, [candidates]);

  if (rows.length === 0) {
    return <p className="text-xs text-slate-500">No repair candidates available.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-2">
      {rows.map((row) => (
        <div key={row.key} className="rounded-lg border border-white/10 bg-white/[0.02] px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-slate-500">{row.label}</dt>
          <dd className="text-xs text-slate-300">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function ShortcutInspector({ shortcut, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);

  const shortcutId = shortcut?.id;

  useEffect(() => {
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
        // requestJson surfaces the server `detail`; a 404 typically reads as
        // "Shortcut not found". Treat it as a distinct, calm state.
        if (/not found/i.test(message) || /404/.test(message)) setNotFound(true);
        else setError(message);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [shortcutId]);

  // Seed header fields from the list view while the fetch is in flight, then
  // prefer the authoritative inspect response once it arrives.
  const view = data || shortcut || {};
  const status = shortcutStatus(view);
  const findings = Array.isArray(view?.validity?.findings) ? view.validity.findings : [];
  const counts = countFindingsBySeverity(findings);
  const typeLabel = TYPE_LABELS[view?.type] || view?.type || "Shortcut";

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

              <section>
                <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-slate-400">
                  Available repair candidates
                </h3>
                <CandidatesSummary candidates={data?.repair_candidates} />
              </section>

              <div className="flex items-start gap-2 rounded-lg border border-sky-400/20 bg-sky-400/[0.06] px-3 py-2 text-xs text-sky-100">
                <Lock size={14} className="mt-0.5 shrink-0 text-sky-300" />
                <span>Repair actions are not available yet. This inspector is read-only.</span>
              </div>
            </>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-white/10 px-5 py-3">
          <button
            type="button"
            disabled
            title="Repair lands in a later slice"
            className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3.5 text-sm font-semibold text-slate-500"
          >
            Repair (coming next)
          </button>
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
