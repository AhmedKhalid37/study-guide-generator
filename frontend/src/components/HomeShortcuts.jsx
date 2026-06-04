import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  ChevronRight,
  Copy,
  Download,
  Info,
  Loader2,
  Pencil,
  Pin,
  PinOff,
  Plus,
  RotateCcw,
  Search,
  Settings2,
  Trash2,
  Upload,
  Wand2,
  Wrench,
  X
} from "lucide-react";
import {
  createShortcut,
  deleteShortcut,
  exportShortcutUrl,
  exportShortcutsUrl,
  getOptions,
  getStyles,
  importShortcuts,
  listShortcuts,
  previewImportShortcuts,
  reorderShortcuts,
  resetShortcutDefaults,
  updateShortcut
} from "../api/client";
import {
  COLOR_CHOICES,
  EXPORT_FORMATS,
  ICON_CHOICES,
  INPUT_TYPES,
  INPUT_TYPE_LABELS,
  SHORTCUT_TYPES,
  summarizePayload,
  TOOL_KEYS,
  TOOL_LABELS,
  TYPE_LABELS,
  VIEW_BASES,
  VIEW_BASE_LABELS,
  generatorPresetOptions,
  payloadHasSavedPrompt,
  withSavedPrompt,
  MAX_SAVED_PROMPT_CHARS
} from "../shortcutMeta";
import RecentJobsPanel from "./RecentJobsPanel";
import ShortcutInspector from "./ShortcutInspector";
import {
  activationDecision,
  ACTIVATE_BLOCKED,
  ACTIVATE_CONFIRM,
  issueCount,
  shortcutFindings,
  shortcutStatus,
  statusBadge,
  STATUS_BROKEN,
  STATUS_DEGRADED,
  STATUS_VALID
} from "../shortcutStatus";

const DEFAULT_COLOR = COLOR_CHOICES[0];

// Tailwind classes per validity tier, shared by the Home card badge and the
// customize-row chip so all surfaces read the same.
const STATUS_CHIP_CLASSES = {
  [STATUS_VALID]: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  [STATUS_DEGRADED]: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  [STATUS_BROKEN]: "border-red-400/30 bg-red-400/10 text-red-200"
};

// ── Home page ───────────────────────────────────────────────────────────────

