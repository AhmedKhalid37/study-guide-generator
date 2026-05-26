import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  Download,
  ExternalLink,
  FolderClosed,
  FolderPlus,
  Layers3,
  Loader2,
  Paperclip,
  Pencil,
  Plus,
  Search,
  Trash2,
  X
} from "lucide-react";
import {
  artifactUrl,
  createFolder,
  deleteFolder,
  getJob,
  getLibrary,
  getStyles,
  moveJobToFolder,
  moveJobsToFolder,
  updateFolder
} from "../api/client";
import { buildStyleLookup, resolveStyle } from "../styleMeta";
import { FOLDER_PRESET_COLORS, folderColor } from "../folderMeta";
import { JobDetailsDrawer, StylePill, FolderPill } from "./RecentJobsPanel";

const SORTS = [
  { id: "newest", label: "Newest" },
  { id: "oldest", label: "Oldest" },
  { id: "title", label: "Title A–Z" },
  { id: "status", label: "Status" }
];

const emptyFilters = { status: "", provider: "", style: "", mode: "", hasAttachments: false, hasWarnings: false };

function statusTone(status) {
  if (status === "done") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (String(status || "").includes("failed")) return "border-red-400/30 bg-red-400/10 text-red-200";
  return "border-amber-300/30 bg-amber-300/10 text-amber-100";
}

