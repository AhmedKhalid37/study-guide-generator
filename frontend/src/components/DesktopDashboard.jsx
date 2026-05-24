import React, { useCallback, useMemo, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Brain,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  FileCode2,
  FileJson,
  FileText,
  Flame,
  Folder,
  History,
  Home,
  Layers3,
  ListChecks,
  MoreHorizontal,
  PenLine,
  Search,
  Share2,
  Sparkles,
  Star,
  Trash2,
  Upload,
  UserRound,
  Wand2,
  Zap
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
  { label: "Starred", icon: Star },
  { label: "Trash", icon: Trash2 }
];

const folders = [
  { label: "Computer Science", count: 12 },
  { label: "Math", count: 8 },
  { label: "Physics", count: 6 },
  { label: "Chemistry", count: 4 }
];

const actions = [
  {
    label: "Paste Text",
    method: "paste",
    icon: FileText,
    color: "blue",
    description: "Paste your content and generate a guide."
  },
  {
    label: "Upload Markdown",
    method: "upload",
    icon: Upload,
    color: "purple",
    description: "Upload .md files or text files."
  },
  {
    label: "Generate with AI",
    method: "llm",
    icon: Wand2,
    color: "orange",
    description: "Describe a topic and let AI write the content."
  }
];

const guideStyles = [
  {
    label: "Baby-Step Explanations",
    promptName: "baby_steps",
    icon: Layers3,
    description: "Learn conceptually with simple, step-by-step explanations."
  },
  {
    label: "Exam Cram",
    promptName: "exam_cram",
    icon: Zap,
    description: "High-yield notes for quick revision and exams."
  },
  {
    label: "MCQ Training",
    promptName: "mcq_training",
    icon: ListChecks,
    description: "Practice MCQs with explanations and difficulty levels."
  },
  {
    label: "Final Solutions",
    promptName: "final_solution",
    icon: Brain,
    description: "Detailed solutions to problems with clear steps."
  },
  {
    label: "Claude-style Guides",
    promptName: "claude_study_guide",
    icon: Sparkles,
    description: "Structured, thoughtful guides inspired by Claude's approach."
  },
  {
    label: "Master Longform",
    promptName: "master_longform",
    icon: Flame,
    description: "Deep 10+ page guides with derivations and examples."
  }
];

const artifactLinks = [
  { name: "final.pdf", label: "Export as PDF", key: "final_pdf", icon: Download },
  { name: "clean.md", label: "Markdown", key: "clean_md", icon: FileText },
  { name: "final.html", label: "HTML", key: "final_html", icon: FileCode2 },
  { name: "validation.json", label: "Validation", key: "validation_json", icon: FileJson },
  { name: "render.log", label: "Render log", key: "render_log", icon: FileText }
];

