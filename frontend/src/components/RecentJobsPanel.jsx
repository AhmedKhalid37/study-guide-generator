import React, { useEffect, useMemo, useState } from "react";
import { AlertCircle, Download, FileCode2, FileJson, FileText, Loader2 } from "lucide-react";
import { artifactUrl, getJob, getJobs } from "../api/client";

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

export default function RecentJobsPanel({ refreshKey = 0, embedded = false, onSelectedJobChange }) {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [jobsError, setJobsError] = useState(null);
  const [loadingJob, setLoadingJob] = useState(false);
  const [jobError, setJobError] = useState(null);

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

  const listPanel = (
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-navy backdrop-blur-xl">
        <div className="flex flex-col gap-2 border-b border-white/10 pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">
              Live API
            </p>
            <h2 className="mt-1 text-xl font-bold text-white">Recent jobs</h2>
          </div>
          <p className="text-sm text-slate-400">Read-only history from FastAPI</p>
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
              return (
                <button
                  key={job.id}
                  type="button"
                  onClick={() => setSelectedJobId(job.id)}
                  className={`w-full rounded-xl border p-4 text-left transition ${
                    selected
                      ? "border-ember-500/70 bg-ember-500/10 shadow-ember"
                      : "border-white/10 bg-navy-900/70 hover:border-white/25 hover:bg-white/[0.06]"
                  }`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-white">{jobTitle(job)}</p>
                      <p className="mt-1 break-all font-mono text-xs text-slate-400">{job.id}</p>
                    </div>
                    <span
                      className={`inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass(
                        job.status
                      )}`}
                    >
                      {job.status || "unknown"}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-1 text-sm text-slate-400 md:grid-cols-2">
                    <span>{providerModel || "provider/model unavailable"}</span>
                    <span className="md:text-right">{job.created_at || "created_at unavailable"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
  );

  if (embedded) {
    return listPanel;
  }

  return (
    <section className="mx-auto mt-10 grid w-full max-w-[1536px] gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      {listPanel}

      <aside className="rounded-2xl border border-white/10 bg-navy-900/80 p-5 shadow-navy backdrop-blur-xl">
        <div className="border-b border-white/10 pb-4">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">Output</p>
          <h2 className="mt-1 text-xl font-bold text-white">Preview panel</h2>
        </div>

        {loadingJob && (
          <div className="flex min-h-52 items-center justify-center gap-3 text-slate-300">
            <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
            <span>Loading job...</span>
          </div>
        )}

        {!loadingJob && jobError && (
          <div className="flex min-h-52 items-center justify-center gap-3 text-red-200">
            <AlertCircle className="h-5 w-5" />
            <span>Could not load job</span>
          </div>
        )}

        {!loadingJob && !jobError && !selectedManifest && (
          <div className="flex min-h-52 items-center justify-center text-slate-400">
            Select a job
          </div>
        )}

        {!loadingJob && !jobError && selectedManifest && (
          <div className="mt-4">
            <dl className="grid gap-3 text-sm">
              <div>
                <dt className="text-slate-500">Job id</dt>
                <dd className="mt-1 break-all font-mono text-slate-200">{selectedManifest.id}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Title</dt>
                <dd className="mt-1 font-medium text-white">{jobTitle(selectedManifest)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Status</dt>
                <dd className="mt-1 text-slate-200">{selectedManifest.status || "unknown"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Provider / model</dt>
                <dd className="mt-1 text-slate-200">
                  {formatProviderModel(selectedManifest) || "provider/model unavailable"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Created</dt>
                <dd className="mt-1 text-slate-200">
                  {selectedManifest.created_at || "created_at unavailable"}
                </dd>
              </div>
            </dl>

            <div className="mt-6">
              <p className="text-sm font-bold text-white">Downloads</p>
              {availableArtifacts.length === 0 ? (
                <p className="mt-3 text-sm text-slate-400">No artifacts available</p>
              ) : (
                <div className="mt-3 grid gap-2">
                  {availableArtifacts.map((artifact) => {
                    const Icon = artifact.icon;
                    return (
                      <a
                        key={artifact.name}
                        href={artifactUrl(selectedManifest.id, artifact.name)}
                        className="inline-flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-bold text-slate-100 transition hover:border-ember-500/70 hover:text-white"
                      >
                        <span>{artifact.label}</span>
                        <Icon className="h-4 w-4 text-ember-500" />
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </aside>
    </section>
  );
}
