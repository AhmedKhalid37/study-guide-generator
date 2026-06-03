import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  ChevronRight,
  Download,
  Folder,
  Home,
  Layers3,
  Library,
  PenLine,
  Plus,
  Sparkles,
  Upload,
  Wand2
} from "lucide-react";
import BuilderWorkspace from "./BuilderWorkspace";
import RecentJobsPanel from "./RecentJobsPanel";
import StylesWorkspace from "./StylesWorkspace";
import LibraryWorkspace from "./LibraryWorkspace";
import ExportsWorkspace from "./ExportsWorkspace";
import ProviderSettingsWorkspace from "./ProviderSettingsWorkspace";
import HomeShortcuts from "./HomeShortcuts";
import { INPUT_TO_SOURCE } from "../shortcutMeta";
import { getJobs } from "../api/client";
import {
  BoltGlyph,
  BookGlyph,
  DocGlyph,
  ListGlyph,
  PDFGlyph,
  SearchI,
  SettingsI,
  SparkleGlyph,
  Tile,
  UploadGlyph
} from "./ClaudeIcons";

const navItems = [
  { id: "home", label: "Home", icon: Home },
  { id: "builder", label: "Builder", icon: PenLine },
  { id: "library", label: "Library", icon: Library },
  { id: "styles", label: "Styles", icon: Layers3 },
  { id: "models", label: "Models", icon: Bot },
  { id: "exports", label: "Exports", icon: Download }
];

// Where each shortcut `tool` key routes. Tools without a dedicated page land on
// the closest workspace (the Builder hosts clean/improve/outline flows).
const TOOL_ROUTES = {
  clean_markdown: { section: "builder", source: "upload" },
  improve_guide: { section: "builder", source: "llm" },
  add_style: { section: "styles" },
  compare_styles: { section: "styles" },
  export_center: { section: "exports" },
  find_guide: { section: "library", view: "search:" },
  quiz: { section: "library" },
  outline: { section: "builder", source: "llm" }
};

export default function DesktopDashboard() {
  const [activeSection, setActiveSection] = useState("home");
  const [builderSource, setBuilderSource] = useState("llm");
  const [selectedStyle, setSelectedStyle] = useState("exam_cram");
  const [jobsRefreshKey, setJobsRefreshKey] = useState(0);
  const [latestJob, setLatestJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  // Builder prefill from a builder_setup shortcut: { payload, nonce }.
  const [builderPrefill, setBuilderPrefill] = useState(null);
  // Library view requested by a library_view/tool shortcut: { view, nonce }.
  const [libraryView, setLibraryView] = useState(null);
  // Latest Builder setup snapshot, so the customize modal can "Capture from Builder".
  const [builderSetup, setBuilderSetup] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getJobs().then((data) => !cancelled && setJobs(data.jobs ?? [])).catch(() => !cancelled && setJobs([]));
    return () => {
      cancelled = true;
    };
  }, [jobsRefreshKey]);

  // Generic "New Guide" opens the AI/LLM mode by default; explicit shortcuts
  // (paste/upload/llm) still override by passing their source.
  const openBuilder = useCallback((source = "llm") => {
    setBuilderSource(source);
    setActiveSection("builder");
  }, []);

  const handleJobCreated = useCallback((job) => {
    setLatestJob(job);
    setJobsRefreshKey((key) => key + 1);
  }, []);

  // Route a clicked shortcut. Invalid shortcuts never load a broken setup — they
  // send the user to where they'd fix the problem instead.
  const handleActivateShortcut = useCallback((shortcut) => {
    if (!shortcut) return;
    const invalid = shortcut.valid === false;

    if (shortcut.type === "builder_setup") {
      if (invalid) {
        // e.g. references a provider with no API key — send them to Models.
        setActiveSection("models");
        return;
      }
      const payload = shortcut.payload || {};
      if (payload.style) setSelectedStyle(payload.style);
      setBuilderSource(INPUT_TO_SOURCE[payload.input_type] || "llm");
      setBuilderPrefill({ payload, nonce: Date.now() });
      setActiveSection("builder");
      return;
    }

    if (shortcut.type === "tool") {
      const route = TOOL_ROUTES[shortcut.payload?.tool];
      if (!route) {
        setActiveSection("home");
        return;
      }
      if (route.view) setLibraryView({ view: route.view, nonce: Date.now() });
      if (route.section === "builder" && route.source) setBuilderSource(route.source);
      setActiveSection(route.section);
      return;
    }

    if (shortcut.type === "library_view") {
      const view = shortcut.payload?.view || "recent";
      setLibraryView({ view, nonce: Date.now() });
      setActiveSection("library");
    }
  }, []);

  return (
    <section className="sg mx-auto h-[calc(100vh-56px)] min-h-[820px] w-full max-w-[1920px]">
      <ClaudeFrame activeSection={activeSection} onNavigate={setActiveSection} onNewGuide={() => openBuilder()}>
        {activeSection === "home" && (
          <HomeShortcuts
            jobs={jobs}
            jobsRefreshKey={jobsRefreshKey}
            onActivateShortcut={handleActivateShortcut}
            onNewGuide={() => openBuilder()}
            onNavigate={setActiveSection}
            currentBuilderSetup={builderSetup}
          />
        )}
        {activeSection === "builder" && (
          <BuilderWorkspace
            initialSource={builderSource}
            selectedStyle={selectedStyle}
            onSelectStyle={setSelectedStyle}
            latestJob={latestJob}
            onJobCreated={handleJobCreated}
            prefill={builderPrefill}
            onReportSetup={setBuilderSetup}
          />
        )}
        {activeSection === "models" && <ProviderSettingsWorkspace />}
        {activeSection === "styles" && (
          <StylesWorkspace selectedStyle={selectedStyle} onSelectStyle={setSelectedStyle} onOpenBuilder={openBuilder} />
        )}
        {activeSection === "library" && (
          <LibraryWorkspace refreshKey={jobsRefreshKey} onOpenBuilder={openBuilder} initialView={libraryView} />
        )}
        {activeSection === "exports" && <ExportsWorkspace refreshKey={jobsRefreshKey} onOpenBuilder={openBuilder} />}
      </ClaudeFrame>
    </section>
  );
}

