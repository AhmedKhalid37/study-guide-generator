import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Copy,
  Download,
  Info,
  Loader2,
  Pencil,
  Pin,
  PinOff,
  Plus,
  RotateCcw,
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
  getLibrary,
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
import StatusPill from "./StatusPill";
import Panel from "./Panel";
import Button from "./Button";
import ItemCard from "./ItemCard";
import ProviderPill from "./ProviderPill";
import Icon from "./Icon";
import deepseekMark from "../assets/providers/deepseek1.svg";
import qwenMark from "../assets/providers/qwen1.svg";
import gemmaMark from "../assets/providers/gemma.svg";
import geminiMark from "../assets/providers/gemini.svg";
import mistralMark from "../assets/providers/mistral.svg";
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

// Provider marks for the hero badge cluster. Sizes/positions are kept inside the
// 540px cluster (left% · 5.4 + size ≤ ~500) so nothing clips against the hero's
// overflow. Each real provider carries static, curated hover copy (model name +
// strength + how GuideForge uses it) — purely informational, nothing dynamic or
// sensitive. EVERY real badge uses the white circular treatment (variant
// "light") so all provider marks read as centred glyphs on matching white
// circles — no badge looks like a dark circle next to the others. There is no
// ghost/empty badge: the cluster shows only real providers.
const HERO_BADGES = [
  {
    x: 38,
    y: 30,
    size: 84,
    src: deepseekMark,
    variant: "light",
    bigMark: true,
    name: "DeepSeek V4 Pro",
    blurb: "Strong reasoning model used for thorough, long-form study guides."
  },
  {
    x: 58,
    y: 8,
    size: 88,
    src: qwenMark,
    variant: "light",
    name: "Qwen 3.7 Max / Plus",
    blurb: "High-coverage model used for dense exam and cram guide generation."
  },
  {
    x: 76,
    y: 40,
    size: 76,
    src: gemmaMark,
    variant: "light",
    name: "Gemma 4 / Local",
    blurb: "Local model path for private, offline GuideForge workflows."
  },
  {
    x: 50,
    y: 64,
    size: 60,
    src: geminiMark,
    variant: "light",
    // Lowest badge in the cluster — open its popover upward so the hero's
    // overflow clip never cuts it off at the bottom edge.
    pop: "up",
    name: "Gemini 3.1",
    blurb: "Multimodal-capable provider option for visual and source-understanding workflows."
  },
  {
    x: 80,
    y: 12,
    size: 64,
    src: mistralMark,
    variant: "light",
    name: "Mistral OCR",
    blurb: "High-accuracy ingestion helper for scanned or image-heavy source material."
  }
];

// How many Quick Launch cards are visible at once before the carousel arrows
// page the rest into view.
const QUICK_LAUNCH_PAGE = 6;

// Provider / model label for a job (e.g. "deepseek / deepseek-chat").
function jobProviderModel(job) {
  return [job.provider, job.model].filter(Boolean).join(" / ");
}

const DEFAULT_COLOR = COLOR_CHOICES[0];

// Semantic tag modifier per validity tier, shared by the customize-row chip so
// all surfaces read the same. (Tailwind utilities are inert in this app.)
const STATUS_CHIP_CLASSES = {
  [STATUS_VALID]: "sg-tag-info",
  [STATUS_DEGRADED]: "sg-tag-warn",
  [STATUS_BROKEN]: "sg-tag-bad"
};

// ── Home page ───────────────────────────────────────────────────────────────

// How many guides each Home panel shows before its "View all" link takes over.
const HOME_PANEL_CAP = 5;