export default function DesktopDashboard() {
  const [creationMethod, setCreationMethod] = useState("paste");
  const [selectedStyle, setSelectedStyle] = useState("exam_cram");
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
    () => buildPreviewModel(selectedJob, createdJob, selectedStyle),
    [selectedJob, createdJob, selectedStyle]
  );

  return (
    <section className="mx-auto w-full max-w-[1920px]">
      <div className="overflow-hidden rounded-[1.75rem] border border-white/15 bg-[radial-gradient(circle_at_35%_0%,rgba(22,58,105,0.55),transparent_32%),linear-gradient(135deg,#071426_0%,#020713_55%,#061225_100%)] shadow-[0_34px_140px_rgba(0,0,0,0.62),inset_0_1px_0_rgba(255,255,255,0.08)]">
        <WindowChrome />
        <div className="grid min-h-[780px] xl:grid-cols-[288px_minmax(0,1fr)_560px]">
          <Sidebar onNewGuide={() => setCreationMethod("paste")} />

          <main className="min-w-0 border-x border-white/10 px-8 py-8">
            <div className="mx-auto max-w-[880px]">
              <div className="flex items-center justify-between gap-5">
                <div>
                  <h1 className="text-3xl font-extrabold tracking-normal text-white">
                    Good evening, Ahmed 👋
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Turn your content into high-quality study guides in seconds.
                  </p>
                </div>
                <div className="hidden min-w-[360px] items-center rounded-xl border border-white/10 bg-white/[0.045] px-4 py-3 text-sm text-slate-400 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] lg:flex">
                  <Search className="mr-3 h-4 w-4 text-slate-500" />
                  <span className="flex-1">Search guides, folders, and more...</span>
                  <span className="rounded-md border border-white/10 bg-white/[0.06] px-2 py-0.5 text-xs text-slate-300">
                    ⌘ K
                  </span>
                </div>
              </div>

              <div className="mt-8 grid gap-5 lg:grid-cols-3">
                {actions.map((action) => (
                  <ActionCard
                    key={action.method}
                    action={action}
                    active={creationMethod === action.method}
                    onClick={() => setCreationMethod(action.method)}
                  />
                ))}
              </div>

              <div className="mt-8 flex items-center justify-between">
                <h2 className="text-xl font-extrabold text-white">Choose a guide style</h2>
                <button type="button" className="text-sm font-medium text-slate-300 hover:text-white">
                  See all
                </button>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
                {guideStyles.map((style) => (
                  <StyleCard
                    key={style.promptName}
                    style={style}
                    selected={selectedStyle === style.promptName}
                    onClick={() => setSelectedStyle(style.promptName)}
                  />
                ))}
              </div>

              <div className="mt-8 rounded-2xl border border-white/10 bg-[#071426]/72 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                <PasteGenerationPanel
                  key={`${creationMethod}-${selectedStyle}`}
                  embedded
                  initialInputMethod={creationMethod}
                  initialPromptName={selectedStyle}
                  onJobCreated={handleJobCreated}
                />
              </div>

              <div className="mt-8">
                <RecentJobsPanel
                  embedded
                  refreshKey={jobsRefreshKey}
                  onSelectedJobChange={handleSelectedJobChange}
                />
              </div>
            </div>
          </main>

          <GuidePreviewPanel preview={preview} />
        </div>
      </div>
    </section>
  );
}

function WindowChrome() {
  return (
    <div className="flex h-9 items-center border-b border-white/10 px-5">
      <div className="flex gap-2">
        <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
        <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
        <span className="h-3 w-3 rounded-full bg-[#28c840]" />
      </div>
    </div>
  );
}

