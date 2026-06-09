import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Check,
  ChevronRight,
  CircleSlash,
  Eraser,
  FileText,
  Loader2,
  MessageSquareText,
  Plus,
  RefreshCw,
  Search,
  Send,
  Server,
  Sparkles,
  Terminal,
  Trash2,
  WifiOff,
} from "lucide-react";
import {
  checkLocalModelStatus,
  clearAskSessionHistory,
  createAskSession,
  deleteAskSession,
  getAskJobContext,
  getAskJobs,
  getAskSession,
  getAskSessions,
  getLocalModelCommandProfile,
  getLocalModelStatus,
  prepareAskJobContext,
  sendAskSessionMessage,
} from "../api/client";
import {
  attachmentRows,
  answerBlocks,
  chatReadiness,
  citationWarningText,
  citationSummary,
  formatCount,
  formatDate,
  guideSourceSummary,
  normalizeAskMessageResponse,
  normalizeAskSessionList,
  normalizeAskSessionPayload,
  nextSessionAfterDelete,
  pageSelectionRows,
  prepareBadge,
  readinessReasons,
  readinessState,
  retrievedChunkRows,
  safeDisplayText,
  safeInputText,
  safeText,
  sessionMetaLabel,
  sessionShortLabel,
  sessionStatusLabel,
} from "../askGuide";
import {
  COPY_COPIED,
  COPY_FAILED,
  COPY_IDLE,
  commandAvailable,
  commandNotes,
  commandProfiles,
  profileById,
} from "../localModelCommand";
import {
  STATE_NOT_CONFIGURED,
  STATE_OFFLINE,
  STATE_REACHABLE,
  localServerState,
  modelChips,
  statusErrorMessage,
  statusLatencyMs,
  statusModelCount,
} from "../localModelStatus";
import { CommandHelper } from "./LocalModelsPanel";

// Map the CSS-agnostic tone keys to the Ask-Guide pill modifier classes
// (design-system.css → "Ask Guide — Slice 7"). Kept as a lookup so every pill
// derives its colour the same way.
const STATUS_TONE = {
  ready: "is-ready",
  neutral: "is-neutral",
  warning: "is-warning",
  error: "is-error",
};

const LOCAL_LABEL = {
  [STATE_REACHABLE]: "Reachable",
  [STATE_OFFLINE]: "Offline",
  [STATE_NOT_CONFIGURED]: "Not configured",
};

