import React, { useCallback, useMemo, useState } from "react";
import {
  Bot,
  Box,
  Brain,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  Flame,
  Folder,
  Home,
  Layers3,
  Library,
  ListChecks,
  PackageCheck,
  PenLine,
  Search,
  Settings2,
  Sparkles,
  Upload,
  UserRound,
  Wand2,
  Zap
} from "lucide-react";
import BrandMark from "./BrandMark";
import BuilderWorkspace from "./BuilderWorkspace";
import RecentJobsPanel from "./RecentJobsPanel";

const sections = [
  { id: "home", label: "Home", icon: Home },
  { id: "builder", label: "Builder", icon: PenLine },
  { id: "library", label: "Library", icon: Library },
  { id: "styles", label: "Styles", icon: Layers3 },
  { id: "models", label: "Models", icon: Bot },
  { id: "exports", label: "Exports", icon: Download }
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
    source: "paste",
    icon: FileText,
    color: "blue",
    description: "Drop in notes and generate a polished guide."
  },
  {
    label: "Upload Markdown",
    source: "upload",
    icon: Upload,
    color: "purple",
    description: "Turn a .md file into a styled PDF."
  },
  {
    label: "Generate with AI",
    source: "llm",
    icon: Wand2,
    color: "orange",
    description: "Describe a topic and build from source material."
  }
];

const guideStyles = [
  {
    label: "Baby-Step Explanations",
    promptName: "baby_steps",
    icon: Layers3,
    description: "Simple, step-by-step explanations."
  },
  {
    label: "Exam Cram",
    promptName: "exam_cram",
    icon: Zap,
    description: "High-yield notes for revision."
  },
  {
    label: "MCQ Training",
    promptName: "mcq_training",
    icon: ListChecks,
    description: "Practice questions with reasoning."
  },
  {
    label: "Final Solutions",
    promptName: "final_solution",
    icon: PackageCheck,
    description: "Clean solution-key style steps."
  },
  {
    label: "Claude-style Guides",
    promptName: "claude_study_guide",
    icon: Sparkles,
    description: "Structured editorial study guides."
  },
  {
    label: "Master Longform",
    promptName: "master_longform",
    icon: Brain,
    description: "Deep 10+ page master guides."
  }
];