export default function HomeShortcuts({
  jobsRefreshKey,
  onActivateShortcut,
  onNewGuide,
  onNavigate,
  onOpenLibraryView,
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

  // Favorite guides — loaded from the FULL library (`/api/library`), not the
  // recent-20 `jobs` prop. The prop is a capped, newest-first slice from
  // `/api/jobs?limit=20`, so favorites on older guides (or favorites toggled in
  // Library after this page first loaded) could fall outside it. Reading the
  // full library here means every real favorite shows regardless of age, and a
  // refresh on `jobsRefreshKey` (plus the remount that happens each time Home is
  // re-opened) keeps it current after a guide is favorited elsewhere.
  const [favorites, setFavorites] = useState([]);
  useEffect(() => {
    let cancelled = false;
    getLibrary({ sort: "newest" })
      .then((data) => {
        if (cancelled) return;
        const all = Array.isArray(data?.jobs) ? data.jobs : [];
        setFavorites(all.filter((job) => job.favorite === true));
      })
      .catch(() => !cancelled && setFavorites([]));
    return () => {
      cancelled = true;
    };
  }, [jobsRefreshKey]);

  // Imperative handle to the embedded Recent Guides panel so the Favorite cards
  // can open the SAME job-details drawer by reusing its openJobDetails — no
  // second drawer and no extra fetch wiring.
  const recentRef = useRef(null);
  const openJobDetails = useCallback((jobId) => recentRef.current?.openJob(jobId), []);

  return (
    <div className="content-inner">
      <Hero onGetStarted={() => onNewGuide?.()} />

      <QuickLaunch
        pinned={pinned}
        loading={loading}
        error={error}
        onCustomize={() => setCustomizeOpen(true)}
        onActivate={requestActivate}
        onInspect={setInspecting}
      />

      <div className="split mt32">
        <FavoriteGuidesPanel
          favorites={favorites}
          cap={HOME_PANEL_CAP}
          onOpenJob={openJobDetails}
          onViewAll={onOpenLibraryView ? () => onOpenLibraryView("favorites") : null}
        />
        <div>
          <RecentJobsPanel
            ref={recentRef}
            embedded
            refreshKey={jobsRefreshKey}
            maxItems={HOME_PANEL_CAP}
            onViewAll={onOpenLibraryView ? () => onOpenLibraryView("recent") : null}
          />
        </div>
      </div>

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

// Hero banner — provider badge cluster + headline + Getting Started. The badges
// are decorative flourish but each real provider reveals a curated hover popover
// (model + strengths + GuideForge usage). The cluster stays aria-hidden so the
// popovers are a mouse/pointer enhancement only and never clutter the a11y tree.
function Hero({ onGetStarted }) {
  return (
    <div className="hero">
      <div className="badge-cluster" aria-hidden="true">
        {HERO_BADGES.map((badge, index) => {
          const variant = badge.ghost ? "ghost" : badge.variant || "default";
          const hasInfo = Boolean(badge.name && badge.blurb);
          return (
            <div
              key={index}
              className={`prov-badge ${variant}${hasInfo ? " has-info" : ""}${badge.bigMark ? " big-mark" : ""}`}
              style={{ left: `${badge.x}%`, top: `${badge.y}%`, width: badge.size, height: badge.size }}
            >
              {badge.src && <img src={badge.src} alt="" className="prov-badge-mark" />}
              {hasInfo && (
                <span className={`prov-pop${badge.pop === "up" ? " up" : ""}`} role="presentation">
                  <span className="prov-pop-name">{badge.name}</span>
                  <span className="prov-pop-blurb">{badge.blurb}</span>
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div className="hero-content">
        <h1>Meet GuideForge — your exam-focused study guide builder</h1>
        <p>Turn lecture decks, PDFs and notes into structured guides and quizzes — generated locally or with your connected models.</p>
        <Button variant="bare" className="hero-cta" onClick={onGetStarted}>
          {Icon.play()} Getting Started
        </Button>
      </div>
    </div>
  );
}

function DegradedActivationDialog({ shortcut, onContinue, onRepair, onCancel }) {
  const issues = issueCount(shortcut);
  const messages = topFindingMessages(shortcut);
  const findings = shortcutFindings(shortcut);
  const extra = Math.max(0, findings.length - messages.length);
  return (
    <div className="sg-modal-scrim">
      <button type="button" aria-label="Cancel" className="sg-scrim-bg" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="dialog-card sg-dialog">
        <div className="sg-dialog-row">
          <AlertTriangle style={{ color: "var(--amber)" }} />
          <div className="sg-dialog-main">
            <h2>Launch “{shortcut.name}”?</h2>
            <p className="pill pill-amber sg-dialog-pill">
              Needs attention{issues > 0 ? ` · ${issues} issue${issues === 1 ? "" : "s"} found` : ""}
            </p>
            {messages.length > 0 && (
              <ul className="sg-dialog-list">
                {messages.map((message, index) => (
                  <li key={index}>
                    <span className="b" style={{ color: "var(--amber)" }}>•</span>
                    <span style={{ minWidth: 0 }}>{message}</span>
                  </li>
                ))}
                {extra > 0 && (
                  <li className="sg-dialog-more">+{extra} more in the inspector</li>
                )}
              </ul>
            )}
            <p className="sg-dialog-note">
              You can continue, but some saved settings may be ignored or replaced by defaults.
            </p>
          </div>
        </div>
        <div className="sg-dialog-actions">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="ghost" onClick={onRepair}>
            <Wrench size={14} /> Repair instead
          </Button>
          <Button variant="white" autoFocus onClick={onContinue}>Continue anyway</Button>
        </div>
      </div>
    </div>
  );
}

function BrokenActivationDialog({ shortcut, onInspect, onCancel }) {
  const messages = topFindingMessages(shortcut);
  const hint = invalidHint(shortcut);
  return (
    <div className="sg-modal-scrim">
      <button type="button" aria-label="Cancel" className="sg-scrim-bg" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="dialog-card sg-dialog">
        <div className="sg-dialog-row">
          <AlertCircle style={{ color: "var(--red)" }} />
          <div className="sg-dialog-main">
            <h2>This shortcut is broken.</h2>
            <p className="sg-dialog-note" style={{ marginTop: 6 }}>
              “{shortcut.name}” can’t launch as saved. {hint}
            </p>
            {messages.length > 0 && (
              <ul className="sg-dialog-list">
                {messages.map((message, index) => (
                  <li key={index}>
                    <span className="b" style={{ color: "var(--red)" }}>•</span>
                    <span style={{ minWidth: 0 }}>{message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="sg-dialog-actions">
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="white" autoFocus onClick={onInspect}>
            <Wrench size={14} /> Inspect / Repair
          </Button>
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

// ── Quick Launch carousel ─────────────────────────────────────────────────────
//
// The pinned shortcuts rendered as pastel cards in a horizontal carousel: up to
// QUICK_LAUNCH_PAGE cards are visible at once and the arrow buttons page the
// rest into view. Full launch behaviour (valid → launch, degraded → confirm,
// broken → block) is unchanged — each card calls back into the parent's
// requestActivate / inspect handlers exactly as before.
function QuickLaunch({ pinned, loading, error, onCustomize, onActivate, onInspect }) {
  const viewportRef = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(true);

  // Derive arrow enablement from the live scroll position so an arrow disables
  // once there is nothing further to reveal in that direction.
  const syncArrows = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    setAtStart(el.scrollLeft <= 1);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    syncArrows();
  }, [syncArrows, pinned.length, loading]);

  const scrollByPage = useCallback((event, dir) => {
    // Arrows live in the header (not over the cards), but stop propagation
    // defensively so an arrow can never bubble into a card activation.
    event.stopPropagation();
    const el = viewportRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth, behavior: "smooth" });
  }, []);

  // Arrows only matter once there are more cards than fit on screen at once.
  const hasOverflow = pinned.length > QUICK_LAUNCH_PAGE;

  return (
    <section className="mt32">
      <div className="ql-head">
        <div className="section-title">Quick Launch</div>
        <div className="ql-head-actions">
          {hasOverflow && (
            <div className="ql-arrows">
              <button
                type="button"
                className="ql-arrow"
                aria-label="Show previous shortcuts"
                disabled={atStart}
                onClick={(e) => scrollByPage(e, -1)}
              >
                {Icon.chevronLeft()}
              </button>
              <button
                type="button"
                className="ql-arrow"
                aria-label="Show more shortcuts"
                disabled={atEnd}
                onClick={(e) => scrollByPage(e, 1)}
              >
                {Icon.chevronRight()}
              </button>
            </div>
          )}
          <Button variant="bare" className="panel-link" onClick={onCustomize}>
            Customize
          </Button>
        </div>
      </div>

      {error && <div className="launch-alert">{error}</div>}

      {loading ? (
        <div className="ql-track" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="ql-card ql-card-skeleton" />
          ))}
        </div>
      ) : pinned.length === 0 ? (
        <div className="launch-empty">
          <p>No pinned shortcuts yet.</p>
          <Button variant="ghost" onClick={onCustomize}>
            Customize shortcuts
          </Button>
        </div>
      ) : (
        <div className="ql-viewport" ref={viewportRef} onScroll={syncArrows}>
          <div
            className="ql-track"
            style={{ "--ql-cols": Math.min(pinned.length, QUICK_LAUNCH_PAGE) }}
          >
            {pinned.map((shortcut) => (
              <LaunchCard
                key={shortcut.id}
                shortcut={shortcut}
                onActivate={() => onActivate(shortcut)}
                onInspect={() => onInspect(shortcut)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

// A single Quick Launch shortcut as a dark glass card (title centred, details
// left-aligned) matching the rest of the app — transparent dark fill, soft-white
// border, white title + muted supporting text, silver hover sheen. Activation
// gating stays on the LEGACY `valid` boolean — the parent's requestActivate owns
// the real routing — and the StatusPill is purely informational, shown only for
// degraded/broken shortcuts.
function LaunchCard({ shortcut, onActivate, onInspect }) {
  const invalid = shortcut.valid === false;
  const typeLabel = TYPE_LABELS[shortcut.type] || shortcut.type;
  const reasonHint = invalid ? invalidHint(shortcut) : null;
  const status = shortcutStatus(shortcut);
  const badge = statusBadge(status);
  // Valid shortcuts stay quiet (no pill); degraded/broken surface a StatusPill.
  const showBadge = status === STATUS_DEGRADED || status === STATUS_BROKEN;

  function handleInspect(event) {
    event.stopPropagation();
    event.preventDefault();
    onInspect?.();
  }

  const inspectKeys = (event) => {
    if (event.key === "Enter" || event.key === " ") handleInspect(event);
  };

  return (
    <button
      type="button"
      className="btn-reset ql-card glass"
      onClick={onActivate}
      title={invalid ? reasonHint : summarizePayload(shortcut)}
      aria-disabled={invalid ? "true" : undefined}
    >
      <div className="ql-card-top">
        <span className="ql-emoji" aria-hidden="true">{shortcutEmoji(shortcut)}</span>
        <span className="row gap8">
          {showBadge && (
            <StatusPill
              status={status}
              className="ql-pill"
              role="button"
              tabIndex={0}
              title={`${badge.label} — click to inspect`}
              onClick={handleInspect}
              onKeyDown={inspectKeys}
            />
          )}
          <span
            className="ql-inspect"
            role="button"
            tabIndex={0}
            onClick={handleInspect}
            onKeyDown={inspectKeys}
            title="Inspect shortcut"
            aria-label="Inspect shortcut"
          >
            {Icon.eye()}
          </span>
        </span>
      </div>
      <div className="ql-title">{shortcut.name}</div>
      {/* Card shows only icon · title · type · arrow — the full description lives
          in the Customize list and the Inspector, not on the launch card. */}
      <div className="ql-meta">
        <span className="ql-type">{typeLabel}</span>
        <span className="ql-go" aria-hidden="true">{Icon.chevronRight()}</span>
      </div>
    </button>
  );
}

// ── Favorite Guides panel ─────────────────────────────────────────────────────
//
// Lower-left panel: jobs already in hand that are flagged favorite, as clickable
// ItemCards that open the shared job-details drawer. No new API calls.
function FavoriteGuidesPanel({ favorites, cap = null, onOpenJob, onViewAll }) {
  if (!favorites || favorites.length === 0) {
    return (
      <Panel title="Favorite Guides">
        <div className="recent-state">No favourite guides yet</div>
      </Panel>
    );
  }
  const visible = cap ? favorites.slice(0, cap) : favorites;
  const viewAll = onViewAll ? (
    <button type="button" className="panel-link btn-reset" onClick={onViewAll}>
      View all
    </button>
  ) : null;
  return (
    <Panel title="Favorite Guides" action={viewAll}>
      <div className="col">
        {visible.map((job) => {
          const providerModel = jobProviderModel(job);
          return (
            <ItemCard
              key={job.id}
              date={job.created_at}
              title={job.title || "Untitled study guide"}
              meta={providerModel ? <ProviderPill provider={providerModel} /> : null}
              role="button"
              tabIndex={0}
              onClick={() => onOpenJob?.(job.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOpenJob?.(job.id);
                }
              }}
            />
          );
        })}
      </div>
    </Panel>
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
    <div className="sg-modal-scrim">
      <button type="button" aria-label="Close" className="sg-scrim-bg" onClick={onClose} />
      <div role="dialog" aria-modal="true" className="sg-shortcuts-modal">
        <div className="sg-sc-head">
          <div className="sg-sc-head-l">
            <Settings2 size={16} />
            <h2>
              {mode === "form" ? (editing ? "Edit shortcut" : "New shortcut") : mode === "import" ? "Import shortcuts" : "Customize shortcuts"}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="sg-sc-x" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="sg-sc-error">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {mode === "list" && (
          <>
            <div className="sg-sc-actions">
              <button type="button" className="sg-modal-action" onClick={() => { setEditing(null); setMode("form"); }}>
                <Plus size={14} /> New
              </button>
              <button type="button" className="sg-modal-action" onClick={() => setMode("import")}>
                <Upload size={14} /> Import
              </button>
              <a className="sg-modal-action" href={exportShortcutsUrl()} download="shortcuts.json">
                <Download size={14} /> Export all
              </a>
              <div className="sg-sc-spacer" />
              <button type="button" className="sg-modal-action" onClick={() => setConfirmReset(true)}>
                <RotateCcw size={14} /> Reset defaults
              </button>
            </div>
            <div className="sg-sc-scroll">
              {items.length === 0 ? (
                <p style={{ textAlign: "center", padding: "32px 0" }}>No shortcuts. Create one or reset to defaults.</p>
              ) : (
                <ul className="sg-sc-list">
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
    <li className="sg-sc-row">
      <div style={{ display: "flex", flexDirection: "column" }}>
        <button type="button" disabled={isFirst} onClick={onUp} className="sg-sc-move" title="Move up">
          <ArrowUp size={13} />
        </button>
        <button type="button" disabled={isLast} onClick={onDown} className="sg-sc-move" title="Move down">
          <ArrowDown size={13} />
        </button>
      </div>
      <span
        className="sg-sc-emoji"
        style={{ background: `color-mix(in srgb, ${accent} 16%, transparent)`, border: `1px solid color-mix(in srgb, ${accent} 30%, transparent)` }}
        aria-hidden
      >
        {shortcutEmoji(shortcut)}
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <strong>{shortcut.name}</strong>
          <span className="sg-tag">
            {TYPE_LABELS[shortcut.type] || shortcut.type}
          </span>
          {showChip && (
            <span
              className={`sg-tag ${STATUS_CHIP_CLASSES[status] || ""}`}
              title={firstFinding?.message || shortcut.reason || badge.label}
            >
              {badge.label}{issues > 0 ? ` · ${issues}` : ""}
            </span>
          )}
          {payloadHasSavedPrompt(shortcut.payload) && (
            <span
              className="sg-tag sg-tag-info"
              title="This shortcut includes saved prompt/source text (user content)."
            >
              Saved prompt
            </span>
          )}
        </div>
        <p className="sg-sc-desc">{shortcut.description || summarizePayload(shortcut)}</p>
      </div>
      {busy && <Loader2 size={14} className="sg-spin" style={{ color: "var(--muted)" }} />}
      <div style={{ display: "flex", flex: "none", alignItems: "center", gap: 2 }}>
        <IconBtn title="Inspect" onClick={onInspect}><Info size={14} /></IconBtn>
        <IconBtn title={shortcut.pinned ? "Unpin from Home" : "Pin to Home"} onClick={onTogglePin}>
          {shortcut.pinned ? <Pin size={14} style={{ color: "#F97316" }} /> : <PinOff size={14} />}
        </IconBtn>
        <IconBtn title="Edit" onClick={onEdit}><Pencil size={14} /></IconBtn>
        <IconBtn title="Duplicate" onClick={onDuplicate}><Copy size={14} /></IconBtn>
        <a className="sg-sc-iconbtn" title="Export" href={exportShortcutUrl(shortcut.id)} download={`${shortcut.id}.json`}>
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
      className={`sg-sc-iconbtn${danger ? " danger" : ""}`}
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
    <form onSubmit={handleSubmit} className="sg-form">
      <div className="sg-form-scroll">
        <Field label="Name">
          <input className="sg-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Exam Cram — Qwen" maxLength={120} autoFocus />
        </Field>
        <Field label="Description">
          <input className="sg-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Short summary shown on the card" maxLength={400} />
        </Field>

        <div className="sg-form-grid">
          <Field label="Icon">
            <div className="sg-icon-grid">
              {ICON_CHOICES.map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => setIcon(choice)}
                  className={`sg-icon-cell${icon === choice ? " active" : ""}`}
                >
                  {choice}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Color">
            <div className="sg-swatch-row">
              {COLOR_CHOICES.map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => setColor(choice)}
                  className={`sg-swatch${color === choice ? " active" : ""}`}
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
              <option key={t} value={t}>
                {TYPE_LABELS[t]}
              </option>
            ))}
          </select>
          {editing && <p style={{ marginTop: 6, fontSize: 11.5, color: "var(--muted)" }}>Type can't change after creation. Duplicate to make a different kind.</p>}
        </Field>

        {type === "builder_setup" && (
          <div className="sg-form-sub">
            <div className="sg-row-between">
              <span className="sg-form-sub-title">Builder setup</span>
              <button
                type="button"
                onClick={captureFromBuilder}
                disabled={!currentBuilderSetup}
                title={currentBuilderSetup ? "Fill these fields from the Builder's current settings" : "Open the Builder once to capture its settings"}
              >
                <Wand2 size={14} /> Capture from Builder
              </button>
            </div>
            <div className="sg-form-grid">
              <Field label="Input type">
                <select className="sg-input" value={builder.input_type} onChange={(e) => setBuilder({ ...builder, input_type: e.target.value })}>
                  {INPUT_TYPES.map((it) => (
                    <option key={it} value={it}>{INPUT_TYPE_LABELS[it]}</option>
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
                  <option value="">— select —</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}{p.configured ? "" : " (no key)"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Model">
                <select className="sg-input" value={builder.model} onChange={(e) => setBuilder({ ...builder, model: e.target.value })}>
                  <option value="">Provider default</option>
                  {providerModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </Field>
              <Field label="Generator preset">
                <select className="sg-input" value={builder.generator_preset} onChange={(e) => setBuilder({ ...builder, generator_preset: e.target.value })}>
                  {generatorPresetOptions(presets, builder.generator_preset).map((opt) => (
                    <option key={opt.id || "__none__"} value={opt.id}>{opt.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Style">
                <select className="sg-input" value={builder.style} onChange={(e) => setBuilder({ ...builder, style: e.target.value })}>
                  <option value="">None</option>
                  {styles.map((s) => (
                    <option key={s.id} value={s.id}>{s.name || s.id}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="sg-check-line">
              <label className="sg-check-row">
                <input type="checkbox" checked={builder.strict_math} onChange={(e) => setBuilder({ ...builder, strict_math: e.target.checked })} />
                Strict math
              </label>
              <div className="sg-check-inline">
                <span>Exports:</span>
                {EXPORT_FORMATS.map((fmt) => {
                  const on = builder.export_formats?.includes(fmt);
                  return (
                    <label key={fmt} className="sg-check-row">
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
                <option key={key} value={key}>{TOOL_LABELS[key]}</option>
              ))}
            </select>
          </Field>
        )}

        {type === "library_view" && (
          <div className="sg-form-grid">
            <Field label="View">
              <select className="sg-input" value={viewBase} onChange={(e) => setViewBase(e.target.value)}>
                {VIEW_BASES.map((v) => (
                  <option key={v} value={v}>{VIEW_BASE_LABELS[v]}</option>
                ))}
                <option value="search">Search query…</option>
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

      <div className="sg-form-footer">
        <button type="button" onClick={onCancel} className="sg-ghost-button">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="sg-ghost-button accent">
          {saving && <Loader2 size={14} className="sg-spin" />}
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
    <div className="sg-import">
      <div className="sg-import-scroll">
        {!preview && (
          <>
            <p style={{ color: "var(--muted)", fontSize: 13.5, lineHeight: 1.5 }}>
              Paste exported shortcut JSON, or upload a <code>.json</code> file. You'll see a preview before anything is saved.
            </p>
            <textarea
              className="sg-input sg-textarea-mono"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder='{"name": "...", "type": "builder_setup", "payload": { ... }}'
            />
            <div className="sg-import-row">
              <button type="button" className="sg-modal-action" onClick={() => fileRef.current?.click()}>
                <Upload size={14} /> Choose file
              </button>
              <input ref={fileRef} type="file" accept=".json,application/json" style={{ display: "none" }} onChange={handleFile} />
              <div className="sg-import-spacer" />
              <button
                type="button"
                disabled={!rawText.trim() || loading}
                onClick={() => runPreview(rawText)}
                className="sg-ghost-button accent"
              >
                {loading && <Loader2 size={14} className="sg-spin" />}
                Preview
              </button>
            </div>
          </>
        )}

        {preview && (
          <>
            <div className="sg-import-head">
              <span className="sg-import-eyebrow">
                Preview · {previewItems.length} shortcut{previewItems.length === 1 ? "" : "s"}
              </span>
              <button type="button" className="sg-modal-action" onClick={() => { setPreview(null); setParsed(null); setRenames({}); }}>
                ← Back
              </button>
            </div>

            {previewErrors.length > 0 && (
              <div className="sg-import-err">
                {previewErrors.length} item{previewErrors.length === 1 ? "" : "s"} could not be read:
                <ul>
                  {previewErrors.map((e, i) => (
                    <li key={i}>#{e.index + 1}: {e.error}</li>
                  ))}
                </ul>
              </div>
            )}

            {previewItems.map((item, index) => (
              <div key={index} className="sg-import-item">
                <div className="sg-import-item-top">
                  <span className="sg-import-emoji">{shortcutEmoji(item)}</span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <strong className="sg-import-name">{item.name}</strong>
                    <span className="sg-import-type">{TYPE_LABELS[item.type] || item.type}</span>
                  </div>
                  {item.valid === false && (
                    <span className="sg-tag sg-tag-warn" title={item.reason}>
                      {invalidHint(item)}
                    </span>
                  )}
                </div>
                <p style={{ marginTop: 8, color: "var(--muted)", fontSize: 13 }}>{summarizePayload(item)}</p>
                {payloadHasSavedPrompt(item.payload) && (
                  <p style={{ marginTop: 4, color: "#C7C9FB", fontSize: 12 }}>
                    Includes saved prompt/source text ({item.payload.saved_prompt.length.toLocaleString()} chars) — user content will be imported.
                  </p>
                )}
                {item._id_regenerated && (
                  <p style={{ marginTop: 4, color: "#C7C9FB", fontSize: 12 }}>Will be imported as a new shortcut (new id).</p>
                )}
                <div style={{ marginTop: 10 }}>
                  <label className="sg-field-cap" style={{ marginBottom: 4 }}>Rename before saving (optional)</label>
                  <input
                    className="sg-input"
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
                    className="sg-modal-action"
                    style={{ marginTop: 10 }}
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

      <div className="sg-import-foot">
        <button type="button" onClick={onCancel} className="sg-ghost-button">
          Cancel
        </button>
        {preview && previewItems.length > 0 && (
          <button type="button" disabled={loading} onClick={handleSave} className="sg-ghost-button accent">
            {loading && <Loader2 size={14} className="sg-spin" />}
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
    <label className="sg-field">
      <span className="sg-field-cap">{label}</span>
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
    <div className="sg-form-sub">
      <label className="sg-prompt-check">
        <input
          type="checkbox"
          checked={savePrompt}
          onChange={(e) => setSavePrompt(e.target.checked)}
        />
        <span>
          <span style={{ fontWeight: 600 }}>Save prompt/source text with this shortcut</span>
          <span className="sg-prompt-sub">
            Includes the current prompt/text inside the shortcut export. Leave off for
            reusable settings only. This may contain private course material.
          </span>
        </span>
      </label>
      {savePrompt && (
        <div>
          <textarea
            className="sg-input sg-textarea-mono"
            style={{ minHeight: 88 }}
            value={savedPromptText}
            onChange={(e) => setSavedPromptText(e.target.value)}
            placeholder="Source prompt/text to store inside this shortcut…"
          />
          <div className={`sg-prompt-count${over ? " over" : ""}`}>
            {len.toLocaleString()} / {MAX_SAVED_PROMPT_CHARS.toLocaleString()} chars
            {over ? " — too long; shorten before saving." : ""}
          </div>
        </div>
      )}
      {!savePrompt && savedPromptText && (
        <div style={{ color: "#F4C76B", fontSize: 12 }}>
          Saved prompt will be removed from this shortcut when you save.
        </div>
      )}
    </div>
  );
}

function ConfirmDialog({ heading, body, actionLabel, busy, onCancel, onConfirm }) {
  return (
    <div className="sg-modal-scrim">
      <button type="button" aria-label="Cancel" className="sg-scrim-bg" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="sg-modal" style={{ maxWidth: 400 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <AlertTriangle style={{ width: 20, height: 20, flex: "none", marginTop: 2, color: "var(--red)" }} />
          <div style={{ minWidth: 0 }}>
            <h2>{heading}</h2>
            <p style={{ marginTop: 6, color: "var(--text-dim)", fontSize: 13, lineHeight: 1.5 }}>{body}</p>
          </div>
        </div>
        <div className="sg-modal-actions">
          <button type="button" autoFocus disabled={busy} onClick={onCancel} className="sg-ghost-button">
            Cancel
          </button>
          <button type="button" disabled={busy} onClick={onConfirm} className="sg-ghost-button danger">
            {busy && <Loader2 className="sg-spin" />}
            {actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