export default function AskGuideWorkspace() {
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsError, setJobsError] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [context, setContext] = useState(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState(null);
  const [prepareResult, setPrepareResult] = useState(null);
  const [prepareLoading, setPrepareLoading] = useState(false);
  const [prepareError, setPrepareError] = useState(null);
  const [localStatus, setLocalStatus] = useState(null);
  const [localLoading, setLocalLoading] = useState(true);
  const [localError, setLocalError] = useState(null);
  const [commandData, setCommandData] = useState(null);
  const [selectedProfileId, setSelectedProfileId] = useState(null);
  const [copyState, setCopyState] = useState(COPY_IDLE);
  const [session, setSession] = useState(null);
  const [sessionSummaries, setSessionSummaries] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState(null);
  const [sessionAction, setSessionAction] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draftMessage, setDraftMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState(null);
  const [lastRetrievedChunks, setLastRetrievedChunks] = useState([]);
  const [lastLocalModel, setLastLocalModel] = useState(null);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) || null,
    [jobs, selectedJobId]
  );

  const loadJobs = useCallback(() => {
    setJobsLoading(true);
    setJobsError(null);
    getAskJobs({ limit: 100 })
      .then((data) => {
        const list = Array.isArray(data.jobs) ? data.jobs : [];
        setJobs(list);
        setSelectedJobId((current) => (current && list.some((job) => job.id === current) ? current : list[0]?.id || null));
      })
      .catch((err) => setJobsError(err?.message || "Ask guides are unavailable."))
      .finally(() => setJobsLoading(false));
  }, []);

  const loadLocalStatus = useCallback((probe = false) => {
    setLocalLoading(true);
    setLocalError(null);
    const call = probe ? checkLocalModelStatus : getLocalModelStatus;
    call()
      .then((data) => setLocalStatus(data))
      .catch((err) => setLocalError(err?.message || "Local model status unavailable."))
      .finally(() => setLocalLoading(false));
  }, []);

  const loadSessions = useCallback((jobId = selectedJobId) => {
    if (!jobId) {
      setSessionSummaries([]);
      setSessionsLoading(false);
      setSessionsError(null);
      return Promise.resolve([]);
    }
    setSessionsLoading(true);
    setSessionsError(null);
    return getAskSessions(jobId)
      .then((data) => {
        const list = normalizeAskSessionList(data);
        setSessionSummaries(list);
        return list;
      })
      .catch((err) => {
        setSessionsError(err?.message || "Chat sessions unavailable.");
        setSessionSummaries([]);
        return [];
      })
      .finally(() => setSessionsLoading(false));
  }, [selectedJobId]);

  useEffect(() => {
    loadJobs();
    loadLocalStatus();
  }, [loadJobs, loadLocalStatus]);

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

  useEffect(() => {
    if (!selectedJobId) {
      setContext(null);
      setPrepareResult(null);
      setPrepareError(null);
      setSession(null);
      setSessionSummaries([]);
      setSessionsError(null);
      setSessionsLoading(false);
      setSessionAction(null);
      setMessages([]);
      setDraftMessage("");
      setSending(false);
      setChatError(null);
      setLastRetrievedChunks([]);
      setLastLocalModel(null);
      return;
    }
    let cancelled = false;
    setContextLoading(true);
    setContextError(null);
    setPrepareResult(null);
    setPrepareError(null);
    setSession(null);
    setSessionSummaries([]);
    setSessionsError(null);
    setSessionsLoading(false);
    setSessionAction(null);
    setMessages([]);
    setDraftMessage("");
    setSending(false);
    setChatError(null);
    setLastRetrievedChunks([]);
    setLastLocalModel(null);
    getAskJobContext(selectedJobId)
      .then((data) => {
        if (!cancelled) setContext(data);
      })
      .catch((err) => {
        if (!cancelled) setContextError(err?.message || "Context inventory unavailable.");
      })
      .finally(() => {
        if (!cancelled) setContextLoading(false);
      });
    loadSessions(selectedJobId);
    return () => {
      cancelled = true;
    };
  }, [loadSessions, selectedJobId]);

  const onPrepare = useCallback(() => {
    if (!selectedJobId) return;
    setPrepareLoading(true);
    setPrepareError(null);
    prepareAskJobContext(selectedJobId)
      .then((data) => setPrepareResult(data))
      .catch((err) => setPrepareError(err?.message || "Context preparation failed."))
      .finally(() => setPrepareLoading(false));
  }, [selectedJobId]);

  const loadSessionById = useCallback(async (sessionId) => {
    if (!sessionId) return null;
    setSessionAction("load");
    setChatError(null);
    try {
      const loaded = await getAskSession(sessionId);
      const normalized = normalizeAskSessionPayload(loaded);
      if (!normalized.session?.sessionId) throw new Error("Session loading failed.");
      setSession(normalized.session);
      setMessages(normalized.history);
      setDraftMessage("");
      setLastRetrievedChunks([]);
      setLastLocalModel(null);
      return normalized.session;
    } catch (err) {
      setChatError({ category: "ask_error", message: safeDisplayText(err?.message || "", "Session loading failed.") });
      return null;
    } finally {
      setSessionAction(null);
    }
  }, []);

  const onNewSession = useCallback(async () => {
    if (!selectedJobId) return;
    setSessionAction("new");
    setChatError(null);
    try {
      const created = await createAskSession(selectedJobId, { title: selectedJob?.title || null });
      const createdSessionId = created?.session?.session_id;
      if (!createdSessionId) throw new Error("Session creation failed.");
      const active = await loadSessionById(createdSessionId);
      if (active) await loadSessions(selectedJobId);
    } catch (err) {
      setChatError({ category: "ask_error", message: safeDisplayText(err?.message || "", "Session creation failed.") });
    } finally {
      setSessionAction(null);
    }
  }, [loadSessionById, loadSessions, selectedJob?.title, selectedJobId]);

  const onClearSession = useCallback(async () => {
    if (!session?.sessionId) return;
    if (!window.confirm("Clear this chat history? The session will stay available.")) return;
    setSessionAction("clear");
    setChatError(null);
    try {
      const cleared = await clearAskSessionHistory(session.sessionId);
      const normalized = normalizeAskSessionPayload(cleared);
      setSession((current) => normalized.session || current);
      setMessages([]);
      setDraftMessage("");
      setLastRetrievedChunks([]);
      setLastLocalModel(null);
      await loadSessions(selectedJobId);
    } catch (err) {
      setChatError({ category: "ask_error", message: safeDisplayText(err?.message || "", "Clear chat failed.") });
    } finally {
      setSessionAction(null);
    }
  }, [loadSessions, selectedJobId, session?.sessionId]);

  const onDeleteSession = useCallback(async () => {
    if (!session?.sessionId) return;
    if (!window.confirm("Delete this chat session? This will not delete the guide or prepared context.")) return;
    const deletedId = session.sessionId;
    setSessionAction("delete");
    setChatError(null);
    try {
      await deleteAskSession(deletedId);
      const next = nextSessionAfterDelete(sessionSummaries, deletedId);
      const updated = await loadSessions(selectedJobId);
      const nextFromUpdated = nextSessionAfterDelete(updated.length ? updated : sessionSummaries, deletedId);
      const target = nextFromUpdated || next;
      if (target?.sessionId) {
        await loadSessionById(target.sessionId);
      } else {
        setSession(null);
        setMessages([]);
        setDraftMessage("");
        setLastRetrievedChunks([]);
        setLastLocalModel(null);
      }
    } catch (err) {
      setChatError({ category: "ask_error", message: safeDisplayText(err?.message || "", "Delete session failed.") });
    } finally {
      setSessionAction(null);
    }
  }, [loadSessionById, loadSessions, selectedJobId, session?.sessionId, sessionSummaries]);

  const ensureSession = useCallback(async () => {
    if (session?.sessionId) return session;
    if (!selectedJobId) throw new Error("Select a generated guide first.");
    const created = await createAskSession(selectedJobId, { title: selectedJob?.title || null });
    const createdSessionId = created?.session?.session_id;
    if (!createdSessionId) throw new Error("Session creation failed.");
    const loaded = await getAskSession(createdSessionId);
    const normalized = normalizeAskSessionPayload(loaded);
    if (!normalized.session?.sessionId) throw new Error("Session loading failed.");
    setSession(normalized.session);
    setMessages(normalized.history);
    loadSessions(selectedJobId);
    return normalized.session;
  }, [loadSessions, selectedJobId, selectedJob?.title, session]);

  const onSendMessage = useCallback(async () => {
    const message = safeDisplayText(draftMessage);
    if (!message || sending) return;
    setSending(true);
    setChatError(null);
    setLastRetrievedChunks([]);
    try {
      const activeSession = await ensureSession();
      const response = await sendAskSessionMessage(activeSession.sessionId, message);
      const normalized = normalizeAskMessageResponse(response, message, `${activeSession.sessionId}-${messages.length}`);
      setLastRetrievedChunks(normalized.retrievedChunks);
      setLastLocalModel(normalized.localModel);
      if (normalized.status === "answered") {
        setMessages((current) => [...current, ...normalized.messages]);
        setDraftMessage("");
        loadSessions(selectedJobId);
      } else {
        setChatError({
          category: normalized.error?.category || normalized.status || "ask_error",
          message: normalized.error?.message || "Ask message failed.",
        });
        if (normalized.status === "local_offline" || normalized.error?.category === "local_offline") {
          loadLocalStatus(true);
        }
      }
    } catch (err) {
      const messageText = safeDisplayText(err?.message || "", "Ask message failed.");
      const category =
        /not.?prepared|context/i.test(messageText)
          ? "not_prepared"
          : /offline|local/i.test(messageText)
            ? "local_offline"
            : "ask_error";
      setChatError({ category, message: messageText });
      if (category === "local_offline") loadLocalStatus(true);
    } finally {
      setSending(false);
    }
  }, [draftMessage, ensureSession, loadLocalStatus, loadSessions, messages.length, selectedJobId, sending]);

  const activeProfile = profileById(commandData, selectedProfileId);
  const profiles = commandProfiles(commandData);
  const helperNotes = commandNotes(commandData);
  const canCopy = commandAvailable(activeProfile);
  const localState = localServerState(localStatus);
  const localReachable = localState === STATE_REACHABLE;
  const readyState = readinessState(context);
  const prep = prepareBadge(prepareResult, prepareLoading, prepareError);
  const prepReady = ["hit", "built", "rebuilt", "ready"].includes(prep.state);
  const chat = chatReadiness({
    hasJob: Boolean(selectedJob),
    contextLoading,
    contextReady: readyState === "ready",
    prepReady,
    localLoading,
    localReachable,
    sending,
  });

  const onCopyCommand = useCallback(async () => {
    if (!activeProfile?.command) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(activeProfile.command);
        setCopyState(COPY_COPIED);
      } else {
        setCopyState(COPY_FAILED);
      }
    } catch {
      setCopyState(COPY_FAILED);
    }
    setTimeout(() => setCopyState(COPY_IDLE), 2600);
  }, [activeProfile]);

  return (
    <div className="sg-ask">
      <div className="sg-ask-head">
        <div className="sg-ask-head-titles">
          <h1>Ask Your Guide</h1>
          <p>Select a generated guide and prepare its context.</p>
        </div>
        <div className="sg-ask-head-actions">
          <Pill tone={localReachable ? "ready" : "warning"}>
            {localLoading ? <Loader2 size={12} className="sg-spin" /> : localReachable ? <Check size={12} /> : <WifiOff size={12} />}
            {localLoading ? "Checking local model" : `Local model: ${LOCAL_LABEL[localState] || "Status unavailable"}`}
          </Pill>
          <button type="button" className="sg-ghost-button" onClick={loadJobs} disabled={jobsLoading}>
            {jobsLoading ? <Loader2 size={15} className="sg-spin" /> : <RefreshCw size={15} />}
            <span>Refresh guides</span>
          </button>
        </div>
      </div>

      <div className="sg-ask-body">
        <GuidePicker
          jobs={jobs}
          loading={jobsLoading}
          error={jobsError}
          selectedJobId={selectedJobId}
          onSelect={setSelectedJobId}
        />

        <main className="sg-ask-chat-col">
          <ChatReadinessPanel
            job={selectedJob}
            context={context}
            contextLoading={contextLoading}
            contextError={contextError}
            readyState={readyState}
            prepareResult={prepareResult}
            prepareLoading={prepareLoading}
            prepareError={prepareError}
            prep={prep}
            prepReady={prepReady}
            localReachable={localReachable}
            localState={localState}
            onPrepare={onPrepare}
            chat={chat}
            messages={messages}
            session={session}
            sessionAction={sessionAction}
            onNewSession={onNewSession}
            onClearSession={onClearSession}
            onDeleteSession={onDeleteSession}
            draftMessage={draftMessage}
            setDraftMessage={setDraftMessage}
            sending={sending}
            chatError={chatError}
            onSendMessage={onSendMessage}
          />
        </main>

        <aside className="sg-ask-rail">
          <ContextRail
            job={selectedJob}
            context={context}
            contextLoading={contextLoading}
            contextError={contextError}
            prepareResult={prepareResult}
            prepareError={prepareError}
            prep={prep}
            localStatus={localStatus}
            localError={localError}
            localLoading={localLoading}
            localState={localState}
            reloadLocal={loadLocalStatus}
            lastRetrievedChunks={lastRetrievedChunks}
            lastLocalModel={lastLocalModel}
            sessions={sessionSummaries}
            sessionsLoading={sessionsLoading}
            sessionsError={sessionsError}
            sessionAction={sessionAction}
            activeSessionId={session?.sessionId || null}
            onSelectSession={(sessionId) => {
              if (sessionId && sessionId !== session?.sessionId) loadSessionById(sessionId);
            }}
            onNewSession={onNewSession}
            onRefreshSessions={() => loadSessions(selectedJobId)}
            commandProps={
              canCopy
                ? {
                    profiles,
                    activeProfile,
                    selectedProfileId,
                    onSelectProfile: (id) => {
                      setSelectedProfileId(id);
                      setCopyState(COPY_IDLE);
                    },
                    copyState,
                    onCopy: onCopyCommand,
                    notes: helperNotes,
                    prominent: localState === STATE_OFFLINE || localState === STATE_NOT_CONFIGURED,
                  }
                : null
            }
          />
        </aside>
      </div>
    </div>
  );
}

