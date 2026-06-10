import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  Download,
  ExternalLink,
  FileCode2,
  FileJson,
  FileText,
  FileArchive,
  Loader2,
  Paperclip,
  RefreshCw,
  Search,
  X
} from "lucide-react";
import {
  artifactUrl,
  downloadExportBundle,
  getExports,
  getJob,
  getStyles,
  rerenderJob
} from "../api/client";
import { buildStyleLookup, resolveStyle } from "../styleMeta";
import { folderColor } from "../folderMeta";
import { JobDetailsDrawer, StylePill, FolderPill } from "./RecentJobsPanel";

// Artifact selectors mirror the backend EXPORT_ARTIFACTS map.
const ARTIFACT_TYPES = [
  { sel: "pdf", label: "PDF", availKey: "final_pdf", file: "final.pdf", icon: Download, openable: true },
  { sel: "docx", label: "DOCX", availKey: "final_docx", file: "final.docx", icon: FileText, openable: false },
  { sel: "markdown", label: "Markdown", availKey: "clean_md", file: "clean.md", icon: FileText, openable: false },
  { sel: "html", label: "HTML", availKey: "final_html", file: "final.html", icon: FileCode2, openable: true },
  { sel: "validation", label: "Validation", availKey: "validation_json", file: "validation.json", icon: FileJson, openable: false },
  { sel: "render_log", label: "Render log", availKey: "render_log", file: "render.log", icon: FileText, openable: false }
];

const SORTS = [
  { id: "newest", label: "Newest" },
  { id: "oldest", label: "Oldest" },
  { id: "title", label: "Title A–Z" },
  { id: "status", label: "Status" }
];

const emptyFilters = {
  status: "",
  provider: "",
  style: "",
  folder: "",
  artifact: "",
  hasAttachments: false,
  hasWarnings: false
};

function statusClass(status) {
  if (status === "done") return "pill-green";
  if (String(status || "").includes("failed")) return "pill-red";
  return "pill-amber";
}

function jobFolder(job) {
  if (!job?.folder_name) return null;
  return { id: job.folder_id, name: job.folder_name, color: job.folder_color };
}

