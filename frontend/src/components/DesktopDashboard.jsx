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
import { getJobs, getOptions } from "../api/client";
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

const smartTools = [
  { id: "styles", title: "Compare Styles", subtitle: "Pick a generation format", icon: SparkleGlyph, route: "styles" },
  { id: "library", title: "Find a Guide", subtitle: "Browse generated jobs", icon: DocGlyph, route: "library" },
  { id: "exports", title: "Export Center", subtitle: "PDF, Markdown, HTML", icon: PDFGlyph, route: "exports" },
  { id: "clean", title: "Clean Markdown", subtitle: "Available through Builder", icon: ListGlyph, disabled: true },
  { id: "template", title: "Create Template", subtitle: "Placeholder", icon: BookGlyph, disabled: true },
  { id: "improve", title: "Improve a Guide", subtitle: "Placeholder", icon: Wand2, disabled: true }
];

export default function DesktopDashboard() {
  const [activeSection, setActiveSection] = useState("home");
  const [builderSource, setBuilderSource] = useState("paste");
  const [selectedStyle, setSelectedStyle] = useState("exam_cram");
  const [jobsRefreshKey, setJobsRefreshKey] = useState(0);
  const [latestJob, setLatestJob] = useState(null);
  const [apiOptions, setApiOptions] = useState(null);
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    let cancelled = false;
    getOptions().then((options) => !cancelled && setApiOptions(options)).catch(() => !cancelled && setApiOptions(null));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getJobs().then((data) => !cancelled && setJobs(data.jobs ?? [])).catch(() => !cancelled && setJobs([]));
    return () => {
      cancelled = true;
    };
  }, [jobsRefreshKey]);

  const openBuilder = useCallback((source = "paste") => {
    setBuilderSource(source);
    setActiveSection("builder");
  }, []);

  const handleJobCreated = useCallback((job) => {
    setLatestJob(job);
    setJobsRefreshKey((key) => key + 1);
  }, []);

  return (
    <section className="sg mx-auto h-[calc(100vh-56px)] min-h-[820px] w-full max-w-[1920px]">
      <ClaudeFrame activeSection={activeSection} onNavigate={setActiveSection} onNewGuide={() => openBuilder("paste")}>
        {activeSection === "home" && (
          <HomeCommandCenter
            jobs={jobs}
            onOpenBuilder={openBuilder}
            onNavigate={setActiveSection}
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
        {activeSection === "models" && <ModelsPage apiOptions={apiOptions} />}
        {activeSection === "styles" && (
          <StylesWorkspace selectedStyle={selectedStyle} onSelectStyle={setSelectedStyle} onOpenBuilder={openBuilder} />
        )}
        {activeSection === "library" && <LibraryWorkspace refreshKey={jobsRefreshKey} onOpenBuilder={openBuilder} />}
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
          <span>32/100</span>
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

function HomeCommandCenter({ jobs, onOpenBuilder, onNavigate, jobsRefreshKey }) {
  const commandCards = [
    { id: "paste", title: "Paste Text", subtitle: "Drop in notes and generate a polished guide.", pill: "Real flow", glyph: DocGlyph, accent: "#F97316", onClick: () => onOpenBuilder("paste") },
    { id: "upload", title: "Upload Markdown", subtitle: "Turn a .md file into a styled PDF.", pill: "Real flow", glyph: UploadGlyph, accent: "#60A5FA", onClick: () => onOpenBuilder("upload") },
    { id: "llm", title: "Generate with AI", subtitle: "Use source material with DeepSeek or Qwen.", pill: "Real flow", glyph: SparkleGlyph, accent: "#A855F7", onClick: () => onOpenBuilder("llm") },
    { id: "styles", title: "Manage Styles", subtitle: "Use built-in, custom, or AI-generated styles.", pill: "Styles", glyph: Layers3, accent: "#C084FC", onClick: () => onNavigate("styles") },
    { id: "exam", title: "Exam Tomorrow", subtitle: "Use the exam-cram preset and jump into Builder.", pill: "Exam Cram", glyph: BoltGlyph, accent: "#F59E0B", onClick: () => onOpenBuilder("paste") },
    { id: "library", title: "Open Library", subtitle: "Browse the generated job archive.", pill: `${jobs.length} jobs`, glyph: BookGlyph, accent: "#34D399", onClick: () => onNavigate("library") },
    { id: "exports", title: "Export Center", subtitle: "Find PDFs, Markdown, HTML, logs, and validation.", pill: "Artifacts", glyph: PDFGlyph, accent: "#F43F5E", onClick: () => onNavigate("exports") }
  ];

  return (
    <div className="sg-page sg-home">
      <div className="sg-grid-glow" />
      <div className="sg-page-head">
        <div>
          <h1>Good evening, Ahmed</h1>
          <p>Pick a goal. The real generator pipeline stays connected behind every guide action.</p>
        </div>
        <button type="button" className="sg-cta sg-press-btn" onClick={() => onOpenBuilder("paste")}>
          <Plus size={16} stroke="#1A1206" strokeWidth={2.6} />
          New Guide
        </button>
      </div>

      <div className="sg-section-head">
        <h2>What are you preparing for?</h2>
        <button type="button" className="sg-ghost-button" onClick={() => onNavigate("styles")}>Customize</button>
      </div>

      <div className="sg-command-grid">
        {commandCards.map((card, index) => (
          <CommandCard key={card.id} card={card} delay={index * 45} />
        ))}
      </div>

      <div className="sg-section-head">
        <h2>Smart Tools</h2>
        <span>Lightweight workflows around the real guide pipeline</span>
      </div>
      <div className="sg-smart-grid">
        {smartTools.map((tool) => (
          <SmartToolCard key={tool.id} tool={tool} onNavigate={onNavigate} />
        ))}
      </div>

      <div className="sg-section-head sg-recent-head">
        <h2>Recent Guides</h2>
        <button type="button" className="sg-ghost-button" onClick={() => onNavigate("library")}>View all</button>
      </div>
      <RecentJobsPanel embedded refreshKey={jobsRefreshKey} />
    </div>
  );
}

function CommandCard({ card, delay }) {
  const Glyph = card.glyph;
  return (
    <button
      type="button"
      className="sg-command-card sg-press-btn"
      onClick={card.onClick}
      style={{ "--accent": card.accent, animationDelay: `${delay}ms` }}
    >
      <span className="sg-card-corner" />
      <span className="sg-card-top">
        <span className="sg-card-icon"><Glyph size={26} color={card.accent} /></span>
      </span>
      <strong>{card.title}</strong>
      <p>{card.subtitle}</p>
      <span className="sg-card-bottom">
        <em>{card.pill}</em>
        <i><ChevronRight size={14} /></i>
      </span>
    </button>
  );
}

function SmartToolCard({ tool, onNavigate }) {
  const Icon = tool.icon;
  const disabled = Boolean(tool.disabled);
  return (
    <button
      type="button"
      disabled={disabled}
      className="sg-smart-card sg-press-btn"
      onClick={() => !disabled && onNavigate(tool.route)}
    >
      <span>{typeof Icon === "function" && Icon.name?.endsWith("Glyph") ? <Icon size={19} color="#F97316" /> : <Icon size={18} />}</span>
      <div>
        <strong>{tool.title}</strong>
        <p>{tool.subtitle}</p>
      </div>
      <ChevronRight size={13} />
    </button>
  );
}

function ModelsPage({ apiOptions }) {
  const providerDetails = normalizeModelProviders(apiOptions);
  const defaultProvider =
    providerDetails.find((provider) => provider.configured) ||
    providerDetails[0];

  return (
    <div className="sg-page">
      <PageHead title="Models" subtitle="Server-side provider registry. Keys stay on the backend." />
      <div className="sg-default-card">
        <Tile size={42} radius={11}><SparkleGlyph size={20} /></Tile>
        <div>
          <span>Default model</span>
          <strong>
            {defaultProvider
              ? `${defaultProvider.display_name} · ${defaultProvider.default_model || defaultProvider.models[0] || "no model configured"}`
              : "Waiting for /api/options"}
          </strong>
        </div>
        <em>No secrets exposed</em>
      </div>
      <SectionHeading title="Provider registry" right="Real options from /api/options" />
      <div className="sg-provider-grid">
        {providerDetails.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} />
        ))}
      </div>
    </div>
  );
}