function Sidebar({ onNewGuide }) {
  return (
    <aside className="flex min-h-full flex-col bg-white/[0.025] px-5 py-7">
      <BrandMark />

      <button
        type="button"
        onClick={onNewGuide}
        className="mt-8 inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-ember-500 to-ember-700 px-4 text-sm font-extrabold text-white shadow-ember transition hover:brightness-110"
      >
        <PenLine className="h-4 w-4" />
        New Guide
        <span className="ml-auto rounded-md bg-white/15 px-1.5 py-0.5 text-[11px]">⌘ N</span>
      </button>

      <nav className="mt-7 grid gap-1.5">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              type="button"
              className={`flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold transition ${
                item.active
                  ? "bg-white/[0.075] text-white"
                  : "text-slate-300 hover:bg-white/[0.05] hover:text-white"
              }`}
            >
              <Icon className={`h-4 w-4 ${item.active ? "text-ember-500" : "text-slate-400"}`} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="mt-8 border-t border-white/10 pt-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-300">Folders</p>
          <button type="button" className="text-lg leading-none text-slate-400 hover:text-white">
            +
          </button>
        </div>
        <div className="grid gap-2">
          {folders.map((folder) => (
            <button
              key={folder.label}
              type="button"
              className="flex h-9 items-center gap-3 rounded-lg px-2 text-sm text-slate-300 transition hover:bg-white/[0.05] hover:text-white"
            >
              <Folder className="h-4 w-4 text-slate-400" />
              <span className="flex-1 text-left">{folder.label}</span>
              <span className="text-xs text-slate-500">{folder.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.04] p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-ember-500/20 text-ember-400">
              <Flame className="h-4 w-4" />
            </span>
            Pro Plan
          </div>
          <button type="button" className="text-xs font-semibold text-slate-300 hover:text-white">
            Manage
          </button>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div className="h-full w-[58%] rounded-full bg-ember-500" />
        </div>
        <p className="mt-3 text-xs text-slate-300">23,450 / 50,000 AI credits used</p>
        <p className="mt-1 text-xs text-slate-500">Resets in 12 days</p>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-full bg-slate-700 text-sm font-bold text-white">
          AR
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-white">Ahmed R.</p>
          <p className="truncate text-xs text-slate-400">local workspace</p>
        </div>
        <ChevronDown className="h-4 w-4 text-slate-500" />
      </div>
    </aside>
  );
}

function ActionCard({ action, active, onClick }) {
  const Icon = action.icon;
  const iconClass =
    action.color === "blue"
      ? "bg-blue-500/15 text-blue-300"
      : action.color === "purple"
        ? "bg-violet-500/15 text-violet-300"
        : "bg-ember-500/15 text-ember-400";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`min-h-[176px] rounded-2xl border p-5 text-left transition ${
        active
          ? "border-ember-500/70 bg-ember-500/[0.08] shadow-[0_22px_80px_rgba(255,122,0,0.16)]"
          : "border-white/10 bg-white/[0.035] hover:border-white/20 hover:bg-white/[0.055]"
      }`}
    >
      <div className="flex items-start justify-between">
        <span className={`grid h-11 w-11 place-items-center rounded-xl ${iconClass}`}>
          <Icon className="h-5 w-5" />
        </span>
        <ChevronRight className="mt-8 h-5 w-5 text-slate-400" />
      </div>
      <p className="mt-5 text-base font-extrabold text-white">{action.label}</p>
      <p className="mt-2 text-sm leading-6 text-slate-300">{action.description}</p>
    </button>
  );
}

function StyleCard({ style, selected, onClick }) {
  const Icon = style.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative min-h-[180px] rounded-2xl border p-4 text-left transition ${
        selected
          ? "border-ember-500 bg-ember-500/[0.06] shadow-[0_22px_80px_rgba(255,122,0,0.16)]"
          : "border-white/10 bg-white/[0.035] hover:border-white/20 hover:bg-white/[0.055]"
      }`}
    >
      {selected && (
        <span className="absolute right-3 top-3 grid h-6 w-6 place-items-center rounded-full bg-ember-500 text-white">
          <Check className="h-3.5 w-3.5" />
        </span>
      )}
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-ember-500/15 text-ember-400">
        <Icon className="h-6 w-6" />
      </span>
      <p className="mt-4 text-base font-extrabold leading-5 text-white">{style.label}</p>
      <p className="mt-2 text-sm leading-5 text-slate-400">{style.description}</p>
    </button>
  );
}

function GuidePreviewPanel({ preview }) {
  const primaryPdf = preview?.artifacts.find((artifact) => artifact.name === "final.pdf");

  return (
    <aside className="min-w-0 bg-white/[0.018] px-8 py-8">
      <div className="flex items-center justify-between">
        <button type="button" className="grid h-10 w-10 place-items-center rounded-xl text-slate-300 hover:bg-white/[0.06] hover:text-white">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-3">
          <button type="button" className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.045] px-4 text-sm font-semibold text-white">
            Export
            <ChevronDown className="h-4 w-4 text-slate-400" />
          </button>
          <button type="button" className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[0.045] text-slate-300 hover:text-white">
            <Share2 className="h-4 w-4" />
          </button>
          <a
            href={primaryPdf?.url}
            className={`inline-flex h-10 items-center gap-2 rounded-xl px-4 text-sm font-extrabold text-white ${
              primaryPdf
                ? "bg-gradient-to-r from-ember-500 to-ember-700 shadow-ember"
                : "pointer-events-none bg-white/10 text-slate-500"
            }`}
          >
            <Sparkles className="h-4 w-4" />
            Regenerate
          </a>
        </div>
      </div>

      {!preview ? (
        <div className="mt-10 rounded-2xl border border-dashed border-white/15 bg-white/[0.035] p-8 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-ember-500/15 text-ember-400">
            <FileText className="h-7 w-7" />
          </div>
          <p className="mt-5 text-xl font-extrabold text-white">No guide selected</p>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Generate a guide or select one from Recent Guides to see its exports, status, and summary.
          </p>
        </div>
      ) : (
        <div className="mt-7">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-3xl font-extrabold tracking-normal text-white">
                {preview.title}
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">
                High-quality study guide generated from your source content and ready for export.
              </p>
            </div>
            <PenLine className="mt-2 h-5 w-5 text-slate-400" />
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-slate-300">
            <span className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.045] px-3 py-2">
              <Bot className="h-4 w-4 text-blue-300" />
              {preview.providerModel || "Local pipeline"}
            </span>
            <span className="h-5 w-px bg-white/10" />
            <span>{preview.status}</span>
            <span className="h-5 w-px bg-white/10" />
            <span>{preview.createdAt || "Recently generated"}</span>
          </div>

          <div className="mt-6 flex border-b border-white/10 text-sm font-semibold">
            {["Overview", "Content", "MCQs", "Preview"].map((tab, index) => (
              <button
                key={tab}
                type="button"
                className={`relative px-4 py-3 ${
                  index === 0 ? "text-ember-500" : "text-slate-300 hover:text-white"
                }`}
              >
                {tab}
                {tab === "MCQs" && (
                  <span className="ml-2 rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">25</span>
                )}
                {index === 0 && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-ember-500" />}
              </button>
            ))}
          </div>

          <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.045] p-5">
            <h3 className="font-extrabold text-white">Guide Summary</h3>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              This guide includes a cleaned Markdown source, rendered HTML, strict math validation,
              and the final PDF artifact when generation succeeds.
            </p>
            <div className="mt-5 grid grid-cols-3 gap-3 text-xs text-slate-300">
              <SummaryStat label="Topics" value="18" />
              <SummaryStat label="Key Points" value="64" />
              <SummaryStat label="Exports" value={String(preview.artifacts.length)} />
            </div>
          </div>

          <div className="mt-6 flex items-center justify-between">
            <h3 className="font-extrabold text-white">Topics</h3>
            <button type="button" className="text-sm text-slate-300 hover:text-white">Expand all</button>
          </div>
          <div className="mt-3 grid gap-3">
            {previewTopics(preview).map((topic, index) => (
              <div
                key={topic}
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.035] px-4 py-3"
              >
                <span className="grid h-7 w-7 place-items-center rounded-full bg-ember-500 text-sm font-extrabold text-white">
                  {index + 1}
                </span>
                <span className="flex-1 text-sm font-semibold text-white">{topic}</span>
                <span className="rounded-lg bg-white/[0.06] px-2.5 py-1 text-xs text-slate-300">
                  {8 + index} key points
                </span>
                <ChevronDown className="h-4 w-4 text-slate-500" />
              </div>
            ))}
          </div>

          <div className="mt-6">
            {preview.artifacts.length === 0 ? (
              <p className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-400">
                No artifacts available yet.
              </p>
            ) : (
              <div className="grid gap-2">
                {preview.artifacts.map((artifact) => {
                  const Icon = artifact.icon;
                  return (
                    <a
                      key={artifact.name}
                      href={artifact.url}
                      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-4 text-sm font-extrabold transition ${
                        artifact.name === "final.pdf"
                          ? "bg-gradient-to-r from-ember-500 to-ember-700 text-white shadow-ember"
                          : "border border-white/10 bg-white/[0.04] text-slate-100 hover:border-ember-500/60"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      {artifact.label}
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

function SummaryStat({ label, value }) {
  return (
    <div className="rounded-xl bg-white/[0.04] p-3">
      <p className="text-base font-extrabold text-white">{value}</p>
      <p className="mt-1 text-slate-400">{label}</p>
    </div>
  );
}

function buildPreviewModel(selectedJob, createdJob, selectedStyle) {
  if (selectedJob?.job) {
    const job = selectedJob.job;
    const availability = selectedJob.artifact_availability ?? {};
    return {
      id: job.id,
      title: job.title || "Untitled study guide",
      status: job.status || "unknown",
      providerModel: [job.provider, job.model].filter(Boolean).join(" / "),
      createdAt: job.created_at,
      style: selectedStyle,
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
      style: selectedStyle,
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

function previewTopics(preview) {
  const base = preview?.style === "master_longform"
    ? ["Conceptual Foundations", "Detailed Derivations", "Worked Examples", "Matrix Form", "Exam Practice", "Cheat Sheet"]
    : ["Core Concepts", "Key Formulas", "Worked Examples", "Common Mistakes", "Practice Questions", "Final Review"];
  return base;
}
