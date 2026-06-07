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
  clearLocalModelLibrarySelection,
  getLocalModelCompanionStatus,
  getLocalModelCommandProfile,
  getLocalModelLibrary,
  getLocalModelLibrarySelection,
  getLocalModelServerStatus,
  getLocalModelStatus,
  restartLocalModelServer,
  scanLocalModelLibrary,
  saveLocalModelLibrarySelection,
  startLocalModelServer,
  stopLocalModelServer,
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
import {
  COMPANION_AUTH_FAILED,
  COMPANION_ERROR,
  COMPANION_OFFLINE,
  COMPANION_REACHABLE,
  COMPANION_UNCONFIGURED,
  companionBadge,
  companionCapabilities,
  companionErrorMessage,
  companionState,
  formatModelModifiedAt,
  formatModelSize,
  libraryModelCount,
  libraryModels,
  libraryRootsConfigured,
  librarySelectionPreview,
  librarySelectionStale,
  libraryWarnings,
  normalizeLibrarySelection,
  selectedLibraryModel,
} from "../localModelLibrary";
import {
  SAFE_SERVER_DEFAULTS,
  SAFE_TEST_PROFILE_ID,
  buildLocalModelServerStartPayload,
  buildLocalModelServerStopPayload,
  localModelServerErrorMessage,
  localModelServerIsManagedRunning,
  localModelServerStatusLabel,
  normalizeLocalModelServerState,
} from "../localModelServer";