export default function LibraryWorkspace({ refreshKey = 0, onOpenBuilder }) {
  const [data, setData] = useState({ folders: [], jobs: [] });
  const [styleLookup, setStyleLookup] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [internalRefresh, setInternalRefresh] = useState(0);

  const [selectedFolder, setSelectedFolder] = useState("all");
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [sort, setSort] = useState("newest");
  const [showFilters, setShowFilters] = useState(false);

  const [newFolderName, setNewFolderName] = useState("");
  const [newFolderColor, setNewFolderColor] = useState(FOLDER_PRESET_COLORS[0]);
  const [renaming, setRenaming] = useState(null); // { id, name, color }
  const [folderError, setFolderError] = useState(null);

  const [selectedIds, setSelectedIds] = useState(() => new Set());

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [jobDetails, setJobDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  const reload = useCallback(() => setInternalRefresh((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getLibrary()
      .then((result) => {
        if (cancelled) return;
        setData({ folders: result.folders ?? [], jobs: result.jobs ?? [] });
        setError(null);
      })
      .catch((err) => !cancelled && setError(err.message || "Could not load library."))
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

  // Drop any selected ids that no longer exist after a reload (e.g. deleted).
  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev;
      const existing = new Set(data.jobs.map((job) => job.id));
      const next = new Set();
      prev.forEach((id) => existing.has(id) && next.add(id));
      return next.size === prev.size ? prev : next;
    });
  }, [data.jobs]);

  const folderMap = useMemo(
    () => Object.fromEntries(data.folders.map((folder) => [folder.id, folder])),
    [data.folders]
  );
  const moveTargets = useMemo(() => data.folders.filter((folder) => folder.id !== "all"), [data.folders]);

  const providers = useMemo(
    () => [...new Set(data.jobs.map((job) => job.provider).filter(Boolean))],
    [data.jobs]
  );
  const statuses = useMemo(
    () => [...new Set(data.jobs.map((job) => job.status).filter(Boolean))],
    [data.jobs]
  );
  const modes = useMemo(
    () => [...new Set(data.jobs.map((job) => job.input_type || job.path_mode).filter(Boolean))],
    [data.jobs]
  );
  const styleChoices = useMemo(() => {
    const map = new Map();
    data.jobs.forEach((job) => {
      if (job.prompt_name) {
        map.set(job.prompt_name, resolveStyle(job.prompt_name, styleLookup).name);
      }
    });
    return [...map.entries()];
  }, [data.jobs, styleLookup]);

  const activeFilterCount =
    (filters.status ? 1 : 0) +
    (filters.provider ? 1 : 0) +
    (filters.style ? 1 : 0) +
    (filters.mode ? 1 : 0) +
    (filters.hasAttachments ? 1 : 0) +
    (filters.hasWarnings ? 1 : 0);

  const filteredJobs = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let list = data.jobs.filter((job) => {
      if (selectedFolder !== "all" && job.folder_id !== selectedFolder) return false;
      if (needle) {
        const hay = [job.title, job.id, job.provider, job.model, job.prompt_name]
          .map((value) => String(value || "").toLowerCase())
          .join(" ");
        if (!hay.includes(needle)) return false;
      }
      if (filters.status && job.status !== filters.status) return false;
      if (filters.provider && String(job.provider || "").toLowerCase() !== filters.provider.toLowerCase()) return false;
      if (filters.style && job.prompt_name !== filters.style) return false;
      if (filters.mode && (job.input_type || job.path_mode) !== filters.mode) return false;
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
  }, [data.jobs, selectedFolder, q, filters, sort]);

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

  const handleMove = useCallback(
    async (jobId, folderId) => {
      try {
        await moveJobToFolder(jobId, folderId);
        reload();
      } catch (err) {
        setError(err.message || "Could not move guide.");
      }
    },
    [reload]
  );

  const toggleSelect = useCallback((jobId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(jobId) ? next.delete(jobId) : next.add(jobId);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const visibleIds = useMemo(() => filteredJobs.map((job) => job.id), [filteredJobs]);
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));

  const toggleSelectAllVisible = useCallback(() => {
    setSelectedIds((prev) => {
      const everySelected = visibleIds.length > 0 && visibleIds.every((id) => prev.has(id));
      return everySelected ? new Set() : new Set(visibleIds);
    });
  }, [visibleIds]);

  const handleBatchMove = useCallback(
    async (folderId) => {
      const ids = [...selectedIds];
      if (ids.length === 0) return;
      try {
        await moveJobsToFolder(ids, folderId);
        clearSelection();
        reload();
      } catch (err) {
        setError(err.message || "Could not move selected guides.");
      }
    },
    [selectedIds, clearSelection, reload]
  );

  async function handleCreateFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    setFolderError(null);
    try {
      await createFolder({ name, color: newFolderColor });
      setNewFolderName("");
      setNewFolderColor(FOLDER_PRESET_COLORS[0]);
      reload();
    } catch (err) {
      setFolderError(err.message || "Could not create folder.");
    }
  }

  async function handleRenameFolder() {
    if (!renaming?.name.trim()) return;
    try {
      await updateFolder(renaming.id, { name: renaming.name.trim(), color: renaming.color });
      setRenaming(null);
      reload();
    } catch (err) {
      setFolderError(err.message || "Could not rename folder.");
    }
  }

  async function handleDeleteFolder(folder) {
    if (!window.confirm(`Delete folder "${folder.name}"? Guides inside move to Unfiled (not deleted).`)) return;
    try {
      await deleteFolder(folder.id);
      if (selectedFolder === folder.id) setSelectedFolder("all");
      reload();
    } catch (err) {
      setError(err.message || "Could not delete folder.");
    }
  }

  return (
    <div className="flex min-h-0 flex-1 gap-4 p-1">
      <FolderRail
        folders={data.folders}
        selectedFolder={selectedFolder}
        onSelect={setSelectedFolder}
        newFolderName={newFolderName}
        setNewFolderName={setNewFolderName}
        newFolderColor={newFolderColor}
        setNewFolderColor={setNewFolderColor}
        onCreate={handleCreateFolder}
        renaming={renaming}
        setRenaming={setRenaming}
        onRename={handleRenameFolder}
        onDelete={handleDeleteFolder}
        folderError={folderError}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sg-page-head">
          <div>
            <h1>{folderMap[selectedFolder]?.name || "Library"}</h1>
            <p>{filteredJobs.length} of {data.jobs.length} guide{data.jobs.length === 1 ? "" : "s"}</p>
          </div>
          <button type="button" className="sg-cta sg-press-btn" onClick={() => onOpenBuilder?.()}>
            <Plus size={16} stroke="#1A1206" strokeWidth={2.6} />
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
            modes={modes}
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
          <BulkBar
            count={selectedIds.size}
            folders={moveTargets.filter((folder) => folder.id !== "unfiled")}
            onMove={handleBatchMove}
            onUnfile={() => handleBatchMove("unfiled")}
            onClear={clearSelection}
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
              <span>Loading library…</span>
            </div>
          ) : filteredJobs.length === 0 ? (
            <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-slate-400">
              <Layers3 className="h-6 w-6 opacity-60" />
              <span>No guides match this view.</span>
            </div>
          ) : (
            <div className="grid gap-2.5">
              {filteredJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  style={resolveStyle(job.prompt_name, styleLookup)}
                  folder={folderMap[job.folder_id]}
                  moveTargets={moveTargets}
                  onMove={handleMove}
                  onDetails={() => openDetails(job.id)}
                  selected={selectedIds.has(job.id)}
                  onToggleSelect={toggleSelect}
                />
              ))}
            </div>
          )}
        </div>
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