function GuidePicker({ jobs, loading, error, selectedJobId, onSelect }) {
  return (
    <aside className="sg-ask-picker">
      <div className="sg-ask-picker-head">
        <div>
          <h2>Generated guides</h2>
          <p>{loading ? "Loading…" : `${jobs.length} eligible`}</p>
        </div>
        <Search size={16} />
      </div>

      {error && <Notice tone="error" title="Guide list unavailable" text={error} />}
      {!loading && !error && jobs.length === 0 && (
        <div className="sg-ask-noguides">
          <BookOpen size={20} />
          <strong>No generated guides yet</strong>
          <span>Generate a guide in Builder first, then return here to prepare it for Ask.</span>
        </div>
      )}

      <div className="sg-ask-guide-list">
        {loading
          ? Array.from({ length: 4 }, (_, i) => <SkeletonGuide key={i} />)
          : jobs.map((job) => {
              const active = job.id === selectedJobId;
              return (
                <button
                  key={job.id}
                  type="button"
                  onClick={() => onSelect(job.id)}
                  className={`sg-ask-guide${active ? " active" : ""}`}
                >
                  <div className="sg-ask-guide-top">
                    <FileText size={15} className="sg-ask-guide-glyph" />
                    <div className="sg-ask-guide-main">
                      <strong className="sg-ask-guide-title">{safeText(job.title, "Untitled guide")}</strong>
                      <span className="sg-ask-guide-date">{formatDate(job.updated_at || job.created_at)}</span>
                    </div>
                    {active && <ChevronRight size={15} className="sg-ask-guide-chevron" />}
                  </div>
                  <div className="sg-ask-chips">
                    <MiniChip>{safeText(job.status, "status unavailable")}</MiniChip>
                    {job.provider && <MiniChip>{job.provider}</MiniChip>}
                    {job.model && <MiniChip>{job.model}</MiniChip>}
                    {job.generator_preset && <MiniChip>{job.generator_preset}</MiniChip>}
                  </div>
                  <p className="sg-ask-guide-summary">{guideSourceSummary(job)}</p>
                </button>
              );
            })}
      </div>
    </aside>
  );
}