// Local Models status panel. The local provider status remains detection-only;
// Phase 2G4 adds companion-managed test/server process controls through the
// backend bridge only. It NEVER edits provider settings, never calls the host
// companion directly, and never renders raw connection details or full URL.
//
// Consumes the detection-only
// Slice 2 endpoints (GET /api/local-model/status on open, POST
// /api/local-model/check on Refresh). It only shows
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
  const [companionStatus, setCompanionStatus] = useState(null);
  const [companionLoading, setCompanionLoading] = useState(true);
  const [companionRequestError, setCompanionRequestError] = useState(null);
  const [libraryData, setLibraryData] = useState(null);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [libraryRequestError, setLibraryRequestError] = useState(null);
  const [scanningLibrary, setScanningLibrary] = useState(false);
  const [scanMessage, setScanMessage] = useState(null);
  const [selectedLibraryModelId, setSelectedLibraryModelId] = useState(null);
  const [librarySelectionData, setLibrarySelectionData] = useState(null);
  const [librarySelectionLoading, setLibrarySelectionLoading] = useState(true);
  const [librarySelectionSaving, setLibrarySelectionSaving] = useState(false);
  const [librarySelectionRequestError, setLibrarySelectionRequestError] = useState(null);
  const [librarySelectionMessage, setLibrarySelectionMessage] = useState(null);
  const [serverStatus, setServerStatus] = useState(null);
  const [serverLoading, setServerLoading] = useState(true);
  const [serverAction, setServerAction] = useState(null);
  const [serverRequestError, setServerRequestError] = useState(null);
  const [serverMessage, setServerMessage] = useState(null);

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

  const fetchCompanionStatus = useCallback(() => {
    setCompanionLoading(true);
    setCompanionRequestError(null);
    return getLocalModelCompanionStatus()
      .then((data) => setCompanionStatus(data))
      .catch((err) => {
        setCompanionStatus(null);
        setCompanionRequestError(
          err?.message || "Companion status is unavailable on this backend version."
        );
      })
      .finally(() => setCompanionLoading(false));
  }, []);

  const fetchLibrary = useCallback((scan = false) => {
    const call = scan ? scanLocalModelLibrary : getLocalModelLibrary;
    if (scan) {
      setScanningLibrary(true);
      setScanMessage(null);
    } else {
      setLibraryLoading(true);
    }
    setLibraryRequestError(null);
    return call()
      .then((data) => {
        setLibraryData(data);
        if (scan) setScanMessage("Scan complete.");
      })
      .catch((err) => {
        const message = err?.message || "Model library is unavailable on this backend version.";
        setLibraryRequestError(message);
        if (scan) setScanMessage("Scan failed.");
      })
      .finally(() => {
        setLibraryLoading(false);
        setScanningLibrary(false);
      });
  }, []);

  useEffect(() => {
    fetchCompanionStatus();
    fetchLibrary(false);
  }, [fetchCompanionStatus, fetchLibrary]);

  const fetchLibrarySelection = useCallback(() => {
    setLibrarySelectionLoading(true);
    setLibrarySelectionRequestError(null);
    return getLocalModelLibrarySelection()
      .then((data) => {
        const selected = normalizeLibrarySelection(data);
        setLibrarySelectionData(data);
        if (selected?.id) setSelectedLibraryModelId(selected.id);
      })
      .catch((err) => {
        setLibrarySelectionData(null);
        setLibrarySelectionRequestError(
          err?.message || "Saved library selection is unavailable on this backend version."
        );
      })
      .finally(() => setLibrarySelectionLoading(false));
  }, []);

  useEffect(() => {
    fetchLibrarySelection();
  }, [fetchLibrarySelection]);

  const fetchServerStatus = useCallback(() => {
    setServerLoading(true);
    setServerRequestError(null);
    return getLocalModelServerStatus()
      .then((data) => setServerStatus(data))
      .catch((err) => {
        setServerStatus(null);
        setServerRequestError(
          err?.message || "Managed server status is unavailable on this backend version."
        );
      })
      .finally(() => setServerLoading(false));
  }, []);

  useEffect(() => {
    fetchServerStatus();
  }, [fetchServerStatus]);

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
  const companionStateKey = companionState(companionStatus, libraryData);
  const companionBadgeMeta = companionBadge(companionStateKey);
  const companionError = companionErrorMessage(companionStatus, libraryData);
  const companionScanCapable = companionCapabilities(companionStatus).includes("scan");
  const libraryModelList = libraryModels(libraryData);
  const librarySelectedModel = selectedLibraryModel(libraryData, selectedLibraryModelId);
  const libraryCount = libraryModelCount(libraryData);
  const libraryRoots = libraryRootsConfigured(libraryData);
  const warnings = libraryWarnings(libraryData);
  const savedLibrarySelection = normalizeLibrarySelection(librarySelectionData);
  const selectionPreview = librarySelectionPreview(librarySelectionData);
  const selectionStale = librarySelectionStale(libraryData, savedLibrarySelection);

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

  const onScanLibrary = useCallback(() => {
    fetchLibrary(true).finally(() => {
      fetchCompanionStatus();
    });
  }, [fetchCompanionStatus, fetchLibrary]);

  const onRememberLibrarySelection = useCallback(() => {
    if (!librarySelectedModel) return;
    setLibrarySelectionSaving(true);
    setLibrarySelectionRequestError(null);
    setLibrarySelectionMessage(null);
    saveLocalModelLibrarySelection({
      model_id: librarySelectedModel.id,
      model: librarySelectedModel,
    })
      .then((data) => {
        setLibrarySelectionData(data);
        setLibrarySelectionMessage("Selected library model remembered.");
      })
      .catch((err) => {
        setLibrarySelectionRequestError(err?.message || "Could not remember selected model.");
      })
      .finally(() => setLibrarySelectionSaving(false));
  }, [librarySelectedModel]);

  const onClearLibrarySelection = useCallback(() => {
    setLibrarySelectionSaving(true);
    setLibrarySelectionRequestError(null);
    setLibrarySelectionMessage(null);
    clearLocalModelLibrarySelection()
      .then((data) => {
        setLibrarySelectionData(data);
        setSelectedLibraryModelId(null);
        setLibrarySelectionMessage("Selected library model cleared.");
      })
      .catch((err) => {
        setLibrarySelectionRequestError(err?.message || "Could not clear selected model.");
      })
      .finally(() => setLibrarySelectionSaving(false));
  }, []);

  const savedServerSelection = normalizeLibrarySelection(librarySelectionData);
  const serverStartPayload = buildLocalModelServerStartPayload(savedServerSelection);
  const runServerAction = useCallback(
    (action) => {
      const startPayload = buildLocalModelServerStartPayload(savedServerSelection);
      let call = null;
      let payload = null;
      if (action === "start") {
        call = startLocalModelServer;
        payload = startPayload;
      } else if (action === "stop") {
        call = stopLocalModelServer;
        payload = buildLocalModelServerStopPayload();
      } else if (action === "restart") {
        call = restartLocalModelServer;
        payload = startPayload;
      }
      if (!call || !payload) return Promise.resolve();

      setServerAction(action);
      setServerRequestError(null);
      setServerMessage(null);
      return call(payload)
        .then((data) => {
          setServerStatus(data);
          const label = localModelServerStatusLabel(data);
          setServerMessage(`Managed server ${action} completed: ${label}.`);
          return data;
        })
        .catch((err) => {
          setServerRequestError(err?.message || `Managed server ${action} failed.`);
        })
        .finally(() => {
          setServerAction(null);
          fetchServerStatus().finally(() => fetchStatus(false));
        });
    },
    [fetchServerStatus, fetchStatus, savedServerSelection]
  );

  return (
    <div className="mt-8 max-w-[860px]">
      <div className="sg-section-head">
        <h2>Local Models</h2>
        <span>Status · library · managed test server</span>
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

            <ModelLibrarySection
              companionStateKey={companionStateKey}
              companionBadgeMeta={companionBadgeMeta}
              companionLoading={companionLoading}
              companionRequestError={companionRequestError}
              companionError={companionError}
              companionScanCapable={companionScanCapable}
              libraryData={libraryData}
              libraryLoading={libraryLoading}
              libraryRequestError={libraryRequestError}
              libraryModels={libraryModelList}
              libraryCount={libraryCount}
              libraryRoots={libraryRoots}
              warnings={warnings}
              scanning={scanningLibrary}
              scanMessage={scanMessage}
              selectedModelId={selectedLibraryModelId}
              selectedModel={librarySelectedModel}
              savedSelection={savedLibrarySelection}
              selectionPreview={selectionPreview}
              selectionStale={selectionStale}
              selectionLoading={librarySelectionLoading}
              selectionSaving={librarySelectionSaving}
              selectionRequestError={librarySelectionRequestError}
              selectionMessage={librarySelectionMessage}
              onScan={onScanLibrary}
              onSelectModel={(id) => {
                setSelectedLibraryModelId(id);
                setLibrarySelectionMessage(null);
              }}
              onRememberSelection={onRememberLibrarySelection}
              onClearSelection={onClearLibrarySelection}
            />

            <ManagedServerSection
              companionStateKey={companionStateKey}
              companionLoading={companionLoading}
              selection={savedServerSelection}
              startPayload={serverStartPayload}
              status={serverStatus}
              loading={serverLoading}
              action={serverAction}
              requestError={serverRequestError}
              message={serverMessage}
              onRefresh={fetchServerStatus}
              onStart={() => runServerAction("start")}
              onStop={() => runServerAction("stop")}
              onRestart={() => runServerAction("restart")}
            />

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
              Local provider status is still detection-only. Managed Server controls use only
              the companion backend bridge and do not edit the Local provider card above.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function ModelLibrarySection({
  companionStateKey,
  companionBadgeMeta,
  companionLoading,
  companionRequestError,
  companionError,
  companionScanCapable,
  libraryData,
  libraryLoading,
  libraryRequestError,
  libraryModels,
  libraryCount,
  libraryRoots,
  warnings,
  scanning,
  scanMessage,
  selectedModelId,
  selectedModel,
  savedSelection,
  selectionPreview,
  selectionStale,
  selectionLoading,
  selectionSaving,
  selectionRequestError,
  selectionMessage,
  onScan,
  onSelectModel,
  onRememberSelection,
  onClearSelection,
}) {
  const badgeTone = companionBadgeMeta.tone || "neutral";
  const statusCopy = companionStatusCopy(
    companionStateKey,
    companionRequestError,
    companionError,
    companionScanCapable
  );
  const lastScan = libraryData?.last_scan_at
    ? formatModelModifiedAt(libraryData.last_scan_at)
    : "Never";
  const chosenName = savedSelection?.display_name || savedSelection?.filename || "—";
  const hasPendingChoice = !!selectedModel && selectedModel.id !== savedSelection?.id;

  return (
    <section className="mt-4 rounded-lg border border-white/10 bg-white/[0.02] p-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <strong className="text-[12.5px] text-[#E8EAF0]">Model Library</strong>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#9098A8]">
              Library discovery only
            </span>
          </div>
          <p className="mt-1 text-[11.5px] leading-5 text-[#9098A8]">
            Approved GGUF folder discovery with app-side selected-model metadata.
          </p>
        </div>
        <span
          className={`inline-flex h-[24px] shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[10.5px] ${PILL_TONE[badgeTone]}`}
        >
          {companionLoading ? <Loader2 size={11} className="animate-spin" /> : <CompanionStateIcon state={companionStateKey} />}
          {companionLoading ? "Checking…" : companionBadgeMeta.label}
        </span>
        <button
          type="button"
          className="sg-ghost-button shrink-0"
          onClick={onScan}
          disabled={scanning}
          title="Ask the companion to rescan approved folders"
        >
          {scanning ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          <span className="ml-1.5">{scanning ? "Scanning…" : "Scan approved folder(s)"}</span>
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Approved roots" value={String(libraryRoots)} />
        <Metric label="Cached models" value={String(libraryCount)} />
        <Metric label="Last scan" value={lastScan} />
        <Metric label="Chosen library model" value={selectionLoading ? "Loading…" : chosenName} />
      </div>

      <p className="mt-3 text-[11.5px] leading-5 text-[#9098A8]">{statusCopy}</p>
      {(libraryRequestError || selectionRequestError) && (
        <p className="mt-2 break-words text-[11.5px] leading-5 text-[#FCD34D]">
          {libraryRequestError || selectionRequestError}
        </p>
      )}
      {(scanMessage || selectionMessage) && (
        <p className="mt-2 text-[11px] leading-4 text-[#6B7185]">{scanMessage || selectionMessage}</p>
      )}

      {savedSelection && (
        <ChosenLibraryModel
          model={savedSelection}
          preview={selectionPreview}
          stale={selectionStale}
          saving={selectionSaving}
          onClear={onClearSelection}
        />
      )}

      {warnings.length > 0 && (
        <div className="mt-3 rounded-lg border border-[#FCD34D]/20 bg-[#FCD34D]/[0.04] p-2.5">
          <span className="mb-1 block text-[10.5px] font-medium uppercase tracking-wide text-[#FCD34D]">
            Scan warnings
          </span>
          <ul className="space-y-1 text-[11px] leading-5 text-[#9098A8]">
            {warnings.slice(0, 5).map((warning, i) => (
              <li key={`${warning.code || "warning"}-${i}`} className="flex gap-1.5">
                <AlertTriangle size={12} className="mt-1 shrink-0 text-[#FCD34D]" />
                <span className="min-w-0 break-words">
                  {warning.message || warning.code || "Companion warning"}
                  {warning.root_id ? ` · root ${warning.root_id}` : ""}
                  {warning.relative_path ? ` · ${warning.relative_path}` : ""}
                  {warning.count ? ` · ${warning.count} more` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3">
        {libraryLoading && !libraryData ? (
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-[11.5px] text-[#9098A8]">
            <Loader2 size={14} className="animate-spin" />
            Loading cached library…
          </div>
        ) : libraryModels.length === 0 ? (
          <EmptyLibraryState state={companionStateKey} roots={libraryRoots} requestError={libraryRequestError} />
        ) : (
          <div className="grid gap-2">
            {libraryModels.map((model) => (
              <LibraryModelButton
                key={model.id}
                model={model}
                selected={model.id === selectedModelId}
                persisted={model.id === savedSelection?.id}
                onSelect={() => onSelectModel(model.id)}
              />
            ))}
          </div>
        )}
      </div>

      {selectedModel && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/5 pt-3">
          <button
            type="button"
            className="sg-ghost-button"
            onClick={onRememberSelection}
            disabled={selectionSaving || !hasPendingChoice}
            title="Persist this selected library model as app-side metadata"
          >
            {selectionSaving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            <span className="ml-1.5">
              {hasPendingChoice ? "Remember selected model" : "Selected model remembered"}
            </span>
          </button>
          <p className="min-w-[220px] flex-1 text-[11px] leading-4 text-[#6B7185]">
            Provider Settings, Ask, and the local provider default are unchanged.
          </p>
        </div>
      )}
    </section>
  );
}

function ManagedServerSection({
  companionStateKey,
  companionLoading,
  selection,
  startPayload,
  status,
  loading,
  action,
  requestError,
  message,
  onRefresh,
  onStart,
  onStop,
  onRestart,
}) {
  const companionAvailable = companionStateKey === COMPANION_REACHABLE;
  const hasSelection = !!selection?.id && !!startPayload;
  const managedRunning = localModelServerIsManagedRunning(status);
  const state = normalizeLocalModelServerState(status);
  const statusLabel = loading ? "Checking..." : localModelServerStatusLabel(status);
  const statusError = localModelServerErrorMessage(status);
  const busy = !!action;
  const canStart = companionAvailable && hasSelection && !busy && !companionLoading;
  const canStop = companionAvailable && managedRunning && !busy && !companionLoading;
  const canRestart = companionAvailable && hasSelection && managedRunning && !busy && !companionLoading;
  const selectedName = selection?.display_name || selection?.filename || selection?.id || "No selected model";
  const port = startPayload?.parameters?.port ?? SAFE_SERVER_DEFAULTS.port;

  let disabledCopy = null;
  if (!companionAvailable) disabledCopy = "Companion must be reachable before managed controls are enabled.";
  else if (!hasSelection) disabledCopy = "Choose and remember a library model before starting the managed server.";
  else if (!managedRunning) disabledCopy = "Stop and restart are enabled only for a companion-managed running server.";

  return (
    <section className="mt-4 rounded-lg border border-white/10 bg-white/[0.02] p-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <strong className="text-[12.5px] text-[#E8EAF0]">Managed Server</strong>
            <span className="rounded-full border border-[#FCD34D]/30 bg-[#FCD34D]/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#FCD34D]">
              {SAFE_TEST_PROFILE_ID} validation profile only
            </span>
          </div>
          <p className="mt-1 text-[11.5px] leading-5 text-[#9098A8]">
            This controls only the companion-managed test/server process.
          </p>
        </div>
        <span className={`inline-flex h-[24px] shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[10.5px] ${PILL_TONE[serverTone(status, companionAvailable)]}`}>
          {loading ? <Loader2 size={11} className="animate-spin" /> : <ServerStateIcon state={state} companionAvailable={companionAvailable} />}
          {statusLabel}
        </span>
        <button
          type="button"
          className="sg-ghost-button shrink-0"
          onClick={onRefresh}
          disabled={loading || busy}
          title="Refresh companion-managed server status"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          <span className="ml-1.5">Refresh managed status</span>
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="State" value={statusLabel} />
        <Metric label="Managed" value={status?.managed === true ? "Yes" : "No"} />
        <Metric label="Model id" value={selection?.id || status?.model_id || "-"} />
        <Metric label="Port" value={String(status?.port || port)} />
      </div>

      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-2.5">
        <span className="mb-1.5 block text-[10.5px] font-medium uppercase tracking-wide text-[#9098A8]">
          Start payload preview
        </span>
        <dl className="grid gap-x-3 gap-y-1 text-[11px] leading-4 text-[#9098A8] sm:grid-cols-2">
          <SafeDetail label="Selected model" value={selectedName} />
          <SafeDetail label="Profile" value={`${SAFE_TEST_PROFILE_ID} only`} />
          <SafeDetail label="Port" value={String(SAFE_SERVER_DEFAULTS.port)} />
          <SafeDetail label="Context" value={String(SAFE_SERVER_DEFAULTS.ctx_size)} />
          <SafeDetail label="GPU layers" value={String(SAFE_SERVER_DEFAULTS.gpu_layers)} />
          <SafeDetail label="Threads" value={String(SAFE_SERVER_DEFAULTS.threads)} />
        </dl>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/5 pt-3">
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onStart}
          disabled={!canStart}
          title="Starts companion-managed server only."
        >
          {action === "start" ? <Loader2 size={14} className="animate-spin" /> : <Server size={14} />}
          <span className="ml-1.5">{action === "start" ? "Starting..." : "Start selected model"}</span>
        </button>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onStop}
          disabled={!canStop}
          title="Stops only the companion-managed server."
        >
          {action === "stop" ? <Loader2 size={14} className="animate-spin" /> : <CircleSlash size={14} />}
          <span className="ml-1.5">{action === "stop" ? "Stopping..." : "Stop managed server"}</span>
        </button>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onRestart}
          disabled={!canRestart}
          title="Restarts with the saved selected model and safe defaults."
        >
          {action === "restart" ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          <span className="ml-1.5">{action === "restart" ? "Restarting..." : "Restart managed server"}</span>
        </button>
      </div>

      <div className="mt-3 space-y-1 text-[11px] leading-4 text-[#6B7185]">
        <p>Starts companion-managed server only.</p>
        <p>Stops only the companion-managed server. Manual servers are not stopped by this button.</p>
        <p>Provider Settings are not changed.</p>
      </div>

      {disabledCopy && (
        <p className="mt-2 text-[11px] leading-4 text-[#9098A8]">{disabledCopy}</p>
      )}
      {(requestError || statusError) && (
        <p className="mt-2 break-words text-[11.5px] leading-5 text-[#FCD34D]">
          {requestError || statusError}
        </p>
      )}
      {message && <p className="mt-2 text-[11px] leading-4 text-[#6B7185]">{message}</p>}
    </section>
  );
}

function serverTone(status, companionAvailable) {
  if (!companionAvailable) return "neutral";
  const state = normalizeLocalModelServerState(status);
  if (state === "running" || state === "already_running") return "reachable";
  if (state === "crashed" || state === "error") return "error";
  if (state === "stopped" || state === "not_running") return "offline";
  return "neutral";
}

function ServerStateIcon({ state, companionAvailable }) {
  if (!companionAvailable) return <CircleSlash size={11} />;
  if (state === "running" || state === "already_running") return <Check size={11} />;
  if (state === "stopped" || state === "not_running") return <CircleSlash size={11} />;
  if (state === "crashed" || state === "error") return <AlertTriangle size={11} />;
  return <CircleSlash size={11} />;
}

function CompanionStateIcon({ state }) {
  if (state === COMPANION_REACHABLE) return <Check size={11} />;
  if (state === COMPANION_UNCONFIGURED) return <CircleSlash size={11} />;
  if (state === COMPANION_OFFLINE) return <WifiOff size={11} />;
  if (state === COMPANION_AUTH_FAILED || state === COMPANION_ERROR) {
    return <AlertTriangle size={11} />;
  }
  return <CircleSlash size={11} />;
}

function companionStatusCopy(state, requestError, errorMessage, scanCapable) {
  if (requestError) return "Companion endpoints are unavailable; manual command helper remains usable below.";
  if (state === COMPANION_REACHABLE) {
    return scanCapable
      ? "Companion is reachable and can scan approved folders."
      : "Companion is reachable; scan capability was not reported.";
  }
  if (state === COMPANION_UNCONFIGURED) {
    return "Companion is not configured on the backend. Configure it server-side to use approved-folder discovery.";
  }
  if (state === COMPANION_OFFLINE) {
    return "Companion is configured but not reachable. Cached library data may be empty or stale.";
  }
  if (state === COMPANION_AUTH_FAILED) {
    return "Companion authentication failed. Check the server-side companion configuration.";
  }
  return errorMessage || "Companion library state is unavailable.";
}

function EmptyLibraryState({ state, roots, requestError }) {
  let copy = "No GGUF models discovered yet.";
  if (requestError) copy = "Cached model library is unavailable on this backend.";
  else if (state === COMPANION_UNCONFIGURED) copy = "No companion configured for approved-folder discovery.";
  else if (state === COMPANION_OFFLINE) copy = "Companion is not reachable; no cached models are available.";
  else if (state === COMPANION_AUTH_FAILED) copy = "Companion auth failed; no cached models are available.";
  else if (roots === 0) copy = "No approved folders are configured on the companion.";
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-[11.5px] leading-5 text-[#9098A8]">
      {copy}
    </div>
  );
}

function ChosenLibraryModel({ model, preview, stale, saving, onClear }) {
  const name = model.display_name || model.filename || model.relative_path || model.id;
  return (
    <div className="mt-3 rounded-lg border border-[#86EFAC]/20 bg-[#86EFAC]/[0.04] p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <strong className="break-words text-[12.5px] text-[#E8EAF0]">{name}</strong>
            <span className="rounded-full border border-[#86EFAC]/30 bg-[#86EFAC]/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#86EFAC]">
              Chosen library model
            </span>
            {stale && (
              <span className="rounded-full border border-[#FCD34D]/30 bg-[#FCD34D]/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#FCD34D]">
                Saved but not in current library
              </span>
            )}
          </div>
          <dl className="mt-2 grid gap-x-3 gap-y-1 text-[11px] leading-4 text-[#9098A8] sm:grid-cols-2">
            <SafeDetail label="File" value={model.filename || "—"} />
            <SafeDetail label="Path" value={model.relative_path || "—"} />
            <SafeDetail label="Root" value={model.root_id || "—"} />
            <SafeDetail label="Size" value={formatModelSize(model.size_bytes)} />
            <SafeDetail label="Modified" value={formatModelModifiedAt(model.modified_at)} />
            <SafeDetail label="Selected" value={formatModelModifiedAt(model.selected_at)} />
          </dl>
          {stale && (
            <p className="mt-2 text-[11px] leading-4 text-[#FCD34D]">
              Scan approved folder(s) again if this model moved or was removed.
            </p>
          )}
        </div>
        <button
          type="button"
          className="sg-ghost-button shrink-0"
          onClick={onClear}
          disabled={saving}
          title="Clear the saved library model selection"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <CircleSlash size={14} />}
          <span className="ml-1.5">Clear selection</span>
        </button>
      </div>
      {preview && <FutureLaunchPreview preview={preview} />}
      <p className="mt-2 text-[11px] leading-4 text-[#6B7185]">
        This selection is used by Managed Server start/restart with safe typed defaults.
        Provider Settings were not changed.
      </p>
    </div>
  );
}

function FutureLaunchPreview({ preview }) {
  return (
    <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-2.5">
      <span className="mb-1.5 block text-[10.5px] font-medium uppercase tracking-wide text-[#9098A8]">
        Saved selection preview
      </span>
      <dl className="grid gap-x-3 gap-y-1 text-[11px] leading-4 text-[#9098A8] sm:grid-cols-2">
        <SafeDetail label="Model id" value={preview.model_id || "—"} />
        <SafeDetail label="File" value={preview.filename || "—"} />
        <SafeDetail label="Path" value={preview.relative_path || "companion resolves id"} />
        <SafeDetail label="Root" value={preview.root_id || "—"} />
        <SafeDetail label="Profile" value={preview.profile || "gpu_default"} />
        <SafeDetail label="Resolver" value={preview.resolver || "companion_model_id"} />
      </dl>
      <p className="mt-2 text-[11px] leading-4 text-[#6B7185]">
        No runnable command is generated here; the companion resolves the model id server-side.
      </p>
    </div>
  );
}

function LibraryModelButton({ model, selected, persisted, onSelect }) {
  const name = model.display_name || model.filename || model.relative_path || model.id;
  const chips = [
    model.family_hint,
    model.quant_hint,
    model.server_compatible === true ? "server compatible" : null,
  ].filter(Boolean);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-lg border p-3 text-left transition ${
        selected
          ? "border-[#86EFAC]/30 bg-[#86EFAC]/[0.07]"
          : "border-white/10 bg-white/[0.025] hover:border-white/20 hover:bg-white/[0.04]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border ${
            selected
              ? "border-[#86EFAC]/40 bg-[#86EFAC]/10 text-[#86EFAC]"
              : "border-white/10 bg-white/[0.03] text-[#6B7185]"
          }`}
          aria-hidden="true"
        >
          {selected ? <Check size={12} /> : null}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <strong className="break-words text-[12.5px] text-[#E8EAF0]">{name}</strong>
            {selected && (
              <span className="rounded-full border border-[#86EFAC]/30 bg-[#86EFAC]/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#86EFAC]">
                Selected here
              </span>
            )}
            {persisted && (
              <span className="rounded-full border border-[#C4B5FD]/30 bg-[#7C3AED]/15 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[#C4B5FD]">
                Remembered
              </span>
            )}
          </div>
          <dl className="mt-2 grid gap-x-3 gap-y-1 text-[11px] leading-4 text-[#9098A8] sm:grid-cols-2">
            <SafeDetail label="File" value={model.filename || "—"} />
            <SafeDetail label="Path" value={model.relative_path || "—"} />
            <SafeDetail label="Root" value={model.root_id || "—"} />
            <SafeDetail label="Size" value={formatModelSize(model.size_bytes)} />
            <SafeDetail label="Modified" value={formatModelModifiedAt(model.modified_at)} />
            <SafeDetail label="Compatible" value={model.server_compatible === true ? "Yes" : "Unknown"} />
          </dl>
          {chips.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {chips.map((chip) => (
                <span
                  key={chip}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10.5px] text-[#D4D4D8]"
                >
                  {chip}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

function SafeDetail({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="inline text-[#6B7185]">{label}: </dt>
      <dd className="inline break-words text-[#D4D4D8]">{value}</dd>
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