export default function HomeShortcuts({
  jobs = [],
  jobsRefreshKey,
  onActivateShortcut,
  onNewGuide,
  onNavigate,
  currentBuilderSetup
}) {
  const [shortcuts, setShortcuts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  // Read-only inspector target (a shortcut view), or null when closed.
  const [inspecting, setInspecting] = useState(null);
  // A degraded shortcut awaiting an explicit launch confirmation, or null.
  const [confirmDegraded, setConfirmDegraded] = useState(null);
  // A broken shortcut the user clicked (blocked from launch), or null.
  const [blockedShortcut, setBlockedShortcut] = useState(null);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  // Gate every Home launch through the shared activation decision so the legacy
  // `valid` guard still controls launch/block, but a degraded-yet-launchable
  // shortcut asks first instead of silently launching with ignored settings.
  const requestActivate = useCallback(
    (shortcut) => {
      if (!shortcut) return;
      const decision = activationDecision(shortcut);
      if (decision === ACTIVATE_BLOCKED) {
        setBlockedShortcut(shortcut);
        return;
      }
      if (decision === ACTIVATE_CONFIRM) {
        setConfirmDegraded(shortcut);
        return;
      }
      onActivateShortcut?.(shortcut);
    },
    [onActivateShortcut]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listShortcuts()
      .then((data) => {
        if (cancelled) return;
        setShortcuts(Array.isArray(data?.shortcuts) ? data.shortcuts : []);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setShortcuts([]);
        setError(err?.message || "Could not load shortcuts.");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const pinned = useMemo(() => shortcuts.filter((s) => s.pinned), [shortcuts]);

  return (
    <div className="sg-page sg-home">
      <div className="sg-grid-glow" />
      <div className="sg-page-head">
        <div>
          <h1>Good evening, Ahmed</h1>
          <p>What are you preparing today? Jump back in with a shortcut, or start fresh.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="sg-ghost-button" onClick={() => onNavigate?.("library")}>
            <Search size={14} className="mr-1.5 inline" />
            Find Guide
          </button>
          <button type="button" className="sg-ghost-button" onClick={() => setCustomizeOpen(true)}>
            <Settings2 size={14} className="mr-1.5 inline" />
            Customize Shortcuts
          </button>
          <button type="button" className="sg-cta sg-press-btn" onClick={() => onNewGuide?.()}>
            <Plus size={16} stroke="#1A1206" strokeWidth={2.6} />
            New Guide
          </button>
        </div>
      </div>

      <div className="sg-section-head">
        <h2>Pinned shortcuts</h2>
      </div>

      {error && (
        <div className="sg-style-alert mb-3">
          <AlertCircle size={15} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="sg-command-grid">
          {[0, 1, 2].map((i) => (
            <div key={i} className="sg-command-card" style={{ opacity: 0.4 }} />
          ))}
        </div>
      ) : pinned.length === 0 ? (
        <div className="sg-empty-shortcuts">
          <p>No pinned shortcuts yet.</p>
          <button type="button" className="sg-ghost-button" onClick={() => setCustomizeOpen(true)}>
            Customize shortcuts
          </button>
        </div>
      ) : (
        <div className="sg-command-grid">
          {pinned.map((shortcut, index) => (
            <ShortcutCard
              key={shortcut.id}
              shortcut={shortcut}
              delay={index * 45}
              onActivate={() => requestActivate(shortcut)}
              onInspect={() => setInspecting(shortcut)}
            />
          ))}
        </div>
      )}

      <div className="sg-section-head sg-recent-head">
        <h2>Recent Guides</h2>
        <button type="button" className="sg-ghost-button" onClick={() => onNavigate?.("library")}>
          View all
        </button>
      </div>
      <RecentJobsPanel embedded refreshKey={jobsRefreshKey} />

      {customizeOpen && (
        <CustomizeShortcutsModal
          shortcuts={shortcuts}
          currentBuilderSetup={currentBuilderSetup}
          onClose={() => setCustomizeOpen(false)}
          onChanged={reload}
          onActivateShortcut={onActivateShortcut}
        />
      )}

      {confirmDegraded && (
        <DegradedActivationDialog
          shortcut={confirmDegraded}
          onContinue={() => {
            const target = confirmDegraded;
            setConfirmDegraded(null);
            onActivateShortcut?.(target);
          }}
          onRepair={() => {
            setInspecting(confirmDegraded);
            setConfirmDegraded(null);
          }}
          onCancel={() => setConfirmDegraded(null)}
        />
      )}

      {blockedShortcut && (
        <BrokenActivationDialog
          shortcut={blockedShortcut}
          onInspect={() => {
            setInspecting(blockedShortcut);
            setBlockedShortcut(null);
          }}
          onCancel={() => setBlockedShortcut(null)}
        />
      )}

      {inspecting && (
        <ShortcutInspector
          shortcut={inspecting}
          onClose={() => setInspecting(null)}
          onRepaired={reload}
        />
      )}
    </div>
  );
}

// ── Activation dialogs (degraded confirm + broken block) ──────────────────────
//
// A degraded shortcut is still launchable (legacy valid === true) but some saved
// settings may be ignored/defaulted. Rather than launch silently we ask first
// and offer to repair instead. A broken shortcut (valid === false) stays blocked
// and only offers Inspect/Repair — never a silent launch.

// Top finding messages, capped so the dialog stays calm. Prefers warning/error
// findings (the actionable ones) and falls back to the legacy reason.
function topFindingMessages(shortcut, cap = 3) {
  const findings = shortcutFindings(shortcut);
  const ranked = [
    ...findings.filter((f) => f?.severity === "error"),
    ...findings.filter((f) => f?.severity === "warning"),
    ...findings.filter((f) => f?.severity === "info")
  ];
  const messages = ranked.map((f) => f?.message).filter(Boolean);
  if (messages.length === 0 && shortcut?.reason) return [shortcut.reason];
  return messages.slice(0, cap);
}

function DegradedActivationDialog({ shortcut, onContinue, onRepair, onCancel }) {
  const issues = issueCount(shortcut);
  const messages = topFindingMessages(shortcut);
  const findings = shortcutFindings(shortcut);
  const extra = Math.max(0, findings.length - messages.length);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button type="button" aria-label="Cancel" className="absolute inset-0 cursor-default bg-black/60" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#0B0F19] p-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-bold text-white">
              Launch “{shortcut.name}”?
            </h2>
            <p className="mt-1 inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[11px] font-semibold text-amber-200">
              Needs attention{issues > 0 ? ` · ${issues} issue${issues === 1 ? "" : "s"} found` : ""}
            </p>
            {messages.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1 text-xs text-slate-300">
                {messages.map((message, index) => (
                  <li key={index} className="flex items-start gap-1.5">
                    <span className="mt-0.5 text-amber-400">•</span>
                    <span className="min-w-0">{message}</span>
                  </li>
                ))}
                {extra > 0 && (
                  <li className="text-[11px] text-slate-500">+{extra} more in the inspector</li>
                )}
              </ul>
            )}
            <p className="mt-2 text-xs text-slate-400">
              You can continue, but some saved settings may be ignored or replaced by defaults.
            </p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button type="button" onClick={onCancel} className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 hover:bg-white/[0.08]">
            Cancel
          </button>
          <button type="button" onClick={onRepair} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-sky-400/40 bg-sky-400/15 px-3.5 text-sm font-bold text-sky-100 hover:bg-sky-400/25">
            <Wrench size={14} /> Repair instead
          </button>
          <button type="button" autoFocus onClick={onContinue} className="inline-flex h-9 items-center rounded-lg border border-[#F97316]/50 bg-[#F97316]/80 px-3.5 text-sm font-bold text-white hover:bg-[#F97316]">
            Continue anyway
          </button>
        </div>
      </div>
    </div>
  );
}

function BrokenActivationDialog({ shortcut, onInspect, onCancel }) {
  const messages = topFindingMessages(shortcut);
  const hint = invalidHint(shortcut);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button type="button" aria-label="Cancel" className="absolute inset-0 cursor-default bg-black/60" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#0B0F19] p-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-bold text-white">This shortcut is broken.</h2>
            <p className="mt-1 text-xs text-slate-400">
              “{shortcut.name}” can’t launch as saved. {hint}
            </p>
            {messages.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1 text-xs text-slate-300">
                {messages.map((message, index) => (
                  <li key={index} className="flex items-start gap-1.5">
                    <span className="mt-0.5 text-red-400">•</span>
                    <span className="min-w-0">{message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 hover:bg-white/[0.08]">
            Cancel
          </button>
          <button type="button" autoFocus onClick={onInspect} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-sky-400/40 bg-sky-400/15 px-3.5 text-sm font-bold text-sky-100 hover:bg-sky-400/25">
            <Wrench size={14} /> Inspect / Repair
          </button>
        </div>
      </div>
    </div>
  );
}

function shortcutEmoji(shortcut) {
  if (shortcut.icon && shortcut.icon.trim()) return shortcut.icon.trim();
  if (shortcut.type === "tool") return "🛠️";
  if (shortcut.type === "library_view") return "🗂️";
  return "📝";
}

function ShortcutCard({ shortcut, delay, onActivate, onInspect }) {
  const accent = shortcut.color || DEFAULT_COLOR;
  // Activation gating stays on the LEGACY `valid` boolean so Home behaviour is
  // byte-for-byte unchanged (DesktopDashboard owns the routing). The badge below
  // is driven by the richer 3-tier validity.status and is purely informational.
  const invalid = shortcut.valid === false;
  const typeLabel = TYPE_LABELS[shortcut.type] || shortcut.type;
  const reasonHint = invalid ? invalidHint(shortcut) : null;
  const status = shortcutStatus(shortcut);
  const badge = statusBadge(status);
  // Valid shortcuts stay quiet (no badge); degraded/broken surface a chip.
  const showBadge = status === STATUS_DEGRADED || status === STATUS_BROKEN;

  function handleInspect(event) {
    event.stopPropagation();
    event.preventDefault();
    onInspect?.();
  }

  return (
    <button
      type="button"
      className={`sg-command-card sg-press-btn ${invalid ? "sg-shortcut-invalid" : ""}`}
      onClick={onActivate}
      style={{ "--accent": accent, animationDelay: `${delay}ms` }}
      title={invalid ? reasonHint : summarizePayload(shortcut)}
      aria-disabled={invalid ? "true" : undefined}
    >
      <span className="sg-card-corner" />
      <span className="sg-card-top">
        <span className="sg-card-icon" style={{ fontSize: 24 }} aria-hidden>
          {shortcutEmoji(shortcut)}
        </span>
        <span className="ml-auto inline-flex items-center gap-1.5">
          {showBadge && (
            <span
              role="button"
              tabIndex={0}
              onClick={handleInspect}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") handleInspect(e);
              }}
              className={`inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                STATUS_CHIP_CLASSES[status] || ""
              }`}
              title={`${badge.label} — click to inspect`}
            >
              {status === STATUS_BROKEN ? <AlertCircle size={11} /> : <AlertTriangle size={11} />}
              {badge.label}
            </span>
          )}
          <span
            role="button"
            tabIndex={0}
            onClick={handleInspect}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") handleInspect(e);
            }}
            className="grid h-6 w-6 cursor-pointer place-items-center rounded-lg text-slate-400 hover:bg-white/10 hover:text-white"
            title="Inspect shortcut"
            aria-label="Inspect shortcut"
          >
            <Info size={13} />
          </span>
        </span>
      </span>
      <strong>{shortcut.name}</strong>
      <p>{invalid ? reasonHint : shortcut.description || summarizePayload(shortcut)}</p>
      <span className="sg-card-bottom">
        <em>{typeLabel}</em>
        <i>
          <ChevronRight size={14} />
        </i>
      </span>
    </button>
  );
}

// Map the backend's terse reason onto actionable, human copy.
function invalidHint(shortcut) {
  const reason = shortcut.reason || "Unavailable";
  const provider = shortcut.payload?.provider;
  if (reason.includes("provider")) {
    const name = provider ? provider.charAt(0).toUpperCase() + provider.slice(1) : "this provider";
    return `Needs ${name} — add a key in Models`;
  }
  if (reason.includes("generator preset")) return "Its generator preset is unavailable — edit the shortcut";
  if (reason.includes("style")) return "Its style is unavailable — edit the shortcut";
  if (reason.includes("tool")) return "This tool is unavailable";
  if (reason.includes("view")) return "This library view is unavailable";
  return reason;
}

// ── Customize modal ──────────────────────────────────────────────────────────

function CustomizeShortcutsModal({ shortcuts, currentBuilderSetup, onClose, onChanged, onActivateShortcut }) {
  // mode: list | form | import
  const [mode, setMode] = useState("list");
  const [editing, setEditing] = useState(null); // shortcut being edited, or null for create
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmReset, setConfirmReset] = useState(false);
  // Read-only inspector target (a shortcut view), or null when closed.
  const [inspecting, setInspecting] = useState(null);
  // Local working copy so reorder/pin feel instant; persisted on each action.
  const [items, setItems] = useState(shortcuts);

  useEffect(() => {
    setItems(shortcuts);
  }, [shortcuts]);

  const refresh = useCallback(async () => {
    try {
      const data = await listShortcuts();
      setItems(Array.isArray(data?.shortcuts) ? data.shortcuts : []);
    } catch {
      // keep current items; the parent reload is the source of truth on close
    }
    onChanged?.();
  }, [onChanged]);

  const handleTogglePin = useCallback(
    async (shortcut) => {
      setBusyId(shortcut.id);
      setError(null);
      try {
        await updateShortcut(shortcut.id, { pinned: !shortcut.pinned });
        await refresh();
      } catch (err) {
        setError(err?.message || "Could not update shortcut.");
      } finally {
        setBusyId(null);
      }
    },
    [refresh]
  );

  const handleMove = useCallback(
    async (index, direction) => {
      const next = [...items];
      const target = index + direction;
      if (target < 0 || target >= next.length) return;
      [next[index], next[target]] = [next[target], next[index]];
      setItems(next); // optimistic
      setError(null);
      try {
        await reorderShortcuts(
          next.map((s, i) => ({ id: s.id, order: i, pinned: s.pinned }))
        );
        await refresh();
      } catch (err) {
        setError(err?.message || "Could not reorder shortcuts.");
        await refresh();
      }
    },
    [items, refresh]
  );

  const handleDuplicate = useCallback(
    async (shortcut) => {
      setBusyId(shortcut.id);
      setError(null);
      try {
        await createShortcut({
          name: `${shortcut.name} copy`,
          description: shortcut.description,
          type: shortcut.type,
          icon: shortcut.icon,
          color: shortcut.color,
          pinned: false,
          payload: shortcut.payload
        });
        await refresh();
      } catch (err) {
        setError(err?.message || "Could not duplicate shortcut.");
      } finally {
        setBusyId(null);
      }
    },
    [refresh]
  );

  const handleDelete = useCallback(async () => {
    if (!confirmDelete) return;
    setBusyId(confirmDelete.id);
    setError(null);
    try {
      await deleteShortcut(confirmDelete.id);
      setConfirmDelete(null);
      await refresh();
    } catch (err) {
      setError(err?.message || "Could not delete shortcut.");
    } finally {
      setBusyId(null);
    }
  }, [confirmDelete, refresh]);

  const handleReset = useCallback(async () => {
    setError(null);
    try {
      await resetShortcutDefaults();
      setConfirmReset(false);
      await refresh();
    } catch (err) {
      setError(err?.message || "Could not reset shortcuts.");
    }
  }, [refresh]);

  const handleSaved = useCallback(async () => {
    setMode("list");
    setEditing(null);
    await refresh();
  }, [refresh]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button type="button" aria-label="Close" className="absolute inset-0 cursor-default bg-black/60" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        className="sg-shortcuts-modal relative flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0B0F19] shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3.5">
          <div className="flex items-center gap-2">
            <Settings2 size={16} className="text-[#F97316]" />
            <h2 className="text-sm font-bold text-white">
              {mode === "form" ? (editing ? "Edit shortcut" : "New shortcut") : mode === "import" ? "Import shortcuts" : "Customize shortcuts"}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-white">
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="mx-5 mt-3 flex items-center gap-2 rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {mode === "list" && (
          <>
            <div className="flex flex-wrap items-center gap-2 px-5 py-3">
              <button type="button" className="sg-modal-action" onClick={() => { setEditing(null); setMode("form"); }}>
                <Plus size={14} /> New
              </button>
              <button type="button" className="sg-modal-action" onClick={() => setMode("import")}>
                <Upload size={14} /> Import
              </button>
              <a className="sg-modal-action" href={exportShortcutsUrl()} download="shortcuts.json">
                <Download size={14} /> Export all
              </a>
              <div className="flex-1" />
              <button type="button" className="sg-modal-action" onClick={() => setConfirmReset(true)}>
                <RotateCcw size={14} /> Reset defaults
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
              {items.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-400">No shortcuts. Create one or reset to defaults.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {items.map((shortcut, index) => (
                    <ShortcutRow
                      key={shortcut.id}
                      shortcut={shortcut}
                      busy={busyId === shortcut.id}
                      isFirst={index === 0}
                      isLast={index === items.length - 1}
                      onUp={() => handleMove(index, -1)}
                      onDown={() => handleMove(index, 1)}
                      onTogglePin={() => handleTogglePin(shortcut)}
                      onEdit={() => { setEditing(shortcut); setMode("form"); }}
                      onDuplicate={() => handleDuplicate(shortcut)}
                      onDelete={() => setConfirmDelete(shortcut)}
                      onInspect={() => setInspecting(shortcut)}
                    />
                  ))}
                </ul>
              )}
            </div>
          </>
        )}

        {mode === "form" && (
          <ShortcutForm
            editing={editing}
            currentBuilderSetup={currentBuilderSetup}
            onCancel={() => { setMode("list"); setEditing(null); }}
            onSaved={handleSaved}
            onError={setError}
          />
        )}

        {mode === "import" && (
          <ImportPanel
            onCancel={() => setMode("list")}
            onImported={handleSaved}
            onActivateShortcut={onActivateShortcut}
            onCloseModal={onClose}
            onError={setError}
          />
        )}
      </div>

      {confirmDelete && (
        <ConfirmDialog
          heading={`Delete "${confirmDelete.name}"?`}
          body="This removes the shortcut for good. You can export it first if you want to keep a copy."
          actionLabel="Delete"
          busy={busyId === confirmDelete.id}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={handleDelete}
        />
      )}
      {confirmReset && (
        <ConfirmDialog
          heading="Reset to default shortcuts?"
          body="This replaces your current shortcuts with the built-in defaults. Custom shortcuts will be lost unless exported."
          actionLabel="Reset"
          onCancel={() => setConfirmReset(false)}
          onConfirm={handleReset}
        />
      )}
      {inspecting && (
        <ShortcutInspector
          shortcut={inspecting}
          onClose={() => setInspecting(null)}
          onRepaired={refresh}
        />
      )}
    </div>
  );
}