export default function ExportsWorkspace({ refreshKey = 0, onOpenBuilder }) {
  const [data, setData] = useState({ folders: [], jobs: [] });
  const [styleLookup, setStyleLookup] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [internalRefresh, setInternalRefresh] = useState(0);

  const [q, setQ] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [sort, setSort] = useState("newest");
  const [showFilters, setShowFilters] = useState(false);

  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bundleArtifacts, setBundleArtifacts] = useState(() => new Set(["pdf"]));
  const [bundling, setBundling] = useState(false);
  const [bundleError, setBundleError] = useState(null);
  const [rerenderingId, setRerenderingId] = useState(null);

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [jobDetails, setJobDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  const reload = useCallback(() => setInternalRefresh((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getExports()
      .then((result) => {
        if (cancelled) return;
        setData({ folders: result.folders ?? [], jobs: result.jobs ?? [] });
        setError(null);
      })
      .catch((err) => !cancelled && setError(err.message || "Could not load exports."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey, internalRefresh]);

  useEffect(() => {
    let cancelled = false;
    getStyles()
      .then((styles) => !cancelled && setStyleLookup(buildStyleLookup(styles)))
      .catch(() => !cancelled && setStyleLookup({}));
    return () => {
      cancelled = true;
    };
  }, [refreshKey, internalRefresh]);

  // Drop selected ids that no longer exist after a reload.
  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev;
      const existing = new Set(data.jobs.map((job) => job.id));
      const next = new Set();
      prev.forEach((id) => existing.has(id) && next.add(id));
      return next.size === prev.size ? prev : next;
    });
  }, [data.jobs]);

  const providers = useMemo(
    () => [...new Set(data.jobs.map((job) => job.provider).filter(Boolean))],
    [data.jobs]
  );
  const statuses = useMemo(
    () => [...new Set(data.jobs.map((job) => job.status).filter(Boolean))],
    [data.jobs]
  );
  const styleChoices = useMemo(() => {
    const map = new Map();
    data.jobs.forEach((job) => {
      if (job.prompt_name) map.set(job.prompt_name, resolveStyle(job.prompt_name, styleLookup).name);
    });
    return [...map.entries()];
  }, [data.jobs, styleLookup]);
  const folderChoices = useMemo(() => data.folders.filter((folder) => folder.id !== "all"), [data.folders]);

  const activeFilterCount =
    (filters.status ? 1 : 0) +
    (filters.provider ? 1 : 0) +
    (filters.style ? 1 : 0) +
    (filters.folder ? 1 : 0) +
    (filters.artifact ? 1 : 0) +
    (filters.hasAttachments ? 1 : 0) +
    (filters.hasWarnings ? 1 : 0);

  const filteredJobs = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const artifactType = ARTIFACT_TYPES.find((type) => type.sel === filters.artifact);
    let list = data.jobs.filter((job) => {
      if (needle) {
        const hay = [job.title, job.id, job.provider, job.model, job.prompt_name]
          .map((value) => String(value || "").toLowerCase())
          .join(" ");
        if (!hay.includes(needle)) return false;
      }
      if (filters.status && job.status !== filters.status) return false;
      if (filters.provider && String(job.provider || "").toLowerCase() !== filters.provider.toLowerCase()) return false;
      if (filters.style && job.prompt_name !== filters.style) return false;
      if (filters.folder && (job.folder_id || "unfiled") !== filters.folder) return false;
      if (artifactType && !(job.artifact_availability || {})[artifactType.availKey]) return false;
      if (filters.hasAttachments && !((job.attachment_summary?.count || 0) > 0)) return false;
      if (filters.hasWarnings && !(job.attachment_summary?.has_warnings || job.error)) return false;
      return true;
    });

    const created = (job) => String(job.created_at || job.id || "");
    if (sort === "oldest") list = [...list].sort((a, b) => created(a).localeCompare(created(b)));
    else if (sort === "title") list = [...list].sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")));
    else if (sort === "status") list = [...list].sort((a, b) => String(a.status || "").localeCompare(String(b.status || "")));
    else list = [...list].sort((a, b) => created(b).localeCompare(created(a)));
    return list;
  }, [data.jobs, q, filters, sort]);

  const visibleIds = useMemo(() => filteredJobs.map((job) => job.id), [filteredJobs]);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));

  const toggleSelect = useCallback((jobId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(jobId) ? next.delete(jobId) : next.add(jobId);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const toggleSelectAllVisible = useCallback(() => {
    setSelectedIds((prev) => {
      const everySelected = visibleIds.length > 0 && visibleIds.every((id) => prev.has(id));
      return everySelected ? new Set() : new Set(visibleIds);
    });
  }, [visibleIds]);

  const toggleBundleArtifact = useCallback((sel) => {
    setBundleArtifacts((prev) => {
      const next = new Set(prev);
      next.has(sel) ? next.delete(sel) : next.add(sel);
      return next;
    });
  }, []);

  const handleDownloadZip = useCallback(async () => {
    const ids = [...selectedIds];
    const artifacts = [...bundleArtifacts];
    if (ids.length === 0 || artifacts.length === 0) return;
    setBundling(true);
    setBundleError(null);
    try {
      await downloadExportBundle(ids, artifacts);
    } catch (err) {
      setBundleError(err.message || "Could not build the export bundle.");
    } finally {
      setBundling(false);
    }
  }, [selectedIds, bundleArtifacts]);

  const handleRerender = useCallback(
    async (jobId) => {
      setRerenderingId(jobId);
      setError(null);
      try {
        await rerenderJob(jobId);
        reload();
      } catch (err) {
        setError(err.message || "Could not re-render guide.");
      } finally {
        setRerenderingId(null);
      }
    },
    [reload]
  );

  const openDetails = useCallback(async (jobId) => {
    setDetailsOpen(true);
    setDetailsLoading(true);
    setDetailsError(null);
    setJobDetails(null);
    try {
      setJobDetails(await getJob(jobId));
    } catch (err) {
      setDetailsError(err);
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  return (
    <div className="sg-exp">
      <div className="sg-page-head">
        <div>
          <h1>Exports</h1>
          <p>{filteredJobs.length} of {data.jobs.length} guide{data.jobs.length === 1 ? "" : "s"} · download artifacts or bundle as ZIP</p>
        </div>
        <button type="button" className="sg-cta sg-press-btn" onClick={() => onOpenBuilder?.()}>
          <Download size={16} strokeWidth={2.4} />
          New Guide
        </button>
      </div>

      <Toolbar
        q={q}
        setQ={setQ}
        sort={sort}
        setSort={setSort}
        showFilters={showFilters}
        setShowFilters={setShowFilters}
        activeFilterCount={activeFilterCount}
      />

      {showFilters && (
        <FilterBar
          filters={filters}
          setFilters={setFilters}
          statuses={statuses}
          providers={providers}
          styleChoices={styleChoices}
          folderChoices={folderChoices}
          onClear={() => setFilters(emptyFilters)}
        />
      )}

      {error && (
        <div className="sg-exp-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {selectedIds.size > 0 && (
        <BundleBar
          count={selectedIds.size}
          bundleArtifacts={bundleArtifacts}
          onToggleArtifact={toggleBundleArtifact}
          onDownload={handleDownloadZip}
          onClear={clearSelection}
          bundling={bundling}
          bundleError={bundleError}
        />
      )}

      {!loading && filteredJobs.length > 0 && (
        <label className="sg-selectall">
          <input
            type="checkbox"
            checked={allVisibleSelected}
            onChange={toggleSelectAllVisible}
          />
          Select all visible ({visibleIds.length})
        </label>
      )}

      <div className="sg-exp-list">
        {loading ? (
          <div className="sg-exp-loading">
            <Loader2 className="sg-spin" />
            <span>Loading exports…</span>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="sg-exp-empty">
            <FileArchive />
            <span>No guides match this view.</span>
          </div>
        ) : (
          <div className="sg-exp-cards">
            {filteredJobs.map((job) => (
              <ExportCard
                key={job.id}
                job={job}
                style={resolveStyle(job.prompt_name, styleLookup)}
                folder={jobFolder(job)}
                selected={selectedIds.has(job.id)}
                onToggleSelect={toggleSelect}
                onDetails={() => openDetails(job.id)}
                onRerender={handleRerender}
                rerendering={rerenderingId === job.id}
              />
            ))}
          </div>
        )}
      </div>

      <JobDetailsDrawer
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        loading={detailsLoading}
        error={detailsError}
        details={jobDetails}
        styleLookup={styleLookup}
        onRetry={reload}
      />
    </div>
  );
}

function Toolbar({ q, setQ, sort, setSort, showFilters, setShowFilters, activeFilterCount }) {
  const filterActive = activeFilterCount > 0 || showFilters;
  return (
    <div className="sg-exp-toolbar">
      <div className="sg-search">
        <Search />
        <input
          placeholder="Search title, id, provider, or style…"
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        {q && (
          <button type="button" onClick={() => setQ("")} aria-label="Clear search">
            <X size={14} />
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowFilters((open) => !open)}
        className={`sg-filter-btn${filterActive ? " active" : ""}`}
      >
        Filters
        {activeFilterCount > 0 && <span className="sg-filter-badge">{activeFilterCount}</span>}
        <ChevronDown size={14} style={showFilters ? { transform: "rotate(180deg)" } : undefined} />
      </button>

      <label className="sg-sort">
        <span>Sort</span>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          {SORTS.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function FilterBar({ filters, setFilters, statuses, providers, styleChoices, folderChoices, onClear }) {
  const set = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  return (
    <div className="sg-filterbar">
      <FilterSelect
        label="Artifact"
        value={filters.artifact}
        onChange={(value) => set("artifact", value)}
        options={ARTIFACT_TYPES.map((type) => ({ value: type.sel, label: type.label }))}
      />
      <FilterSelect label="Status" value={filters.status} onChange={(value) => set("status", value)} options={statuses} />
      <FilterSelect
        label="Folder"
        value={filters.folder}
        onChange={(value) => set("folder", value)}
        options={folderChoices.map((folder) => ({ value: folder.id, label: folder.name }))}
      />
      <FilterSelect label="Provider" value={filters.provider} onChange={(value) => set("provider", value)} options={providers} />
      <FilterSelect
        label="Style"
        value={filters.style}
        onChange={(value) => set("style", value)}
        options={styleChoices.map(([id, name]) => ({ value: id, label: name }))}
      />
      <button
        type="button"
        className={`sg-toggle-chip${filters.hasAttachments ? " active" : ""}`}
        onClick={() => set("hasAttachments", !filters.hasAttachments)}
      >
        <Paperclip size={13} /> Attachments
      </button>
      <button
        type="button"
        className={`sg-toggle-chip${filters.hasWarnings ? " active" : ""}`}
        onClick={() => set("hasWarnings", !filters.hasWarnings)}
      >
        <AlertCircle size={13} /> Warnings
      </button>
      <button type="button" className="sg-filter-clear" onClick={onClear}>
        Clear all
      </button>
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  const normalized = options.map((option) =>
    typeof option === "string" ? { value: option, label: option } : option
  );
  return (
    <label className="sg-filter-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {normalized.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function BundleBar({ count, bundleArtifacts, onToggleArtifact, onDownload, onClear, bundling, bundleError }) {
  return (
    <div className="sg-exp-bundle">
      <div className="sg-exp-bundle-row">
        <span className="sg-exp-bundle-count">{count} selected</span>
        <span className="sg-exp-bundle-label">Include:</span>
        <div className="sg-exp-fmts">
          {ARTIFACT_TYPES.map((type) => {
            const active = bundleArtifacts.has(type.sel);
            const Icon = type.icon;
            return (
              <button
                key={type.sel}
                type="button"
                onClick={() => onToggleArtifact(type.sel)}
                className={`sg-exp-fmt${active ? " active" : ""}`}
              >
                <Icon size={11} /> {type.label}
              </button>
            );
          })}
        </div>
        <div className="sg-exp-bundle-actions">
          <button
            type="button"
            onClick={onDownload}
            disabled={bundling || bundleArtifacts.size === 0}
            className="sg-btn-sm accent"
          >
            {bundling ? <Loader2 size={13} className="sg-spin" /> : <FileArchive size={13} />}
            {bundling ? "Bundling…" : "Download ZIP"}
          </button>
          <button type="button" onClick={onClear} className="sg-btn-sm">
            <X size={13} /> Clear
          </button>
        </div>
      </div>
      {bundleArtifacts.size === 0 && (
        <p className="sg-exp-bundle-note warn">Choose at least one artifact type to bundle.</p>
      )}
      {bundleError && <p className="sg-exp-bundle-note error">{bundleError}</p>}
    </div>
  );
}

function ExportCard({ job, style, folder, selected, onToggleSelect, onDetails, onRerender, rerendering }) {
  const availability = job.artifact_availability || {};
  const attachments = job.attachment_summary || {};
  const created = job.created_at || "";
  const available = ARTIFACT_TYPES.filter((type) => availability[type.availKey]);
  const canRerender = Boolean(availability.clean_md);

  return (
    <div className={`sg-job-card${selected ? " selected" : ""}`}>
      <label className="sg-job-check" onClick={(event) => event.stopPropagation()}>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(job.id)}
          aria-label={`Select ${job.title || "study guide"}`}
        />
      </label>

      <div className="sg-exp-body">
        <div className="sg-exp-row">
          <div className="sg-job-main">
            <p className="sg-job-title">{job.title || "Untitled study guide"}</p>
            <p className="sg-job-sub">
              {[[job.provider, job.model].filter(Boolean).join(" / ") || "Study guide", created].filter(Boolean).join(" · ")}
            </p>
            <div className="sg-job-meta">
              <span className={`pill ${statusClass(job.status)}`}>{job.status || "unknown"}</span>
              {style && <StylePill style={style} />}
              {folder && <FolderPill folder={folder} />}
              {(attachments.count || 0) > 0 && (
                <span className="pill pill-green">
                  <Paperclip size={12} /> {attachments.count}
                </span>
              )}
              {attachments.has_warnings && (
                <span className="pill pill-amber">
                  <AlertCircle size={12} /> {attachments.warning_count || 1}
                </span>
              )}
            </div>
          </div>

          <div className="sg-job-actions">
            {availability.final_pdf && (
              <a
                href={`${artifactUrl(job.id, "final.pdf")}?disposition=inline`}
                target="_blank"
                rel="noreferrer"
                className="sg-btn-sm"
              >
                <ExternalLink size={13} /> PDF
              </a>
            )}
            {availability.final_pdf && (
              <a href={artifactUrl(job.id, "final.pdf")} className="sg-btn-sm">
                <Download size={13} /> PDF
              </a>
            )}
            {availability.final_docx && (
              <a href={artifactUrl(job.id, "final.docx")} className="sg-btn-sm">
                <Download size={13} /> DOCX
              </a>
            )}
            {availability.clean_md && (
              <a href={artifactUrl(job.id, "clean.md")} className="sg-btn-sm">
                <Download size={13} /> MD
              </a>
            )}
            {availability.final_html && (
              <a
                href={`${artifactUrl(job.id, "final.html")}?disposition=inline`}
                target="_blank"
                rel="noreferrer"
                className="sg-btn-sm"
              >
                <ExternalLink size={13} /> HTML
              </a>
            )}
            {canRerender && (
              <button
                type="button"
                onClick={() => onRerender(job.id)}
                disabled={rerendering}
                title="Re-render PDF/HTML from existing clean.md"
                className="sg-btn-sm"
              >
                {rerendering ? <Loader2 size={13} className="sg-spin" /> : <RefreshCw size={13} />}
                {rerendering ? "Rendering" : "Re-render"}
              </button>
            )}
            <button type="button" onClick={onDetails} className="sg-btn-sm accent">
              Details
            </button>
          </div>
        </div>

        <div className="sg-exp-formats">
          {available.length === 0 ? (
            <span className="sg-exp-formats-empty">No artifacts available</span>
          ) : (
            available.map((type) => {
              const Icon = type.icon;
              return (
                <span key={type.sel} className="sg-exp-fmt-chip">
                  <Icon size={11} /> {type.label}
                </span>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