function ClaudeFrame({ activeSection, onNavigate, onNewGuide, children }) {
  return (
    <div className="sg-frame">
      <AmbientBackdrop />
      <div className="sg-frame-content">
        <TitleBar />
        <div className="sg-main-row">
          <Sidebar activeSection={activeSection} onNavigate={onNavigate} onNewGuide={onNewGuide} />
          <main className="sg-route">{children}</main>
        </div>
      </div>
    </div>
  );
}

function AmbientBackdrop() {
  return (
    <>
      <div className="sg-glow sg-glow-a"><div className="sg-glow-inner" /></div>
      <div className="sg-glow sg-glow-b"><div className="sg-glow-inner" /></div>
      <div className="sg-stars">
        {[{ x: 20, y: 30 }, { x: 70, y: 65 }, { x: 85, y: 20 }, { x: 15, y: 75 }, { x: 45, y: 12 }, { x: 92, y: 78 }].map((star, index) => (
          <span
            key={index}
            className="sg-star"
            style={{ left: `${star.x}%`, top: `${star.y}%`, animationDelay: `${index * -1.2}s` }}
          />
        ))}
      </div>
    </>
  );
}

function TitleBar() {
  return (
    <header className="sg-titlebar">
      <div className="sg-title-left">
        <Tile size={20} radius={6}>
          <span className="sg-book-page"><BookGlyph size={12} /></span>
        </Tile>
        <span>Study Guide Generator</span>
      </div>
      <div className="sg-commandbar">
        <SearchI size={13} stroke="#9098A8" sw={2} />
        <span>Search guides, styles, or paste a URL...</span>
        <kbd>Ctrl + K</kbd>
      </div>
      <div className="sg-window-buttons" aria-hidden>
        <button><span /></button>
        <button><i /></button>
        <button className="sg-close"><b /></button>
      </div>
    </header>
  );
}

function Sidebar({ activeSection, onNavigate, onNewGuide }) {
  const navRef = useRef(null);
  const [barTop, setBarTop] = useState(0);
  const activeIndex = navItems.findIndex((item) => item.id === activeSection);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    const row = nav.querySelectorAll("[data-side-row]")[activeIndex];
    if (!row) return;
    const navRect = nav.getBoundingClientRect();
    const rowRect = row.getBoundingClientRect();
    setBarTop(rowRect.top - navRect.top + rowRect.height / 2 - 9);
  }, [activeIndex]);

  return (
    <aside className="sg-sidebar">
      <div className="sg-sidebar-label">Workspace</div>
      <button type="button" className="sg-sidebar-new sg-press-btn" onClick={onNewGuide}>
        <Plus size={15} stroke="#1A1206" strokeWidth={2.5} />
        New Guide
      </button>
      <nav ref={navRef} className="sg-sidebar-nav">
        <span className="sg-side-bar" style={{ transform: `translate3d(-12px, ${barTop}px, 0)` }} />
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = item.id === activeSection;
          return (
            <button
              key={item.id}
              type="button"
              data-side-row
              onClick={() => onNavigate(item.id)}
              className={`sg-side-row ${active ? "active" : ""}`}
            >
              <span className="sg-side-icon"><Icon size={18} /></span>
              {item.label}
            </button>
          );
        })}
      </nav>
      <div className="sg-sidebar-spacer" />
      <div className="sg-storage-card">
        <div>
          <span>Library</span>
          <span>On disk</span>
        </div>
        <div className="sg-storage-meter"><i /></div>
        <p>Generated guides stay in the local jobs store.</p>
      </div>
      <div className="sg-user-row">
        <span>A</span>
        <div>
          <strong>Ahmed</strong>
          <em>Local workspace</em>
        </div>
        <SettingsI size={16} stroke="#6B7185" sw={2} />
      </div>
    </aside>
  );
}
