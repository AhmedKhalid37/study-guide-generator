import React, { useCallback, useMemo, useState } from "react";
import {
  Bot,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Download,
  FileCode2,
  FileJson,
  FileText,
  Flame,
  GraduationCap,
  History,
  Home,
  Layers3,
  ListChecks,
  PenLine,
  Sparkles,
  Star,
  Upload,
  UserRound,
  Wand2
} from "lucide-react";
import { apiUrl, artifactUrl } from "../api/client";
import BrandMark from "./BrandMark";
import PasteGenerationPanel from "./PasteGenerationPanel";
import RecentJobsPanel from "./RecentJobsPanel";

const navigationItems = [
  { label: "Home", icon: Home, active: true },
  { label: "My Guides", icon: FileText },
  { label: "Templates", icon: Layers3 },
  { label: "AI Models", icon: Bot },
  { label: "History", icon: History },
  { label: "Starred", icon: Star }
];

const actions = [
  {
    label: "Paste Text",
    method: "paste",
    icon: PenLine,
    description: "Turn notes into a PDF-ready guide."
  },
  {
    label: "Upload Markdown",
    method: "upload",
    icon: Upload,
    description: "Render an existing .md file."
  },
  {
    label: "Generate with AI",
    method: "llm",
    icon: Wand2,
    description: "Create a guide from source material."
  }
];

const guideStyles = [
  { label: "Baby-step Explanations", icon: GraduationCap },
  { label: "Exam Cram", icon: Flame },
  { label: "MCQ Training", icon: ListChecks },
  { label: "Final Solutions", icon: CheckCircle2 },
  { label: "Claude-style Guides", icon: Sparkles },
  { label: "Master-level Longform", icon: Brain }
];

const artifactLinks = [
  { name: "final.pdf", label: "PDF", key: "final_pdf", icon: Download },
  { name: "clean.md", label: "Markdown", key: "clean_md", icon: FileText },
  { name: "final.html", label: "HTML", key: "final_html", icon: FileCode2 },
  { name: "validation.json", label: "Validation", key: "validation_json", icon: FileJson },
  { name: "render.log", label: "Render log", key: "render_log", icon: FileText }
];

