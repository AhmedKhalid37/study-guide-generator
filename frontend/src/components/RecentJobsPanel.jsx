import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  FileCode2,
  FileJson,
  FileText,
  FolderClosed,
  Layers,
  ListChecks,
  Loader2,
  Paperclip,
  RefreshCw,
  RotateCcw,
  Sparkles,
  X,
  XCircle
} from "lucide-react";
import {
  artifactUrl,
  generateQuiz,
  getCleanMd,
  getJob,
  getJobSections,
  getJobs,
  getJobVersions,
  getOptions,
  getOutlineCompliance,
  getQuiz,
  getStyles,
  getVersionCleanMd,
  listQuizzes,
  putCleanMd,
  quizExportUrl,
  regenerateSection,
  retryJob,
  revertJobVersion
} from "../api/client";
import { buildStyleLookup, resolveStyle } from "../styleMeta";
import { folderColor } from "../folderMeta";
import Panel from "./Panel";
import ItemCard from "./ItemCard";
import ProviderPill from "./ProviderPill";

const artifactLinks = [
  { name: "final.pdf", label: "PDF", key: "final_pdf", icon: Download },
  { name: "final.docx", label: "DOCX", key: "final_docx", icon: FileText },
  { name: "clean.md", label: "Markdown", key: "clean_md", icon: FileText },
  { name: "final.html", label: "HTML", key: "final_html", icon: FileCode2 },
  { name: "validation.json", label: "Validation", key: "validation_json", icon: FileJson },
  { name: "render.log", label: "Render log", key: "render_log", icon: FileText }
];

function formatProviderModel(job) {
  return [job.provider, job.model].filter(Boolean).join(" / ");
}

function jobTitle(job) {
  return job.title || "Untitled study guide";
}

function statusClass(status) {
  if (status === "done") {
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  }
  if (status?.includes("failed")) {
    return "border-red-400/30 bg-red-400/10 text-red-200";
  }
  return "border-amber-300/30 bg-amber-300/10 text-amber-100";
}

// Build a {id, name, color} folder object from a job's flat folder_* fields,
// or null when the job is unfiled. Works for /api/jobs and /api/jobs/{id}.
function jobFolder(job) {
  if (!job?.folder_id || !job?.folder_name) {
    return null;
  }
  return { id: job.folder_id, name: job.folder_name, color: job.folder_color };
}

function attachmentSummary(job) {
  const attachments = job.attachments ?? [];
  const warnings = job.extraction_warnings ?? [];
  return {
    count: job.attachment_summary?.count ?? attachments.length,
    warningCount: job.attachment_summary?.warning_count ?? warnings.length,
    totalChars: job.attachment_summary?.total_extracted_chars ?? job.total_extracted_chars ?? 0,
    hasWarnings: job.attachment_summary?.has_warnings ?? warnings.length > 0
  };
}

function RecentJobsPanel({ refreshKey = 0, embedded = false, onSelectedJobChange }, ref) {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobsError, setJobsError] = useState(null);
  const [loadingJob, setLoadingJob] = useState(false);
  const [jobError, setJobError] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [styleLookup, setStyleLookup] = useState({});

  useEffect(() => {
    let cancelled = false;
    getStyles()
      .then((data) => !cancelled && setStyleLookup(buildStyleLookup(data)))
      .catch(() => !cancelled && setStyleLookup({}));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    let cancelled = false;

    async function loadJobs() {
      setLoadingJobs(true);
      setJobsError(null);
      try {
        const data = await getJobs();
        if (cancelled) {
          return;
        }
        const nextJobs = data.jobs ?? [];
        setJobs(nextJobs);
        setSelectedJobId((current) => {
          if (current && nextJobs.some((job) => job.id === current)) {
            return current;
          }
          return nextJobs[0]?.id ?? null;
        });
      } catch (error) {
        if (!cancelled) {
          setJobsError(error);
        }
      } finally {
        if (!cancelled) {
          setLoadingJobs(false);
        }
      }
    }

    loadJobs();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    let cancelled = false;

    async function loadJob() {
      if (!selectedJobId) {
        setSelectedJob(null);
        onSelectedJobChange?.(null);
        return;
      }

      setLoadingJob(true);
      setJobError(null);
      try {
        const data = await getJob(selectedJobId);
        if (!cancelled) {
          setSelectedJob(data);
          onSelectedJobChange?.(data);
        }
      } catch (error) {
        if (!cancelled) {
          setJobError(error);
          setSelectedJob(null);
          onSelectedJobChange?.(null);
        }
      } finally {
        if (!cancelled) {
          setLoadingJob(false);
        }
      }
    }

    loadJob();
    return () => {
      cancelled = true;
    };
  }, [selectedJobId, onSelectedJobChange]);

  const selectedManifest = selectedJob?.job;
  const availability = selectedJob?.artifact_availability ?? {};
  const availableArtifacts = useMemo(
    () => artifactLinks.filter((artifact) => availability[artifact.key]),
    [availability]
  );

  const openJobDetails = useCallback((jobId) => {
    setSelectedJobId(jobId);
    setDetailsOpen(true);
  }, []);

  // Let a parent (Home's Favorite Guides) open the SAME drawer for any job id —
  // the job-load effect fetches it whether or not it is in the recent list.
  useImperativeHandle(ref, () => ({ openJob: openJobDetails }), [openJobDetails]);

  const listPanel = (
    <Panel title="Recent Guides" action={<span className="panel-link">View all</span>}>
      {loadingJobs && (
        <div className="recent-state">
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--muted)" }} />
          <span>Loading guides…</span>
        </div>
      )}

      {!loadingJobs && jobsError && (
        <div className="recent-state" style={{ color: "var(--red)" }}>
          <AlertCircle className="h-5 w-5" />
          <span>Could not load guides</span>
        </div>
      )}

      {!loadingJobs && !jobsError && jobs.length === 0 && (
        <div className="recent-state">No guides yet</div>
      )}

      {!loadingJobs && !jobsError && jobs.length > 0 && (
        <div className="col">
          {jobs.map((job) => {
            const selected = selectedJobId === job.id;
            const providerModel = formatProviderModel(job);
            const sources = attachmentSummary(job);
            const jobStyle = resolveStyle(job.prompt_name, styleLookup);
            // Truthful meta snippet from the list payload: non-terminal status
            // (so failures stay visible), style, and source count.
            const bits = [];
            if (job.status && job.status !== "done") bits.push(job.status.replace(/_/g, " "));
            if (jobStyle) bits.push(jobStyle.name);
            if (sources.count > 0) bits.push(`${sources.count} source${sources.count === 1 ? "" : "s"}`);
            const snippet = bits.join(" · ") || "Study guide";
            return (
              <ItemCard
                key={job.id}
                date={job.created_at}
                title={jobTitle(job)}
                description={snippet}
                meta={providerModel ? <ProviderPill provider={providerModel} /> : null}
                role="button"
                tabIndex={0}
                aria-current={selected ? "true" : undefined}
                onClick={() => openJobDetails(job.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openJobDetails(job.id);
                  }
                }}
                style={selected ? { borderColor: "var(--card-border-2)", background: "#1E1E22" } : undefined}
              />
            );
          })}
        </div>
      )}
    </Panel>
  );

  // After a successful retry the drawer closes and the jobs list refreshes via
  // the parent's refreshKey mechanism. Here we use a local key bump to reload.
  const [localRefresh, setLocalRefresh] = useState(0);

  function handleRetry() {
    // Re-select the same job so its details reload, and re-fetch the list.
    setLocalRefresh((k) => k + 1);
    setSelectedJobId((id) => {
      // Force effect to re-run even though id is the same.
      setSelectedJob(null);
      return id;
    });
  }

  if (embedded) {
    return (
      <>
        {listPanel}
        <JobDetailsDrawer
          open={detailsOpen}
          onClose={() => setDetailsOpen(false)}
          loading={loadingJob}
          error={jobError}
          details={selectedJob}
          styleLookup={styleLookup}
          onRetry={handleRetry}
        />
      </>
    );
  }

  return (
    <>
      <section className="mx-auto mt-10 grid w-full max-w-[1536px] gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        {listPanel}

        <aside className="rounded-2xl border border-white/10 bg-navy-900/80 p-5 shadow-navy backdrop-blur-xl">
          <PreviewPanel
            loading={loadingJob}
            error={jobError}
            manifest={selectedManifest}
            availableArtifacts={availableArtifacts}
            onOpenDetails={() => selectedManifest && setDetailsOpen(true)}
          />
        </aside>
      </section>
      <JobDetailsDrawer
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        loading={loadingJob}
        error={jobError}
        details={selectedJob}
        styleLookup={styleLookup}
        onRetry={handleRetry}
      />
    </>
  );
}