function ProviderCard({ provider }) {
  return (
    <div className="sg-provider-card sg-recent-row">
      <div className="sg-provider-top">
        <span>{provider.display_name.slice(0, 1)}</span>
        <div>
          <strong>{provider.display_name}</strong>
          <p>
            {provider.configured
              ? `${provider.models.length || 1} model${provider.models.length === 1 ? "" : "s"} · default ${provider.default_model || "unset"}`
              : "Not configured"}
          </p>
        </div>
      </div>
      <div className="sg-provider-tags">
        {(provider.models.length ? provider.models.slice(0, 4) : ["No models discovered"]).map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      {provider.base_url && (
        <p className="mt-2 break-all text-[11.5px] leading-5 text-[#9098A8]">
          Base URL: {provider.base_url}
        </p>
      )}
      {provider.discovery_error && (
        <p className="mt-2 text-[11.5px] leading-5 text-[#FCA5A5]">
          Discovery error: {provider.discovery_error}
        </p>
      )}
      <button type="button" className="sg-ghost-button" disabled={!provider.configured}>
        {provider.configured ? "Available in Builder" : "Configure in .env"}
      </button>
    </div>
  );
}

function normalizeModelProviders(apiOptions) {
  const details = apiOptions?.provider_details ?? apiOptions?.providers_v2;
  if (Array.isArray(details) && details.length > 0) {
    return details.map((provider) => ({
      id: provider.id,
      display_name: provider.display_name || provider.name || provider.id,
      configured: Boolean(provider.configured),
      models: Array.isArray(provider.available_models) ? provider.available_models : [],
      default_model: provider.default_model || "",
      base_url: provider.base_url || "",
      discovery_error: provider.discovery_error || ""
    }));
  }

  const providers = apiOptions?.providers ?? ["DeepSeek", "Qwen"];
  const models = apiOptions?.models ?? {};
  return providers.map((name) => ({
    id: String(name).toLowerCase(),
    display_name: name,
    configured: false,
    models: models[name] ?? [],
    default_model: models[name]?.[0] ?? "",
    base_url: "",
    discovery_error: ""
  }));
}

function PageHead({ title, subtitle, right }) {
  return (
    <div className="sg-page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

function SectionHeading({ title, right }) {
  return (
    <div className="sg-section-head">
      <h2>{title}</h2>
      {right && <span>{right}</span>}
    </div>
  );
}