function ChatReadinessPanel({
  job,
  context,
  contextLoading,
  contextError,
  readyState,
  prepareResult,
  prepareLoading,
  prepareError,
  prep,
  prepReady,
  localReachable,
  localState,
  onPrepare,
  chat,
  messages,
  session,
  sessionAction,
  onNewSession,
  onClearSession,
  onDeleteSession,
  draftMessage,
  setDraftMessage,
  sending,
  chatError,
  onSendMessage,
}) {
  const reasons = readinessReasons(context);
  const title = safeText(context?.title || job?.title, "Select a guide");
  const canSend = chat.enabled && draftMessage.trim().length > 0;
  return (
    <div className="sg-ask-center">
      <section className="sg-ask-readiness">
        <div className="sg-ask-readiness-head">
          <span className="sg-ask-readiness-icon">
            <MessageSquareText size={20} />
          </span>
          <div className="sg-ask-readiness-main">
            <div className="sg-ask-readiness-titlerow">
              <h2 className="sg-ask-readiness-title">{title}</h2>
              <Pill tone={prep.tone}>{prep.label}</Pill>
            </div>
            <p className="sg-ask-readiness-desc">
              Prepare this guide once, then ask grounded questions through the local model. Sessions are created lazily on first send.
            </p>
            {session?.sessionId && (
              <div className="sg-ask-session-line">
                <p>{sessionStatusLabel(session)}</p>
                <button type="button" className="sg-btn-sm" onClick={onClearSession} disabled={sessionAction !== null || messages.length === 0}>
                  <Eraser size={13} />
                  <span>Clear chat</span>
                </button>
                <button type="button" className="sg-btn-sm danger" onClick={onDeleteSession} disabled={sessionAction !== null}>
                  <Trash2 size={13} />
                  <span>Delete</span>
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="sg-ask-metric-grid cols-3">
          <Metric label="Guide chars" value={contextLoading ? "…" : formatCount(context?.guide?.char_count)} />
          <Metric label="Source chars" value={contextLoading ? "…" : formatCount(context?.source?.char_count)} />
          <Metric label="Chunks" value={prepareResult?.ready ? formatCount(prepareResult.total_chunk_count) : "Not prepared"} />
        </div>

        {contextError && <Notice tone="error" title="Context unavailable" text={contextError} />}
        {prepareError && <Notice tone="error" title="Prepare failed" text={prepareError} />}
        {!contextError && readyState !== "ready" && !contextLoading && job && (
          <Notice
            tone="warning"
            title="Selected guide is not ready"
            text={reasons.length ? reasons.join(" ") : "The selected guide is missing required context."}
          />
        )}
        {!localReachable && (
          <Notice
            tone="warning"
            title="Local model offline"
            text={
              localState === STATE_NOT_CONFIGURED
                ? "Configure the Local provider and start a local OpenAI-compatible server before chat is enabled."
                : "Start your local model server and refresh status before chat is enabled."
            }
          />
        )}

        <div className="sg-ask-prep-row">
          <button
            type="button"
            onClick={onPrepare}
            disabled={!job || contextLoading || prepareLoading || readyState !== "ready"}
            className="sg-cta sg-press-btn"
            title="Build or reuse the safe chunk index for this guide"
          >
            {prepareLoading ? <Loader2 size={15} className="sg-spin" /> : prepReady ? <Check size={15} /> : <Sparkles size={15} />}
            {prepareLoading ? "Preparing…" : prepReady ? "Prepare again" : "Prepare context"}
          </button>
          <span className="sg-ask-prep-hint">
            {prepReady ? "Context index is ready for local chat." : "Builds guide/source chunks without exposing text."}
          </span>
          <button
            type="button"
            onClick={onNewSession}
            disabled={!job || sessionAction !== null}
            className="sg-btn-sm"
          >
            {sessionAction === "new" ? <Loader2 size={13} className="sg-spin" /> : <Plus size={13} />}
            <span>New chat</span>
          </button>
        </div>
      </section>

      <section className="sg-ask-chat">
        <div className="sg-ask-chat-scroll">
          {messages.length === 0 ? (
            <EmptyChatState chat={chat} prepReady={prepReady} localReachable={localReachable} />
          ) : (
            <div className="sg-ask-msgs">
              {messages.map((message, index) => (
                <ChatBubble key={message.id || `${message.role}-${index}`} message={message} />
              ))}
            </div>
          )}
          {sending && (
            <div className="sg-ask-sending">
              <Loader2 size={14} className="sg-spin" />
              Asking the local model…
            </div>
          )}
          {chatError && (
            <Notice
              tone={chatError.category === "local_offline" || chatError.category === "not_prepared" ? "warning" : "error"}
              title={chatError.category === "local_offline" ? "Local model offline" : chatError.category === "not_prepared" ? "Prepare context first" : "Message failed"}
              text={chatError.message}
            />
          )}
          {chatError?.category === "not_prepared" && (
            <button
              type="button"
              onClick={onPrepare}
              disabled={!job || contextLoading || prepareLoading || readyState !== "ready"}
              className="sg-cta sg-press-btn sg-ask-prep-inline"
            >
              {prepareLoading ? <Loader2 size={15} className="sg-spin" /> : <Sparkles size={15} />}
              {prepareLoading ? "Preparing…" : "Prepare context"}
            </button>
          )}
        </div>
        <form
          className="sg-ask-composer"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSend) onSendMessage();
          }}
        >
          <div className={`sg-ask-input-wrap${chat.enabled ? "" : " disabled"}`}>
            <textarea
              disabled={!chat.enabled}
              value={draftMessage}
              onChange={(event) => setDraftMessage(safeInputText(event.target.value))}
              rows={1}
              className="sg-ask-textarea"
              placeholder={chat.enabled ? "Ask a question about this guide…" : chat.label}
            />
            <button
              type="submit"
              disabled={!canSend}
              className="sg-ask-send"
              title={chat.enabled ? "Send message" : chat.label}
            >
              {sending ? <Loader2 size={15} className="sg-spin" /> : <Send size={15} />}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function EmptyChatState({ chat, prepReady, localReachable }) {
  const title =
    chat.state === "no_guide"
      ? "Select a guide"
      : !prepReady
        ? "Prepare context first"
        : !localReachable
          ? "Local model offline"
          : "Ready to ask";
  const text =
    chat.state === "no_guide"
      ? "Choose an eligible generated guide from the list."
      : !prepReady
        ? "Build the guide/source chunk index before sending the first message."
        : !localReachable
          ? "Start the local OpenAI-compatible server, then refresh local status."
          : "Ask a focused question. Answers and citations come from the backend response only.";
  return (
    <div className="sg-ask-empty-chat">
      <CircleSlash size={18} />
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  );
}

function ChatBubble({ message }) {
  const assistant = message.role === "assistant";
  return (
    <article className={`sg-ask-bubble-row${assistant ? " assistant" : " user"}`}>
      <div className={`sg-ask-bubble${assistant ? " assistant" : " user"}`}>
        <div className="sg-ask-bubble-role">{assistant ? "Ask Your Guide" : "You"}</div>
        {assistant ? <AnswerText content={message.content} /> : <p className="sg-ask-user-text">{message.content}</p>}
        {assistant && citationWarningText(message) && (
          <p className="sg-ask-cite-warn">{citationWarningText(message)}</p>
        )}
        {assistant && message.citations?.length > 0 && (
          <div className="sg-ask-sources">
            <div className="sg-ask-sources-head">
              <Check size={12} />
              Sources used
            </div>
            <div className="sg-ask-chips">
              {message.citations.map((label) => (
                <MiniChip key={label}>{label}</MiniChip>
              ))}
            </div>
          </div>
        )}
        {assistant && message.retrievedChunks?.length > 0 && (
          <details className="sg-ask-retrieved">
            <summary>Retrieved chunk metadata ({formatCount(message.retrievedChunks.length)})</summary>
            <div className="sg-ask-retrieved-body">
              <RetrievedChunkList rows={message.retrievedChunks} compact />
            </div>
          </details>
        )}
      </div>
    </article>
  );
}

function AnswerText({ content }) {
  const blocks = answerBlocks(content);
  if (blocks.length === 0) return <p className="sg-ask-answer-empty">No answer text.</p>;
  return (
    <div className="sg-ask-answer">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return (
            <h3 key={index}>
              <InlineSegments segments={block.segments} />
            </h3>
          );
        }
        if (block.type === "list") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <InlineSegments segments={item} />
                </li>
              ))}
            </ol>
          );
        }
        if (block.type === "pre") {
          return (
            <pre key={index} className="sg-ask-code">
              {block.text}
            </pre>
          );
        }
        if (block.type === "math") {
          return (
            <div key={index} className="sg-ask-math">
              <pre>{block.text}</pre>
            </div>
          );
        }
        return (
          <p key={index}>
            <InlineSegments segments={block.segments} />
          </p>
        );
      })}
    </div>
  );
}

