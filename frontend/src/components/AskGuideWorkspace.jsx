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

const STATUS_TONE = {
  ready: "border-[#86EFAC]/30 bg-[#86EFAC]/10 text-[#86EFAC]",
  neutral: "border-white/10 bg-white/5 text-[#9098A8]",
  warning: "border-[#FCD34D]/30 bg-[#FCD34D]/10 text-[#FCD34D]",
  error: "border-[#FCA5A5]/30 bg-[#FCA5A5]/10 text-[#FCA5A5]",
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
    <div className="flex h-full min-h-0 flex-col bg-[#0A0F1A]">
      <div className="flex h-[58px] shrink-0 items-center justify-between border-b border-white/5 px-5">
        <div className="min-w-0">
          <h1 className="text-[16px] font-semibold text-[#F4F4F5]">Ask Your Guide</h1>
          <p className="mt-0.5 text-[11.5px] text-[#6B7185]">Select a generated guide and prepare its context.</p>
        </div>
        <div className="flex items-center gap-2">
          <Pill tone={localReachable ? "ready" : "warning"}>
            {localLoading ? <Loader2 size={12} className="animate-spin" /> : localReachable ? <Check size={12} /> : <WifiOff size={12} />}
            {localLoading ? "Checking local model" : `Local model: ${LOCAL_LABEL[localState] || "Status unavailable"}`}
          </Pill>
          <button type="button" className="sg-ghost-button" onClick={loadJobs} disabled={jobsLoading}>
            {jobsLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            <span className="ml-1.5">Refresh guides</span>
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(420px,1fr)_360px]">
        <GuidePicker
          jobs={jobs}
          loading={jobsLoading}
          error={jobsError}
          selectedJobId={selectedJobId}
          onSelect={setSelectedJobId}
        />

        <main className="min-w-0 overflow-y-auto border-x border-white/5 p-5">
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

        <aside className="min-w-0 overflow-y-auto p-4">
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
    <aside className="min-h-0 overflow-y-auto p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-[13px] font-semibold text-[#E8EAF0]">Generated guides</h2>
          <p className="mt-0.5 text-[11px] text-[#6B7185]">{loading ? "Loading…" : `${jobs.length} eligible`}</p>
        </div>
        <Search size={15} className="text-[#6B7185]" />
      </div>

      {error && <Notice tone="error" title="Guide list unavailable" text={error} />}
      {!loading && !error && jobs.length === 0 && (
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-[12px] leading-5 text-[#9098A8]">
          <BookOpen size={18} className="mb-2 text-[#F97316]" />
          <strong className="block text-[#E8EAF0]">No generated guides yet</strong>
          <span className="mt-1 block">Generate a guide in Builder first, then return here to prepare it for Ask.</span>
        </div>
      )}

      <div className="space-y-2">
        {loading
          ? Array.from({ length: 4 }, (_, i) => <SkeletonGuide key={i} />)
          : jobs.map((job) => {
              const active = job.id === selectedJobId;
              return (
                <button
                  key={job.id}
                  type="button"
                  onClick={() => onSelect(job.id)}
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    active
                      ? "border-[#F97316]/45 bg-[#F97316]/10"
                      : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <FileText size={15} className={active ? "mt-0.5 shrink-0 text-[#F97316]" : "mt-0.5 shrink-0 text-[#9098A8]"} />
                    <div className="min-w-0 flex-1">
                      <strong className="block truncate text-[12.5px] text-[#E8EAF0]">{safeText(job.title, "Untitled guide")}</strong>
                      <span className="mt-0.5 block truncate text-[11px] text-[#6B7185]">
                        {formatDate(job.updated_at || job.created_at)}
                      </span>
                    </div>
                    {active && <ChevronRight size={15} className="mt-0.5 shrink-0 text-[#F97316]" />}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <MiniChip>{safeText(job.status, "status unavailable")}</MiniChip>
                    {job.provider && <MiniChip>{job.provider}</MiniChip>}
                    {job.model && <MiniChip>{job.model}</MiniChip>}
                    {job.generator_preset && <MiniChip>{job.generator_preset}</MiniChip>}
                  </div>
                  <p className="mt-2 text-[11px] leading-4 text-[#9098A8]">{guideSourceSummary(job)}</p>
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
    <div className="mx-auto flex min-h-full max-w-[860px] flex-col">
      <section className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <div className="flex items-start gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-[#F97316]/15 text-[#FDBA74]">
            <MessageSquareText size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="min-w-0 truncate text-[18px] font-semibold text-[#F4F4F5]">{title}</h2>
              <Pill tone={prep.tone}>{prep.label}</Pill>
            </div>
            <p className="mt-2 text-[12.5px] leading-5 text-[#A8AEBC]">
              Prepare this guide once, then ask grounded questions through the local model. Sessions are created lazily on first send.
            </p>
            {session?.sessionId && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <p className="text-[11px] text-[#6B7185]">{sessionStatusLabel(session)}</p>
                <button type="button" className="sg-ghost-button h-7 px-2 text-[11px]" onClick={onClearSession} disabled={sessionAction !== null || messages.length === 0}>
                  <Eraser size={12} />
                  <span className="ml-1">Clear chat</span>
                </button>
                <button type="button" className="sg-ghost-button h-7 px-2 text-[11px] text-[#FCA5A5]" onClick={onDeleteSession} disabled={sessionAction !== null}>
                  <Trash2 size={12} />
                  <span className="ml-1">Delete</span>
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-2">
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

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onPrepare}
            disabled={!job || contextLoading || prepareLoading || readyState !== "ready"}
            className="sg-cta sg-press-btn disabled:cursor-not-allowed disabled:opacity-50"
            title="Build or reuse the safe chunk index for this guide"
          >
            {prepareLoading ? <Loader2 size={15} className="animate-spin" /> : prepReady ? <Check size={15} /> : <Sparkles size={15} />}
            {prepareLoading ? "Preparing…" : prepReady ? "Prepare again" : "Prepare context"}
          </button>
          <span className="text-[11.5px] text-[#6B7185]">
            {prepReady ? "Context index is ready for local chat." : "Builds guide/source chunks without exposing text."}
          </span>
          <button
            type="button"
            onClick={onNewSession}
            disabled={!job || sessionAction !== null}
            className="sg-ghost-button h-8 px-2 text-[11px] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sessionAction === "new" ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            <span className="ml-1">New chat</span>
          </button>
        </div>
      </section>

      <section className="mt-4 flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-xl border border-white/10 bg-black/20">
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <EmptyChatState chat={chat} prepReady={prepReady} localReachable={localReachable} />
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => (
                <ChatBubble key={message.id || `${message.role}-${index}`} message={message} />
              ))}
            </div>
          )}
          {sending && (
            <div className="mt-4 flex items-center gap-2 text-[12px] text-[#9098A8]">
              <Loader2 size={14} className="animate-spin" />
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
              className="sg-cta sg-press-btn mt-3 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {prepareLoading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
              {prepareLoading ? "Preparing…" : "Prepare context"}
            </button>
          )}
        </div>
        <form
          className="border-t border-white/5 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSend) onSendMessage();
          }}
        >
          <div className={`flex items-end gap-2 rounded-lg border px-3 py-2 ${chat.enabled ? "border-white/10 bg-white/[0.03]" : "border-white/10 bg-white/[0.02] opacity-70"}`}>
            <textarea
              disabled={!chat.enabled}
              value={draftMessage}
              onChange={(event) => setDraftMessage(safeInputText(event.target.value))}
              rows={1}
              className="max-h-32 min-h-[36px] min-w-0 flex-1 resize-none bg-transparent py-2 text-[13px] leading-5 text-[#E8EAF0] outline-none placeholder:text-[#6B7185]"
              placeholder={chat.enabled ? "Ask a question about this guide…" : chat.label}
            />
            <button
              type="submit"
              disabled={!canSend}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-[#F97316] text-white transition hover:bg-[#FB923C] disabled:cursor-not-allowed disabled:bg-white/5 disabled:text-[#6B7185]"
              title={chat.enabled ? "Send message" : chat.label}
            >
              {sending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
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
    <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.02] p-5">
      <div className="flex items-start gap-3">
        <CircleSlash size={18} className="mt-0.5 shrink-0 text-[#6B7185]" />
        <div className="min-w-0">
          <strong className="block text-[13px] text-[#E8EAF0]">{title}</strong>
          <p className="mt-1 max-w-[620px] text-[12px] leading-5 text-[#9098A8]">{text}</p>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ message }) {
  const assistant = message.role === "assistant";
  return (
    <article className={`flex ${assistant ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[82%] rounded-xl border px-4 py-3 ${
          assistant
            ? "border-white/10 bg-white/[0.04] text-[#E8EAF0]"
            : "border-[#F97316]/30 bg-[#F97316]/15 text-[#FFF7ED]"
        }`}
      >
        <div className="mb-1 text-[10.5px] font-semibold uppercase text-[#6B7185]">
          {assistant ? "Ask Your Guide" : "You"}
        </div>
        {assistant ? <AnswerText content={message.content} /> : <p className="whitespace-pre-wrap break-words text-[13px] leading-6">{message.content}</p>}
        {assistant && citationWarningText(message) && (
          <p className="mt-3 rounded-md border border-[#FCD34D]/20 bg-[#FCD34D]/[0.05] px-2 py-1.5 text-[11px] leading-4 text-[#FCD34D]">
            {citationWarningText(message)}
          </p>
        )}
        {assistant && message.citations?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {message.citations.map((label) => (
              <MiniChip key={label}>{label}</MiniChip>
            ))}
          </div>
        )}
        {assistant && message.retrievedChunks?.length > 0 && (
          <details className="mt-3 border-t border-white/5 pt-2">
            <summary className="cursor-pointer text-[11px] font-medium text-[#A8AEBC]">Sources used</summary>
            <div className="mt-2">
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
  if (blocks.length === 0) return <p className="text-[13px] leading-6 text-[#9098A8]">No answer text.</p>;
  return (
    <div className="space-y-2 break-words text-[13px] leading-6">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return (
            <h3 key={index} className="pt-1 text-[14px] font-semibold leading-6 text-[#F4F4F5]">
              <InlineSegments segments={block.segments} />
            </h3>
          );
        }
        if (block.type === "list") {
          return (
            <ol key={index} className="list-decimal space-y-1 pl-5">
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
            <pre key={index} className="overflow-x-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/30 p-2 text-[12px] leading-5 text-[#D4D4D8]">
              {block.text}
            </pre>
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
          <strong key={index} className="font-semibold text-[#F4F4F5]">
            {segment.text}
          </strong>
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
    return <p className="text-[11.5px] leading-5 text-[#9098A8]">No retrieved citation metadata.</p>;
  }
  return (
    <div className="space-y-1.5">
      {safeRows.map((row, index) => (
        <div key={`${row.label}-${row.chunkId || index}`} className={compact ? "text-[11px] leading-5 text-[#9098A8]" : "rounded-lg border border-white/10 bg-white/[0.02] p-2 text-[11.5px] leading-5 text-[#D4D4D8]"}>
          <span className="font-medium text-[#E8EAF0]">{row.label}</span>
          <span className="text-[#6B7185]">
            {row.sourceType ? ` · ${row.sourceType}` : ""}
            {row.page !== null ? ` · p. ${row.page}` : ""}
            {row.approxTokens !== null ? ` · ~${formatCount(row.approxTokens)} tokens` : ""}
          </span>
        </div>
      ))}
    </div>
  );
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
    <div className="space-y-3">
      <Panel title="Selected guide" icon={BookOpen}>
        {!job ? (
          <p className="text-[12px] leading-5 text-[#9098A8]">Select a generated guide to inspect its context.</p>
        ) : (
          <div className="space-y-3">
            <div>
              <strong className="block text-[13px] text-[#E8EAF0]">{safeText(job.title, "Untitled guide")}</strong>
              <p className="mt-1 text-[11px] text-[#6B7185]">{formatDate(job.updated_at || job.created_at)}</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {job.status && <MiniChip>{job.status}</MiniChip>}
              {job.style && <MiniChip>{job.style}</MiniChip>}
              {job.generator_preset && <MiniChip>{job.generator_preset}</MiniChip>}
              {job.provider && <MiniChip>{job.provider}</MiniChip>}
              {job.model && <MiniChip>{job.model}</MiniChip>}
            </div>
            <p className="text-[11.5px] leading-5 text-[#9098A8]">
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
        {!contextLoading && !contextError && context && (
          <ContextInventory context={context} />
        )}
      </Panel>

      <Panel title="Preparation" icon={Sparkles}>
        <div className="flex items-center justify-between gap-2">
          <Pill tone={prep.tone}>{prep.label}</Pill>
          {prepareResult?.cache_status && <MiniChip>{prepareResult.cache_status}</MiniChip>}
        </div>
        {prepareError && <p className="mt-2 break-words text-[11.5px] leading-5 text-[#FCA5A5]">{prepareError}</p>}
        {prepareResult?.ready && <PrepareSummary result={prepareResult} />}
      </Panel>

      {(lastRetrievedChunks.length > 0 || lastLocalModel?.model) && (
        <Panel title="Latest answer context" icon={MessageSquareText}>
          {lastLocalModel?.model && (
            <p className="mb-2 text-[11.5px] leading-5 text-[#9098A8]">
              Local model: <span className="text-[#D4D4D8]">{lastLocalModel.model}</span>
            </p>
          )}
          {lastRetrievedChunks.length > 0 && (
            <details>
              <summary className="cursor-pointer text-[11.5px] font-medium text-[#A8AEBC]">Show retrieved chunks</summary>
              <div className="mt-2">
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
        )}
      </Panel>
    </div>
  );
}

function SessionManager({ job, sessions, loading, error, action, activeSessionId, onSelect, onNew, onRefresh }) {
  if (!job) {
    return <p className="text-[12px] leading-5 text-[#9098A8]">Select a generated guide to see its chats.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button type="button" className="sg-cta sg-press-btn h-8 px-3 text-[11.5px]" onClick={onNew} disabled={action !== null}>
          {action === "new" ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          <span className="ml-1">New chat</span>
        </button>
        <button type="button" className="sg-ghost-button h-8 px-2 text-[11px]" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          <span className="ml-1">Refresh</span>
        </button>
      </div>
      {error && <p className="break-words text-[11.5px] leading-5 text-[#FCA5A5]">{error}</p>}
      {loading && <InlineLoading label="Loading sessions" />}
      {!loading && !error && sessions.length === 0 && (
        <p className="text-[11.5px] leading-5 text-[#9098A8]">No saved chats for this guide yet. Sending a message will create one.</p>
      )}
      {!loading && sessions.length > 0 && (
        <div className="space-y-2">
          {sessions.map((item) => {
            const active = item.sessionId === activeSessionId;
            return (
              <button
                key={item.sessionId}
                type="button"
                onClick={() => onSelect(item.sessionId)}
                disabled={action !== null || active}
                className={`w-full rounded-lg border p-2 text-left transition ${
                  active
                    ? "border-[#F97316]/40 bg-[#F97316]/10"
                    : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
                } disabled:cursor-default`}
              >
                <div className="flex items-center justify-between gap-2">
                  <strong className="min-w-0 truncate text-[11.5px] text-[#E8EAF0]">{sessionShortLabel(item)}</strong>
                  {active && <MiniChip>Active</MiniChip>}
                </div>
                <p className="mt-1 truncate text-[10.5px] text-[#6B7185]">{sessionMetaLabel(item)}</p>
                {item.lastMessage?.snippet && (
                  <p className="mt-1 max-h-8 overflow-hidden text-[11px] leading-4 text-[#9098A8]">
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
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Guide present" value={context.guide?.clean_md_present ? "Yes" : "No"} />
        <Metric label="Guide headings" value={formatCount(context.guide?.heading_count)} />
        <Metric label="Source present" value={context.source?.extracted_txt_present ? "Yes" : "No"} />
        <Metric label="Page anchors" value={formatCount(context.source?.page_anchor_count)} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Guide chars" value={formatCount(context.guide?.char_count)} />
        <Metric label="Source chars" value={formatCount(context.source?.char_count)} />
      </div>
      {reasons.length > 0 && (
        <ul className="space-y-1 text-[11.5px] leading-5 text-[#FCD34D]">
          {reasons.map((reason, i) => <li key={i}>{reason}</li>)}
        </ul>
      )}
      <div>
        <span className="mb-1.5 block text-[10.5px] font-semibold uppercase text-[#6B7185]">Attachments</span>
        {attachments.length === 0 ? (
          <p className="text-[11.5px] text-[#9098A8]">No attachment metadata.</p>
        ) : (
          <div className="space-y-2">
            {attachments.map((item, i) => (
              <div key={`${item.filename}-${i}`} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-[11.5px] text-[#D4D4D8]">{item.filename}</span>
                  <MiniChip>{item.mode}</MiniChip>
                </div>
                <p className="mt-1 text-[11px] text-[#6B7185]">
                  {item.extractedChars === null ? "Extracted chars unavailable" : `${formatCount(item.extractedChars)} extracted chars`}
                </p>
                {item.warnings.length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-[11px] text-[#FCD34D]">
                    {item.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      <div>
        <span className="mb-1.5 block text-[10.5px] font-semibold uppercase text-[#6B7185]">Page selections</span>
        {selections.length === 0 ? (
          <p className="text-[11.5px] text-[#9098A8]">No page selections.</p>
        ) : (
          <div className="space-y-1">
            {selections.map((item, i) => (
              <p key={`${item.filename}-${i}`} className="text-[11.5px] leading-5 text-[#D4D4D8]">
                {item.filename}: <span className="text-[#9098A8]">{item.ranges.join(", ") || "range unavailable"}</span>
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
    <div className="mt-3 space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <Metric label="Total" value={formatCount(result.total_chunk_count)} />
        <Metric label="Guide" value={formatCount(result.guide_chunk_count)} />
        <Metric label="Source" value={formatCount(result.source_chunk_count)} />
      </div>
      <div>
        <span className="mb-1.5 block text-[10.5px] font-semibold uppercase text-[#6B7185]">Citation summary</span>
        <p className="text-[11.5px] leading-5 text-[#9098A8]">
          {formatCount(summary.guideHeadingCount)} guide headings · {formatCount(summary.sourcePageCount)} source pages
        </p>
        {summary.headings.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {summary.headings.map((heading) => <MiniChip key={heading}>{heading}</MiniChip>)}
          </div>
        )}
        {summary.pages.length > 0 && (
          <p className="mt-2 text-[11px] text-[#6B7185]">Pages: {summary.pages.join(", ")}</p>
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
    <div>
      <div className="flex items-center justify-between gap-2">
        <Pill tone={reachable ? "ready" : "warning"}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : reachable ? <Check size={12} /> : <WifiOff size={12} />}
          {loading ? "Checking" : LOCAL_LABEL[state] || "Status unavailable"}
        </Pill>
        <button type="button" className="sg-ghost-button h-8 px-2 text-[11px]" onClick={() => onRefresh(true)} disabled={loading}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          <span className="ml-1">Refresh</span>
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric label="Latency" value={latency === null ? "—" : `${latency} ms`} />
        <Metric label="Models" value={formatCount(count)} />
        <Metric label="Default" value={defaultModel || "—"} />
        <Metric label="Selected" value={selected || "—"} />
      </div>
      {errorMessage && !reachable && (
        <p className="mt-2 break-words text-[11.5px] leading-5 text-[#FCD34D]">{errorMessage}</p>
      )}
      {shown.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {shown.map((model) => <MiniChip key={model}>{model}</MiniChip>)}
          {overflow > 0 && <MiniChip>+{overflow} more</MiniChip>}
        </div>
      )}
      {!reachable && (
        <div className="mt-3 rounded-lg border border-[#FCD34D]/20 bg-[#FCD34D]/[0.05] p-3 text-[11.5px] leading-5 text-[#D4D4D8]">
          <div className="flex gap-2">
            <Terminal size={14} className="mt-0.5 shrink-0 text-[#FCD34D]" />
            <span>Chat input stays disabled until the local OpenAI-compatible server is reachable.</span>
          </div>
        </div>
      )}
    </div>
  );
}

function Panel({ title, icon: Icon, children }) {
  return (
    <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-white/[0.04] text-[#F97316]">
          <Icon size={14} />
        </span>
        <h2 className="text-[12.5px] font-semibold text-[#E8EAF0]">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Pill({ tone = "neutral", children }) {
  return (
    <span className={`inline-flex h-[24px] shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-[10.5px] ${STATUS_TONE[tone] || STATUS_TONE.neutral}`}>
      {children}
    </span>
  );
}

function MiniChip({ children }) {
  return (
    <span className="inline-flex max-w-full items-center truncate rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10.5px] text-[#A8AEBC]">
      {children}
    </span>
  );
}

function Metric({ label, value }) {
  return (
    <div className="min-w-0 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2">
      <span className="block text-[10px] uppercase text-[#6B7185]">{label}</span>
      <span className="mt-0.5 block truncate text-[12px] text-[#E8EAF0]" title={String(value)}>{value}</span>
    </div>
  );
}

function Notice({ tone, title, text }) {
  const isError = tone === "error";
  return (
    <div className={`mt-4 rounded-lg border p-3 ${isError ? "border-[#FCA5A5]/20 bg-[#FCA5A5]/[0.05]" : "border-[#FCD34D]/20 bg-[#FCD34D]/[0.05]"}`}>
      <div className="flex items-start gap-2">
        <AlertTriangle size={14} className={`mt-0.5 shrink-0 ${isError ? "text-[#FCA5A5]" : "text-[#FCD34D]"}`} />
        <div className="min-w-0 text-[11.5px] leading-5">
          <strong className={`block ${isError ? "text-[#FCA5A5]" : "text-[#FCD34D]"}`}>{title}</strong>
          <span className="break-words text-[#D4D4D8]">{text}</span>
        </div>
      </div>
    </div>
  );
}

function InlineLoading({ label }) {
  return (
    <div className="flex items-center gap-2 text-[12px] text-[#9098A8]">
      <Loader2 size={14} className="animate-spin" />
      {label}
    </div>
  );
}

function SkeletonGuide() {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
      <div className="h-3 w-4/5 rounded bg-white/10" />
      <div className="mt-2 h-2.5 w-2/5 rounded bg-white/5" />
      <div className="mt-3 flex gap-1.5">
        <div className="h-5 w-14 rounded-full bg-white/5" />
        <div className="h-5 w-20 rounded-full bg-white/5" />
      </div>
    </div>
  );
}
