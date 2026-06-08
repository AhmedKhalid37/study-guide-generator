import React, { useCallback, useEffect, useState } from "react";
import BuilderWorkspace from "./BuilderWorkspace";
import StylesWorkspace from "./StylesWorkspace";
import LibraryWorkspace from "./LibraryWorkspace";
import ExportsWorkspace from "./ExportsWorkspace";
import ProviderSettingsWorkspace from "./ProviderSettingsWorkspace";
import AskGuideWorkspace from "./AskGuideWorkspace";
import HomeShortcuts from "./HomeShortcuts";
import Icon from "./Icon";
import Button, { IconButton } from "./Button";
import { INPUT_TO_SOURCE } from "../shortcutMeta";
import { getJobs } from "../api/client";

// Sidebar nav, grouped to match the reskin reference. The ids and order are the
// real activeSection ids consumed below — only the icon keys (resolved against
// the Icon map) and the section grouping are presentational.
const navSections = [
  {
    label: "General",
    items: [
      { id: "home", label: "Home", icon: "home" },
      { id: "builder", label: "Builder", icon: "builder" },
      { id: "library", label: "Library", icon: "library" },
      { id: "ask", label: "Ask Guide", icon: "ask" }
    ]
  },
  {
    label: "Tools / Resources",
    items: [
      { id: "styles", label: "Styles", icon: "styles" },
      { id: "models", label: "Models", icon: "models" },
      { id: "exports", label: "Exports", icon: "exports" }
    ]
  }
];

// Where each shortcut `tool` key routes. Tools without a dedicated page land on
// the closest workspace (the Builder hosts clean/improve/outline flows).
const TOOL_ROUTES = {
  clean_markdown: { section: "builder", source: "upload" },
  improve_guide: { section: "builder", source: "llm" },
  add_style: { section: "styles" },
  compare_styles: { section: "styles" },
  ask_guide: { section: "ask" },
  export_center: { section: "exports" },
  find_guide: { section: "library", view: "search:" },
  quiz: { section: "library" },
  outline: { section: "builder", source: "llm" }
};

// Sidebar collapsed-state persistence. This is the real Vite app, so
// localStorage is fine; reads/writes are guarded for private-mode browsers.
const SIDEBAR_COLLAPSE_KEY = "gf:sidebar-collapsed";

function readSidebarCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

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
  // Collapsed sidebar — local UI state only, persisted across reloads.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarCollapsed);

  useEffect(() => {
    let cancelled = false;
    getJobs().then((data) => !cancelled && setJobs(data.jobs ?? [])).catch(() => !cancelled && setJobs([]));
    return () => {
      cancelled = true;
    };
  }, [jobsRefreshKey]);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSE_KEY, sidebarCollapsed ? "1" : "0");
    } catch {
      // ignore (private mode / storage disabled) — state still works in-session
    }
  }, [sidebarCollapsed]);

  const toggleSidebar = useCallback(() => setSidebarCollapsed((v) => !v), []);

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
    <div className={`app ${sidebarCollapsed ? "is-collapsed" : ""}`.trim()}>
      <Sidebar
        activeSection={activeSection}
        onNavigate={setActiveSection}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />
      <div className="main">
        <Topbar onNavigate={setActiveSection} />
        <div className="content scroll">
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
          {activeSection === "ask" && <AskGuideWorkspace />}
          {activeSection === "styles" && (
            <StylesWorkspace selectedStyle={selectedStyle} onSelectStyle={setSelectedStyle} onOpenBuilder={openBuilder} />
          )}
          {activeSection === "library" && (
            <LibraryWorkspace refreshKey={jobsRefreshKey} onOpenBuilder={openBuilder} initialView={libraryView} />
          )}
          {activeSection === "exports" && <ExportsWorkspace refreshKey={jobsRefreshKey} onOpenBuilder={openBuilder} />}
        </div>
      </div>
    </div>
  );
}

// Presentational switch visual (a <div> so the .toggle box renders inside the
// owning button); the surrounding button carries the interaction + aria.
function Toggle({ on }) {
  return (
    <div className={`toggle ${on ? "on" : ""}`} aria-hidden="true">
      <div className="knob" />
    </div>
  );
}

function Sidebar({ activeSection, onNavigate, collapsed, onToggleCollapse }) {
  // The app is dark-only today; the toggle is presentational (slides locally)
  // until a real theme switch exists.
  const [dark, setDark] = useState(true);

  // When collapsed, the label text is visually hidden (kept in the DOM as the
  // accessible name); a native title surfaces it as a hover tooltip.
  const tip = (label) => (collapsed ? label : undefined);

  const renderItem = (item) => {
    const active = item.id === activeSection;
    return (
      <Button
        key={item.id}
        variant="bare"
        className={`nav-item ${active ? "active" : ""}`.trim()}
        aria-current={active ? "page" : undefined}
        title={tip(item.label)}
        onClick={() => onNavigate(item.id)}
      >
        {Icon[item.icon]()}
        <span>{item.label}</span>
      </Button>
    );
  };

  const toggleDark = () => setDark((v) => !v);

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">{Icon.logo({ width: 30, height: 30 })}</div>
        <div className="brand-name">GuideForge</div>
        <IconButton
          className="sidebar-collapse"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={onToggleCollapse}
        >
          {collapsed ? Icon.chevronRight() : Icon.chevronLeft()}
        </IconButton>
      </div>

      <div className="scroll" style={{ flex: "1 1 auto", margin: "0 -6px", padding: "0 6px" }}>
        {navSections.map((section) => (
          <div className="nav-section" key={section.label}>
            <div className="nav-label">{section.label}</div>
            {section.items.map(renderItem)}
          </div>
        ))}

        <div className="nav-section">
          <div className="nav-label">Settings</div>
          {/* Help & Settings have no dedicated workspace yet — presentational rows. */}
          <Button variant="bare" className="nav-item" title={tip("Help")}>
            {Icon.help()}
            <span>Help</span>
          </Button>
          {/* The whole row is the switch — no nested button. */}
          <Button
            variant="bare"
            className="nav-item"
            role="switch"
            aria-checked={dark}
            title={tip("Dark Mode")}
            onClick={toggleDark}
          >
            {Icon.moon()}
            <span>Dark Mode</span>
            <Toggle on={dark} />
          </Button>
          <Button variant="bare" className="nav-item" title={tip("Settings")}>
            {Icon.settings()}
            <span>Settings</span>
          </Button>
        </div>
      </div>

      <div className="profile-divider" />
      <div className="profile">
        <div className="avatar" />
        <div>
          <div className="profile-name">Ahmed</div>
          <div className="profile-mail">Local workspace</div>
        </div>
      </div>
      <Button variant="bare" className="signout" title={tip("Sign Out")}>
        {Icon.signout()}
        <span>Sign Out</span>
      </Button>
    </aside>
  );
}

function Topbar({ onNavigate }) {
  return (
    <header className="topbar">
      <div style={{ width: 1 }} />
      <div className="search">
        {Icon.search()}
        <input placeholder="Search guides, sources, quizzes…" />
        <span className="kbd">⌘ + F</span>
      </div>
      <div className="topbar-right">
        <Button variant="assistant" onClick={() => onNavigate("ask")}>
          {Icon.sparkle()} Ask Guide
        </Button>
        <IconButton aria-label="History">{Icon.history()}</IconButton>
        <IconButton aria-label="Messages">{Icon.mail()}</IconButton>
        <IconButton aria-label="Notifications">{Icon.bell()}</IconButton>
      </div>
    </header>
  );
}