export default function DesktopDashboard() {
  const [activeSection, setActiveSection] = useState("home");
  const [builderSource, setBuilderSource] = useState("paste");
  const [selectedStyle, setSelectedStyle] = useState("exam_cram");
  const [jobsRefreshKey, setJobsRefreshKey] = useState(0);
  const [latestJob, setLatestJob] = useState(null);

  const openBuilder = useCallback((source = "paste") => {
    setBuilderSource(source);
    setActiveSection("builder");
  }, []);

  const handleJobCreated = useCallback((job) => {
    setLatestJob(job);
    setJobsRefreshKey((key) => key + 1);
  }, []);

  const pageTitle = useMemo(
    () => sections.find((section) => section.id === activeSection)?.label ?? "Home",
    [activeSection]
  );

  return (
    <section className="mx-auto w-full max-w-[1920px]">
      <div className="overflow-hidden rounded-[1.75rem] border border-white/15 bg-[radial-gradient(circle_at_32%_0%,rgba(21,67,116,0.48),transparent_34%),linear-gradient(135deg,#071426_0%,#020713_58%,#061225_100%)] shadow-[0_34px_140px_rgba(0,0,0,0.62),inset_0_1px_0_rgba(255,255,255,0.08)]">
        <WindowChrome />
        <div className="grid min-h-[780px] xl:grid-cols-[288px_minmax(0,1fr)]">
          <Sidebar
            activeSection={activeSection}
            onSectionChange={setActiveSection}
            onNewGuide={() => openBuilder("paste")}
          />
          <main className="min-w-0 border-l border-white/10">
            <TopWorkspaceBar title={pageTitle} />
            <div className="p-6 lg:p-8">
              {activeSection === "home" && (
                <HomeDashboard
                  selectedStyle={selectedStyle}
                  onSelectStyle={setSelectedStyle}
                  onOpenBuilder={openBuilder}
                  jobsRefreshKey={jobsRefreshKey}
                />
              )}
              {activeSection === "builder" && (
                <BuilderWorkspace
                  initialSource={builderSource}
                  selectedStyle={selectedStyle}
                  onSelectStyle={setSelectedStyle}
                  latestJob={latestJob}
                  onJobCreated={handleJobCreated}
                />
              )}
              {activeSection !== "home" && activeSection !== "builder" && (
                <PlaceholderSection
                  title={pageTitle}
                  onOpenBuilder={() => openBuilder("paste")}
                />
              )}
            </div>
          </main>
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

function Sidebar({ activeSection, onSectionChange, onNewGuide }) {
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
        {sections.map((item) => {
          const Icon = item.icon;
          const active = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSectionChange(item.id)}
              className={`flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold transition ${
                active
                  ? "bg-white/[0.075] text-white"
                  : "text-slate-300 hover:bg-white/[0.05] hover:text-white"
              }`}
            >
              <Icon className={`h-4 w-4 ${active ? "text-ember-500" : "text-slate-400"}`} />
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

function TopWorkspaceBar({ title }) {
  return (
    <header className="flex min-h-20 items-center justify-between gap-5 border-b border-white/10 px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-ember-500">Workspace</p>
        <h1 className="mt-1 text-xl font-extrabold text-white">{title}</h1>
      </div>
      <div className="hidden min-w-[420px] items-center rounded-xl border border-white/10 bg-white/[0.045] px-4 py-3 text-sm text-slate-400 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] lg:flex">
        <Search className="mr-3 h-4 w-4 text-slate-500" />
        <span className="flex-1">Search guides, drafts, models, and exports...</span>
        <span className="rounded-md border border-white/10 bg-white/[0.06] px-2 py-0.5 text-xs text-slate-300">
          ⌘ K
        </span>
      </div>
    </header>
  );
}

function HomeDashboard({ selectedStyle, onSelectStyle, onOpenBuilder, jobsRefreshKey }) {
  return (
    <div className="mx-auto max-w-[1180px]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-3xl font-extrabold tracking-normal text-white">
            Good evening, Ahmed 👋
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Turn your content into high-quality study guides in seconds.
          </p>
        </div>
        <button
          type="button"
          onClick={() => onOpenBuilder("paste")}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-ember-500 to-ember-700 px-4 text-sm font-extrabold text-white shadow-ember transition hover:brightness-110"
        >
          <Wand2 className="h-4 w-4" />
          Open Builder
        </button>
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-3">
        {actions.map((action) => (
          <ActionCard
            key={action.source}
            action={action}
            onClick={() => onOpenBuilder(action.source)}
          />
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between">
        <h3 className="text-xl font-extrabold text-white">Choose a guide style</h3>
        <button type="button" className="text-sm font-medium text-slate-300 hover:text-white">
          See all
        </button>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {guideStyles.map((style) => (
          <StyleCard
            key={style.promptName}
            style={style}
            selected={selectedStyle === style.promptName}
            onClick={() => onSelectStyle(style.promptName)}
          />
        ))}
      </div>

      <div className="mt-8">
        <RecentJobsPanel embedded refreshKey={jobsRefreshKey} />
      </div>
    </div>
  );
}

function ActionCard({ action, onClick }) {
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
      className="min-h-[176px] rounded-2xl border border-white/10 bg-white/[0.035] p-5 text-left transition hover:border-ember-500/45 hover:bg-ember-500/[0.055]"
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
      className={`relative min-h-[166px] rounded-2xl border p-4 text-left transition ${
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

function PlaceholderSection({ title, onOpenBuilder }) {
  return (
    <div className="mx-auto grid min-h-[600px] max-w-4xl place-items-center">
      <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-10 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-ember-500/15 text-ember-400">
          <Box className="h-7 w-7" />
        </div>
        <h2 className="mt-5 text-2xl font-extrabold text-white">{title}</h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-400">
          This workspace section is ready for the next UI phase. Guide creation is available in Builder.
        </p>
        <button
          type="button"
          onClick={onOpenBuilder}
          className="mt-6 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-ember-500 to-ember-700 px-4 text-sm font-extrabold text-white shadow-ember"
        >
          <PenLine className="h-4 w-4" />
          Go to Builder
        </button>
      </div>
    </div>
  );
}