function PreviewPanel({ loading, error, manifest, availableArtifacts, onOpenDetails }) {
  return (
    <>
      <div className="border-b border-white/10 pb-4">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">Output</p>
        <h2 className="mt-1 text-xl font-bold text-white">Preview panel</h2>
      </div>

      {loading && (
        <div className="flex min-h-52 items-center justify-center gap-3 text-slate-300">
          <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
          <span>Loading job...</span>
        </div>
      )}

      {!loading && error && (
        <div className="flex min-h-52 items-center justify-center gap-3 text-red-200">
          <AlertCircle className="h-5 w-5" />
          <span>Could not load job</span>
        </div>
      )}

      {!loading && !error && !manifest && (
        <div className="flex min-h-52 items-center justify-center text-slate-400">
          Select a job
        </div>
      )}

      {!loading && !error && manifest && (
        <div className="mt-4">
          <dl className="grid gap-3 text-sm">
            <MetaTerm label="Job id" value={manifest.id} mono />
            <MetaTerm label="Title" value={jobTitle(manifest)} />
            <MetaTerm label="Status" value={manifest.status || "unknown"} />
            <MetaTerm label="Provider / model" value={formatProviderModel(manifest) || "provider/model unavailable"} />
            <MetaTerm label="Created" value={manifest.created_at || "created_at unavailable"} />
          </dl>

          <AttachmentDetails manifest={manifest} />

          <div className="mt-6">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-bold text-white">Downloads</p>
              <button type="button" onClick={onOpenDetails} className="text-xs font-bold text-ember-500 hover:text-ember-300">
                Details
              </button>
            </div>
            <ArtifactLinkGrid jobId={manifest.id} artifacts={availableArtifacts} />
          </div>
        </div>
      )}
    </>
  );
}