function InlineSegments({ segments }) {
  return (
    <>
      {segments.map((segment, index) =>
        segment.type === "strong" ? (
          <strong key={index}>{segment.text}</strong>
        ) : segment.type === "math" ? (
          <code key={index} className="sg-ask-imath">
            {segment.text}
          </code>
        ) : (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        )
      )}
    </>
  );
}

function RetrievedChunkList({ rows, compact = false }) {
  const safeRows = retrievedChunkRows(rows);
  if (safeRows.length === 0) {
    return <p className="sg-ask-muted">No retrieved citation metadata.</p>;
  }
  return (
    <div className="sg-ask-chunk-list">
      {safeRows.map((row, index) => (
        <div key={`${row.label}-${row.chunkId || index}`} className={`sg-ask-chunk${compact ? " compact" : ""}`}>
          <div className="sg-ask-chunk-top">
            <span className="sg-ask-chunk-label">{row.label}</span>
            {row.score !== null && <span className="sg-ask-chunk-score">score {formatScore(row.score)}</span>}
          </div>
          <div className="sg-ask-chunk-meta">
            {row.sourceType && <SourceMeta label="Type" value={row.sourceType} />}
            {row.page !== null && <SourceMeta label="Page" value={formatCount(row.page)} />}
            {row.approxTokens !== null && <SourceMeta label="Tokens" value={`~${formatCount(row.approxTokens)}`} />}
          </div>
        </div>
      ))}
    </div>
  );
}

