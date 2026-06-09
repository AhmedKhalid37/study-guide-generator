import React, { useCallback, useEffect, useMemo, useState } from "react";
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
  getLocalModelServerProfiles,
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
  libraryRootSummaries,
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
  coerceProfileParameterValue,
  localModelServerProfileDefaults,
  localModelServerProfiles,
  localModelServerErrorMessage,
  localModelServerIsManagedRunning,
  localModelServerStatusLabel,
  normalizeLocalModelServerState,
  profileById as serverProfileById,
  safestRunnableServerProfile,
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

// Tone → pill modifier class. The selection LOGIC (which tone key applies) is
// unchanged from the previous palette; only the resolved class is the GuideForge
// semantic pill (green reachable / amber offline / grey neutral / red error).
const PILL_TONE = {
  reachable: "is-ok",
  offline: "is-warn",
  error: "is-error",
  neutral: "is-neutral",
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
  const [serverProfilesData, setServerProfilesData] = useState(null);
  const [serverProfilesLoading, setServerProfilesLoading] = useState(true);
  const [serverProfilesRequestError, setServerProfilesRequestError] = useState(null);
  const [selectedServerProfileId, setSelectedServerProfileId] = useState(null);
  const [serverParameterValues, setServerParameterValues] = useState({});

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

  const fetchServerProfiles = useCallback(() => {
    setServerProfilesLoading(true);
    setServerProfilesRequestError(null);
    return getLocalModelServerProfiles()
      .then((data) => setServerProfilesData(data))
      .catch((err) => {
        setServerProfilesData(null);
        setServerProfilesRequestError(
          err?.message || "Managed server profiles are unavailable on this backend version."
        );
      })
      .finally(() => setServerProfilesLoading(false));
  }, []);

  useEffect(() => {
    fetchServerProfiles();
  }, [fetchServerProfiles]);

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
  const rootSummaries = libraryRootSummaries(libraryData);
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
  const serverProfiles = useMemo(() => localModelServerProfiles(serverProfilesData), [serverProfilesData]);
  const selectedServerProfile =
    serverProfileById(serverProfiles, selectedServerProfileId) ||
    safestRunnableServerProfile(serverProfiles);
  const serverStartPayload = buildLocalModelServerStartPayload(
    savedServerSelection,
    selectedServerProfile,
    serverParameterValues
  );

  useEffect(() => {
    const safest = safestRunnableServerProfile(serverProfiles);
    const current = serverProfileById(serverProfiles, selectedServerProfileId);
    if (!current && safest) {
      setSelectedServerProfileId(safest.id);
    }
  }, [selectedServerProfileId, serverProfiles]);

  useEffect(() => {
    if (!selectedServerProfile) {
      setServerParameterValues({});
      return;
    }
    setServerParameterValues(localModelServerProfileDefaults(selectedServerProfile));
  }, [selectedServerProfile?.id]);

  const onSelectServerProfile = useCallback(
    (profileId) => {
      const profile = serverProfileById(serverProfiles, profileId);
      if (!profile) return;
      setSelectedServerProfileId(profile.id);
      setServerParameterValues(localModelServerProfileDefaults(profile));
      setServerMessage(null);
    },
    [serverProfiles]
  );

  const onChangeServerParameter = useCallback(
    (name, value) => {
      const schema = selectedServerProfile?.parameters?.[name];
      if (!schema) return;
      setServerParameterValues((current) => ({
        ...current,
        [name]: coerceProfileParameterValue(schema, value),
      }));
    },
    [selectedServerProfile]
  );

  const onResetServerParameters = useCallback(() => {
    if (!selectedServerProfile) return;
    setServerParameterValues(localModelServerProfileDefaults(selectedServerProfile));
    setServerMessage("Profile defaults restored.");
  }, [selectedServerProfile]);

  const runServerAction = useCallback(
    (action) => {
      const startPayload = buildLocalModelServerStartPayload(
        savedServerSelection,
        selectedServerProfile,
        serverParameterValues
      );
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
    [fetchServerStatus, fetchStatus, savedServerSelection, selectedServerProfile, serverParameterValues]
  );

  return (
    <div className="sg-mdl-local">
      <div className="sg-mdl-section-head">
        <h2>Local Models</h2>
        <span>Status · library · managed test server</span>
      </div>

      <div className="sg-mdl-local-card">
        {/* Header row: title + live status pill + Refresh */}
        <div className="sg-mdl-local-head">
          <span className="sg-mdl-server-icon">
            <Server size={18} />
          </span>
          <div className="sg-mdl-local-head-main">
            <strong>Local OpenAI-compatible server</strong>
            <p>
              {host ? `host: ${host}` : "no base URL configured"}
              {inDocker ? " · app in Docker" : ""}
            </p>
          </div>
          <span className={`sg-mdl-pill ${PILL_TONE[tone]}`}>
            {loading ? <Loader2 size={11} className="sg-spin" /> : <PillIcon size={11} />}
            {loading ? "Checking…" : STATE_LABEL[state]}
          </span>
          <button
            type="button"
            className="sg-ghost-button"
            onClick={() => fetchStatus(true)}
            disabled={loading || refreshing}
            title="Re-probe the local server (does not save settings or start anything)"
          >
            {refreshing ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
            <span>{refreshing ? "Checking…" : "Refresh status"}</span>
          </button>
        </div>

        {requestError ? (
          <div className="sg-mdl-infobox start">
            <CircleSlash size={14} />
            <div className="sg-mdl-infobox-body">
              <strong>Local model status unavailable</strong>
              <span>{requestError}</span>
            </div>
          </div>
        ) : (
          <>
            {/* Metrics strip */}
            <div className="sg-mdl-metrics">
              <Metric label="Latency" value={latency === null ? "—" : `${latency} ms`} />
              <Metric label="Models" value={String(count)} />
              <Metric label="Default" value={defaultModel || "—"} />
              <Metric label="Selected" value={selectedModel || "—"} />
            </div>

            {/* Error / offline message (already redacted server-side) */}
            {errorMessage && state !== STATE_REACHABLE && (
              <p className="sg-mdl-notice warn">{errorMessage}</p>
            )}

            {/* Discovered models — compact chips, bounded list */}
            <div>
              <span className="sg-mdl-sublabel">Discovered models</span>
              {shown.length === 0 ? (
                <p className="sg-mdl-help dim">
                  {state === STATE_REACHABLE
                    ? "Server reachable but no models reported."
                    : "None — start the server and Refresh."}
                </p>
              ) : (
                <div className="sg-mdl-chips">
                  {shown.map((m) => (
                    <span
                      key={m}
                      className={`sg-mdl-chip ${m === selectedModel ? "is-selected" : ""}`}
                    >
                      {m}
                    </span>
                  ))}
                  {overflow > 0 && (
                    <span className="sg-mdl-chip">+{overflow} more</span>
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
              <ul className="sg-mdl-bullets">
                {notes.map((note, i) => (
                  <li key={i}>
                    <span className="sg-mdl-dot">•</span>
                    <span>{note}</span>
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
              rootSummaries={rootSummaries}
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
              profiles={serverProfiles}
              profilesLoading={serverProfilesLoading}
              profilesRequestError={serverProfilesRequestError}
              selectedProfile={selectedServerProfile}
              selectedProfileId={selectedServerProfile?.id || selectedServerProfileId}
              parameterValues={serverParameterValues}
              status={serverStatus}
              loading={serverLoading}
              action={serverAction}
              requestError={serverRequestError}
              message={serverMessage}
              onSelectProfile={onSelectServerProfile}
              onChangeParameter={onChangeServerParameter}
              onResetParameters={onResetServerParameters}
              onRefreshProfiles={fetchServerProfiles}
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
            <div className="sg-mdl-foot-actions">
              <button
                type="button"
                className="sg-ghost-button"
                onClick={onEditLocalProvider}
              >
                <SettingsGlyph />
                <span>{editAction?.label || "Edit local provider settings"}</span>
              </button>
              {plannedActions.map((action) => (
                <span
                  key={action.id}
                  className="sg-mdl-planned"
                  title={action.reason || "Planned for a later slice."}
                  aria-disabled="true"
                >
                  <Terminal size={13} />
                  {action.label}
                  <span className="sg-mdl-planned-tag">Planned</span>
                </span>
              ))}
            </div>
            <div className="sg-mdl-disclaimer">
              <p>
                Local provider status is still detection-only. Managed Server controls use only
                the companion backend bridge and do not edit the Local provider card above.
              </p>
            </div>
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
  rootSummaries,
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
  const canScan = companionStateKey === COMPANION_REACHABLE && companionScanCapable && !scanning;

  return (
    <section className="sg-mdl-subcard">
      <div className="sg-mdl-subcard-head">
        <div className="sg-mdl-subcard-head-main">
          <div className="sg-mdl-subcard-title">
            <strong>Model Library</strong>
            <span className="sg-mdl-tag">Library discovery only</span>
          </div>
          <p>Approved GGUF folders are configured in the host companion config.</p>
        </div>
        <span className={`sg-mdl-pill ${PILL_TONE[badgeTone]}`}>
          {companionLoading ? <Loader2 size={11} className="sg-spin" /> : <CompanionStateIcon state={companionStateKey} />}
          {companionLoading ? "Checking…" : companionBadgeMeta.label}
        </span>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onScan}
          disabled={!canScan}
          title="Ask the companion to rescan approved folders"
        >
          {scanning ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
          <span>{scanning ? "Scanning…" : "Scan approved folder(s)"}</span>
        </button>
      </div>

      <div className="sg-mdl-metrics">
        <Metric label="Approved roots" value={String(libraryRoots)} />
        <Metric label="Cached models" value={String(libraryCount)} />
        <Metric label="Last scan" value={lastScan} />
        <Metric label="Chosen library model" value={selectionLoading ? "Loading…" : chosenName} />
      </div>

      <p className="sg-mdl-help">{statusCopy}</p>
      {rootSummaries.length > 0 && <RootSummaryList roots={rootSummaries} />}
      {companionStateKey === COMPANION_UNCONFIGURED && <CompanionSetupGuide />}
      {(libraryRequestError || selectionRequestError) && (
        <p className="sg-mdl-notice warn">
          {libraryRequestError || selectionRequestError}
        </p>
      )}
      {(scanMessage || selectionMessage) && (
        <p className="sg-mdl-help dim">{scanMessage || selectionMessage}</p>
      )}

      {savedSelection && (
        <ChosenLibraryModel
          model={savedSelection}
          preview={selectionPreview}
          stale={selectionStale}
          companionStateKey={companionStateKey}
          saving={selectionSaving}
          onClear={onClearSelection}
        />
      )}

      {warnings.length > 0 && (
        <div className="sg-mdl-box warn">
          <span className="sg-mdl-box-title">Scan warnings</span>
          <ul className="sg-mdl-warnlist">
            {warnings.slice(0, 5).map((warning, i) => (
              <li key={`${warning.code || "warning"}-${i}`}>
                <AlertTriangle size={12} />
                <span>
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

      {libraryLoading && !libraryData ? (
        <div className="sg-mdl-infobox row">
          <Loader2 size={14} className="sg-spin" />
          Loading cached library…
        </div>
      ) : libraryModels.length === 0 ? (
        <EmptyLibraryState state={companionStateKey} roots={libraryRoots} requestError={libraryRequestError} />
      ) : (
        <div className="sg-mdl-modelgrid">
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

      {selectedModel && (
        <div className="sg-mdl-foot-actions tight">
          <button
            type="button"
            className="sg-ghost-button"
            onClick={onRememberSelection}
            disabled={selectionSaving || !hasPendingChoice}
            title="Persist this selected library model as app-side metadata"
          >
            {selectionSaving ? <Loader2 size={14} className="sg-spin" /> : <Check size={14} />}
            <span>
              {hasPendingChoice ? "Remember selected model" : "Selected model remembered"}
            </span>
          </button>
          <p className="sg-mdl-foot-note">
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
  profiles,
  profilesLoading,
  profilesRequestError,
  selectedProfile,
  selectedProfileId,
  parameterValues,
  status,
  loading,
  action,
  requestError,
  message,
  onSelectProfile,
  onChangeParameter,
  onResetParameters,
  onRefreshProfiles,
  onRefresh,
  onStart,
  onStop,
  onRestart,
}) {
  const companionAvailable = companionStateKey === COMPANION_REACHABLE;
  const hasSelection = !!selection?.id && !!startPayload;
  const hasRunnableProfile = !!selectedProfile?.runnable;
  const hasProfiles = profiles.length > 0;
  const managedRunning = localModelServerIsManagedRunning(status);
  const state = normalizeLocalModelServerState(status);
  const statusLabel = loading ? "Checking..." : localModelServerStatusLabel(status);
  const statusError = localModelServerErrorMessage(status);
  const busy = !!action;
  const canStart = companionAvailable && hasSelection && hasRunnableProfile && !busy && !companionLoading && !profilesLoading;
  const canStop = companionAvailable && managedRunning && !busy && !companionLoading;
  const canRestart = companionAvailable && hasSelection && hasRunnableProfile && managedRunning && !busy && !companionLoading && !profilesLoading;
  const selectedName = selection?.display_name || selection?.filename || selection?.id || "No selected model";
  const port = startPayload?.parameters?.port ?? SAFE_SERVER_DEFAULTS.port;
  const profileLabel = selectedProfile?.display_name || selectedProfileId || "No profile";
  const profileWarnings = selectedProfile?.warnings || [];
  const parameterEntries = selectedProfile?.parameters
    ? Object.entries(selectedProfile.parameters).filter(([, schema]) => schema && typeof schema === "object")
    : [];

  let disabledCopy = null;
  if (!companionAvailable) disabledCopy = "Companion must be reachable before managed controls are enabled.";
  else if (!hasProfiles) disabledCopy = "No companion launch profiles are configured.";
  else if (!hasRunnableProfile) disabledCopy = "Selected launch profile is unavailable.";
  else if (!hasSelection) disabledCopy = "Choose and remember a library model before starting the managed server.";
  else if (!managedRunning) disabledCopy = "Stop and restart are enabled only for a companion-managed running server.";

  return (
    <section className="sg-mdl-subcard">
      <div className="sg-mdl-subcard-head">
        <div className="sg-mdl-subcard-head-main">
          <div className="sg-mdl-subcard-title">
            <strong>Managed Server</strong>
            {selectedProfile?.test_profile && (
              <span className="sg-mdl-tag warn">
                {SAFE_TEST_PROFILE_ID} validation profile
              </span>
            )}
            {selectedProfile && !selectedProfile.runnable && (
              <span className="sg-mdl-tag error">
                Profile unavailable
              </span>
            )}
          </div>
          <p>Start/stop controls require a configured host companion.</p>
        </div>
        <span className={`sg-mdl-pill ${PILL_TONE[serverTone(status, companionAvailable)]}`}>
          {loading ? <Loader2 size={11} className="sg-spin" /> : <ServerStateIcon state={state} companionAvailable={companionAvailable} />}
          {statusLabel}
        </span>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onRefresh}
          disabled={loading || busy}
          title="Refresh companion-managed server status"
        >
          {loading ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
          <span>Refresh managed status</span>
        </button>
      </div>

      <div className="sg-mdl-metrics">
        <Metric label="State" value={statusLabel} />
        <Metric label="Managed" value={status?.managed === true ? "Yes" : "No"} />
        <Metric label="Model id" value={selection?.id || status?.model_id || "-"} />
        <Metric label="Port" value={String(status?.port || port)} />
      </div>

      <div className="sg-mdl-grid-2 managed">
        <div className="sg-mdl-panel">
          <label className="sg-mdl-panel-label" htmlFor="managed-server-profile">
            Launch profile
          </label>
          <div className="sg-mdl-profile-row">
            <select
              id="managed-server-profile"
              className="sg-mdl-select"
              value={selectedProfileId || ""}
              disabled={!companionAvailable || profilesLoading || busy || profiles.length === 0}
              onChange={(event) => onSelectProfile(event.target.value)}
            >
              {profiles.length === 0 ? (
                <option value="">No profiles configured</option>
              ) : (
                profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.display_name}{profile.runnable ? "" : " (unavailable)"}
                  </option>
                ))
              )}
            </select>
            <button
              type="button"
              className="sg-icon-button"
              onClick={onRefreshProfiles}
              disabled={!companionAvailable || profilesLoading || busy}
              title="Refresh configured launch profiles"
            >
              {profilesLoading ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
            </button>
          </div>
          {selectedProfile?.description && (
            <p className="sg-mdl-help">{selectedProfile.description}</p>
          )}
          {selectedProfile?.runnable_reason && !selectedProfile.runnable && (
            <p className="sg-mdl-notice warn">
              Reason: {selectedProfile.runnable_reason}
            </p>
          )}
          {profilesRequestError && (
            <p className="sg-mdl-notice warn">{profilesRequestError}</p>
          )}
          {!hasProfiles && !profilesLoading && (
            <p className="sg-mdl-help">
              No profiles are configured. Launch profiles come from companion config or preset files.
            </p>
          )}
        </div>

        <div className="sg-mdl-panel">
          <div className="sg-mdl-panel-headrow">
            <span className="sg-mdl-panel-label">Profile parameters</span>
            <button
              type="button"
              className="sg-btn-sm"
              onClick={onResetParameters}
              disabled={!companionAvailable || !selectedProfile || busy}
              title="Restore configured profile defaults"
            >
              <RefreshCw size={13} />
              <span>Use profile defaults</span>
            </button>
          </div>
          {parameterEntries.length === 0 ? (
            <p className="sg-mdl-help dim">
              Companion profile metadata is unavailable.
            </p>
          ) : (
            <div className="sg-mdl-params">
              {parameterEntries.map(([name, schema]) => (
                <ProfileParameterControl
                  key={name}
                  name={name}
                  schema={schema}
                  value={parameterValues[name]}
                  disabled={!companionAvailable || busy || !selectedProfile?.runnable}
                  onChange={onChangeParameter}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="sg-mdl-panel">
        <span className="sg-mdl-panel-label">Start payload preview</span>
        <dl className="sg-mdl-detail-grid">
          <SafeDetail label="Selected model" value={selectedName} />
          <SafeDetail label="Profile" value={profileLabel} />
          {Object.entries(startPayload?.parameters || localModelServerProfileDefaults(selectedProfile)).map(([name, value]) => (
            <SafeDetail key={name} label={name.replaceAll("_", " ")} value={String(value)} />
          ))}
        </dl>
      </div>

      <div className="sg-mdl-foot-actions">
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onStart}
          disabled={!canStart}
          title="Starts companion-managed server only."
        >
          {action === "start" ? <Loader2 size={14} className="sg-spin" /> : <Server size={14} />}
          <span>{action === "start" ? "Starting..." : "Start selected model"}</span>
        </button>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onStop}
          disabled={!canStop}
          title="Stops only the companion-managed server."
        >
          {action === "stop" ? <Loader2 size={14} className="sg-spin" /> : <CircleSlash size={14} />}
          <span>{action === "stop" ? "Stopping..." : "Stop managed server"}</span>
        </button>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onRestart}
          disabled={!canRestart}
          title="Restarts with the saved selected model and safe defaults."
        >
          {action === "restart" ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
          <span>{action === "restart" ? "Restarting..." : "Restart managed server"}</span>
        </button>
      </div>

      <div className="sg-mdl-disclaimer">
        <p>These buttons control only the companion-managed process.</p>
        <p>Starts companion-managed server only.</p>
        <p>Stops only the companion-managed server. Manual servers are not stopped by this button.</p>
        <p>Provider Settings are not changed.</p>
        <p>High GPU layers can fail with out-of-memory errors on large models.</p>
        <p>CPU mode is safer but slower.</p>
        <p>Only configured profile settings are editable here.</p>
        {profileWarnings.map((warning) => (
          <p key={warning}>{warning}</p>
        ))}
      </div>

      {disabledCopy && (
        <p className="sg-mdl-help">{disabledCopy}</p>
      )}
      {(requestError || statusError) && (
        <p className="sg-mdl-notice warn">
          {requestError || statusError}
        </p>
      )}
      {message && <p className="sg-mdl-help dim">{message}</p>}
    </section>
  );
}

function ProfileParameterControl({ name, schema, value, disabled, onChange }) {
  const controlId = `managed-param-${name}`;
  const current = value ?? schema.default;
  return (
    <label className="sg-mdl-param" htmlFor={controlId}>
      <span className="sg-mdl-param-label">{schema.label}</span>
      {schema.type === "integer" && (
        <input
          id={controlId}
          type="number"
          min={schema.min}
          max={schema.max}
          step="1"
          value={current}
          disabled={disabled}
          onChange={(event) => onChange(name, event.target.value)}
          className="sg-mdl-param-input"
        />
      )}
      {schema.type === "boolean" && (
        <span className="sg-mdl-param-check">
          <input
            id={controlId}
            type="checkbox"
            checked={current === true}
            disabled={disabled}
            onChange={(event) => onChange(name, event.target.checked)}
          />
          Enabled
        </span>
      )}
      {schema.type === "enum" && (
        <select
          id={controlId}
          value={current}
          disabled={disabled}
          onChange={(event) => onChange(name, event.target.value)}
          className="sg-mdl-param-input"
        >
          {schema.allowed_values.map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </select>
      )}
      {schema.help && <span className="sg-mdl-param-help">{schema.help}</span>}
    </label>
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
    return "Approved GGUF folders are configured in the host companion config. The web app cannot safely browse your whole PC or pick host folders directly.";
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
  else if (state === COMPANION_UNCONFIGURED) copy = "Configure the companion and scan approved folder(s) to show all GGUF models.";
  else if (state === COMPANION_OFFLINE) copy = "Companion is not reachable; no cached models are available.";
  else if (state === COMPANION_AUTH_FAILED) copy = "Companion auth failed; no cached models are available.";
  else if (roots === 0) copy = "No approved folders are configured on the companion.";
  return (
    <div className="sg-mdl-infobox">
      {copy}
    </div>
  );
}

function RootSummaryList({ roots }) {
  return (
    <div className="sg-mdl-panel">
      <span className="sg-mdl-panel-label">Configured approved roots</span>
      <div className="sg-mdl-roots">
        {roots.map((root) => (
          <span key={root.id} className="sg-mdl-root">
            {root.id}
            <span>
              {root.recursive ? "recursive" : "top level"} · {root.model_count ?? 0} models
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function CompanionSetupGuide() {
  const template = `{
  "approved_roots": [
    {
      "id": "models",
      "path": "/mnt/ai/llm-models",
      "recursive": true
    }
  ],
  "token": "replace-with-local-token",
  "process_runtime_dir": "/tmp/lmm-companion-runtime"
}`;
  return (
    <div className="sg-mdl-box warn">
      <strong className="sg-mdl-box-title">Companion setup required</strong>
      <ul className="sg-mdl-guide-list">
        <li>Approved GGUF folders are configured in the host companion config.</li>
        <li>The web app cannot safely browse your whole PC or pick host folders directly.</li>
        <li>Configure approved_roots in the companion config, then restart the companion and click Scan.</li>
        <li>Manual server mode still works without the companion.</li>
      </ul>
      <span className="sg-mdl-panel-label">Example/edit-me config template</span>
      <div className="sg-mdl-code template">
        <pre>
          <code>{template}</code>
        </pre>
      </div>
    </div>
  );
}

function ChosenLibraryModel({ model, preview, stale, companionStateKey, saving, onClear }) {
  const name = model.display_name || model.filename || model.relative_path || model.id;
  const unconfigured = companionStateKey === COMPANION_UNCONFIGURED;
  return (
    <div className="sg-mdl-box ok">
      <div className="sg-mdl-box-head">
        <div className="sg-mdl-box-head-main">
          <div className="sg-mdl-box-name-row">
            <strong>{name}</strong>
            <span className="sg-mdl-tag ok">Chosen library model</span>
            {unconfigured && (
              <span className="sg-mdl-tag warn">Saved selected model</span>
            )}
            {stale && !unconfigured && (
              <span className="sg-mdl-tag warn">Saved but not in current library</span>
            )}
          </div>
          <dl className="sg-mdl-detail-grid">
            <SafeDetail label="File" value={model.filename || "—"} />
            <SafeDetail label="Path" value={model.relative_path || "—"} />
            <SafeDetail label="Root" value={model.root_id || "—"} />
            <SafeDetail label="Size" value={formatModelSize(model.size_bytes)} />
            <SafeDetail label="Modified" value={formatModelModifiedAt(model.modified_at)} />
            <SafeDetail label="Selected" value={formatModelModifiedAt(model.selected_at)} />
          </dl>
          {unconfigured ? (
            <p className="sg-mdl-box-note warn">
              This is a saved selected model from a previous validation or session.
              It is not currently confirmed by a live library scan because the companion is unconfigured.
              Configure the companion and scan approved folder(s) to show all GGUF models.
            </p>
          ) : stale ? (
            <p className="sg-mdl-box-note warn">
              Saved but not in current scan. The file may have moved, been renamed,
              or the approved root may need rescanning.
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className="sg-ghost-button"
          onClick={onClear}
          disabled={saving}
          title="Clear the saved library model selection"
        >
          {saving ? <Loader2 size={14} className="sg-spin" /> : <CircleSlash size={14} />}
          <span>Clear selection</span>
        </button>
      </div>
      {preview && <FutureLaunchPreview preview={preview} />}
      <p className="sg-mdl-box-note dim">
        This selection is used by Managed Server start/restart with safe typed defaults.
        Provider Settings were not changed.
      </p>
    </div>
  );
}

function FutureLaunchPreview({ preview }) {
  return (
    <div className="sg-mdl-panel">
      <span className="sg-mdl-panel-label">Saved selection preview</span>
      <dl className="sg-mdl-detail-grid">
        <SafeDetail label="Model id" value={preview.model_id || "—"} />
        <SafeDetail label="File" value={preview.filename || "—"} />
        <SafeDetail label="Path" value={preview.relative_path || "companion resolves id"} />
        <SafeDetail label="Root" value={preview.root_id || "—"} />
        <SafeDetail label="Profile" value={preview.profile || "gpu_default"} />
        <SafeDetail label="Resolver" value={preview.resolver || "companion_model_id"} />
      </dl>
      <p className="sg-mdl-help dim">
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
      className={`sg-mdl-modelbtn ${selected ? "is-selected" : ""}`}
    >
      <div className="sg-mdl-modelbtn-inner">
        <span
          className={`sg-mdl-modelbtn-radio ${selected ? "is-selected" : ""}`}
          aria-hidden="true"
        >
          {selected ? <Check size={12} /> : null}
        </span>
        <div className="sg-mdl-modelbtn-main">
          <div className="sg-mdl-modelbtn-title">
            <strong>{name}</strong>
            {selected && (
              <span className="sg-mdl-tag ok">Selected here</span>
            )}
            {persisted && (
              <span className="sg-mdl-tag accent">Remembered</span>
            )}
          </div>
          <dl className="sg-mdl-detail-grid">
            <SafeDetail label="File" value={model.filename || "—"} />
            <SafeDetail label="Path" value={model.relative_path || "—"} />
            <SafeDetail label="Root" value={model.root_id || "—"} />
            <SafeDetail label="Size" value={formatModelSize(model.size_bytes)} />
            <SafeDetail label="Modified" value={formatModelModifiedAt(model.modified_at)} />
            <SafeDetail label="Compatible" value={model.server_compatible === true ? "Yes" : "Unknown"} />
          </dl>
          {chips.length > 0 && (
            <div className="sg-mdl-modelbtn-chips">
              {chips.map((chip) => (
                <span key={chip} className="sg-mdl-chip">
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
    <div className="sg-mdl-detail">
      <dt>{label}: </dt>
      <dd>{value}</dd>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="sg-mdl-metric">
      <span className="sg-mdl-metric-label">{label}</span>
      <span className="sg-mdl-metric-value" title={value}>
        {value}
      </span>
    </div>
  );
}

function Troubleshooting({ state, host, inDocker, notes }) {
  const isDockerHost = host === "host.docker.internal";
  return (
    <div className="sg-mdl-trouble">
      <AlertTriangle size={14} />
      <div className="sg-mdl-trouble-body">
        {state === STATE_NOT_CONFIGURED ? (
          <>
            <strong>No local server configured</strong>
            <p>
              Set the base URL on the Local provider card above (an OpenAI-compatible
              endpoint ending in <code>/v1</code>), then Refresh.
            </p>
          </>
        ) : (
          <>
            <strong>Local server not reachable</strong>
            <ol className="sg-mdl-steps">
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
          <ul className="sg-mdl-bullets">
            {notes.map((note, i) => (
              <li key={i}>
                <span className="sg-mdl-dot">•</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        )}
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
    <div className="sg-mdl-helper-body">
      <p className="sg-mdl-helper-intro">
        Run this in a terminal <strong>on your host machine</strong>.
        The app never runs it for you — copy it, edit the model path, run it, then click
        Refresh status.
      </p>

      {/* Profile picker (only when more than one whitelisted profile exists) */}
      {profiles.length > 1 && (
        <div className="sg-mdl-helper-profiles">
          {profiles.map((p) => {
            const active = p.id === activeProfile.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelectProfile(p.id)}
                aria-pressed={active}
                className={`sg-mdl-helper-profile ${active ? "active" : ""}`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      )}
      {activeProfile.description && (
        <p className="sg-mdl-helper-desc">{activeProfile.description}</p>
      )}

      {/* The command itself — selectable code block + copy button */}
      <div className="sg-mdl-code">
        <div className="sg-mdl-code-head">
          <span className="sg-mdl-code-head-label">
            <Terminal size={12} /> Start command
          </span>
          <button
            type="button"
            onClick={onCopy}
            className={`sg-mdl-copy ${copied ? "copied" : failed ? "failed" : ""}`}
            title="Copy the command to your clipboard (does not run it)"
          >
            <CopyIcon size={12} />
            {copyButtonLabel(copyState)}
          </button>
        </div>
        <pre>
          <code>{activeProfile.command}</code>
        </pre>
      </div>

      {failed && (
        <p className="sg-mdl-notice warn">
          Couldn’t access the clipboard. Select the command text above and copy it manually
          (Ctrl/Cmd+C).
        </p>
      )}

      {/* Static safety/usage warnings from the backend profile */}
      {activeProfile.warnings.length > 0 && (
        <ul className="sg-mdl-bullets">
          {activeProfile.warnings.map((w, i) => (
            <li key={i}>
              <span className="sg-mdl-dot">•</span>
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Top-level helper notes (e.g. the Docker base-URL hint) */}
      {notes.length > 0 && (
        <ul className="sg-mdl-bullets">
          {notes.map((n, i) => (
            <li key={i}>
              <span className="sg-mdl-dot">•</span>
              <span>{n}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  const heading = (
    <span className="sg-mdl-helper-head">
      <Terminal size={14} />
      How to start llama-server (manual)
    </span>
  );

  // Prominent: expanded inline block (offline / not-configured). Secondary: a
  // collapsed <details> so a reachable server keeps it tucked away.
  if (prominent) {
    return (
      <div className="sg-mdl-helper">
        {heading}
        {body}
      </div>
    );
  }
  return (
    <details className="sg-mdl-helper">
      <summary>{heading}</summary>
      {body}
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
