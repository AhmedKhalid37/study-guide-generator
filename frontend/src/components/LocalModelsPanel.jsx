import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CircleSlash,
  ClipboardCheck,
  Copy,
  Loader2,
  RefreshCw,
  Server,
  Terminal,
  WifiOff,
} from "lucide-react";
import {
  checkLocalModelStatus,
  getLocalModelCommandProfile,
  getLocalModelStatus,
} from "../api/client";
import {
  STATE_ERROR,
  STATE_NOT_CONFIGURED,
  STATE_OFFLINE,
  STATE_REACHABLE,
  STATE_UNKNOWN,
  findAction,
  localServerState,
  modelChips,
  statusActions,
  statusErrorMessage,
  statusLatencyMs,
  statusModelCount,
  statusNotes,
} from "../localModelStatus";
import {
  COPY_COPIED,
  COPY_FAILED,
  COPY_IDLE,
  commandAvailable,
  commandNotes,
  commandProfiles,
  copyButtonLabel,
  profileById,
} from "../localModelCommand";

// Read-only Local Models status panel (LMM Slice 3). Consumes the detection-only
// Slice 2 endpoints (GET /api/local-model/status on open, POST
// /api/local-model/check on Refresh). It NEVER edits provider settings, never
// starts/stops a process, and never renders a raw key or full URL — it only shows
// the already-safe fields the backend exposes. Config edits link back to the
// Providers cards above (the single writer). Designed to mount under the provider
// list inside ProviderSettingsWorkspace.

// Tone → pill classes, matching the dark/orange premium vocabulary used by the
// provider StatusPill (green reachable / amber offline / grey neutral / red error).
const PILL_TONE = {
  reachable: "border border-[#86EFAC]/30 bg-[#86EFAC]/10 text-[#86EFAC]",
  offline: "border border-[#FCD34D]/30 bg-[#FCD34D]/10 text-[#FCD34D]",
  error: "border border-[#FCA5A5]/30 bg-[#FCA5A5]/10 text-[#FCA5A5]",
  neutral: "border border-white/10 bg-white/5 text-[#9098A8]",
};

const PILL_ICON = {
  [STATE_REACHABLE]: Check,
  [STATE_OFFLINE]: WifiOff,
  [STATE_ERROR]: AlertTriangle,
  [STATE_NOT_CONFIGURED]: CircleSlash,
  [STATE_UNKNOWN]: CircleSlash,
};

const STATE_TONE = {
  [STATE_REACHABLE]: "reachable",
  [STATE_OFFLINE]: "offline",
  [STATE_ERROR]: "error",
  [STATE_NOT_CONFIGURED]: "neutral",
  [STATE_UNKNOWN]: "neutral",
};

const STATE_LABEL = {
  [STATE_REACHABLE]: "Reachable",
  [STATE_OFFLINE]: "Offline",
  [STATE_ERROR]: "Error",
  [STATE_NOT_CONFIGURED]: "Not configured",
  [STATE_UNKNOWN]: "Status unavailable",
};