function SourceMeta({ label, value }) {
  return (
    <span className="sg-ask-meta-tag">
      <span className="k">{label}</span> <span className="v">{value}</span>
    </span>
  );
}

function formatScore(value) {
  return Number.isFinite(value) ? value.toFixed(value >= 10 ? 0 : 2) : "0";
}

function ContextRail({
  job,
  context,
  contextLoading,
  contextError,
  prepareResult,
  prepareError,
  prep,
  localStatus,
  localError,
  localLoading,
  localState,
  reloadLocal,
  lastRetrievedChunks,
  lastLocalModel,
  sessions,
  sessionsLoading,
  sessionsError,
  sessionAction,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onRefreshSessions,
  commandProps,
}) {
  return (
    <div className="sg-ask-rail-stack">
      <Panel title="Selected guide" icon={BookOpen}>
        {!job ? (
          <p className="sg-ask-muted">Select a generated guide to inspect its context.</p>
        ) : (
          <div className="sg-ask-selguide">
            <div>
              <strong className="sg-ask-selguide-title">{safeText(job.title, "Untitled guide")}</strong>
              <p className="sg-ask-selguide-date">{formatDate(job.updated_at || job.created_at)}</p>
            </div>
            <div className="sg-ask-chips">
              {job.status && <MiniChip>{job.status}</MiniChip>}
              {job.style && <MiniChip>{job.style}</MiniChip>}
              {job.generator_preset && <MiniChip>{job.generator_preset}</MiniChip>}
              {job.provider && <MiniChip>{job.provider}</MiniChip>}
              {job.model && <MiniChip>{job.model}</MiniChip>}
            </div>
            <p className="sg-ask-muted">
              {job.source_available ? "Generated guide and extracted source are available." : "Generated guide is available; extracted source is not present."}
            </p>
          </div>
        )}
      </Panel>

      <Panel title="Chat sessions" icon={MessageSquareText}>
        <SessionManager
          job={job}
          sessions={sessions}
          loading={sessionsLoading}
          error={sessionsError}
          action={sessionAction}
          activeSessionId={activeSessionId}
          onSelect={onSelectSession}
          onNew={onNewSession}
          onRefresh={onRefreshSessions}
        />
      </Panel>

      <Panel title="Context sources" icon={FileText}>
        {contextLoading && <InlineLoading label="Loading context inventory" />}
        {contextError && <Notice tone="error" title="Context unavailable" text={contextError} />}
        {!contextLoading && !contextError && context && <ContextInventory context={context} />}
      </Panel>

      <Panel title="Preparation" icon={Sparkles}>
        <div className="sg-ask-panel-row">
          <Pill tone={prep.tone}>{prep.label}</Pill>
          {prepareResult?.cache_status && <MiniChip>{prepareResult.cache_status}</MiniChip>}
        </div>
        {prepareError && <p className="sg-ask-err-text">{prepareError}</p>}
        {prepareResult?.ready && <PrepareSummary result={prepareResult} />}
      </Panel>

      {(lastRetrievedChunks.length > 0 || lastLocalModel?.model) && (
        <Panel title="Latest answer context" icon={MessageSquareText}>
          {lastLocalModel?.model && (
            <p className="sg-ask-muted sg-ask-latest-model">
              Local model: <span>{lastLocalModel.model}</span>
            </p>
          )}
          {lastRetrievedChunks.length > 0 && (
            <details className="sg-ask-retrieved">
              <summary>Show retrieved chunks ({formatCount(lastRetrievedChunks.length)})</summary>
              <div className="sg-ask-retrieved-body">
                <RetrievedChunkList rows={lastRetrievedChunks} />
              </div>
            </details>
          )}
        </Panel>
      )}

      <Panel title="Local model" icon={Server}>
        <LocalModelSummary
          status={localStatus}
          error={localError}
          loading={localLoading}
          state={localState}
          onRefresh={reloadLocal}
        />
        {commandProps && (
          <div className="sg-ask-cmd">
            <CommandHelper
              prominent={commandProps.prominent}
              profiles={commandProps.profiles}
              activeProfile={commandProps.activeProfile}
              selectedProfileId={commandProps.selectedProfileId}
              onSelectProfile={commandProps.onSelectProfile}
              copyState={commandProps.copyState}
              onCopy={commandProps.onCopy}
              notes={commandProps.notes}
            />
          </div>
        )}
      </Panel>
    </div>
  );
}

