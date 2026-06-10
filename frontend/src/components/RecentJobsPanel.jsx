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
import MathVerificationPanel from "./MathVerificationPanel";

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
  if (status === "done") return "pill-green";
  if (status?.includes("failed")) return "pill-red";
  return "pill-amber";
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

function RecentJobsPanel({ refreshKey = 0, embedded = false, onSelectedJobChange, maxItems = null, onViewAll = null }, ref) {
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

  // On Home the embedded panel shows only the first `maxItems` guides with a
  // working "View all" that deep-links into the Library (newest sort). When no
  // handler/cap is provided the panel behaves exactly as before.
  const visibleJobs = maxItems ? jobs.slice(0, maxItems) : jobs;
  const viewAllAction = onViewAll ? (
    <button type="button" className="panel-link btn-reset" onClick={onViewAll}>
      View all
    </button>
  ) : (
    <span className="panel-link">View all</span>
  );

  const listPanel = (
    <Panel title="Recent Guides" action={viewAllAction}>
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
          {visibleJobs.map((job) => {
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
  return (
    <span className={`pill ${style.isCustom ? "pill-indigo" : "pill-soft"}`}>
      {style.name}
      <span style={{ opacity: 0.7 }}>· {style.isCustom ? "Custom" : "Built-in"}</span>
    </span>
  );
}

export function FolderPill({ folder }) {
  if (!folder || !folder.name) {
    return null;
  }
  return (
    <span className="pill pill-soft">
      <FolderClosed style={{ width: 13, height: 13 }} color={folderColor(folder)} />
      {folder.name}
    </span>
  );
}

function AttachmentPill({ count }) {
  return (
    <span className="sg-tag sg-tag-green">
      <Paperclip />
      {count} {count === 1 ? "source" : "sources"}
    </span>
  );
}

function WarningPill({ count }) {
  return (
    <span className="sg-tag sg-tag-amber">
      <AlertCircle />
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
    <section>
      <div className="sg-head-row">
        <h3>Attached sources</h3>
        <div className="sg-chip-row">
          <AttachmentPill count={summary.count} />
          {summary.hasWarnings && <WarningPill count={summary.warningCount} />}
        </div>
      </div>
      <div className="sg-stack" style={{ marginTop: 12 }}>
        {attachments.map((attachment, index) => {
          const warnings = attachment.warnings ?? [];
          return (
            <div key={`${attachment.filename}-${index}`} className="sg-att-item">
              <div className="sg-att-item-top">
                <span className="sg-att-name">{attachment.filename}</span>
                <span className={`sg-tag ${attachment.status === "extracted" ? "sg-tag-green" : "sg-tag-amber"}`}>
                  {attachment.status || "unknown"}
                </span>
              </div>
              <div className="sg-att-meta">
                <span>{attachment.mode || attachment.extension || "unsupported"}</span>
                <span>{Number(attachment.extracted_chars || 0).toLocaleString()} chars</span>
                {attachment.truncated && <span>truncated</span>}
              </div>
              {warnings.length > 0 && (
                <div className="sg-stack" style={{ marginTop: 8 }}>
                  {warnings.map((warning, warningIndex) => (
                    <p key={warningIndex} className="sg-notice sg-notice-amber">{warning}</p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MetaTerm({ label, value, mono = false }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd style={{ wordBreak: "break-word", fontFamily: mono ? "var(--mono)" : undefined, fontSize: mono ? "13px" : undefined }}>
        {value || "unavailable"}
      </dd>
    </div>
  );
}

function ArtifactLinkGrid({ jobId, artifacts }) {
  if (!artifacts?.length) {
    return <p style={{ marginTop: 12 }}>No artifacts available</p>;
  }

  return (
    <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
      {artifacts.map((artifact) => {
        const Icon = artifact.icon || artifactIcon(artifact.name);
        const href = artifact.url ? apiArtifactUrl(artifact.url) : artifactUrl(jobId, artifact.name);
        const previewHref = artifact.name === "final.pdf" ? `${href}?disposition=inline` : href;
        return (
          <div key={artifact.name} className="sg-art-row">
            <div className="sg-art-top">
              <span className="sg-art-name">
                <Icon />
                <span className="truncate">{artifact.label}</span>
              </span>
              <span className={`pill ${artifact.available === false ? "pill-soft" : "pill-green"}`}>
                {artifact.available === false ? "missing" : "ready"}
              </span>
            </div>
            {artifact.available !== false && (
              <div className="sg-art-actions">
                <a href={href}>
                  <Download style={{ width: 14, height: 14 }} />
                  Download
                </a>
                {(artifact.name === "final.pdf" || artifact.name === "final.html") && (
                  <a href={previewHref} target="_blank" rel="noreferrer">
                    <ExternalLink style={{ width: 14, height: 14 }} />
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
    { key: "verification", label: "Verification", icon: CheckCircle2 },
    { key: "quiz", label: "Quiz", icon: BookOpen, disabled: !canEdit },
    { key: "outline", label: "Outline", icon: ListChecks, disabled: !canEdit },
    { key: "sections", label: "Sections", icon: Layers, disabled: !canEdit },
    { key: "edit", label: "Edit Markdown", icon: Edit3, disabled: !canEdit },
    { key: "history", label: "Version History", icon: Clock, disabled: !canEdit },
  ];

  return (
    <div className="sg-drawer-root">
      <button type="button" className="sg-drawer-scrim" onClick={onClose} aria-label="Close job details" />
      <aside className="sg-drawer-sheet">
        <div className="sg-drawer-head">
          <div className="min-w-0">
            <p className="sg-drawer-eyebrow">Job Details</p>
            <h2 className="sg-drawer-title">
              {manifest ? jobTitle(manifest) : "Loading job"}
            </h2>
            {manifest?.id && <p className="sg-drawer-id">{manifest.id}</p>}
          </div>
          <button type="button" onClick={onClose} className="sg-drawer-close" aria-label="Close">
            <X />
          </button>
        </div>

        {/* Tab bar */}
        {!loading && !error && manifest && (
          <div className="sg-drawer-tabs">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  type="button"
                  disabled={tab.disabled}
                  onClick={() => setDrawerTab(tab.key)}
                  className={`sg-drawer-tab${drawerTab === tab.key ? " active" : ""}`}
                >
                  {Icon && <Icon />}
                  {tab.label}
                </button>
              );
            })}
          </div>
        )}

        <div className="sg-drawer-body">
          {loading && (
            <div className="recent-state">
              <Loader2 className="sg-spin" />
              <span>Loading details...</span>
            </div>
          )}

          {!loading && error && (
            <div className="recent-state" style={{ color: "var(--red)" }}>
              <AlertCircle />
              <span>Could not load job details</span>
            </div>
          )}

          {!loading && !error && manifest && drawerTab === "details" && (
            <div className="sg-tab-stack">
              <section>
                <div className="sg-meta-pills">
                  <StatusPill status={manifest.status} />
                  <span className="pill pill-soft">
                    {manifest.path_mode || manifest.input_type || "input"}
                  </span>
                  {manifest.provider && (
                    <span className="pill pill-soft">
                      {formatProviderModel(manifest)}
                    </span>
                  )}
                  {style && <StylePill style={style} />}
                  {folder && <FolderPill folder={folder} />}
                </div>
                <dl>
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
                  <ol>
                    {manifest.outline_titles.map((sectionTitle, index) => (
                      <li key={`${sectionTitle}-${index}`} className="sg-num-row">
                        <span className="sg-num">{index + 1}</span>
                        <span className="t">{sectionTitle}</span>
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
                  <div className="sg-stack">
                    {extractionWarnings.map((warning, index) => (
                      <p key={index} className="sg-notice sg-notice-amber">
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

          {!loading && !error && manifest && drawerTab === "verification" && (
            <MathVerificationPanel jobId={manifest.id} />
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
  return <span className="sg-tag sg-tag-red">{label}</span>;
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
    <section>
      <div className="sg-row-between">
        <div className="sg-row">
          <AlertTriangle style={{ width: 16, height: 16, flex: "none", color: "var(--amber)" }} />
          <span style={{ color: "var(--text)", fontWeight: 600, fontSize: 13.5 }}>
            {count} math expression{count === 1 ? "" : "s"} couldn&apos;t render
          </span>
        </div>
        {canEdit && (
          <button type="button" onClick={onEdit}>
            <Edit3 style={{ width: 14, height: 14 }} />
            Fix in Markdown editor
          </button>
        )}
      </div>
      <p>
        The guide rendered, but these expressions show as error-marked spans. Edit
        them in the Markdown editor and re-render to clean them up.
      </p>
      <ul style={{ marginTop: 12 }}>
        {failures.map((failure, index) => (
          <li key={index} style={{ border: "1px solid var(--card-border)", background: "var(--card)", borderRadius: 9, padding: 10 }}>
            <code>
              {failure.display_mode ? "display" : "inline"}: {failure.expr}
            </code>
            {failure.message && (
              <span style={{ marginTop: 4, display: "block", color: "var(--muted)", fontSize: 12 }}>{failure.message}</span>
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
    <section className="sg-danger-card">
      <div className="sg-head-row">
        <div className="sg-chip-row">
          <AlertCircle style={{ color: "var(--red)" }} />
          <span style={{ color: "var(--text)", fontWeight: 600, fontSize: 13.5 }}>Generation failed</span>
          <ErrorCategoryBadge category={category} />
        </div>
        <div className="sg-btn-row">
          {(hasLog || validation?.available) && (
            <button type="button" onClick={() => setLogsExpanded((v) => !v)}>
              {logsExpanded ? <ChevronUp /> : <ChevronDown />}
              View logs
            </button>
          )}
          <button type="button" onClick={handleRetry} disabled={retrying} className="sg-btn-accent">
            {retrying
              ? <><Loader2 className="sg-spin" /> Retrying…</>
              : <><RefreshCw /> Try again</>}
          </button>
        </div>
      </div>

      {message && (
        <p className="sg-notice sg-notice-red" style={{ marginTop: 12 }}>
          {message}
        </p>
      )}

      {retryError && (
        <p className="sg-notice sg-notice-red" style={{ marginTop: 8 }}>{retryError}</p>
      )}

      {logsExpanded && (
        <div className="sg-stack" style={{ marginTop: 14 }}>
          {hasLog && renderLog.last_lines?.length > 0 && (
            <div>
              <p className="sg-sub-label" style={{ marginBottom: 6 }}>Render log (last lines)</p>
              <pre className="sg-pre">
                {renderLog.last_lines.join("\n")}
              </pre>
            </div>
          )}
          {validation?.available && validation.error_count > 0 && (
            <div>
              <p className="sg-sub-label" style={{ marginBottom: 6 }}>
                Math validation — {validation.error_count} issue{validation.error_count !== 1 ? "s" : ""}
              </p>
              <p className="sg-hint">
                Download <span style={{ fontFamily: "var(--mono)" }}>validation.json</span> from Artifacts for the full expression list.
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
    <section>
      <h3>{title}</h3>
      <div style={{ marginTop: 10 }}>{children}</div>
    </section>
  );
}

function StatusPill({ status }) {
  return <span className={`pill ${statusClass(status)}`}>{status || "unknown"}</span>;
}

function ValidationSummary({ validation, manifest }) {
  const fallback = manifest?.math_validation;
  const ok = validation?.ok ?? fallback?.ok;
  const errorCount = validation?.error_count ?? fallback?.errors ?? 0;
  const displayBlocks = validation?.display_blocks ?? fallback?.display_blocks ?? 0;
  const inlineFormulas = validation?.inline_formulas ?? fallback?.inline_formulas ?? 0;
  return (
    <div className="sg-grid-3">
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
    return <p className="sg-hint">Render log is not available.</p>;
  }
  return (
    <div className="sg-stack">
      <InfoTile label="Lines" value={String(renderLog.line_count || 0)} tone="neutral" />
      {renderLog.last_lines?.length > 0 && (
        <pre className="sg-pre">
          {renderLog.last_lines.join("\n")}
        </pre>
      )}
    </div>
  );
}

function InfoTile({ icon: Icon, label, value, tone = "neutral" }) {
  return (
    <div className={`sg-tile${tone === "good" ? " good" : tone === "warn" ? " warn" : ""}`}>
      <div className="sg-tile-label">
        {Icon && <Icon />}
        {label}
      </div>
      <div className="sg-tile-value">{value}</div>
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
      <div className="recent-state">
        <Loader2 className="sg-spin" />
        <span>Checking outline compliance…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="recent-state" style={{ color: "var(--red)" }}>
        <AlertCircle />
        {error}
      </div>
    );
  }

  if (!compliance?.has_outline) {
    return (
      <div className="recent-state">
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
    <div className="sg-tab-stack">
      <div className="sg-head-row">
        <h3>Outline Compliance</h3>
        <div className="sg-chip-row">
          {counts.found > 0 && <span className="sg-tag sg-tag-green">{counts.found} found</span>}
          {counts.renamed > 0 && <span className="sg-tag sg-tag-amber">{counts.renamed} renamed</span>}
          {counts.missing > 0 && <span className="sg-tag sg-tag-red">{counts.missing} missing</span>}
        </div>
      </div>

      <ol className="sg-stack">
        {sections.map((section, i) => {
          const isFound = section.status === "found";
          const isRenamed = section.status === "renamed";
          const isMissing = section.status === "missing";
          return (
            <li
              key={i}
              className={`sg-card-row ${isFound ? "good" : isRenamed ? "warn" : "bad"}`}
              style={{ display: "flex", alignItems: "flex-start", gap: 10 }}
            >
              <span style={{ flex: "none", marginTop: 1 }}>
                {isFound && <CheckCircle2 style={{ color: "var(--green)" }} />}
                {isRenamed && <AlertTriangle style={{ color: "var(--amber)" }} />}
                {isMissing && <XCircle style={{ color: "var(--red)" }} />}
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <p style={{ fontWeight: 600, color: isFound ? "#6EE7B7" : isRenamed ? "#F4C76B" : "#FCA5A5" }}>
                  {section.required_title}
                </p>
                {isRenamed && section.matched_heading && (
                  <p className="sg-hint" style={{ marginTop: 2 }}>
                    Found as: <span style={{ color: "#F4C76B" }}>{section.matched_heading}</span>
                  </p>
                )}
                {isMissing && (
                  <p className="sg-hint" style={{ marginTop: 2 }}>Not found in the guide</p>
                )}
              </div>
              <span className={`sg-tag ${isFound ? "sg-tag-green" : isRenamed ? "sg-tag-amber" : "sg-tag-red"}`}>
                {section.status}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="sg-hint">
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
      <div className="recent-state" style={{ color: "var(--red)" }}>
        <AlertCircle />
        {loadError}
      </div>
    );
  }

  if (sections === null) {
    return (
      <div className="recent-state">
        <Loader2 className="sg-spin" />
        <span>Loading sections…</span>
      </div>
    );
  }

  if (sections.length === 0) {
    return (
      <div className="recent-state">
        No heading sections found in this guide.
      </div>
    );
  }

  const canRegenerate = selectedIdx !== null && (action !== "custom" || instruction.trim()) && provider.trim();

  return (
    <div className="sg-tab-stack">
      <div>
        <h3>Select a section</h3>
        <div className="sg-stack" style={{ marginTop: 8, maxHeight: 224, overflowY: "auto", paddingRight: 4 }}>
          {sections.map((section) => (
            <button
              key={section.index}
              type="button"
              onClick={() => { setSelectedIdx(section.index); setSuccessMsg(null); setRegenError(null); }}
              className={`sg-opt-btn${selectedIdx === section.index ? " sel" : ""}`}
            >
              <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", marginRight: 8 }}>
                {"#".repeat(section.heading_level)}
              </span>
              <span style={{ fontWeight: 600 }}>{section.heading_text || "(untitled)"}</span>
            </button>
          ))}
        </div>
      </div>

      {selectedIdx !== null && (
        <div className="sg-form-sub">
          <div>
            <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
              Action
            </label>
            <select value={action} onChange={(e) => setAction(e.target.value)}>
              {SECTION_ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>

          {action === "custom" && (
            <div>
              <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
                Instruction
              </label>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Describe what you want done to this section…"
                rows={3}
                style={{ minHeight: 84 }}
              />
            </div>
          )}

          <div className="sg-grid-2">
            <div>
              <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
                Provider
              </label>
              {configuredProviders.length > 0 ? (
                <select value={provider} onChange={(e) => { setProvider(e.target.value); setModel(""); }}>
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
                />
              )}
            </div>
            <div>
              <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
                Model
              </label>
              {configuredProviders.length > 0 && provider ? (
                <select value={model} onChange={(e) => setModel(e.target.value)}>
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
                />
              )}
            </div>
          </div>

          {regenError && (
            <p className="sg-notice sg-notice-red">
              {regenError}
            </p>
          )}

          {successMsg && (
            <p className="sg-notice sg-notice-green">
              {successMsg}{" "}
              <span style={{ color: "var(--muted)" }}>To undo, open the Version History tab.</span>
            </p>
          )}

          <button
            type="button"
            onClick={handleRegenerate}
            disabled={!canRegenerate || regenerating}
            className="sg-btn-accent"
            style={{ justifyContent: "center" }}
          >
            {regenerating ? (
              <><Loader2 className="sg-spin" /> Regenerating…</>
            ) : (
              <><Sparkles /> Regenerate Section</>
            )}
          </button>
        </div>
      )}

      <p className="sg-hint">
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
      <div className="recent-state" style={{ color: "var(--red)" }}>
        <AlertCircle />
        {loadError}
      </div>
    );
  }

  if (text === null) {
    return (
      <div className="recent-state">
        <Loader2 className="sg-spin" />
        <span>Loading markdown…</span>
      </div>
    );
  }

  return (
    <div className="sg-tab-stack">
      <div className="sg-head-row">
        <div className="sg-chip-row">
          <h3>Edit Markdown</h3>
          {isDirty && <span className="sg-tag sg-tag-amber">unsaved</span>}
          {saveOk && !isDirty && <span className="sg-tag sg-tag-green">saved</span>}
        </div>
        <div className="sg-btn-row">
          <button type="button" onClick={() => setShowPreview((v) => !v)}>
            {showPreview ? <EyeOff /> : <Eye />}
            {showPreview ? "Hide Preview" : "Show Preview"}
          </button>
          <button type="button" onClick={handleSave} disabled={saving || !isDirty} className="sg-btn-accent">
            {saving ? (
              <><Loader2 className="sg-spin" /> Saving…</>
            ) : (
              <><RefreshCw /> Save & Re-render</>
            )}
          </button>
        </div>
      </div>

      {saveError && (
        <p className="sg-notice sg-notice-red">{saveError}</p>
      )}

      <div className={showPreview ? "sg-grid-2" : ""}>
        <textarea
          value={text}
          onChange={(e) => { setText(e.target.value); setSaveOk(false); }}
          spellCheck={false}
          style={{ minHeight: 480, fontSize: 13, lineHeight: 1.5 }}
        />
        {showPreview && (
          <iframe
            key={previewKey}
            src={`/api/jobs/${encodeURIComponent(jobId)}/artifacts/final.html?disposition=inline`}
            title="HTML preview"
            sandbox="allow-same-origin allow-scripts"
            style={{ minHeight: 480, width: "100%", borderRadius: 11, border: "1px solid var(--card-border)", background: "#fff" }}
          />
        )}
      </div>

      <p className="sg-hint">
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
    generated: { label: "Generated", tone: "sg-tag-indigo" },
    edited: { label: "Edited", tone: "sg-tag-indigo" },
    rerendered: { label: "Re-rendered", tone: "" },
    reverted: { label: "Reverted", tone: "sg-tag-amber" },
  };

  if (loadError) {
    return (
      <div className="recent-state" style={{ color: "var(--red)" }}>
        <AlertCircle />
        {loadError}
      </div>
    );
  }

  if (currentText === null) {
    return (
      <div className="recent-state">
        <Loader2 className="sg-spin" />
        <span>Loading history…</span>
      </div>
    );
  }

  if (versions.length === 0) {
    return <p className="sg-hint" style={{ marginTop: 16 }}>No version history yet.</p>;
  }

  const latestVersion = versions[versions.length - 1]?.version;

  return (
    <div className="sg-tab-stack">
      <h3>{versions.length} version{versions.length !== 1 ? "s" : ""}</h3>

      {revertError && (
        <p className="sg-notice sg-notice-red">{revertError}</p>
      )}

      <div className="sg-stack">
        {[...versions].reverse().map((v) => {
          const isLatest = v.version === latestVersion;
          const srcInfo = SOURCE_LABELS[v.source] ?? { label: v.source, tone: "" };
          const isExpanded = expandedDiff === v.version;
          const vDiff = isExpanded ? diffContent[v.version] : undefined;
          const diff = vDiff !== undefined && currentText !== null ? computeLineDiff(vDiff, currentText) : null;

          return (
            <div key={v.version} className="sg-card-row">
              <div className="sg-head-row">
                <div className="sg-chip-row">
                  <span style={{ fontFamily: "var(--mono)", fontWeight: 700, color: "var(--text)" }}>v{v.version}</span>
                  <span className={`sg-tag ${srcInfo.tone}`}>{srcInfo.label}</span>
                  {isLatest && <span className="sg-tag sg-tag-green">current</span>}
                  <span className="sg-hint">{v.created_at}</span>
                </div>
                <div className="sg-btn-row">
                  <button type="button" onClick={() => handleToggleDiff(v.version)}>
                    {loadingDiff === v.version ? <Loader2 className="sg-spin" /> : <Eye />}
                    {isExpanded ? "Hide" : "Diff vs current"}
                  </button>
                  {!isLatest && (
                    <button
                      type="button"
                      onClick={() => handleRevert(v.version)}
                      disabled={reverting !== null}
                      className="sg-btn-accent"
                    >
                      {reverting === v.version ? <Loader2 className="sg-spin" /> : <RotateCcw />}
                      Restore
                    </button>
                  )}
                </div>
              </div>

              {isExpanded && (
                <div style={{ marginTop: 12 }}>
                  {loadingDiff === v.version || vDiff === undefined ? (
                    <div className="sg-row sg-hint">
                      <Loader2 className="sg-spin" /> Loading…
                    </div>
                  ) : vDiff === null ? (
                    <p className="sg-notice sg-notice-red">Could not load version content.</p>
                  ) : isLatest ? (
                    <pre className="sg-pre">{vDiff}</pre>
                  ) : diff ? (
                    <DiffView diff={diff} />
                  ) : null}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="sg-hint">
        Restoring a version creates a new snapshot — history is never deleted.
      </p>
    </div>
  );
}

function DiffView({ diff }) {
  const [showUnchanged, setShowUnchanged] = useState(false);

  const hasChanges = diff.some((l) => l.type !== "same" && l.type !== "info");

  if (!hasChanges) {
    return <p className="sg-hint">No differences — versions are identical.</p>;
  }

  const addedCount = diff.filter((l) => l.type === "added").length;
  const removedCount = diff.filter((l) => l.type === "removed").length;

  return (
    <div className="sg-stack">
      <div className="sg-head-row">
        <div className="sg-chip-row">
          {addedCount > 0 && <span style={{ color: "#6EE7B7", fontSize: 12 }}>+{addedCount} added</span>}
          {removedCount > 0 && <span style={{ color: "#FCA5A5", fontSize: 12 }}>−{removedCount} removed</span>}
        </div>
        <button type="button" onClick={() => setShowUnchanged((v) => !v)}>
          {showUnchanged ? "Hide unchanged" : "Show all lines"}
        </button>
      </div>
      <pre className="sg-pre">
        {diff.map((line, i) => {
          if (line.type === "same" && !showUnchanged) return null;
          const cls =
            line.type === "added" ? "sg-diff-add" :
            line.type === "removed" ? "sg-diff-del" :
            line.type === "info" ? "sg-diff-info" :
            "sg-diff-same";
          const prefix = line.type === "added" ? "+ " : line.type === "removed" ? "− " : "  ";
          return (
            <span key={i} className={`sg-diff-line ${cls}`}>{prefix}{line.text}</span>
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
    <div className="sg-tab-stack">
      {/* Config panel */}
      <section>
        <h3 style={{ marginBottom: 12 }}>Generate Quiz</h3>

        <div className="sg-stack">
          <div>
            <label className="sg-sub-label" style={{ display: "block", marginBottom: 8 }}>
              Question Types
            </label>
            <div className="sg-chip-row">
              {QUIZ_TYPE_OPTIONS.map((opt) => {
                const checked = questionTypes.includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => toggleType(opt.value)}
                    className={checked ? "sg-btn-accent" : undefined}
                  >
                    {checked && <CheckCircle2 />}
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="sg-grid-3">
            <div>
              <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
                Count
              </label>
              <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {QUIZ_COUNT_OPTIONS.map((n) => (
                  <option key={n} value={n}>{n} questions</option>
                ))}
              </select>
            </div>
            <div>
              <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
                Difficulty
              </label>
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                {QUIZ_DIFFICULTY_OPTIONS.map((d) => (
                  <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="sg-sub-label" style={{ display: "block", marginBottom: 4 }}>
                Focus
              </label>
              <select value={focus} onChange={(e) => setFocus(e.target.value)}>
                {QUIZ_FOCUS_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
          </div>

          {genError && (
            <p className="sg-notice sg-notice-red">
              {genError}
            </p>
          )}

          <button
            type="button"
            onClick={handleGenerate}
            disabled={!canGenerate}
            className="sg-btn-accent"
            style={{ justifyContent: "center" }}
          >
            {generating ? (
              <><Loader2 className="sg-spin" /> Generating…</>
            ) : (
              <><Sparkles /> Generate Quiz</>
            )}
          </button>
        </div>
      </section>

      {/* Previously generated quizzes */}
      {quizzesError && (
        <p className="sg-notice sg-notice-red">{quizzesError}</p>
      )}

      {quizzes === null && !quizzesError && (
        <div className="sg-row sg-hint">
          <Loader2 className="sg-spin" />
          Loading quizzes…
        </div>
      )}

      {quizzes !== null && quizzes.length > 0 && (
        <section>
          <h3 style={{ marginBottom: 8 }}>Saved Quizzes</h3>
          <div className="sg-stack">
            {[...quizzes].reverse().map((q) => {
              const isActive = activeQuiz?.n === q.n;
              const types = (q.config?.question_types ?? []).join(", ");
              return (
                <button
                  key={q.n}
                  type="button"
                  onClick={() => handleLoadQuiz(q.n)}
                  className={`sg-opt-btn${isActive ? " sel" : ""}`}
                >
                  <span style={{ fontWeight: 700 }}>Quiz #{q.n}</span>
                  <span style={{ marginLeft: 8, color: "var(--muted)" }}>{q.item_count} questions · {types} · {q.config?.difficulty}</span>
                  <span style={{ marginLeft: 8, color: "var(--muted)" }}>{q.created_at?.slice(0, 10)}</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Active quiz display */}
      {activeQuiz && (
        <section>
          <div className="sg-head-row" style={{ marginBottom: 12 }}>
            <div>
              <h3>
                Quiz #{activeQuiz.n} · {activeQuiz.item_count} questions
              </h3>
              <p className="sg-hint" style={{ marginTop: 2 }}>
                {(activeQuiz.config?.question_types ?? []).join(", ")} · {activeQuiz.config?.difficulty} · {activeQuiz.config?.focus}
              </p>
            </div>
            <div className="sg-btn-row">
              <button
                type="button"
                onClick={() => { setShowAnswers((v) => !v); setOpenAnswerIdx(null); }}
              >
                {showAnswers ? <EyeOff /> : <Eye />}
                {showAnswers ? "Hide All Answers" : "Show All Answers"}
              </button>
            </div>
          </div>

          {/* Export buttons */}
          <div className="sg-btn-row" style={{ marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid var(--hairline)", alignItems: "center" }}>
            <span className="sg-sub-label" style={{ alignSelf: "center" }}>Export:</span>
            {[
              { format: "csv", label: "CSV" },
              { format: "anki_tsv", label: "Anki TSV" },
              { format: "quizlet", label: "Quizlet" },
            ].map(({ format, label }) => (
              <a
                key={format}
                href={quizExportUrl(jobId, activeQuiz.n, format)}
                download
                className="sg-modal-action"
              >
                <Download />
                {label}
              </a>
            ))}
          </div>

          {/* Questions list */}
          <div className="sg-stack">
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
    mcq: "sg-tag-indigo",
    true_false: "",
    fill_blank: "sg-tag-amber",
    short_answer: "sg-tag-green",
    flashcards: "sg-tag-indigo",
  }[item.type] ?? "";

  return (
    <div className="sg-card-row">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, minWidth: 0 }}>
          <span className="sg-idx" style={{ marginTop: 1 }}>
            {index + 1}
          </span>
          <div style={{ minWidth: 0 }}>
            <p style={{ fontWeight: 600, color: "var(--text)" }}>{item.question}</p>
            {item.type === "mcq" && item.options && (
              <ul className="sg-stack" style={{ marginTop: 8 }}>
                {item.options.map((opt, oi) => {
                  const letter = opt.charAt(0).toUpperCase();
                  const isCorrect = answerVisible && letter === (item.answer ?? "").toUpperCase();
                  return (
                    <li key={oi} className={`sg-q-opt${isCorrect ? " correct" : ""}`}>
                      {opt}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
        <span className={`sg-tag ${typeTone}`}>{typeLabel}</span>
      </div>

      {item.topic && (
        <p className="sg-hint" style={{ marginTop: 8, marginLeft: 30 }}>Topic: {item.topic}</p>
      )}

      {/* Answer toggle (individual) — only when not showing all answers */}
      {!showAllAnswers && (
        <button
          type="button"
          onClick={onToggleAnswer}
          style={{ marginTop: 8, marginLeft: 30 }}
        >
          {answerVisible ? <ChevronUp /> : <ChevronDown />}
          {answerVisible ? "Hide answer" : "Show answer"}
        </button>
      )}

      {answerVisible && (
        <div className="sg-card-row good" style={{ marginTop: 8, marginLeft: 30 }}>
          <p className="sg-sub-label" style={{ color: "#6EE7B7", marginBottom: 2 }}>Answer</p>
          <p style={{ color: "#6EE7B7" }}>{item.answer}</p>
        </div>
      )}
    </div>
  );
}

// forwardRef wrapper so Home can imperatively open the job-details drawer for a
// favorite guide (see useImperativeHandle above).
const RecentJobsPanelWithRef = forwardRef(RecentJobsPanel);
export default RecentJobsPanelWithRef;