export default function DesktopDashboard() {
  const [creationMethod, setCreationMethod] = useState("paste");
  const [jobsRefreshKey, setJobsRefreshKey] = useState(0);
  const [selectedJob, setSelectedJob] = useState(null);
  const [createdJob, setCreatedJob] = useState(null);

  const handleJobCreated = useCallback((job) => {
    setCreatedJob(job);
    setJobsRefreshKey((key) => key + 1);
  }, []);

  const handleSelectedJobChange = useCallback((job) => {
    setSelectedJob(job);
  }, []);

  const preview = useMemo(
    () => buildPreviewModel(selectedJob, createdJob),
    [selectedJob, createdJob]
  );

  return (
    <section className="mx-auto grid min-h-[calc(100vh-9rem)] w-full max-w-[1800px] gap-5 xl:grid-cols-[280px_minmax(0,1fr)_380px]">
      <aside className="flex rounded-3xl border border-white/10 bg-[#071426]/90 p-4 shadow-navy backdrop-blur-xl xl:sticky xl:top-28 xl:h-[calc(100vh-8rem)] xl:flex-col">
        <div className="flex w-full flex-col">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <BrandMark />
          </div>

          <button
            type="button"
            onClick={() => setCreationMethod("paste")}
            className="mt-5 inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-ember-500 to-ember-700 px-4 text-sm font-extrabold text-white shadow-ember transition hover:brightness-110"
          >
            <Wand2 className="h-4 w-4" />
            New Guide
          </button>

          <nav className="mt-6 grid gap-2">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  className={`flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-bold transition ${
                    item.active
                      ? "border border-ember-500/40 bg-ember-500/10 text-white"
                      : "text-slate-400 hover:bg-white/[0.05] hover:text-white"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="mt-auto hidden rounded-2xl border border-white/10 bg-white/[0.04] p-4 xl:block">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-ember-500/15 text-ember-400">
                <UserRound className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-white">Local Workspace</p>
                <p className="text-xs font-medium text-slate-400">PDF pipeline ready</p>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <main className="min-w-0">
        <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 shadow-navy backdrop-blur-xl sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-ember-500">
                Dashboard
              </p>
              <h1 className="mt-2 text-3xl font-extrabold tracking-normal text-white sm:text-4xl">
                Build production-ready study guides
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
                Create polished PDF guides from pasted notes, Markdown files, or AI generation.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 rounded-2xl border border-white/10 bg-[#071426] p-3 text-sm sm:grid-cols-3">
              <Metric label="Modes" value="3" />
              <Metric label="Theme" value="Claude" />
              <Metric label="Math" value="Strict" />
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {actions.map((action) => {
              const Icon = action.icon;
              const active = creationMethod === action.method;
              return (
                <button
                  key={action.method}
                  type="button"
                  onClick={() => setCreationMethod(action.method)}
                  className={`rounded-2xl border p-4 text-left transition ${
                    active
                      ? "border-ember-500/70 bg-ember-500/10 shadow-ember"
                      : "border-white/10 bg-[#071426]/80 hover:border-white/25 hover:bg-white/[0.06]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-ember-500/15 text-ember-400">
                      <Icon className="h-5 w-5" />
                    </span>
                    <ChevronRight className="h-4 w-4 text-slate-500" />
                  </div>
                  <p className="mt-4 font-bold text-white">{action.label}</p>
                  <p className="mt-1 text-sm leading-5 text-slate-400">{action.description}</p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-5 rounded-3xl border border-white/10 bg-[#071426]/80 p-5 shadow-navy backdrop-blur-xl sm:p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-ember-500">
                Guide styles
              </p>
              <h2 className="mt-1 text-xl font-extrabold text-white">Choose the output shape</h2>
            </div>
            <p className="text-sm text-slate-400">Available in Generate with LLM</p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
            {guideStyles.map((style) => {
              const Icon = style.icon;
              return (
                <div
                  key={style.label}
                  className="rounded-2xl border border-white/10 bg-white/[0.035] p-4"
                >
                  <Icon className="h-5 w-5 text-ember-500" />
                  <p className="mt-3 text-sm font-bold text-white">{style.label}</p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-5">
          <PasteGenerationPanel
            key={creationMethod}
            embedded
            initialInputMethod={creationMethod}
            onJobCreated={handleJobCreated}
          />
        </div>

        <div className="mt-5">
          <RecentJobsPanel
            embedded
            refreshKey={jobsRefreshKey}
            onSelectedJobChange={handleSelectedJobChange}
          />
        </div>
      </main>

      <GuidePreviewPanel preview={preview} />
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-extrabold text-white">{value}</p>
    </div>
  );
}

function GuidePreviewPanel({ preview }) {
  return (
    <aside className="rounded-3xl border border-white/10 bg-[#071426]/90 p-5 shadow-navy backdrop-blur-xl xl:sticky xl:top-28 xl:h-[calc(100vh-8rem)] xl:overflow-y-auto">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-ember-500">Output</p>
          <h2 className="mt-1 text-xl font-extrabold text-white">Guide preview</h2>
        </div>
        <Clock3 className="h-5 w-5 text-slate-500" />
      </div>

      {!preview && (
        <div className="mt-5 rounded-2xl border border-dashed border-white/15 bg-white/[0.03] p-5 text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-ember-500/15 text-ember-400">
            <FileText className="h-6 w-6" />
          </div>
          <p className="mt-4 font-bold text-white">No guide selected</p>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            Generate a guide or select a recent job to see exports and metadata here.
          </p>
        </div>
      )}

      {preview && (
        <div className="mt-5">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-lg font-extrabold text-white">{preview.title}</p>
                <p className="mt-2 break-all font-mono text-xs text-slate-500">{preview.id}</p>
              </div>
              <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-xs font-bold text-emerald-200">
                {preview.status}
              </span>
            </div>
          </div>

          <dl className="mt-5 grid gap-4 text-sm">
            <PreviewRow label="Provider / model" value={preview.providerModel} />
            <PreviewRow label="Created" value={preview.createdAt} />
          </dl>

          <div className="mt-6">
            <p className="text-sm font-bold text-white">Export</p>
            {preview.artifacts.length === 0 ? (
              <p className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-400">
                No artifacts available yet.
              </p>
            ) : (
              <div className="mt-3 grid gap-2">
                {preview.artifacts.map((artifact) => {
                  const Icon = artifact.icon;
                  return (
                    <a
                      key={artifact.name}
                      href={artifact.url}
                      className={`inline-flex items-center justify-between rounded-xl border px-4 py-3 text-sm font-bold transition ${
                        artifact.name === "final.pdf"
                          ? "border-ember-500/50 bg-ember-500/15 text-white hover:bg-ember-500/25"
                          : "border-white/10 bg-white/[0.04] text-slate-100 hover:border-ember-500/60"
                      }`}
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
  );
}

function PreviewRow({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-200">{value || "Unavailable"}</dd>
    </div>
  );
}

function buildPreviewModel(selectedJob, createdJob) {
  if (selectedJob?.job) {
    const job = selectedJob.job;
    const availability = selectedJob.artifact_availability ?? {};
    return {
      id: job.id,
      title: job.title || "Untitled study guide",
      status: job.status || "unknown",
      providerModel: [job.provider, job.model].filter(Boolean).join(" / "),
      createdAt: job.created_at,
      artifacts: artifactLinks
        .filter((artifact) => availability[artifact.key])
        .map((artifact) => ({
          ...artifact,
          url: artifactUrl(job.id, artifact.name)
        }))
    };
  }

  if (createdJob) {
    return {
      id: createdJob.job_id,
      title: createdJob.title || "Generated study guide",
      status: createdJob.status || "unknown",
      providerModel: [createdJob.provider, createdJob.model].filter(Boolean).join(" / "),
      createdAt: createdJob.created_at,
      artifacts: Object.entries(createdJob.artifact_urls ?? {})
        .map(([name, url]) => {
          const definition = artifactLinks.find((artifact) => artifact.name === name);
          if (!definition) {
            return null;
          }
          return {
            ...definition,
            url: apiUrl(url)
          };
        })
        .filter(Boolean)
    };
  }

  return null;
}