function FolderRail({
  folders,
  selectedFolder,
  onSelect,
  newFolderName,
  setNewFolderName,
  newFolderColor,
  setNewFolderColor,
  onCreate,
  renaming,
  setRenaming,
  onRename,
  onDelete,
  folderError
}) {
  return (
    <aside className="flex w-56 shrink-0 flex-col rounded-2xl border border-white/10 bg-white/[0.035] p-3">
      <p className="px-1 pb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">Folders</p>
      <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
        {folders.map((folder) => {
          const active = selectedFolder === folder.id;
          const isRenaming = renaming?.id === folder.id;
          return (
            <div key={folder.id} className="group">
              {isRenaming ? (
                <div className="grid gap-1.5 px-1 py-1">
                  <div className="flex items-center gap-1">
                    <input
                      autoFocus
                      className="sg-input h-8 px-2 text-sm"
                      value={renaming.name}
                      onChange={(event) => setRenaming({ ...renaming, name: event.target.value })}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") onRename();
                        if (event.key === "Escape") setRenaming(null);
                      }}
                    />
                    <button type="button" className="sg-icon-button" onClick={onRename} title="Save">
                      <Plus size={13} />
                    </button>
                  </div>
                  <ColorSwatches
                    value={renaming.color}
                    onChange={(color) => setRenaming({ ...renaming, color })}
                  />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => onSelect(folder.id)}
                  className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition ${
                    active ? "bg-ember-500/[0.12] text-white" : "text-slate-300 hover:bg-white/[0.05]"
                  }`}
                >
                  <FolderGlyph folder={folder} />
                  <span className="min-w-0 flex-1 truncate">{folder.name}</span>
                  <span className="text-[11px] tabular-nums text-slate-500">{folder.count}</span>
                  {!folder.system && (
                    <span className="hidden shrink-0 items-center gap-0.5 group-hover:flex">
                      <span
                        role="button"
                        tabIndex={0}
                        className="grid h-5 w-5 place-items-center rounded text-slate-400 hover:text-white"
                        onClick={(event) => {
                          event.stopPropagation();
                          setRenaming({ id: folder.id, name: folder.name, color: folder.color || FOLDER_PRESET_COLORS[0] });
                        }}
                        title="Rename"
                      >
                        <Pencil size={12} />
                      </span>
                      <span
                        role="button"
                        tabIndex={0}
                        className="grid h-5 w-5 place-items-center rounded text-slate-400 hover:text-red-300"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDelete(folder);
                        }}
                        title="Delete"
                      >
                        <Trash2 size={12} />
                      </span>
                    </span>
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-2 border-t border-white/10 pt-2">
        <div className="flex items-center gap-1">
          <input
            className="sg-input h-8 px-2 text-sm"
            placeholder="New folder…"
            value={newFolderName}
            onChange={(event) => setNewFolderName(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && onCreate()}
          />
          <button type="button" className="sg-icon-button" onClick={onCreate} title="Create folder">
            <FolderPlus size={14} />
          </button>
        </div>
        <div className="mt-1.5 px-1">
          <ColorSwatches value={newFolderColor} onChange={setNewFolderColor} />
        </div>
        {folderError && <p className="mt-1.5 px-1 text-[11px] text-red-300">{folderError}</p>}
      </div>
    </aside>
  );
}

function FolderGlyph({ folder }) {
  const color = folder.color || (folder.system ? "#9098A8" : "#F97316");
  if (folder.id === "all") return <Layers3 size={15} color="#F97316" />;
  return <FolderClosed size={15} color={color} />;
}

function ColorSwatches({ value, onChange }) {
  return (
    <div className="flex items-center gap-1.5">
      {FOLDER_PRESET_COLORS.map((color) => {
        const active = (value || "").toLowerCase() === color.toLowerCase();
        return (
          <button
            key={color}
            type="button"
            onClick={() => onChange(color)}
            title={color}
            aria-label={`Folder color ${color}`}
            className={`h-4 w-4 rounded-full border transition ${
              active ? "ring-2 ring-white/70 ring-offset-1 ring-offset-[#0B0F19]" : "border-white/20"
            }`}
            style={{ backgroundColor: color }}
          />
        );
      })}
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

function FilterBar({ filters, setFilters, statuses, providers, styleChoices, modes, onClear }) {
  const set = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
      <FilterSelect label="Status" value={filters.status} onChange={(value) => set("status", value)} options={statuses} />
      <FilterSelect label="Provider" value={filters.provider} onChange={(value) => set("provider", value)} options={providers} />
      <FilterSelect
        label="Style"
        value={filters.style}
        onChange={(value) => set("style", value)}
        options={styleChoices.map(([id, name]) => ({ value: id, label: name }))}
      />
      <FilterSelect label="Input" value={filters.mode} onChange={(value) => set("mode", value)} options={modes} />
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

function JobCard({ job, style, folder, moveTargets, onMove, onDetails, selected, onToggleSelect }) {
  const availability = job.artifact_availability || {};
  const attachments = job.attachment_summary || {};
  const created = job.created_at || "";
  return (
    <div
      className={`flex gap-3 rounded-xl border p-3 transition ${
        selected
          ? "border-ember-500/60 bg-ember-500/[0.08]"
          : "border-white/10 bg-white/[0.035] hover:border-white/20"
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
      <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
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
            {folder && folder.id !== "unfiled" && <FolderPill folder={folder} />}
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
          {availability.clean_md && (
            <a
              href={artifactUrl(job.id, "clean.md")}
              className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
            >
              <Download size={13} /> MD
            </a>
          )}
          <MoveMenu job={job} folders={moveTargets} onMove={onMove} />
          <button
            type="button"
            onClick={onDetails}
            className="inline-flex h-8 items-center rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-ember-300 transition hover:border-ember-500/60 hover:text-white"
          >
            Details
          </button>
        </div>
      </div>
    </div>
  );
}

function BulkBar({ count, folders, onMove, onUnfile, onClear }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-ember-500/40 bg-ember-500/[0.08] px-3 py-2">
      <span className="text-sm font-bold text-white">{count} selected</span>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <BatchMoveMenu folders={folders} onMove={onMove} />
        <button
          type="button"
          onClick={onUnfile}
          className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
        >
          <FolderClosed size={13} /> Move to Unfiled
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
  );
}

function BatchMoveMenu({ folders, onMove }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-8 items-center gap-1 rounded-lg border border-ember-500/50 bg-ember-500/10 px-2.5 text-xs font-bold text-white transition hover:border-ember-500/70"
      >
        <FolderClosed size={13} /> Move to folder <ChevronDown size={12} />
      </button>
      {open && (
        <>
          <button type="button" className="fixed inset-0 z-40 cursor-default" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-1 max-h-64 w-48 overflow-y-auto rounded-xl border border-white/10 bg-[#0B0F19] p-1 shadow-2xl">
            {folders.length === 0 && (
              <p className="px-2.5 py-1.5 text-xs text-slate-500">No folders yet.</p>
            )}
            {folders.map((folder) => (
              <button
                key={folder.id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  onMove(folder.id);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm text-slate-200 hover:bg-white/[0.06]"
              >
                <FolderClosed size={13} color={folderColor(folder)} />
                <span className="min-w-0 flex-1 truncate">{folder.name}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function MoveMenu({ job, folders, onMove }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
      >
        <FolderClosed size={13} /> Move <ChevronDown size={12} />
      </button>
      {open && (
        <>
          <button type="button" className="fixed inset-0 z-40 cursor-default" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-1 max-h-64 w-48 overflow-y-auto rounded-xl border border-white/10 bg-[#0B0F19] p-1 shadow-2xl">
            {folders.map((folder) => {
              const current = job.folder_id === folder.id;
              return (
                <button
                  key={folder.id}
                  type="button"
                  disabled={current}
                  onClick={() => {
                    setOpen(false);
                    if (!current) onMove(job.id, folder.id);
                  }}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm ${
                    current ? "text-slate-500" : "text-slate-200 hover:bg-white/[0.06]"
                  }`}
                >
                  <FolderClosed size={13} color={folder.color || "#9098A8"} />
                  <span className="min-w-0 flex-1 truncate">{folder.name}</span>
                  {current && <span className="text-[10px]">current</span>}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
