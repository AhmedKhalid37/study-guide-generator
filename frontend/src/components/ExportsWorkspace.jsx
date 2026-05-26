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

function statusTone(status) {
  if (status === "done") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (String(status || "").includes("failed")) return "border-red-400/30 bg-red-400/10 text-red-200";
  return "border-amber-300/30 bg-amber-300/10 text-amber-100";
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
    <div className="flex min-h-0 flex-1 flex-col p-1">
      <div className="sg-page-head">
        <div>
          <h1>Exports</h1>
          <p>{filteredJobs.length} of {data.jobs.length} guide{data.jobs.length === 1 ? "" : "s"} · download artifacts or bundle as ZIP</p>
        </div>
        <button type="button" className="sg-cta sg-press-btn" onClick={() => onOpenBuilder?.()}>
          <Download size={16} stroke="#1A1206" strokeWidth={2.4} />
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
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-400/30 bg-red-400/10 px-4 py-2 text-sm text-red-200">
          <AlertCircle size={15} />
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
        <label className="mt-3 inline-flex w-fit cursor-pointer items-center gap-2 px-0.5 text-xs font-semibold text-slate-400 hover:text-slate-200">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 accent-ember-500"
            checked={allVisibleSelected}
            onChange={toggleSelectAllVisible}
          />
          Select all visible ({visibleIds.length})
        </label>
      )}

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1">
        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 text-slate-300">
            <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
            <span>Loading exports…</span>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-slate-400">
            <FileArchive className="h-6 w-6 opacity-60" />
            <span>No guides match this view.</span>
          </div>
        ) : (
          <div className="grid gap-2.5">
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
      />
    </div>
  );
}