export default function LocalModelsPanel({ onEditLocalProvider }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // Set only when the status REQUEST itself fails (e.g. an old backend with no
  // local-model endpoint). A reachable:false server is NOT this — that is a
  // normal status the panel renders calmly.
  const [requestError, setRequestError] = useState(null);
  // Static command-helper profiles (LMM Slice 4). Fetched once; null until loaded
  // or if the endpoint is unavailable (old backend) — the helper then hides.
  const [commandData, setCommandData] = useState(null);
  const [selectedProfileId, setSelectedProfileId] = useState(null);
  const [copyState, setCopyState] = useState(COPY_IDLE);

  const fetchStatus = useCallback((probe) => {
    const call = probe ? checkLocalModelStatus : getLocalModelStatus;
    if (probe) setRefreshing(true);
    else setLoading(true);
    setRequestError(null);
    return call()
      .then((data) => setStatus(data))
      .catch((err) =>
        setRequestError(
          err?.message ||
            "Local model status is unavailable on this backend version."
        )
      )
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  }, []);

  useEffect(() => {
    fetchStatus(false);
  }, [fetchStatus]);

  // Load the static command-helper profiles once. A failure (e.g. an older backend
  // without the endpoint) simply leaves commandData null → the helper hides; it is
  // never an error the user has to act on.
  useEffect(() => {
    let cancelled = false;
    getLocalModelCommandProfile()
      .then((data) => {
        if (!cancelled) setCommandData(data);
      })
      .catch(() => {
        if (!cancelled) setCommandData(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const state = localServerState(status);
  const tone = STATE_TONE[state] || "neutral";
  const PillIcon = PILL_ICON[state] || CircleSlash;
  const latency = statusLatencyMs(status);
  const count = statusModelCount(status);
  const { shown, overflow } = modelChips(status, 12);
  const errorMessage = statusErrorMessage(status);
  const notes = statusNotes(status);
  const host = typeof status?.base_url_host === "string" ? status.base_url_host : null;
  const inDocker = status?.in_docker === true;
  const selectedModel = typeof status?.selected_model === "string" ? status.selected_model : null;
  const defaultModel = typeof status?.default_model === "string" ? status.default_model : null;
  const editAction = findAction(status, "open_provider_settings");
  // Disabled, planned-only affordances rendered as clearly disabled chips — never
  // an enabled control that does nothing. `copy_start_command` is EXCLUDED: it is
  // now superseded by the first-class command helper below (driven by the separate
  // /command-profile endpoint), so we never show a leftover "Planned" chip for it.
  const plannedActions = statusActions(status).filter(
    (a) => !a.enabled && a.id !== "copy_start_command"
  );

  // Command helper (LMM Slice 4): the active profile + whether a copyable command
  // exists. Offline/not-configured surfaces it prominently; reachable keeps it
  // secondary (collapsed). This is COPY-ONLY — nothing here ever executes it.
  const profiles = commandProfiles(commandData);
  const activeProfile = profileById(commandData, selectedProfileId);
  const canCopy = commandAvailable(activeProfile);
  const helperNotes = commandNotes(commandData);
  const helperProminent = state === STATE_OFFLINE || state === STATE_NOT_CONFIGURED;

  const onCopyCommand = useCallback(async () => {
    if (!activeProfile?.command) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(activeProfile.command);
        setCopyState(COPY_COPIED);
      } else {
        // No Clipboard API (insecure origin / old browser) → fall back to a manual
        // "select and copy" instruction rather than failing silently.
        setCopyState(COPY_FAILED);
      }
    } catch {
      setCopyState(COPY_FAILED);
    }
    setTimeout(() => setCopyState(COPY_IDLE), 2600);
  }, [activeProfile]);

  return (
    <div className="mt-8 max-w-[860px]">
      <div className="sg-section-head">
        <h2>Local Models</h2>
        <span>Detection-only · read-only</span>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        {/* Header row: title + live status pill + Refresh */}
        <div className="flex items-center gap-3">
          <span className="grid h-[42px] w-[42px] shrink-0 place-items-center rounded-[11px] bg-[#7C3AED]/30 text-[#C4B5FD]">
            <Server size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <strong className="block text-[13px] text-[#E8EAF0]">Local OpenAI-compatible server</strong>
            <p className="truncate text-[11.5px] text-[#9098A8]">
              {host ? `host: ${host}` : "no base URL configured"}
              {inDocker ? " · app in Docker" : ""}
            </p>
          </div>
          <span
            className={`inline-flex h-[24px] shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[10.5px] ${PILL_TONE[tone]}`}
          >
            {loading ? <Loader2 size={11} className="animate-spin" /> : <PillIcon size={11} />}
            {loading ? "Checking…" : STATE_LABEL[state]}
          </span>
          <button
            type="button"
            className="sg-ghost-button shrink-0"
            onClick={() => fetchStatus(true)}
            disabled={loading || refreshing}
            title="Re-probe the local server (does not save settings or start anything)"
          >
            {refreshing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            <span className="ml-1.5">{refreshing ? "Checking…" : "Refresh status"}</span>
          </button>
        </div>

        {requestError ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-[11.5px] leading-5 text-[#9098A8]">
            <CircleSlash size={14} className="mt-0.5 shrink-0" />
            <div className="min-w-0">
              <strong className="block text-[#D4D4D8]">Local model status unavailable</strong>
              <span className="block break-words">{requestError}</span>
            </div>
          </div>
        ) : (
          <>
            {/* Metrics strip */}
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metric label="Latency" value={latency === null ? "—" : `${latency} ms`} />
              <Metric label="Models" value={String(count)} />
              <Metric label="Default" value={defaultModel || "—"} />
              <Metric label="Selected" value={selectedModel || "—"} />
            </div>

            {/* Error / offline message (already redacted server-side) */}
            {errorMessage && state !== STATE_REACHABLE && (
              <p className="mt-3 break-words text-[11.5px] leading-5 text-[#FCD34D]">
                {errorMessage}
              </p>
            )}

            {/* Discovered models — compact chips, bounded list */}
            <div className="mt-4">
              <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-[#9098A8]">
                Discovered models
              </span>
              {shown.length === 0 ? (
                <p className="text-[11.5px] leading-5 text-[#6B7185]">
                  {state === STATE_REACHABLE
                    ? "Server reachable but no models reported."
                    : "None — start the server and Refresh."}
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {shown.map((m) => (
                    <span
                      key={m}
                      className={`inline-flex h-[22px] items-center gap-1 rounded-full border px-2 text-[10.5px] ${
                        m === selectedModel
                          ? "border-[#86EFAC]/30 bg-[#86EFAC]/10 text-[#86EFAC]"
                          : "border-white/10 bg-white/5 text-[#D4D4D8]"
                      }`}
                    >
                      {m}
                    </span>
                  ))}
                  {overflow > 0 && (
                    <span className="inline-flex h-[22px] items-center rounded-full border border-white/10 bg-white/5 px-2 text-[10.5px] text-[#9098A8]">
                      +{overflow} more
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Offline / not-configured troubleshooting — non-executing */}
            {(state === STATE_OFFLINE || state === STATE_NOT_CONFIGURED) && (
              <Troubleshooting state={state} host={host} inDocker={inDocker} notes={notes} />
            )}

            {/* Backend notes for reachable/error states (e.g. binding hints) */}
            {state !== STATE_OFFLINE && state !== STATE_NOT_CONFIGURED && notes.length > 0 && (
              <ul className="mt-3 space-y-1 text-[11.5px] leading-5 text-[#9098A8]">
                {notes.map((note, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span className="text-[#6B7185]">•</span>
                    <span className="break-words">{note}</span>
                  </li>
                ))}
              </ul>
            )}

            {/* Command helper (LMM Slice 4): copyable, manual-only start command */}
            {canCopy && (
              <CommandHelper
                prominent={helperProminent}
                profiles={profiles}
                activeProfile={activeProfile}
                selectedProfileId={selectedProfileId}
                onSelectProfile={(id) => {
                  setSelectedProfileId(id);
                  setCopyState(COPY_IDLE);
                }}
                copyState={copyState}
                onCopy={onCopyCommand}
                notes={helperNotes}
              />
            )}

            {/* Actions: edit-link (single writer is Providers) + disabled planned */}
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/5 pt-4">
              <button
                type="button"
                className="sg-ghost-button"
                onClick={onEditLocalProvider}
              >
                <SettingsGlyph />
                <span className="ml-1.5">{editAction?.label || "Edit local provider settings"}</span>
              </button>
              {plannedActions.map((action) => (
                <span
                  key={action.id}
                  className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.02] px-3 text-[12px] text-[#6B7185]"
                  title={action.reason || "Planned for a later slice."}
                  aria-disabled="true"
                >
                  <Terminal size={13} />
                  {action.label}
                  <span className="rounded-full border border-white/10 px-1.5 text-[10px] uppercase tracking-wide">
                    Planned
                  </span>
                </span>
              ))}
            </div>
            <p className="mt-2 text-[11px] leading-4 text-[#6B7185]">
              Read-only — this panel detects the local server. It never starts, stops, or
              configures it. Edit the base URL and default model on the Local provider card above.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2">
      <span className="block text-[10px] uppercase tracking-wide text-[#6B7185]">{label}</span>
      <span className="mt-0.5 block truncate text-[12.5px] text-[#E8EAF0]" title={value}>
        {value}
      </span>
    </div>
  );
}

function Troubleshooting({ state, host, inDocker, notes }) {
  const isDockerHost = host === "host.docker.internal";
  return (
    <div className="mt-4 rounded-lg border border-[#FCD34D]/20 bg-[#FCD34D]/[0.05] p-3">
      <div className="flex items-start gap-2">
        <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#FCD34D]" />
        <div className="min-w-0 text-[11.5px] leading-5 text-[#D4D4D8]">
          {state === STATE_NOT_CONFIGURED ? (
            <>
              <strong className="block text-[#FCD34D]">No local server configured</strong>
              <p className="mt-1 text-[#9098A8]">
                Set the base URL on the Local provider card above (an OpenAI-compatible
                endpoint ending in <code>/v1</code>), then Refresh.
              </p>
            </>
          ) : (
            <>
              <strong className="block text-[#FCD34D]">Local server not reachable</strong>
              <ol className="mt-1.5 list-decimal space-y-1 pl-4 text-[#9098A8]">
                <li>Start your local OpenAI-compatible server (e.g. <code>llama-server</code>) on your host.</li>
                <li>
                  Confirm it exposes the OpenAI-compatible models endpoint at{" "}
                  <code>{host ? `${host}…/v1/models` : "…/v1/models"}</code>.
                </li>
                {inDocker && isDockerHost && (
                  <li>
                    The app runs in Docker and reaches your host at{" "}
                    <code>host.docker.internal</code>. Bind the server with{" "}
                    <code>--host 0.0.0.0</code> (not <code>127.0.0.1</code>) so the container can reach it.
                  </li>
                )}
                <li>Then click <strong>Refresh status</strong>.</li>
              </ol>
            </>
          )}
          {/* Any extra backend notes not already implied above */}
          {notes.length > 0 && (
            <ul className="mt-2 space-y-1 text-[#9098A8]">
              {notes.map((note, i) => (
                <li key={i} className="flex gap-1.5">
                  <span className="text-[#6B7185]">•</span>
                  <span className="break-words">{note}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// Copyable, MANUAL-ONLY llama-server start command (LMM Slice 4). This renders a
// display template the operator runs themselves in a terminal — there is NO Start
// button and nothing here executes. `prominent` expands it inline (offline /
// not-configured); otherwise it is a collapsed, secondary <details> so a reachable
// server keeps the helper out of the way.
export function CommandHelper({
  prominent,
  profiles,
  activeProfile,
  selectedProfileId,
  onSelectProfile,
  copyState,
  onCopy,
  notes,
}) {
  if (!activeProfile?.command) return null;
  const failed = copyState === COPY_FAILED;
  const copied = copyState === COPY_COPIED;
  const CopyIcon = copied ? ClipboardCheck : Copy;

  const body = (
    <div className="space-y-3">
      <p className="text-[11.5px] leading-5 text-[#9098A8]">
        Run this in a terminal <strong className="text-[#D4D4D8]">on your host machine</strong>.
        The app never runs it for you — copy it, edit the model path, run it, then click
        Refresh status.
      </p>

      {/* Profile picker (only when more than one whitelisted profile exists) */}
      {profiles.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {profiles.map((p) => {
            const active = p.id === activeProfile.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelectProfile(p.id)}
                aria-pressed={active}
                className={`inline-flex h-[26px] items-center rounded-full border px-2.5 text-[11px] ${
                  active
                    ? "border-[#C4B5FD]/40 bg-[#7C3AED]/20 text-[#C4B5FD]"
                    : "border-white/10 bg-white/[0.03] text-[#9098A8] hover:text-[#D4D4D8]"
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      )}
      {activeProfile.description && (
        <p className="text-[11px] leading-5 text-[#6B7185]">{activeProfile.description}</p>
      )}

      {/* The command itself — selectable code block + copy button */}
      <div className="rounded-lg border border-white/10 bg-black/30">
        <div className="flex items-center justify-between gap-2 border-b border-white/5 px-3 py-1.5">
          <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-wide text-[#6B7185]">
            <Terminal size={12} /> Start command
          </span>
          <button
            type="button"
            onClick={onCopy}
            className={`inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-[11px] ${
              copied
                ? "border-[#86EFAC]/30 bg-[#86EFAC]/10 text-[#86EFAC]"
                : failed
                ? "border-[#FCD34D]/30 bg-[#FCD34D]/10 text-[#FCD34D]"
                : "border-white/10 bg-white/5 text-[#D4D4D8] hover:bg-white/10"
            }`}
            title="Copy the command to your clipboard (does not run it)"
          >
            <CopyIcon size={12} />
            {copyButtonLabel(copyState)}
          </button>
        </div>
        <pre className="overflow-x-auto px-3 py-2.5 text-[11.5px] leading-5 text-[#E8EAF0]">
          <code className="whitespace-pre-wrap break-all font-mono">{activeProfile.command}</code>
        </pre>
      </div>

      {failed && (
        <p className="text-[11px] leading-4 text-[#FCD34D]">
          Couldn’t access the clipboard. Select the command text above and copy it manually
          (Ctrl/Cmd+C).
        </p>
      )}

      {/* Static safety/usage warnings from the backend profile */}
      {activeProfile.warnings.length > 0 && (
        <ul className="space-y-1 text-[11px] leading-5 text-[#9098A8]">
          {activeProfile.warnings.map((w, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="text-[#6B7185]">•</span>
              <span className="break-words">{w}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Top-level helper notes (e.g. the Docker base-URL hint) */}
      {notes.length > 0 && (
        <ul className="space-y-1 text-[11px] leading-5 text-[#6B7185]">
          {notes.map((n, i) => (
            <li key={i} className="flex gap-1.5">
              <span>•</span>
              <span className="break-words">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  const heading = (
    <span className="inline-flex items-center gap-2 text-[12px] font-medium text-[#E8EAF0]">
      <Terminal size={14} className="text-[#C4B5FD]" />
      How to start llama-server (manual)
    </span>
  );

  // Prominent: expanded inline block (offline / not-configured). Secondary: a
  // collapsed <details> so a reachable server keeps it tucked away.
  if (prominent) {
    return (
      <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.02] p-3">
        <div className="mb-2">{heading}</div>
        {body}
      </div>
    );
  }
  return (
    <details className="mt-4 rounded-lg border border-white/10 bg-white/[0.02] p-3">
      <summary className="cursor-pointer list-none">{heading}</summary>
      <div className="mt-3">{body}</div>
    </details>
  );
}

// Small inline gear glyph (avoids pulling another icon name that may not exist in
// the pinned lucide-react version).
function SettingsGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}
