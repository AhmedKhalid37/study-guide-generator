import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
  FileCode2,
  FileJson,
  FileText,
  Loader2,
  Paperclip,
  X
} from "lucide-react";
import { artifactUrl, getJob, getJobs, getStyles } from "../api/client";
import { buildStyleLookup, resolveStyle } from "../styleMeta";

const artifactLinks = [
  { name: "final.pdf", label: "PDF", key: "final_pdf", icon: Download },
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

export default function RecentJobsPanel({ refreshKey = 0, embedded = false, onSelectedJobChange }) {
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

  function openJobDetails(jobId) {
    setSelectedJobId(jobId);
    setDetailsOpen(true);
  }

  const listPanel = (
      <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl">
        <div className="flex flex-col gap-2 border-b border-white/10 pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-xl font-extrabold text-white">Recent Guides</h2>
          </div>
          <button type="button" className="text-sm font-medium text-slate-300 hover:text-white">
            View all
          </button>
        </div>

        {loadingJobs && (
          <div className="flex min-h-48 items-center justify-center gap-3 text-slate-300">
            <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
            <span>Loading jobs...</span>
          </div>
        )}

        {!loadingJobs && jobsError && (
          <div className="flex min-h-48 items-center justify-center gap-3 text-red-200">
            <AlertCircle className="h-5 w-5" />
            <span>Could not load jobs</span>
          </div>
        )}

        {!loadingJobs && !jobsError && jobs.length === 0 && (
          <div className="flex min-h-48 items-center justify-center text-slate-400">
            No jobs yet
          </div>
        )}

        {!loadingJobs && !jobsError && jobs.length > 0 && (
          <div className="mt-4 grid gap-3">
            {jobs.map((job) => {
              const selected = selectedJobId === job.id;
              const providerModel = formatProviderModel(job);
              const sources = attachmentSummary(job);
              const jobStyle = resolveStyle(job.prompt_name, styleLookup);
              return (
                <button
                  key={job.id}
                  type="button"
                  onClick={() => openJobDetails(job.id)}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    selected
                      ? "border-ember-500/60 bg-ember-500/[0.08]"
                      : "border-white/10 bg-white/[0.035] hover:border-white/20 hover:bg-white/[0.055]"
                  }`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-white">{jobTitle(job)}</p>
                      <p className="mt-1 truncate text-xs text-slate-400">
                        {[providerModel || "Study guide", job.created_at].filter(Boolean).join(" · ")}
                      </p>
                      {(jobStyle || sources.count > 0) && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {jobStyle && <StylePill style={jobStyle} />}
                          {sources.count > 0 && <AttachmentPill count={sources.count} />}
                          {sources.count > 0 && sources.hasWarnings && <WarningPill count={sources.warningCount} />}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={`inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass(
                          job.status
                        )}`}
                      >
                        {job.status || "unknown"}
                      </span>
                      <span className="rounded-lg bg-white/[0.06] px-2.5 py-1 text-xs font-bold text-slate-300">
                        PDF
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
  );

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

export function JobDetailsDrawer({ open, onClose, loading, error, details, styleLookup }) {
  const manifest = details?.job;
  const artifacts = details?.artifacts ?? artifactLinks
    .filter((artifact) => details?.artifact_availability?.[artifact.key])
    .map((artifact) => ({ ...artifact, available: true }));
  const validation = details?.validation_summary;
  const renderLog = details?.render_log_summary;
  const style = resolveStyle(manifest?.prompt_name, styleLookup);
  const warnings = [
    ...(manifest?.extraction_warnings ?? []),
    ...(manifest?.error ? [String(manifest.error)] : [])
  ];

  if (!open) {
    return null;
  }

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

          {!loading && !error && manifest && (
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
                </div>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <MetaTerm label="Created" value={manifest.created_at} />
                  <MetaTerm label="Input type" value={manifest.input_type || manifest.path_mode} />
                  <MetaTerm
                    label="Style"
                    value={style ? `${style.name} (${style.isCustom ? "Custom" : "Built-in"})` : "markdown pipeline"}
                  />
                  <MetaTerm label="Theme" value={manifest.theme} />
                  <MetaTerm label="Mode" value={manifest.mode} />
                  <MetaTerm label="Strict math" value={String(Boolean(manifest.strict_math))} />
                </dl>
              </section>

              <DetailsSection title="Artifacts">
                <ArtifactLinkGrid jobId={manifest.id} artifacts={artifacts} />
              </DetailsSection>

              <DetailsSection title="Validation">
                <ValidationSummary validation={validation} manifest={manifest} />
              </DetailsSection>

              <DetailsSection title="Render log">
                <RenderLogSummary renderLog={renderLog} />
              </DetailsSection>

              <AttachmentDetails manifest={manifest} />

              {warnings.length > 0 && (
                <DetailsSection title="Warnings and errors">
                  <div className="grid gap-2">
                    {warnings.map((warning, index) => (
                      <p key={index} className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">
                        {warning}
                      </p>
                    ))}
                  </div>
                </DetailsSection>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
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