function Toolbar({ q, setQ, sort, setSort, showFilters, setShowFilters, activeFilterCount }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3">
        <Search size={15} className="shrink-0 text-slate-500" />
        <input
          className="h-9 w-full min-w-0 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
          placeholder="Search title, id, provider, or style…"
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        {q && (
          <button type="button" className="text-slate-500 hover:text-white" onClick={() => setQ("")}>
            <X size={14} />
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowFilters((open) => !open)}
        className={`inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-sm font-semibold transition ${
          activeFilterCount > 0 || showFilters
            ? "border-ember-500/50 bg-ember-500/10 text-white"
            : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
        }`}
      >
        Filters
        {activeFilterCount > 0 && (
          <span className="grid h-4 min-w-4 place-items-center rounded-full bg-ember-500 px-1 text-[10px] font-bold text-[#1A1206]">
            {activeFilterCount}
          </span>
        )}
        <ChevronDown size={14} className={showFilters ? "rotate-180 transition" : "transition"} />
      </button>

      <label className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2 text-sm text-slate-300">
        <span className="text-xs text-slate-500">Sort</span>
        <select
          className="bg-transparent text-sm text-slate-100 outline-none"
          value={sort}
          onChange={(event) => setSort(event.target.value)}
        >
          {SORTS.map((option) => (
            <option key={option.id} value={option.id} className="bg-[#0B0F19]">
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
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
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
      <ToggleChip active={filters.hasAttachments} onClick={() => set("hasAttachments", !filters.hasAttachments)}>
        <Paperclip size={12} /> Attachments
      </ToggleChip>
      <ToggleChip active={filters.hasWarnings} onClick={() => set("hasWarnings", !filters.hasWarnings)}>
        <AlertCircle size={12} /> Warnings
      </ToggleChip>
      <button type="button" className="ml-auto text-xs font-semibold text-slate-400 hover:text-white" onClick={onClear}>
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
    <label className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2 text-xs text-slate-300">
      <span className="text-slate-500">{label}</span>
      <select
        className="max-w-[140px] bg-transparent text-xs text-slate-100 outline-none"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="" className="bg-[#0B0F19]">All</option>
        {normalized.map((option) => (
          <option key={option.value} value={option.value} className="bg-[#0B0F19]">
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ToggleChip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-semibold transition ${
        active
          ? "border-ember-500/50 bg-ember-500/10 text-white"
          : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}

function BundleBar({ count, bundleArtifacts, onToggleArtifact, onDownload, onClear, bundling, bundleError }) {
  return (
    <div className="mt-3 rounded-lg border border-ember-500/40 bg-ember-500/[0.08] px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-bold text-white">{count} selected</span>
        <span className="text-xs text-slate-400">Include:</span>
        <div className="flex flex-wrap items-center gap-1.5">
          {ARTIFACT_TYPES.map((type) => {
            const active = bundleArtifacts.has(type.sel);
            const Icon = type.icon;
            return (
              <button
                key={type.sel}
                type="button"
                onClick={() => onToggleArtifact(type.sel)}
                className={`inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-[11px] font-bold transition ${
                  active
                    ? "border-ember-500/60 bg-ember-500/20 text-white"
                    : "border-white/10 bg-white/[0.04] text-slate-300 hover:text-white"
                }`}
              >
                <Icon size={11} /> {type.label}
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={onDownload}
            disabled={bundling || bundleArtifacts.size === 0}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ember-500/60 bg-ember-500/15 px-3 text-xs font-bold text-white transition hover:border-ember-500/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {bundling ? <Loader2 size={13} className="animate-spin" /> : <FileArchive size={13} />}
            {bundling ? "Bundling…" : "Download ZIP"}
          </button>
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-300 transition hover:text-white"
          >
            <X size={13} /> Clear
          </button>
        </div>
      </div>
      {bundleArtifacts.size === 0 && (
        <p className="mt-1.5 text-[11px] text-amber-200">Choose at least one artifact type to bundle.</p>
      )}
      {bundleError && <p className="mt-1.5 text-[11px] text-red-300">{bundleError}</p>}
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
    <div
      className={`flex gap-3 rounded-xl border p-3 transition ${
        selected ? "border-ember-500/60 bg-ember-500/[0.08]" : "border-white/10 bg-white/[0.035] hover:border-white/20"
      }`}
    >
      <label className="flex shrink-0 items-start pt-0.5" onClick={(event) => event.stopPropagation()}>
        <input
          type="checkbox"
          className="h-4 w-4 accent-ember-500"
          checked={selected}
          onChange={() => onToggleSelect(job.id)}
          aria-label={`Select ${job.title || "study guide"}`}
        />
      </label>

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold text-white">{job.title || "Untitled study guide"}</p>
            <p className="mt-0.5 truncate text-xs text-slate-400">
              {[[job.provider, job.model].filter(Boolean).join(" / ") || "Study guide", created].filter(Boolean).join(" · ")}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-bold ${statusTone(job.status)}`}>
                {job.status || "unknown"}
              </span>
              {style && <StylePill style={style} />}
              {folder && <FolderPill folder={folder} />}
              {(attachments.count || 0) > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-bold text-emerald-200">
                  <Paperclip size={11} /> {attachments.count}
                </span>
              )}
              {attachments.has_warnings && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-300/30 bg-amber-300/10 px-2 py-0.5 text-[11px] font-bold text-amber-100">
                  <AlertCircle size={11} /> {attachments.warning_count || 1}
                </span>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-1.5">
            {availability.final_pdf && (
              <a
                href={`${artifactUrl(job.id, "final.pdf")}?disposition=inline`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
              >
                <ExternalLink size={13} /> PDF
              </a>
            )}
            {availability.final_pdf && (
              <a
                href={artifactUrl(job.id, "final.pdf")}
                className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
              >
                <Download size={13} /> PDF
              </a>
            )}
            {availability.final_docx && (
              <a
                href={artifactUrl(job.id, "final.docx")}
                className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
              >
                <Download size={13} /> DOCX
              </a>
            )}
            {availability.clean_md && (
              <a
                href={artifactUrl(job.id, "clean.md")}
                className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
              >
                <Download size={13} /> MD
              </a>
            )}
            {availability.final_html && (
              <a
                href={`${artifactUrl(job.id, "final.html")}?disposition=inline`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
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
                className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white disabled:opacity-50"
              >
                {rerendering ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                {rerendering ? "Rendering" : "Re-render"}
              </button>
            )}
            <button
              type="button"
              onClick={onDetails}
              className="inline-flex h-8 items-center rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-ember-300 transition hover:border-ember-500/60 hover:text-white"
            >
              Details
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {available.length === 0 ? (
            <span className="text-[11px] text-slate-500">No artifacts available</span>
          ) : (
            available.map((type) => {
              const Icon = type.icon;
              return (
                <span
                  key={type.sel}
                  className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.05] px-1.5 py-0.5 text-[10.5px] font-semibold text-slate-300"
                >
                  <Icon size={11} className="text-ember-300" /> {type.label}
                </span>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