function ShortcutRow({ shortcut, busy, isFirst, isLast, onUp, onDown, onTogglePin, onEdit, onDuplicate, onDelete, onInspect }) {
  const accent = shortcut.color || DEFAULT_COLOR;
  const status = shortcutStatus(shortcut);
  const badge = statusBadge(status);
  const issues = issueCount(shortcut);
  const showChip = status === STATUS_DEGRADED || status === STATUS_BROKEN;
  const firstFinding = shortcutFindings(shortcut)[0];
  return (
    <li className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5">
      <div className="flex flex-col">
        <button type="button" disabled={isFirst} onClick={onUp} className="rounded p-0.5 text-slate-400 hover:text-white disabled:opacity-25" title="Move up">
          <ArrowUp size={13} />
        </button>
        <button type="button" disabled={isLast} onClick={onDown} className="rounded p-0.5 text-slate-400 hover:text-white disabled:opacity-25" title="Move down">
          <ArrowDown size={13} />
        </button>
      </div>
      <span
        className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-lg"
        style={{ background: `color-mix(in srgb, ${accent} 16%, transparent)`, border: `1px solid color-mix(in srgb, ${accent} 30%, transparent)` }}
        aria-hidden
      >
        {shortcutEmoji(shortcut)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <strong className="truncate text-sm font-semibold text-white">{shortcut.name}</strong>
          <span className="shrink-0 rounded border border-white/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
            {TYPE_LABELS[shortcut.type] || shortcut.type}
          </span>
          {showChip && (
            <span
              className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${STATUS_CHIP_CLASSES[status] || ""}`}
              title={firstFinding?.message || shortcut.reason || badge.label}
            >
              {badge.label}{issues > 0 ? ` · ${issues}` : ""}
            </span>
          )}
          {payloadHasSavedPrompt(shortcut.payload) && (
            <span
              className="shrink-0 rounded border border-sky-400/30 bg-sky-400/10 px-1.5 py-0.5 text-[10px] text-sky-200"
              title="This shortcut includes saved prompt/source text (user content)."
            >
              Saved prompt
            </span>
          )}
        </div>
        <p className="truncate text-xs text-slate-400">{shortcut.description || summarizePayload(shortcut)}</p>
      </div>
      {busy && <Loader2 size={14} className="animate-spin text-slate-400" />}
      <div className="flex shrink-0 items-center gap-0.5">
        <IconBtn title="Inspect" onClick={onInspect}><Info size={14} /></IconBtn>
        <IconBtn title={shortcut.pinned ? "Unpin from Home" : "Pin to Home"} onClick={onTogglePin}>
          {shortcut.pinned ? <Pin size={14} className="text-[#F97316]" /> : <PinOff size={14} />}
        </IconBtn>
        <IconBtn title="Edit" onClick={onEdit}><Pencil size={14} /></IconBtn>
        <IconBtn title="Duplicate" onClick={onDuplicate}><Copy size={14} /></IconBtn>
        <a className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 hover:bg-white/10 hover:text-white" title="Export" href={exportShortcutUrl(shortcut.id)} download={`${shortcut.id}.json`}>
          <Download size={14} />
        </a>
        <IconBtn title="Delete" onClick={onDelete} danger><Trash2 size={14} /></IconBtn>
      </div>
    </li>
  );
}

function IconBtn({ title, onClick, danger, children }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`grid h-7 w-7 place-items-center rounded-lg hover:bg-white/10 ${danger ? "text-slate-400 hover:text-red-300" : "text-slate-400 hover:text-white"}`}
    >
      {children}
    </button>
  );
}

// ── Create / edit form ────────────────────────────────────────────────────────

const BLANK_BUILDER = {
  input_type: "generate_llm",
  provider: "",
  model: "",
  generator_preset: "",
  style: "",
  mode: "study_guide",
  target_pages: 20,
  modules: {},
  strict_math: true,
  export_formats: ["pdf"]
};

function ShortcutForm({ editing, currentBuilderSetup, onCancel, onSaved, onError }) {
  const [name, setName] = useState(editing?.name || "");
  const [description, setDescription] = useState(editing?.description || "");
  const [icon, setIcon] = useState(editing?.icon || ICON_CHOICES[0]);
  const [color, setColor] = useState(editing?.color || DEFAULT_COLOR);
  const [type, setType] = useState(editing?.type || "builder_setup");
  const [saving, setSaving] = useState(false);

  // Type-specific payload state.
  const [builder, setBuilder] = useState(() =>
    editing?.type === "builder_setup" ? { ...BLANK_BUILDER, ...editing.payload } : { ...BLANK_BUILDER }
  );
  const [tool, setTool] = useState(editing?.type === "tool" ? editing.payload?.tool || TOOL_KEYS[0] : TOOL_KEYS[0]);
  const [viewBase, setViewBase] = useState(() => {
    const v = editing?.type === "library_view" ? editing.payload?.view || "recent" : "recent";
    return v.includes(":") ? "search" : v;
  });
  const [viewQuery, setViewQuery] = useState(() => {
    const v = editing?.type === "library_view" ? editing.payload?.view || "" : "";
    return v.startsWith("search:") ? v.slice(7) : "";
  });

  // Opt-in saved prompt/source text. Only builder_setup shortcuts can carry it.
  // `savedPromptText` is the captured content (here, only ever an EXISTING saved
  // prompt being edited — the live-prompt capture path is the Builder's own
  // "Save as shortcut"). `savePrompt` governs whether it persists on save, so an
  // editor can deliberately strip user content from a shortcut.
  const [savedPromptText, setSavedPromptText] = useState(editing?.payload?.saved_prompt || "");
  const [savePrompt, setSavePrompt] = useState(Boolean(editing?.payload?.saved_prompt));

  // Option sources for the builder_setup form.
  const [providers, setProviders] = useState([]);
  const [presets, setPresets] = useState([]);
  const [styles, setStyles] = useState([]);

  useEffect(() => {
    let cancelled = false;
    getOptions()
      .then((opts) => {
        if (cancelled) return;
        const details = opts?.provider_details || opts?.providers_v2 || [];
        setProviders(
          Array.isArray(details)
            ? details.map((p) => ({
                id: p.id,
                label: p.display_name || p.name || p.id,
                configured: Boolean(p.configured),
                models: Array.isArray(p.available_models) ? p.available_models : []
              }))
            : []
        );
        // CANONICAL generator presets — the same /api/options.generator_presets the
        // Builder Style tab uses (None / Claude-Exam / Claude-Review / Claude-Cram).
        // NOT /api/presets (those are Outline quick-templates, a separate registry).
        setPresets(Array.isArray(opts?.generator_presets) ? opts.generator_presets : []);
      })
      .catch(() => {
        if (cancelled) return;
        setProviders([]);
        setPresets([]);
      });
    getStyles()
      .then((res) => !cancelled && setStyles([...(res?.builtin ?? []), ...(res?.custom ?? [])]))
      .catch(() => !cancelled && setStyles([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const providerModels = useMemo(
    () => providers.find((p) => p.id === builder.provider)?.models ?? [],
    [providers, builder.provider]
  );

  function captureFromBuilder() {
    if (currentBuilderSetup) setBuilder({ ...BLANK_BUILDER, ...currentBuilderSetup });
  }

  function buildPayload() {
    if (type === "tool") return { tool };
    if (type === "library_view") {
      const view = viewBase === "search" ? `search:${viewQuery.trim()}` : viewBase;
      return { view };
    }
    const base = {
      ...builder,
      target_pages: Number(builder.target_pages) || 20,
      provider: builder.provider || null,
      model: builder.model || null,
      generator_preset: builder.generator_preset || null,
      style: builder.style || null
    };
    // saved_prompt is opt-in: withSavedPrompt strips any inherited key and only
    // re-attaches the captured text when the checkbox is on — never silently.
    return withSavedPrompt(base, { savePrompt, sourceText: savedPromptText });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!name.trim()) {
      onError?.("Name is required.");
      return;
    }
    setSaving(true);
    onError?.(null);
    try {
      const body = {
        name: name.trim(),
        description: description.trim(),
        type,
        icon,
        color,
        payload: buildPayload()
      };
      if (editing) {
        await updateShortcut(editing.id, { ...body, pinned: editing.pinned });
      } else {
        await createShortcut({ ...body, pinned: true });
      }
      onSaved?.();
    } catch (err) {
      onError?.(err?.message || "Could not save shortcut.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <Field label="Name">
          <input className="sg-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Exam Cram — Qwen" maxLength={120} autoFocus />
        </Field>
        <Field label="Description">
          <input className="sg-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Short summary shown on the card" maxLength={400} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Icon">
            <div className="flex flex-wrap gap-1.5">
              {ICON_CHOICES.map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => setIcon(choice)}
                  className={`grid h-8 w-8 place-items-center rounded-lg border text-base ${icon === choice ? "border-[#F97316] bg-[#F97316]/15" : "border-white/10 bg-white/[0.03] hover:bg-white/10"}`}
                >
                  {choice}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Color">
            <div className="flex flex-wrap gap-1.5">
              {COLOR_CHOICES.map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => setColor(choice)}
                  className={`h-8 w-8 rounded-lg border-2 ${color === choice ? "border-white" : "border-transparent"}`}
                  style={{ background: choice }}
                  aria-label={choice}
                />
              ))}
            </div>
          </Field>
        </div>

        <Field label="Type">
          <select className="sg-input" value={type} onChange={(e) => setType(e.target.value)} disabled={Boolean(editing)}>
            {SHORTCUT_TYPES.map((t) => (
              <option key={t} value={t} className="bg-[#0B0F19]">
                {TYPE_LABELS[t]}
              </option>
            ))}
          </select>
          {editing && <p className="mt-1 text-[11px] text-slate-500">Type can't change after creation. Duplicate to make a different kind.</p>}
        </Field>

        {type === "builder_setup" && (
          <div className="space-y-3 rounded-xl border border-white/10 bg-white/[0.02] p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Builder setup</span>
              <button
                type="button"
                onClick={captureFromBuilder}
                disabled={!currentBuilderSetup}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.04] px-2.5 py-1 text-[11px] font-semibold text-slate-200 hover:bg-white/[0.08] disabled:opacity-40"
                title={currentBuilderSetup ? "Fill these fields from the Builder's current settings" : "Open the Builder once to capture its settings"}
              >
                <Wand2 size={12} /> Capture from Builder
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Input type">
                <select className="sg-input" value={builder.input_type} onChange={(e) => setBuilder({ ...builder, input_type: e.target.value })}>
                  {INPUT_TYPES.map((it) => (
                    <option key={it} value={it} className="bg-[#0B0F19]">{INPUT_TYPE_LABELS[it]}</option>
                  ))}
                </select>
              </Field>
              <Field label="Target pages">
                <input type="number" min={1} max={100} className="sg-input" value={builder.target_pages} onChange={(e) => setBuilder({ ...builder, target_pages: e.target.value })} />
              </Field>
              <Field label="Provider">
                <select
                  className="sg-input"
                  value={builder.provider}
                  onChange={(e) => setBuilder({ ...builder, provider: e.target.value, model: "" })}
                >
                  <option value="" className="bg-[#0B0F19]">— select —</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id} className="bg-[#0B0F19]">
                      {p.label}{p.configured ? "" : " (no key)"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Model">
                <select className="sg-input" value={builder.model} onChange={(e) => setBuilder({ ...builder, model: e.target.value })}>
                  <option value="" className="bg-[#0B0F19]">Provider default</option>
                  {providerModels.map((m) => (
                    <option key={m} value={m} className="bg-[#0B0F19]">{m}</option>
                  ))}
                </select>
              </Field>
              <Field label="Generator preset">
                <select className="sg-input" value={builder.generator_preset} onChange={(e) => setBuilder({ ...builder, generator_preset: e.target.value })}>
                  {generatorPresetOptions(presets, builder.generator_preset).map((opt) => (
                    <option key={opt.id || "__none__"} value={opt.id} className="bg-[#0B0F19]">{opt.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Style">
                <select className="sg-input" value={builder.style} onChange={(e) => setBuilder({ ...builder, style: e.target.value })}>
                  <option value="" className="bg-[#0B0F19]">None</option>
                  {styles.map((s) => (
                    <option key={s.id} value={s.id} className="bg-[#0B0F19]">{s.name || s.id}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={builder.strict_math} onChange={(e) => setBuilder({ ...builder, strict_math: e.target.checked })} />
                Strict math
              </label>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Exports:</span>
                {EXPORT_FORMATS.map((fmt) => {
                  const on = builder.export_formats?.includes(fmt);
                  return (
                    <label key={fmt} className="flex items-center gap-1 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={Boolean(on)}
                        onChange={(e) => {
                          const set = new Set(builder.export_formats || []);
                          if (e.target.checked) set.add(fmt);
                          else set.delete(fmt);
                          setBuilder({ ...builder, export_formats: [...set] });
                        }}
                      />
                      {fmt}
                    </label>
                  );
                })}
              </div>
            </div>

            <SavedPromptControl
              savePrompt={savePrompt}
              setSavePrompt={setSavePrompt}
              savedPromptText={savedPromptText}
              setSavedPromptText={setSavedPromptText}
            />
          </div>
        )}

        {type === "tool" && (
          <Field label="Tool">
            <select className="sg-input" value={tool} onChange={(e) => setTool(e.target.value)}>
              {TOOL_KEYS.map((key) => (
                <option key={key} value={key} className="bg-[#0B0F19]">{TOOL_LABELS[key]}</option>
              ))}
            </select>
          </Field>
        )}

        {type === "library_view" && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="View">
              <select className="sg-input" value={viewBase} onChange={(e) => setViewBase(e.target.value)}>
                {VIEW_BASES.map((v) => (
                  <option key={v} value={v} className="bg-[#0B0F19]">{VIEW_BASE_LABELS[v]}</option>
                ))}
                <option value="search" className="bg-[#0B0F19]">Search query…</option>
              </select>
            </Field>
            {viewBase === "search" && (
              <Field label="Search query">
                <input className="sg-input" value={viewQuery} onChange={(e) => setViewQuery(e.target.value)} placeholder="e.g. thermodynamics" />
              </Field>
            )}
          </div>
        )}
      </div>

      <div className="flex justify-end gap-2 border-t border-white/10 px-5 py-3">
        <button type="button" onClick={onCancel} className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 hover:bg-white/[0.08]">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#F97316]/50 bg-[#F97316]/80 px-3.5 text-sm font-bold text-white hover:bg-[#F97316] disabled:opacity-50">
          {saving && <Loader2 size={14} className="animate-spin" />}
          {editing ? "Save changes" : "Create shortcut"}
        </button>
      </div>
    </form>
  );
}

// ── Import flow (preview → save / use once / rename) ──────────────────────────

function ImportPanel({ onCancel, onImported, onActivateShortcut, onCloseModal, onError }) {
  const [rawText, setRawText] = useState("");
  const [preview, setPreview] = useState(null); // { shortcuts, errors, ... }
  const [parsed, setParsed] = useState(null); // the parsed JSON we previewed
  const [loading, setLoading] = useState(false);
  const [renames, setRenames] = useState({}); // index -> new name
  const fileRef = useRef(null);

  function parseInput(text) {
    try {
      return JSON.parse(text);
    } catch {
      return undefined;
    }
  }

  async function runPreview(text) {
    const data = parseInput(text);
    if (data === undefined) {
      onError?.("That doesn't look like valid JSON.");
      setPreview(null);
      return;
    }
    setLoading(true);
    onError?.(null);
    try {
      const result = await previewImportShortcuts(data, false);
      setPreview(result);
      setParsed(data);
    } catch (err) {
      onError?.(err?.message || "Could not read that import.");
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }

  function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      setRawText(text);
      runPreview(text);
    };
    reader.readAsText(file);
  }

  // Apply per-row rename overrides onto the parsed payload before saving.
  function payloadWithRenames() {
    if (!parsed) return parsed;
    const list = Array.isArray(parsed)
      ? parsed
      : Array.isArray(parsed?.shortcuts)
        ? parsed.shortcuts
        : [parsed];
    const next = list.map((item, index) =>
      renames[index] && renames[index].trim() ? { ...item, name: renames[index].trim() } : item
    );
    return Array.isArray(parsed) ? next : { ...(typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {}), shortcuts: next };
  }

  async function handleSave() {
    setLoading(true);
    onError?.(null);
    try {
      // overwrite stays false: the backend regenerates conflicting ids, so an
      // import never silently replaces an existing shortcut.
      await importShortcuts(payloadWithRenames(), false);
      onImported?.();
    } catch (err) {
      onError?.(err?.message || "Could not import.");
    } finally {
      setLoading(false);
    }
  }

  // "Use once": load a builder_setup straight into the Builder without saving.
  function handleUseOnce(shortcut) {
    onActivateShortcut?.(shortcut);
    onCloseModal?.();
  }

  const previewItems = preview?.shortcuts ?? [];
  const previewErrors = preview?.errors ?? [];
  const onlyBuilder = previewItems.length === 1 && previewItems[0]?.type === "builder_setup";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {!preview && (
          <>
            <p className="text-xs text-slate-400">
              Paste exported shortcut JSON, or upload a <code>.json</code> file. You'll see a preview before anything is saved.
            </p>
            <textarea
              className="sg-input h-40 font-mono text-xs"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder='{"name": "...", "type": "builder_setup", "payload": { ... }}'
            />
            <div className="flex items-center gap-2">
              <button type="button" className="sg-modal-action" onClick={() => fileRef.current?.click()}>
                <Upload size={14} /> Choose file
              </button>
              <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" onChange={handleFile} />
              <div className="flex-1" />
              <button
                type="button"
                disabled={!rawText.trim() || loading}
                onClick={() => runPreview(rawText)}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#F97316]/50 bg-[#F97316]/80 px-3.5 text-sm font-bold text-white hover:bg-[#F97316] disabled:opacity-50"
              >
                {loading && <Loader2 size={14} className="animate-spin" />}
                Preview
              </button>
            </div>
          </>
        )}

        {preview && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wide text-slate-400">
                Preview · {previewItems.length} shortcut{previewItems.length === 1 ? "" : "s"}
              </span>
              <button type="button" className="text-xs text-slate-400 hover:text-white" onClick={() => { setPreview(null); setParsed(null); setRenames({}); }}>
                ← Back
              </button>
            </div>

            {previewErrors.length > 0 && (
              <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-200">
                {previewErrors.length} item{previewErrors.length === 1 ? "" : "s"} could not be read:
                <ul className="mt-1 list-disc pl-4">
                  {previewErrors.map((e, i) => (
                    <li key={i}>#{e.index + 1}: {e.error}</li>
                  ))}
                </ul>
              </div>
            )}

            {previewItems.map((item, index) => (
              <div key={index} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                <div className="flex items-center gap-2">
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/5 text-base">{shortcutEmoji(item)}</span>
                  <div className="min-w-0 flex-1">
                    <strong className="block truncate text-sm text-white">{item.name}</strong>
                    <span className="text-[11px] uppercase tracking-wide text-slate-500">{TYPE_LABELS[item.type] || item.type}</span>
                  </div>
                  {item.valid === false && (
                    <span className="rounded border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-[10px] text-amber-200" title={item.reason}>
                      {invalidHint(item)}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs text-slate-400">{summarizePayload(item)}</p>
                {payloadHasSavedPrompt(item.payload) && (
                  <p className="mt-1 text-[11px] text-sky-300">
                    Includes saved prompt/source text ({item.payload.saved_prompt.length.toLocaleString()} chars) — user content will be imported.
                  </p>
                )}
                {item._id_regenerated && (
                  <p className="mt-1 text-[11px] text-sky-300">Will be imported as a new shortcut (new id).</p>
                )}
                <div className="mt-2">
                  <label className="text-[11px] text-slate-500">Rename before saving (optional)</label>
                  <input
                    className="sg-input mt-1"
                    placeholder={item.name}
                    value={renames[index] ?? ""}
                    onChange={(e) => setRenames({ ...renames, [index]: e.target.value })}
                  />
                </div>
                {item.type === "builder_setup" && (
                  <button
                    type="button"
                    onClick={() => handleUseOnce(item)}
                    disabled={item.valid === false}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.04] px-2.5 py-1 text-[11px] font-semibold text-slate-200 hover:bg-white/[0.08] disabled:opacity-40"
                    title={item.valid === false ? "Fix the referenced provider/style first" : "Load into the Builder without saving"}
                  >
                    Use once (don't save)
                  </button>
                )}
              </div>
            ))}
          </>
        )}
      </div>

      <div className="flex justify-end gap-2 border-t border-white/10 px-5 py-3">
        <button type="button" onClick={onCancel} className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 hover:bg-white/[0.08]">
          Cancel
        </button>
        {preview && previewItems.length > 0 && (
          <button type="button" disabled={loading} onClick={handleSave} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[#F97316]/50 bg-[#F97316]/80 px-3.5 text-sm font-bold text-white hover:bg-[#F97316] disabled:opacity-50">
            {loading && <Loader2 size={14} className="animate-spin" />}
            {onlyBuilder ? "Save as my shortcut" : "Save all as my shortcuts"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Small shared bits ─────────────────────────────────────────────────────────

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</span>
      {children}
    </label>
  );
}

// Opt-in "Save prompt/source text with this shortcut" control (builder_setup).
// Default OFF. The textarea is only shown when ON and there is captured text to
// review/edit so prompt content is never displayed (or saved) unless intended.
// When editing a shortcut that already carries a saved prompt, the count makes
// the included user content explicit; unchecking strips it on save.
function SavedPromptControl({ savePrompt, setSavePrompt, savedPromptText, setSavedPromptText }) {
  const len = (savedPromptText || "").length;
  const over = len > MAX_SAVED_PROMPT_CHARS;
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
      <label className="flex items-start gap-2 text-xs text-slate-200">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={savePrompt}
          onChange={(e) => setSavePrompt(e.target.checked)}
        />
        <span>
          <span className="font-semibold">Save prompt/source text with this shortcut</span>
          <span className="mt-0.5 block text-[11px] font-normal text-slate-400">
            Includes the current prompt/text inside the shortcut export. Leave off for
            reusable settings only. This may contain private course material.
          </span>
        </span>
      </label>
      {savePrompt && (
        <div className="mt-2">
          <textarea
            className="sg-input min-h-[88px] w-full font-mono text-[12px]"
            value={savedPromptText}
            onChange={(e) => setSavedPromptText(e.target.value)}
            placeholder="Source prompt/text to store inside this shortcut…"
          />
          <div className={`mt-1 text-[11px] ${over ? "text-red-300" : "text-slate-400"}`}>
            {len.toLocaleString()} / {MAX_SAVED_PROMPT_CHARS.toLocaleString()} chars
            {over ? " — too long; shorten before saving." : ""}
          </div>
        </div>
      )}
      {!savePrompt && savedPromptText && (
        <div className="mt-2 text-[11px] text-amber-300">
          Saved prompt will be removed from this shortcut when you save.
        </div>
      )}
    </div>
  );
}

function ConfirmDialog({ heading, body, actionLabel, busy, onCancel, onConfirm }) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button type="button" aria-label="Cancel" className="absolute inset-0 cursor-default bg-black/60" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="relative w-full max-w-sm rounded-2xl border border-white/10 bg-[#0B0F19] p-5 shadow-2xl">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-white">{heading}</h2>
            <p className="mt-1 text-sm text-slate-400">{body}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" autoFocus disabled={busy} onClick={onCancel} className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 hover:bg-white/[0.08] disabled:opacity-50">
            Cancel
          </button>
          <button type="button" disabled={busy} onClick={onConfirm} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-red-400/50 bg-red-500/80 px-3.5 text-sm font-bold text-white hover:bg-red-500 disabled:opacity-50">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