export function StylePill({ style }) {
  if (!style) {
    return null;
  }
  const tone = style.isCustom
    ? "border-violet-400/30 bg-violet-400/10 text-violet-200"
    : "border-sky-400/25 bg-sky-400/10 text-sky-200";
  return (
    <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-bold ${tone}`}>
      {style.name}
      <span className="opacity-70">· {style.isCustom ? "Custom" : "Built-in"}</span>
    </span>
  );
}

export function FolderPill({ folder }) {
  if (!folder || !folder.name) {
    return null;
  }
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[11px] font-semibold text-slate-300">
      <FolderClosed className="h-3 w-3" color={folderColor(folder)} />
      {folder.name}
    </span>
  );
}

function AttachmentPill({ count }) {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-bold text-emerald-200">
      <Paperclip className="h-3 w-3" />
      {count} {count === 1 ? "source" : "sources"}
    </span>
  );
}

function WarningPill({ count }) {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-amber-300/30 bg-amber-300/10 px-2 py-0.5 text-[11px] font-bold text-amber-100">
      <AlertCircle className="h-3 w-3" />
      {count || 1} warning{count === 1 ? "" : "s"}
    </span>
  );
}

function AttachmentDetails({ manifest }) {
  const attachments = manifest?.attachments ?? [];
  if (attachments.length === 0) {
    return null;
  }

  const summary = attachmentSummary(manifest);
  return (
    <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.035] p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-white">Attached sources</p>
        <div className="flex flex-wrap justify-end gap-1.5">
          <AttachmentPill count={summary.count} />
          {summary.hasWarnings && <WarningPill count={summary.warningCount} />}
        </div>
      </div>
      <div className="mt-3 grid gap-2">
        {attachments.map((attachment, index) => {
          const warnings = attachment.warnings ?? [];
          return (
            <div key={`${attachment.filename}-${index}`} className="rounded-lg border border-white/[0.08] bg-[#070B14] p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-xs font-bold text-slate-100">{attachment.filename}</span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${attachment.status === "extracted" ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-amber-300/30 bg-amber-300/10 text-amber-100"}`}>
                  {attachment.status || "unknown"}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[10.5px] font-semibold text-slate-400">
                <span>{attachment.mode || attachment.extension || "unsupported"}</span>
                <span>{Number(attachment.extracted_chars || 0).toLocaleString()} chars</span>
                {attachment.truncated && <span>truncated</span>}
              </div>
              {warnings.length > 0 && (
                <div className="mt-2 grid gap-1 text-[11px] leading-4 text-amber-100">
                  {warnings.map((warning, warningIndex) => (
                    <p key={warningIndex}>{warning}</p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MetaTerm({ label, value, mono = false }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className={`mt-1 break-words text-slate-200 ${mono ? "font-mono text-xs" : "font-medium"}`}>
        {value || "unavailable"}
      </dd>
    </div>
  );
}

function ArtifactLinkGrid({ jobId, artifacts }) {
  if (!artifacts?.length) {
    return <p className="mt-3 text-sm text-slate-400">No artifacts available</p>;
  }

  return (
    <div className="mt-3 grid gap-2">
      {artifacts.map((artifact) => {
        const Icon = artifact.icon || artifactIcon(artifact.name);
        const href = artifact.url ? apiArtifactUrl(artifact.url) : artifactUrl(jobId, artifact.name);
        const previewHref = artifact.name === "final.pdf" ? `${href}?disposition=inline` : href;
        return (
          <div
            key={artifact.name}
            className="rounded-xl border border-white/10 bg-white/[0.04] p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex min-w-0 items-center gap-2 text-sm font-bold text-slate-100">
                <Icon className="h-4 w-4 shrink-0 text-ember-500" />
                <span className="truncate">{artifact.label}</span>
              </span>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${artifact.available === false ? "border-white/10 text-slate-500" : "border-emerald-400/25 bg-emerald-400/10 text-emerald-200"}`}>
                {artifact.available === false ? "missing" : "ready"}
              </span>
            </div>
            {artifact.available !== false && (
              <div className="mt-3 flex gap-2">
                <a
                  href={href}
                  className="inline-flex h-8 flex-1 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
                >
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  Download
                </a>
                {(artifact.name === "final.pdf" || artifact.name === "final.html") && (
                  <a
                    href={previewHref}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-8 flex-1 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
                  >
                    <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                    Open
                  </a>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function JobDetailsDrawer({ open, onClose, loading, error, details, styleLookup, onRetry, initialTab = "details" }) {
  const manifest = details?.job;
  const artifacts = details?.artifacts ?? artifactLinks
    .filter((artifact) => details?.artifact_availability?.[artifact.key])
    .map((artifact) => ({ ...artifact, available: true }));
  const validation = details?.validation_summary;
  const renderLog = details?.render_log_summary;
  const style = resolveStyle(manifest?.prompt_name, styleLookup);
  const folder = jobFolder(manifest);
  const extractionWarnings = manifest?.extraction_warnings ?? [];
  const isFailed = manifest?.status?.includes("failed");
  const canEdit = details?.artifact_availability?.clean_md && !isFailed;

  const [drawerTab, setDrawerTab] = useState(initialTab);

  // Reset to the caller-requested tab when a new job is opened. Defaults to
  // "details"; callers (e.g. the Builder dirty-state notice) can deep-link to
  // "sections" to land directly on the section-regeneration picker.
  useEffect(() => {
    if (open) setDrawerTab(initialTab);
  }, [manifest?.id, open, initialTab]);

  if (!open) {
    return null;
  }

  const tabs = [
    { key: "details", label: "Details" },
    { key: "quiz", label: "Quiz", icon: BookOpen, disabled: !canEdit },
    { key: "outline", label: "Outline", icon: ListChecks, disabled: !canEdit },
    { key: "sections", label: "Sections", icon: Layers, disabled: !canEdit },
    { key: "edit", label: "Edit Markdown", icon: Edit3, disabled: !canEdit },
    { key: "history", label: "Version History", icon: Clock, disabled: !canEdit },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-sm">
      <button type="button" className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Close job details" />
      <aside className="relative flex h-full w-full max-w-[760px] flex-col border-l border-white/10 bg-[#090D16]/95 shadow-[-24px_0_80px_rgba(0,0,0,0.45)]">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 p-5">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">Job Details</p>
            <h2 className="mt-1 truncate text-2xl font-bold text-white">
              {manifest ? jobTitle(manifest) : "Loading job"}
            </h2>
            {manifest?.id && <p className="mt-1 break-all font-mono text-xs text-slate-500">{manifest.id}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tab bar */}
        {!loading && !error && manifest && (
          <div className="flex gap-1 border-b border-white/10 px-5 pt-3">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  type="button"
                  disabled={tab.disabled}
                  onClick={() => setDrawerTab(tab.key)}
                  className={`inline-flex items-center gap-1.5 rounded-t-lg border border-b-0 px-3 py-2 text-xs font-bold transition ${
                    drawerTab === tab.key
                      ? "border-white/10 bg-[#090D16] text-ember-400"
                      : "border-transparent text-slate-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
                  }`}
                >
                  {Icon && <Icon className="h-3.5 w-3.5" />}
                  {tab.label}
                </button>
              );
            })}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex min-h-72 items-center justify-center gap-3 text-slate-300">
              <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
              <span>Loading details...</span>
            </div>
          )}

          {!loading && error && (
            <div className="flex min-h-72 items-center justify-center gap-3 text-red-200">
              <AlertCircle className="h-5 w-5" />
              <span>Could not load job details</span>
            </div>
          )}

          {!loading && !error && manifest && drawerTab === "details" && (
            <div className="grid gap-5">
              <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                <div className="flex flex-wrap gap-2">
                  <StatusPill status={manifest.status} />
                  <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-bold text-slate-300">
                    {manifest.path_mode || manifest.input_type || "input"}
                  </span>
                  {manifest.provider && (
                    <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-bold text-slate-300">
                      {formatProviderModel(manifest)}
                    </span>
                  )}
                  {style && <StylePill style={style} />}
                  {folder && <FolderPill folder={folder} />}
                </div>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <MetaTerm label="Created" value={manifest.created_at} />
                  <MetaTerm label="Input type" value={manifest.input_type || manifest.path_mode} />
                  <MetaTerm
                    label="Style"
                    value={style ? `${style.name} (${style.isCustom ? "Custom" : "Built-in"})` : "markdown pipeline"}
                  />
                  <MetaTerm label="Folder" value={folder?.name || "Unfiled"} />
                  <MetaTerm
                    label="Outline"
                    value={manifest.outline_enabled ? `${manifest.outline_section_count || 0} sections` : "None"}
                  />
                  <MetaTerm label="Theme" value={manifest.theme} />
                  <MetaTerm label="Mode" value={manifest.mode} />
                  <MetaTerm label="Strict math" value={String(Boolean(manifest.strict_math))} />
                </dl>
              </section>

              {isFailed && (
                <FailedJobPanel
                  manifest={manifest}
                  renderLog={renderLog}
                  validation={validation}
                  jobId={manifest.id}
                  onRetry={onRetry}
                  onClose={onClose}
                />
              )}

              {!isFailed && (manifest.math_failures?.length ?? 0) > 0 && (
                <MathDegradedNotice
                  failures={manifest.math_failures}
                  canEdit={canEdit}
                  onEdit={() => setDrawerTab("edit")}
                />
              )}

              {manifest.outline_enabled && (manifest.outline_titles?.length ?? 0) > 0 && (
                <DetailsSection title={`Outline · ${manifest.outline_section_count || manifest.outline_titles.length} sections`}>
                  <ol className="grid gap-1.5">
                    {manifest.outline_titles.map((sectionTitle, index) => (
                      <li
                        key={`${sectionTitle}-${index}`}
                        className="flex items-center gap-2.5 rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200"
                      >
                        <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-ember-500/15 font-mono text-[10px] font-bold text-ember-300">
                          {index + 1}
                        </span>
                        <span className="min-w-0 truncate font-semibold">{sectionTitle}</span>
                      </li>
                    ))}
                  </ol>
                </DetailsSection>
              )}

              {!isFailed && (
                <DetailsSection title="Artifacts">
                  <ArtifactLinkGrid jobId={manifest.id} artifacts={artifacts} />
                </DetailsSection>
              )}

              <DetailsSection title="Validation">
                <ValidationSummary validation={validation} manifest={manifest} />
              </DetailsSection>

              <DetailsSection title="Render log">
                <RenderLogSummary renderLog={renderLog} />
              </DetailsSection>

              <AttachmentDetails manifest={manifest} />

              {extractionWarnings.length > 0 && (
                <DetailsSection title="Extraction warnings">
                  <div className="grid gap-2">
                    {extractionWarnings.map((warning, index) => (
                      <p key={index} className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">
                        {warning}
                      </p>
                    ))}
                  </div>
                </DetailsSection>
              )}
            </div>
          )}

          {!loading && !error && manifest && drawerTab === "quiz" && canEdit && (
            <QuizTab jobId={manifest.id} manifest={manifest} />
          )}

          {!loading && !error && manifest && drawerTab === "outline" && canEdit && (
            <OutlineComplianceTab jobId={manifest.id} manifest={manifest} />
          )}

          {!loading && !error && manifest && drawerTab === "sections" && canEdit && (
            <SectionRegenerateTab jobId={manifest.id} manifest={manifest} onRegenerated={onRetry} />
          )}

          {!loading && !error && manifest && drawerTab === "edit" && canEdit && (
            <EditMarkdownTab jobId={manifest.id} onSaved={onRetry} />
          )}

          {!loading && !error && manifest && drawerTab === "history" && canEdit && (
            <VersionHistoryTab jobId={manifest.id} onReverted={onRetry} />
          )}
        </div>
      </aside>
    </div>
  );
}

const CATEGORY_LABELS = {
  extraction: "Extraction error",
  ocr: "OCR error",
  math: "Math validation",
  pdf: "PDF render error",
  docx: "DOCX error",
  provider_auth: "Auth error",
  provider_model: "Model error",
  provider_ratelimit: "Rate limit",
  local_offline: "Server offline",
  unknown: "Unknown error",
};

function ErrorCategoryBadge({ category }) {
  const label = CATEGORY_LABELS[category] || category || "Error";
  return (
    <span className="inline-flex items-center rounded-full border border-red-400/30 bg-red-400/10 px-3 py-1 text-xs font-bold text-red-200">
      {label}
    </span>
  );
}

// Non-blocking notice for jobs that finished with renderable bad math. The guide
// IS usable — these expressions just rendered as error-marked spans — so we point
// the user at the existing Edit Markdown tab to fix them, never a failure state.
function MathDegradedNotice({ failures, canEdit, onEdit }) {
  const count = failures?.length ?? 0;
  if (count === 0) {
    return null;
  }
  return (
    <section className="rounded-2xl border border-amber-300/25 bg-amber-300/[0.06] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" />
          <span className="text-sm font-bold text-amber-100">
            {count} math expression{count === 1 ? "" : "s"} couldn&apos;t render
          </span>
        </div>
        {canEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-amber-300/40 bg-amber-300/10 px-3 text-xs font-bold text-amber-100 transition hover:border-amber-300/70 hover:text-white"
          >
            <Edit3 className="h-3.5 w-3.5" />
            Fix in Markdown editor
          </button>
        )}
      </div>
      <p className="mt-2 text-xs leading-5 text-amber-100/80">
        The guide rendered, but these expressions show as error-marked spans. Edit
        them in the Markdown editor and re-render to clean them up.
      </p>
      <ul className="mt-3 grid gap-2">
        {failures.map((failure, index) => (
          <li
            key={index}
            className="rounded-lg border border-amber-300/15 bg-[#070B14] p-3 text-xs leading-5"
          >
            <code className="block break-all font-mono text-amber-100">
              {failure.display_mode ? "display" : "inline"}: {failure.expr}
            </code>
            {failure.message && (
              <span className="mt-1 block text-amber-100/70">{failure.message}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function FailedJobPanel({ manifest, renderLog, validation, jobId, onRetry, onClose }) {
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const category = manifest?.error_category || "unknown";
  const message = manifest?.error;
  const hasLog = renderLog?.available;

  async function handleRetry() {
    setRetrying(true);
    setRetryError(null);
    try {
      await retryJob(jobId);
      onClose?.();
      onRetry?.();
    } catch (err) {
      setRetryError(err.message || "Retry failed. Check the logs and try again.");
    } finally {
      setRetrying(false);
    }
  }

  return (
    <section className="rounded-2xl border border-red-400/20 bg-red-400/[0.04] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
          <span className="text-sm font-bold text-white">Generation failed</span>
          <ErrorCategoryBadge category={category} />
        </div>
        <div className="flex gap-2">
          {(hasLog || validation?.available) && (
            <button
              type="button"
              onClick={() => setLogsExpanded((v) => !v)}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:border-white/20 hover:text-white"
            >
              {logsExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              View logs
            </button>
          )}
          <button
            type="button"
            onClick={handleRetry}
            disabled={retrying}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ember-500/50 bg-ember-500/10 px-3 text-xs font-bold text-ember-300 transition hover:border-ember-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {retrying
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Retrying…</>
              : <><RefreshCw className="h-3.5 w-3.5" /> Try again</>}
          </button>
        </div>
      </div>

      {message && (
        <p className="mt-3 rounded-lg border border-red-400/15 bg-[#070B14] p-3 text-xs leading-5 text-red-200">
          {message}
        </p>
      )}

      {retryError && (
        <p className="mt-2 text-xs text-red-300">{retryError}</p>
      )}

      {logsExpanded && (
        <div className="mt-4 grid gap-3">
          {hasLog && renderLog.last_lines?.length > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-500">Render log (last lines)</p>
              <pre className="max-h-48 overflow-auto rounded-xl border border-white/10 bg-[#070B14] p-3 text-xs leading-5 text-slate-300">
                {renderLog.last_lines.join("\n")}
              </pre>
            </div>
          )}
          {validation?.available && validation.error_count > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-500">
                Math validation — {validation.error_count} issue{validation.error_count !== 1 ? "s" : ""}
              </p>
              <p className="text-xs text-amber-200">
                Download <span className="font-mono">validation.json</span> from Artifacts for the full expression list.
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function DetailsSection({ title, children }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <h3 className="text-sm font-bold text-white">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function StatusPill({ status }) {
  return (
    <span className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-bold ${statusClass(status)}`}>
      {status || "unknown"}
    </span>
  );
}

function ValidationSummary({ validation, manifest }) {
  const fallback = manifest?.math_validation;
  const ok = validation?.ok ?? fallback?.ok;
  const errorCount = validation?.error_count ?? fallback?.errors ?? 0;
  const displayBlocks = validation?.display_blocks ?? fallback?.display_blocks ?? 0;
  const inlineFormulas = validation?.inline_formulas ?? fallback?.inline_formulas ?? 0;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <InfoTile
        icon={ok ? CheckCircle2 : AlertCircle}
        label="Status"
        value={ok === undefined || ok === null ? "Unavailable" : ok ? "Passed" : "Issues found"}
        tone={ok ? "good" : "warn"}
      />
      <InfoTile label="Issues" value={String(errorCount)} tone={errorCount ? "warn" : "neutral"} />
      <InfoTile label="Math" value={`${displayBlocks} display / ${inlineFormulas} inline`} tone="neutral" />
    </div>
  );
}

function RenderLogSummary({ renderLog }) {
  if (!renderLog?.available) {
    return <p className="text-sm text-slate-400">Render log is not available.</p>;
  }
  return (
    <div className="grid gap-3">
      <InfoTile label="Lines" value={String(renderLog.line_count || 0)} tone="neutral" />
      {renderLog.last_lines?.length > 0 && (
        <pre className="max-h-36 overflow-auto rounded-xl border border-white/10 bg-[#070B14] p-3 text-xs leading-5 text-slate-300">
          {renderLog.last_lines.join("\n")}
        </pre>
      )}
    </div>
  );
}

function InfoTile({ icon: Icon, label, value, tone = "neutral" }) {
  const toneClass = tone === "good" ? "text-emerald-200" : tone === "warn" ? "text-amber-100" : "text-slate-100";
  return (
    <div className="rounded-xl border border-white/10 bg-[#070B14] p-3">
      <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {label}
      </div>
      <div className={`mt-2 text-sm font-bold ${toneClass}`}>{value}</div>
    </div>
  );
}

function artifactIcon(name) {
  return artifactLinks.find((artifact) => artifact.name === name)?.icon || FileText;
}

function apiArtifactUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  return artifactUrlFromPath(url);
}

function artifactUrlFromPath(path) {
  const match = path.match(/\/api\/jobs\/([^/]+)\/artifacts\/(.+)$/);
  if (!match) {
    return path;
  }
  return artifactUrl(match[1], decodeURIComponent(match[2]));
}

// --- Outline Compliance tab ---

function OutlineComplianceTab({ jobId, manifest }) {
  const [compliance, setCompliance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setCompliance(null);
    setLoading(true);
    setError(null);
    getOutlineCompliance(jobId)
      .then((d) => { if (!cancelled) setCompliance(d); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-3 text-slate-300">
        <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
        <span>Checking outline compliance…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-2 text-red-300 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {error}
      </div>
    );
  }

  if (!compliance?.has_outline) {
    return (
      <div className="flex min-h-48 items-center justify-center text-slate-400 text-sm">
        No outline was set for this guide.
      </div>
    );
  }

  const sections = compliance.sections ?? [];
  const counts = sections.reduce(
    (acc, s) => { acc[s.status] = (acc[s.status] || 0) + 1; return acc; },
    {}
  );

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-white">Outline Compliance</h3>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          {counts.found > 0 && (
            <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 font-bold text-emerald-200">
              {counts.found} found
            </span>
          )}
          {counts.renamed > 0 && (
            <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-2 py-0.5 font-bold text-amber-200">
              {counts.renamed} renamed
            </span>
          )}
          {counts.missing > 0 && (
            <span className="rounded-full border border-red-400/30 bg-red-400/10 px-2 py-0.5 font-bold text-red-200">
              {counts.missing} missing
            </span>
          )}
        </div>
      </div>

      <ol className="grid gap-2">
        {sections.map((section, i) => {
          const isFound = section.status === "found";
          const isRenamed = section.status === "renamed";
          const isMissing = section.status === "missing";
          return (
            <li
              key={i}
              className={`flex items-start gap-3 rounded-xl border p-3 text-xs ${
                isFound
                  ? "border-emerald-400/20 bg-emerald-400/[0.04]"
                  : isRenamed
                  ? "border-amber-300/20 bg-amber-300/[0.04]"
                  : "border-red-400/20 bg-red-400/[0.04]"
              }`}
            >
              <span className="mt-0.5 shrink-0">
                {isFound && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
                {isRenamed && <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />}
                {isMissing && <XCircle className="h-3.5 w-3.5 text-red-400" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className={`font-semibold ${isFound ? "text-emerald-200" : isRenamed ? "text-amber-200" : "text-red-200"}`}>
                  {section.required_title}
                </p>
                {isRenamed && section.matched_heading && (
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    Found as: <span className="text-amber-300">{section.matched_heading}</span>
                  </p>
                )}
                {isMissing && (
                  <p className="mt-0.5 text-[11px] text-slate-500">Not found in the guide</p>
                )}
              </div>
              <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                isFound ? "border-emerald-400/25 text-emerald-300" :
                isRenamed ? "border-amber-300/30 text-amber-300" :
                "border-red-400/30 text-red-300"
              }`}>
                {section.status}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-[11px] text-slate-500">
        Compliance is checked by comparing the required outline titles against the headings in the guide's Markdown.
      </p>
    </div>
  );
}

// --- Section Regeneration tab ---

const SECTION_ACTIONS = [
  { value: "simplify", label: "Simplify" },
  { value: "expand", label: "Expand" },
  { value: "add_mcqs", label: "Add MCQs" },
  { value: "summarize", label: "Summarize" },
  { value: "exam_notes", label: "Exam Notes" },
  { value: "expand_formulas", label: "Expand Formulas" },
  { value: "custom", label: "Custom instruction…" },
];

function SectionRegenerateTab({ jobId, manifest, onRegenerated }) {
  const [sections, setSections] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [action, setAction] = useState("simplify");
  const [instruction, setInstruction] = useState("");
  const [provider, setProvider] = useState(manifest?.provider || "");
  const [model, setModel] = useState(manifest?.model || "");
  const [configuredProviders, setConfiguredProviders] = useState([]);
  const [regenerating, setRegenerating] = useState(false);
  const [regenError, setRegenError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setSections(null);
    setLoadError(null);
    setSelectedIdx(null);
    setSuccessMsg(null);
    setRegenError(null);
    getJobSections(jobId)
      .then((d) => { if (!cancelled) setSections(d.sections ?? []); })
      .catch((e) => { if (!cancelled) setLoadError(e.message); });
    return () => { cancelled = true; };
  }, [jobId]);

  useEffect(() => {
    let cancelled = false;
    getOptions()
      .then((d) => {
        if (!cancelled) {
          const configured = (d.providers_v2 || []).filter((p) => p.configured);
          setConfiguredProviders(configured);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  async function handleRegenerate() {
    if (selectedIdx === null) return;
    setRegenerating(true);
    setRegenError(null);
    setSuccessMsg(null);
    try {
      await regenerateSection(jobId, selectedIdx, {
        action,
        instruction: action === "custom" ? instruction : "",
        provider: provider || null,
        model: model || null,
      });
      setSuccessMsg("Section regenerated. Use Version History to revert if needed.");
      onRegenerated?.();
    } catch (e) {
      setRegenError(e.message || "Regeneration failed.");
    } finally {
      setRegenerating(false);
    }
  }

  if (loadError) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-2 text-red-300 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {loadError}
      </div>
    );
  }

  if (sections === null) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-3 text-slate-300">
        <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
        <span>Loading sections…</span>
      </div>
    );
  }

  if (sections.length === 0) {
    return (
      <div className="flex min-h-48 items-center justify-center text-slate-400 text-sm">
        No heading sections found in this guide.
      </div>
    );
  }

  const canRegenerate = selectedIdx !== null && (action !== "custom" || instruction.trim()) && provider.trim();

  return (
    <div className="grid gap-4">
      <div>
        <h3 className="text-sm font-bold text-white">Select a section</h3>
        <div className="mt-2 grid gap-1.5 max-h-56 overflow-y-auto pr-1">
          {sections.map((section) => (
            <button
              key={section.index}
              type="button"
              onClick={() => { setSelectedIdx(section.index); setSuccessMsg(null); setRegenError(null); }}
              className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition ${
                selectedIdx === section.index
                  ? "border-ember-500/60 bg-ember-500/[0.08] text-white"
                  : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20 hover:text-white"
              }`}
            >
              <span className="font-mono text-[10px] text-slate-500 mr-2">
                {"#".repeat(section.heading_level)}
              </span>
              <span className="font-semibold">{section.heading_text || "(untitled)"}</span>
            </button>
          ))}
        </div>
      </div>

      {selectedIdx !== null && (
        <div className="grid gap-3 rounded-xl border border-white/10 bg-white/[0.025] p-3">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
              Action
            </label>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 outline-none focus:border-ember-500/40"
            >
              {SECTION_ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>

          {action === "custom" && (
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Instruction
              </label>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Describe what you want done to this section…"
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-ember-500/40 resize-y"
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Provider
              </label>
              {configuredProviders.length > 0 ? (
                <select
                  value={provider}
                  onChange={(e) => { setProvider(e.target.value); setModel(""); }}
                  className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 outline-none focus:border-ember-500/40"
                >
                  <option value="">Select provider…</option>
                  {configuredProviders.map((p) => (
                    <option key={p.id} value={p.id}>{p.display_name}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  placeholder="e.g. deepseek"
                  className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-ember-500/40"
                />
              )}
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Model
              </label>
              {configuredProviders.length > 0 && provider ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 outline-none focus:border-ember-500/40"
                >
                  <option value="">Default</option>
                  {(configuredProviders.find((p) => p.id === provider)?.available_models ?? []).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="default"
                  className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-ember-500/40"
                />
              )}
            </div>
          </div>

          {regenError && (
            <p className="rounded-lg border border-red-400/20 bg-red-400/10 p-2.5 text-xs text-red-300">
              {regenError}
            </p>
          )}

          {successMsg && (
            <p className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-2.5 text-xs text-emerald-200">
              {successMsg}{" "}
              <span className="text-slate-400">To undo, open the Version History tab.</span>
            </p>
          )}

          <button
            type="button"
            onClick={handleRegenerate}
            disabled={!canRegenerate || regenerating}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-ember-500/50 bg-ember-500/10 px-4 text-xs font-bold text-ember-300 transition hover:border-ember-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {regenerating ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Regenerating…</>
            ) : (
              <><Sparkles className="h-3.5 w-3.5" /> Regenerate Section</>
            )}
          </button>
        </div>
      )}

      <p className="text-[11px] text-slate-500">
        Only the selected section is rewritten. A version snapshot is created automatically — use Version History to revert.
      </p>
    </div>
  );
}

// --- Edit Markdown tab ---

function EditMarkdownTab({ jobId, onSaved }) {
  const [text, setText] = useState(null);
  const [original, setOriginal] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saveOk, setSaveOk] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setText(null);
    setOriginal(null);
    setLoadError(null);
    setSaveError(null);
    setSaveOk(false);
    getCleanMd(jobId)
      .then((t) => {
        if (!cancelled) { setText(t); setOriginal(t); }
      })
      .catch((e) => { if (!cancelled) setLoadError(e.message); });
    return () => { cancelled = true; };
  }, [jobId]);

  async function handleSave() {
    if (text === null) return;
    setSaving(true);
    setSaveError(null);
    setSaveOk(false);
    try {
      await putCleanMd(jobId, text);
      setOriginal(text);
      setSaveOk(true);
      setPreviewKey((k) => k + 1);
      onSaved?.();
    } catch (e) {
      setSaveError(e.message || "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  const isDirty = text !== null && text !== original;

  if (loadError) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-2 text-red-300 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {loadError}
      </div>
    );
  }

  if (text === null) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-3 text-slate-300">
        <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
        <span>Loading markdown…</span>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-white">Edit Markdown</h3>
          {isDirty && (
            <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-2 py-0.5 text-[10px] font-bold text-amber-200">
              unsaved
            </span>
          )}
          {saveOk && !isDirty && (
            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-bold text-emerald-200">
              saved
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:border-white/20 hover:text-white"
          >
            {showPreview ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            {showPreview ? "Hide Preview" : "Show Preview"}
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !isDirty}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ember-500/50 bg-ember-500/10 px-3 text-xs font-bold text-ember-300 transition hover:border-ember-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…</>
            ) : (
              <><RefreshCw className="h-3.5 w-3.5" /> Save & Re-render</>
            )}
          </button>
        </div>
      </div>

      {saveError && (
        <p className="rounded-lg border border-red-400/20 bg-red-400/10 p-2.5 text-xs text-red-300">{saveError}</p>
      )}

      <div className={showPreview ? "grid gap-3 lg:grid-cols-2" : ""}>
        <textarea
          value={text}
          onChange={(e) => { setText(e.target.value); setSaveOk(false); }}
          spellCheck={false}
          className="min-h-[480px] w-full rounded-xl border border-white/10 bg-[#070B14] p-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-ember-500/40 resize-y"
        />
        {showPreview && (
          <iframe
            key={previewKey}
            src={`/api/jobs/${encodeURIComponent(jobId)}/artifacts/final.html?disposition=inline`}
            title="HTML preview"
            sandbox="allow-same-origin allow-scripts"
            className="min-h-[480px] w-full rounded-xl border border-white/10 bg-white"
          />
        )}
      </div>

      <p className="text-[11px] text-slate-500">
        Saving re-renders PDF and HTML from the edited markdown. A version snapshot is created automatically before each save.
      </p>
    </div>
  );
}

// --- Version History tab ---

function computeLineDiff(oldText, newText) {
  const a = (oldText || "").split("\n");
  const b = (newText || "").split("\n");
  if (a.length > 600 || b.length > 600) {
    return [{ type: "info", text: "(File too large for inline diff — download both versions to compare)" }];
  }
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  const result = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.unshift({ type: "same", text: a[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: "added", text: b[j - 1] });
      j--;
    } else {
      result.unshift({ type: "removed", text: a[i - 1] });
      i--;
    }
  }
  return result;
}

function VersionHistoryTab({ jobId, onReverted }) {
  const [versions, setVersions] = useState([]);
  const [currentText, setCurrentText] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [reverting, setReverting] = useState(null);
  const [revertError, setRevertError] = useState(null);
  const [expandedDiff, setExpandedDiff] = useState(null);
  const [diffContent, setDiffContent] = useState({});
  const [loadingDiff, setLoadingDiff] = useState(null);

  function reload() {
    return Promise.all([getJobVersions(jobId), getCleanMd(jobId)])
      .then(([vData, text]) => {
        setVersions(vData.versions ?? []);
        setCurrentText(text);
      });
  }

  useEffect(() => {
    setVersions([]);
    setCurrentText(null);
    setLoadError(null);
    setExpandedDiff(null);
    setDiffContent({});
    reload().catch((e) => setLoadError(e.message));
  }, [jobId]);

  async function handleRevert(version) {
    setReverting(version);
    setRevertError(null);
    try {
      await revertJobVersion(jobId, version);
      await reload();
      setExpandedDiff(null);
      setDiffContent({});
      onReverted?.();
    } catch (e) {
      setRevertError(e.message || "Revert failed.");
    } finally {
      setReverting(null);
    }
  }

  async function handleToggleDiff(version) {
    if (expandedDiff === version) {
      setExpandedDiff(null);
      return;
    }
    setExpandedDiff(version);
    if (diffContent[version] !== undefined) return;
    setLoadingDiff(version);
    try {
      const text = await getVersionCleanMd(jobId, version);
      setDiffContent((prev) => ({ ...prev, [version]: text }));
    } catch {
      setDiffContent((prev) => ({ ...prev, [version]: null }));
    } finally {
      setLoadingDiff(null);
    }
  }

  const SOURCE_LABELS = {
    generated: { label: "Generated", tone: "border-sky-400/25 bg-sky-400/10 text-sky-200" },
    edited: { label: "Edited", tone: "border-violet-400/30 bg-violet-400/10 text-violet-200" },
    rerendered: { label: "Re-rendered", tone: "border-white/10 bg-white/[0.04] text-slate-300" },
    reverted: { label: "Reverted", tone: "border-amber-300/30 bg-amber-300/10 text-amber-200" },
  };

  if (loadError) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-2 text-red-300 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {loadError}
      </div>
    );
  }

  if (currentText === null) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-3 text-slate-300">
        <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
        <span>Loading history…</span>
      </div>
    );
  }

  if (versions.length === 0) {
    return <p className="mt-4 text-sm text-slate-400">No version history yet.</p>;
  }

  const latestVersion = versions[versions.length - 1]?.version;

  return (
    <div className="grid gap-3">
      <h3 className="text-sm font-bold text-white">{versions.length} version{versions.length !== 1 ? "s" : ""}</h3>

      {revertError && (
        <p className="rounded-lg border border-red-400/20 bg-red-400/10 p-2.5 text-xs text-red-300">{revertError}</p>
      )}

      <div className="grid gap-2">
        {[...versions].reverse().map((v) => {
          const isLatest = v.version === latestVersion;
          const srcInfo = SOURCE_LABELS[v.source] ?? { label: v.source, tone: "border-white/10 bg-white/[0.04] text-slate-300" };
          const isExpanded = expandedDiff === v.version;
          const vDiff = isExpanded ? diffContent[v.version] : undefined;
          const diff = vDiff !== undefined && currentText !== null ? computeLineDiff(vDiff, currentText) : null;

          return (
            <div key={v.version} className="rounded-xl border border-white/10 bg-white/[0.035] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-bold text-white">v{v.version}</span>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${srcInfo.tone}`}>
                    {srcInfo.label}
                  </span>
                  {isLatest && (
                    <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-bold text-emerald-200">
                      current
                    </span>
                  )}
                  <span className="text-[11px] text-slate-500">{v.created_at}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleToggleDiff(v.version)}
                    className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-[11px] font-bold text-slate-300 transition hover:border-white/20 hover:text-white"
                  >
                    {loadingDiff === v.version ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Eye className="h-3 w-3" />
                    )}
                    {isExpanded ? "Hide" : "Diff vs current"}
                  </button>
                  {!isLatest && (
                    <button
                      type="button"
                      onClick={() => handleRevert(v.version)}
                      disabled={reverting !== null}
                      className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-ember-500/40 bg-ember-500/10 px-2.5 text-[11px] font-bold text-ember-300 transition hover:border-ember-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {reverting === v.version ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3 w-3" />
                      )}
                      Restore
                    </button>
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="mt-3">
                  {loadingDiff === v.version || vDiff === undefined ? (
                    <div className="flex h-12 items-center gap-2 text-xs text-slate-400">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-ember-500" /> Loading…
                    </div>
                  ) : vDiff === null ? (
                    <p className="text-xs text-red-300">Could not load version content.</p>
                  ) : isLatest ? (
                    <pre className="max-h-72 overflow-auto rounded-lg border border-white/10 bg-[#070B14] p-2.5 font-mono text-[11px] leading-5 text-slate-300 whitespace-pre-wrap">{vDiff}</pre>
                  ) : diff ? (
                    <DiffView diff={diff} />
                  ) : null}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-slate-500">
        Restoring a version creates a new snapshot — history is never deleted.
      </p>
    </div>
  );
}

function DiffView({ diff }) {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const hasChanges = diff.some((l) => l.type !== "same" && l.type !== "info");

  if (!hasChanges) {
    return <p className="text-xs text-slate-400">No differences — versions are identical.</p>;
  }

  const addedCount = diff.filter((l) => l.type === "added").length;
  const removedCount = diff.filter((l) => l.type === "removed").length;

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex gap-2 text-[11px]">
          {addedCount > 0 && <span className="text-emerald-300">+{addedCount} added</span>}
          {removedCount > 0 && <span className="text-red-300">−{removedCount} removed</span>}
        </div>
        <button
          type="button"
          onClick={() => setShowUnchanged((v) => !v)}
          className="text-[11px] text-slate-500 hover:text-slate-300"
        >
          {showUnchanged ? "Hide unchanged" : "Show all lines"}
        </button>
      </div>
      <pre className="max-h-72 overflow-auto rounded-lg border border-white/10 bg-[#070B14] p-2.5 font-mono text-[11px] leading-5 whitespace-pre-wrap">
        {diff.map((line, i) => {
          if (line.type === "same" && !showUnchanged) return null;
          const cls =
            line.type === "added" ? "text-emerald-300 bg-emerald-900/20" :
            line.type === "removed" ? "text-red-300 bg-red-900/20 line-through opacity-70" :
            line.type === "info" ? "text-slate-500 italic" :
            "text-slate-400";
          const prefix = line.type === "added" ? "+ " : line.type === "removed" ? "− " : "  ";
          return (
            <span key={i} className={`block ${cls}`}>{prefix}{line.text}</span>
          );
        })}
      </pre>
    </div>
  );
}

// --- Quiz / Flashcards tab ---

const QUIZ_TYPE_OPTIONS = [
  { value: "mcq", label: "Multiple Choice" },
  { value: "true_false", label: "True / False" },
  { value: "fill_blank", label: "Fill in the Blank" },
  { value: "short_answer", label: "Short Answer" },
  { value: "flashcards", label: "Flashcards" },
];

const QUIZ_COUNT_OPTIONS = [10, 25, 50, 100];
const QUIZ_DIFFICULTY_OPTIONS = ["easy", "medium", "exam"];
const QUIZ_FOCUS_OPTIONS = [
  { value: "all", label: "All concepts" },
  { value: "definitions", label: "Definitions & terms" },
  { value: "formulas", label: "Formulas & math" },
  { value: "examples", label: "Examples & applications" },
];

function QuizTab({ jobId, manifest }) {
  // Config
  const [questionTypes, setQuestionTypes] = useState(["mcq", "flashcards"]);
  const [count, setCount] = useState(25);
  const [difficulty, setDifficulty] = useState("medium");
  const [focus, setFocus] = useState("all");

  // Generation
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);

  // Quiz list
  const [quizzes, setQuizzes] = useState(null);
  const [quizzesError, setQuizzesError] = useState(null);

  // Active quiz view
  const [activeQuiz, setActiveQuiz] = useState(null);
  const [showAnswers, setShowAnswers] = useState(false);
  const [openAnswerIdx, setOpenAnswerIdx] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setQuizzes(null);
    setQuizzesError(null);
    setActiveQuiz(null);
    listQuizzes(jobId)
      .then((d) => { if (!cancelled) setQuizzes(d.quizzes ?? []); })
      .catch((e) => { if (!cancelled) setQuizzesError(e.message); });
    return () => { cancelled = true; };
  }, [jobId]);

  function toggleType(type) {
    setQuestionTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  }

  async function handleGenerate() {
    if (questionTypes.length === 0) return;
    setGenerating(true);
    setGenError(null);
    try {
      const data = await generateQuiz(jobId, { questionTypes, count, difficulty, focus });
      setQuizzes((prev) => [...(prev ?? []), {
        n: data.n,
        created_at: data.created_at,
        item_count: data.item_count,
        config: data.config,
      }]);
      setActiveQuiz(data);
      setShowAnswers(false);
      setOpenAnswerIdx(null);
    } catch (e) {
      setGenError(e.message || "Quiz generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleLoadQuiz(n) {
    if (activeQuiz?.n === n) return;
    try {
      const data = await getQuiz(jobId, n);
      setActiveQuiz(data);
      setShowAnswers(false);
      setOpenAnswerIdx(null);
    } catch (e) {
      setGenError(e.message || "Could not load quiz.");
    }
  }

  const canGenerate = questionTypes.length > 0 && !generating;

  return (
    <div className="grid gap-5">
      {/* Config panel */}
      <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
        <h3 className="text-sm font-bold text-white mb-3">Generate Quiz</h3>

        <div className="grid gap-3">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-2">
              Question Types
            </label>
            <div className="flex flex-wrap gap-2">
              {QUIZ_TYPE_OPTIONS.map((opt) => {
                const checked = questionTypes.includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleType(opt.value)}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold transition ${
                      checked
                        ? "border-ember-500/60 bg-ember-500/15 text-ember-300"
                        : "border-white/10 bg-white/[0.035] text-slate-400 hover:border-white/20 hover:text-white"
                    }`}
                  >
                    {checked && <CheckCircle2 className="h-3 w-3" />}
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Count
              </label>
              <select
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 outline-none focus:border-ember-500/40"
              >
                {QUIZ_COUNT_OPTIONS.map((n) => (
                  <option key={n} value={n}>{n} questions</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Difficulty
              </label>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 outline-none focus:border-ember-500/40"
              >
                {QUIZ_DIFFICULTY_OPTIONS.map((d) => (
                  <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Focus
              </label>
              <select
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-[#070B14] px-3 py-2 text-xs text-slate-200 outline-none focus:border-ember-500/40"
              >
                {QUIZ_FOCUS_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
          </div>

          {genError && (
            <p className="rounded-lg border border-red-400/20 bg-red-400/10 p-2.5 text-xs text-red-300">
              {genError}
            </p>
          )}

          <button
            type="button"
            onClick={handleGenerate}
            disabled={!canGenerate}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-ember-500/50 bg-ember-500/10 px-4 text-xs font-bold text-ember-300 transition hover:border-ember-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {generating ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…</>
            ) : (
              <><Sparkles className="h-3.5 w-3.5" /> Generate Quiz</>
            )}
          </button>
        </div>
      </section>

      {/* Previously generated quizzes */}
      {quizzesError && (
        <p className="text-xs text-red-300">{quizzesError}</p>
      )}

      {quizzes === null && !quizzesError && (
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-ember-500" />
          Loading quizzes…
        </div>
      )}

      {quizzes !== null && quizzes.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
          <h3 className="text-sm font-bold text-white mb-2">Saved Quizzes</h3>
          <div className="grid gap-1.5">
            {[...quizzes].reverse().map((q) => {
              const isActive = activeQuiz?.n === q.n;
              const types = (q.config?.question_types ?? []).join(", ");
              return (
                <button
                  key={q.n}
                  type="button"
                  onClick={() => handleLoadQuiz(q.n)}
                  className={`w-full rounded-xl border px-3 py-2 text-left text-xs transition ${
                    isActive
                      ? "border-ember-500/60 bg-ember-500/[0.08] text-white"
                      : "border-white/10 bg-[#070B14] text-slate-300 hover:border-white/20 hover:text-white"
                  }`}
                >
                  <span className="font-bold">Quiz #{q.n}</span>
                  <span className="ml-2 text-slate-400">{q.item_count} questions · {types} · {q.config?.difficulty}</span>
                  <span className="ml-2 text-slate-500">{q.created_at?.slice(0, 10)}</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Active quiz display */}
      {activeQuiz && (
        <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div>
              <h3 className="text-sm font-bold text-white">
                Quiz #{activeQuiz.n} · {activeQuiz.item_count} questions
              </h3>
              <p className="mt-0.5 text-[11px] text-slate-400">
                {(activeQuiz.config?.question_types ?? []).join(", ")} · {activeQuiz.config?.difficulty} · {activeQuiz.config?.focus}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => { setShowAnswers((v) => !v); setOpenAnswerIdx(null); }}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:border-white/20 hover:text-white"
              >
                {showAnswers ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                {showAnswers ? "Hide All Answers" : "Show All Answers"}
              </button>
            </div>
          </div>

          {/* Export buttons */}
          <div className="flex flex-wrap gap-2 mb-4 pb-3 border-b border-white/10">
            <span className="self-center text-[11px] font-bold uppercase tracking-wide text-slate-500">Export:</span>
            {[
              { format: "csv", label: "CSV" },
              { format: "anki_tsv", label: "Anki TSV" },
              { format: "quizlet", label: "Quizlet" },
            ].map(({ format, label }) => (
              <a
                key={format}
                href={quizExportUrl(jobId, activeQuiz.n, format)}
                download
                className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[11px] font-bold text-slate-300 transition hover:border-ember-500/60 hover:text-white"
              >
                <Download className="h-3 w-3" />
                {label}
              </a>
            ))}
          </div>

          {/* Questions list */}
          <div className="grid gap-3">
            {(activeQuiz.items ?? []).map((item, idx) => {
              const answerVisible = showAnswers || openAnswerIdx === idx;
              return (
                <QuizQuestionCard
                  key={idx}
                  item={item}
                  index={idx}
                  answerVisible={answerVisible}
                  onToggleAnswer={() => setOpenAnswerIdx(openAnswerIdx === idx ? null : idx)}
                  showAllAnswers={showAnswers}
                />
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

function QuizQuestionCard({ item, index, answerVisible, onToggleAnswer, showAllAnswers }) {
  const typeLabel = {
    mcq: "MCQ",
    true_false: "T/F",
    fill_blank: "Fill",
    short_answer: "Short",
    flashcards: "Flash",
  }[item.type] ?? item.type;

  const typeTone = {
    mcq: "border-sky-400/25 bg-sky-400/10 text-sky-200",
    true_false: "border-violet-400/30 bg-violet-400/10 text-violet-200",
    fill_blank: "border-amber-300/30 bg-amber-300/10 text-amber-100",
    short_answer: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
    flashcards: "border-ember-500/30 bg-ember-500/10 text-ember-200",
  }[item.type] ?? "border-white/10 bg-white/[0.04] text-slate-300";

  return (
    <div className="rounded-xl border border-white/10 bg-[#070B14] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <span className="mt-0.5 shrink-0 grid h-5 w-5 place-items-center rounded bg-white/[0.06] font-mono text-[10px] font-bold text-slate-400">
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-100 leading-5">{item.question}</p>
            {item.type === "mcq" && item.options && (
              <ul className="mt-2 grid gap-1">
                {item.options.map((opt, oi) => {
                  const letter = opt.charAt(0).toUpperCase();
                  const isCorrect = answerVisible && letter === (item.answer ?? "").toUpperCase();
                  return (
                    <li
                      key={oi}
                      className={`rounded-lg border px-2.5 py-1 text-[11px] transition ${
                        isCorrect
                          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200 font-bold"
                          : "border-white/[0.06] bg-white/[0.025] text-slate-300"
                      }`}
                    >
                      {opt}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-1.5">
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${typeTone}`}>
            {typeLabel}
          </span>
        </div>
      </div>

      {item.topic && (
        <p className="mt-2 text-[10px] text-slate-500 ml-7">Topic: {item.topic}</p>
      )}

      {/* Answer toggle (individual) — only when not showing all answers */}
      {!showAllAnswers && (
        <button
          type="button"
          onClick={onToggleAnswer}
          className="mt-2 ml-7 inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-500 transition hover:text-ember-300"
        >
          {answerVisible ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {answerVisible ? "Hide answer" : "Show answer"}
        </button>
      )}

      {answerVisible && (
        <div className="mt-2 ml-7 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2">
          <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-500 mb-0.5">Answer</p>
          <p className="text-xs text-emerald-200">{item.answer}</p>
        </div>
      )}
    </div>
  );
}

// forwardRef wrapper so Home can imperatively open the job-details drawer for a
// favorite guide (see useImperativeHandle above).
const RecentJobsPanelWithRef = forwardRef(RecentJobsPanel);
export default RecentJobsPanelWithRef;