function SessionManager({ job, sessions, loading, error, action, activeSessionId, onSelect, onNew, onRefresh }) {
  if (!job) {
    return <p className="sg-ask-muted">Select a generated guide to see its chats.</p>;
  }
  return (
    <div className="sg-ask-sessions">
      <div className="sg-ask-session-actions">
        <button type="button" className="sg-btn-sm accent" onClick={onNew} disabled={action !== null}>
          {action === "new" ? <Loader2 size={13} className="sg-spin" /> : <Plus size={13} />}
          <span>New chat</span>
        </button>
        <button type="button" className="sg-btn-sm" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={13} className="sg-spin" /> : <RefreshCw size={13} />}
          <span>Refresh</span>
        </button>
      </div>
      {error && <p className="sg-ask-err-text">{error}</p>}
      {loading && <InlineLoading label="Loading sessions" />}
      {!loading && !error && sessions.length === 0 && (
        <p className="sg-ask-muted">No saved chats for this guide yet. Sending a message will create one.</p>
      )}
      {!loading && sessions.length > 0 && (
        <div className="sg-ask-session-list">
          {sessions.map((item) => {
            const active = item.sessionId === activeSessionId;
            return (
              <button
                key={item.sessionId}
                type="button"
                onClick={() => onSelect(item.sessionId)}
                disabled={action !== null || active}
                className={`sg-ask-session${active ? " active" : ""}`}
              >
                <div className="sg-ask-session-top">
                  <strong>{sessionShortLabel(item)}</strong>
                  {active && <MiniChip>Active</MiniChip>}
                </div>
                <p className="sg-ask-session-meta">{sessionMetaLabel(item)}</p>
                {item.lastMessage?.snippet && (
                  <p className="sg-ask-session-snippet">
                    {item.lastMessage.role === "user" ? "You: " : "Guide: "}
                    {item.lastMessage.snippet}
                  </p>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ContextInventory({ context }) {
  const attachments = attachmentRows(context);
  const selections = pageSelectionRows(context);
  const reasons = readinessReasons(context);
  return (
    <div className="sg-ask-inventory">
      <div className="sg-ask-metric-grid cols-2">
        <Metric label="Guide present" value={context.guide?.clean_md_present ? "Yes" : "No"} />
        <Metric label="Guide headings" value={formatCount(context.guide?.heading_count)} />
        <Metric label="Source present" value={context.source?.extracted_txt_present ? "Yes" : "No"} />
        <Metric label="Page anchors" value={formatCount(context.source?.page_anchor_count)} />
      </div>
      <div className="sg-ask-metric-grid cols-2">
        <Metric label="Guide chars" value={formatCount(context.guide?.char_count)} />
        <Metric label="Source chars" value={formatCount(context.source?.char_count)} />
      </div>
      {reasons.length > 0 && (
        <ul className="sg-ask-reasons">
          {reasons.map((reason, i) => <li key={i}>{reason}</li>)}
        </ul>
      )}
      <div>
        <span className="sg-ask-sublabel">Attachments</span>
        {attachments.length === 0 ? (
          <p className="sg-ask-muted">No attachment metadata.</p>
        ) : (
          <div className="sg-ask-attach-list">
            {attachments.map((item, i) => (
              <div key={`${item.filename}-${i}`} className="sg-ask-attach">
                <div className="sg-ask-attach-top">
                  <span className="sg-ask-attach-name">{item.filename}</span>
                  <MiniChip>{item.mode}</MiniChip>
                </div>
                <p className="sg-ask-attach-chars">
                  {item.extractedChars === null ? "Extracted chars unavailable" : `${formatCount(item.extractedChars)} extracted chars`}
                </p>
                {item.warnings.length > 0 && (
                  <ul className="sg-ask-attach-warn">
                    {item.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      <div>
        <span className="sg-ask-sublabel">Page selections</span>
        {selections.length === 0 ? (
          <p className="sg-ask-muted">No page selections.</p>
        ) : (
          <div className="sg-ask-pagesel-list">
            {selections.map((item, i) => (
              <p key={`${item.filename}-${i}`} className="sg-ask-pagesel">
                {item.filename}: <span>{item.ranges.join(", ") || "range unavailable"}</span>
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PrepareSummary({ result }) {
  const summary = citationSummary(result);
  return (
    <div className="sg-ask-prep-summary">
      <div className="sg-ask-metric-grid cols-3">
        <Metric label="Total" value={formatCount(result.total_chunk_count)} />
        <Metric label="Guide" value={formatCount(result.guide_chunk_count)} />
        <Metric label="Source" value={formatCount(result.source_chunk_count)} />
      </div>
      <div>
        <span className="sg-ask-sublabel">Citation summary</span>
        <p className="sg-ask-muted">
          {formatCount(summary.guideHeadingCount)} guide headings · {formatCount(summary.sourcePageCount)} source pages
        </p>
        {summary.headings.length > 0 && (
          <div className="sg-ask-chips sg-ask-chips-spaced">
            {summary.headings.map((heading) => <MiniChip key={heading}>{heading}</MiniChip>)}
          </div>
        )}
        {summary.pages.length > 0 && (
          <p className="sg-ask-muted sg-ask-pages">Pages: {summary.pages.join(", ")}</p>
        )}
      </div>
    </div>
  );
}

function LocalModelSummary({ status, error, loading, state, onRefresh }) {
  const latency = statusLatencyMs(status);
  const count = statusModelCount(status);
  const selected = typeof status?.selected_model === "string" ? status.selected_model : null;
  const defaultModel = typeof status?.default_model === "string" ? status.default_model : null;
  const errorMessage = error || statusErrorMessage(status);
  const { shown, overflow } = modelChips(status, 8);
  const reachable = state === STATE_REACHABLE;
  return (
    <div className="sg-ask-local">
      <div className="sg-ask-panel-row sg-ask-local-head">
        <Pill tone={reachable ? "ready" : "warning"}>
          {loading ? <Loader2 size={12} className="sg-spin" /> : reachable ? <Check size={12} /> : <WifiOff size={12} />}
          {loading ? "Checking" : LOCAL_LABEL[state] || "Status unavailable"}
        </Pill>
        <button type="button" className="sg-btn-sm" onClick={() => onRefresh(true)} disabled={loading}>
          {loading ? <Loader2 size={13} className="sg-spin" /> : <RefreshCw size={13} />}
          <span>Refresh</span>
        </button>
      </div>
      <div className="sg-ask-metric-grid cols-2">
        <Metric label="Latency" value={latency === null ? "—" : `${latency} ms`} />
        <Metric label="Models" value={formatCount(count)} />
        <Metric label="Default" value={defaultModel || "—"} />
        <Metric label="Selected" value={selected || "—"} />
      </div>
      {errorMessage && !reachable && <p className="sg-ask-warn-text">{errorMessage}</p>}
      {shown.length > 0 && (
        <div className="sg-ask-chips sg-ask-chips-spaced">
          {shown.map((model) => <MiniChip key={model}>{model}</MiniChip>)}
          {overflow > 0 && <MiniChip>+{overflow} more</MiniChip>}
        </div>
      )}
      {!reachable && (
        <div className="sg-ask-offline">
          <Terminal size={14} />
          <span>Chat input stays disabled until the local OpenAI-compatible server is reachable.</span>
        </div>
      )}
    </div>
  );
}

function Panel({ title, icon: Icon, children }) {
  return (
    <section className="sg-ask-panel">
      <div className="sg-ask-panel-head">
        <span className="sg-ask-panel-icon">
          <Icon size={14} />
        </span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Pill({ tone = "neutral", children }) {
  return <span className={`sg-ask-pill ${STATUS_TONE[tone] || STATUS_TONE.neutral}`}>{children}</span>;
}

function MiniChip({ children }) {
  return <span className="sg-ask-tag">{children}</span>;
}

function Metric({ label, value }) {
  return (
    <div className="sg-ask-metric">
      <span className="sg-ask-metric-k">{label}</span>
      <span className="sg-ask-metric-v" title={String(value)}>{value}</span>
    </div>
  );
}

function Notice({ tone, title, text }) {
  const isError = tone === "error";
  return (
    <div className={`sg-ask-notice${isError ? " error" : " warn"}`}>
      <AlertTriangle size={14} />
      <div className="sg-ask-notice-body">
        <strong>{title}</strong>
        <span>{text}</span>
      </div>
    </div>
  );
}

function InlineLoading({ label }) {
  return (
    <div className="sg-ask-inline-load">
      <Loader2 size={14} className="sg-spin" />
      {label}
    </div>
  );
}

function SkeletonGuide() {
  return (
    <div className="sg-ask-skel">
      <div className="sg-ask-skel-line w80" />
      <div className="sg-ask-skel-line w40" />
      <div className="sg-ask-skel-chips">
        <div className="sg-ask-skel-chip w14" />
        <div className="sg-ask-skel-chip w20" />
      </div>
    </div>
  );
}
