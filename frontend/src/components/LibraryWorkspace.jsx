import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
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
  RotateCcw,
  Search,
  Star,
  Trash2,
  X
} from "lucide-react";
import {
  artifactUrl,
  bulkDeleteJobs,
  bulkMoveJobs,
  bulkPurgeJobs,
  bulkRestoreJobs,
  createFolder,
  deleteFolder,
  emptyTrash,
  getJob,
  getLibrary,
  getStyles,
  getTrash,
  moveJobToFolder,
  purgeTrashedJob,
  restoreJob,
  setJobFavorite,
  trashJob,
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

// Special pseudo-folder id for the Trash view.
const TRASH_VIEW = "__trash__";

function statusTone(status) {
  if (status === "done") return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  if (String(status || "").includes("failed")) return "border-red-400/30 bg-red-400/10 text-red-200";
  return "border-amber-300/30 bg-amber-300/10 text-amber-100";
}

// Split a bulk-action response ({ results: [{ id, status }], ... }) into the
// three outcome buckets so the UI can update selection/toasts honestly instead
// of assuming all-or-nothing.
function partitionResults(response) {
  const ok = [];
  const skipped = [];
  const failed = []; // keep full {id, detail} for failures
  for (const result of response?.results || []) {
    if (result.status === "ok") ok.push(result.id);
    else if (result.status === "skipped") skipped.push(result.id);
    else failed.push(result);
  }
  return { ok, skipped, failed };
}

export default function LibraryWorkspace({ refreshKey = 0, onOpenBuilder, initialView = null }) {
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
  // Folder multi-select (rail) — React state only, never persisted.
  const [selectedFolderIds, setSelectedFolderIds] = useState(() => new Set());
  // Trash multi-select — React state only.
  const [selectedTrashIds, setSelectedTrashIds] = useState(() => new Set());
  // Staged folder bulk-delete: null | { folderIds: string[], jobCount: number }.
  const [folderDelete, setFolderDelete] = useState(null);
  const [folderDeleteBusy, setFolderDeleteBusy] = useState(false);

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [jobDetails, setJobDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  const [trashJobs, setTrashJobs] = useState([]);
  // confirm modal: null | { kind: "trash"|"purge"|"emptyTrash"|"bulkTrash"|"bulkPurge", job?, count?, ids? }
  const [confirm, setConfirm] = useState(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  // Lightweight transient toast: null | { id, message, tone, action? }. Used for
  // bulk-action summaries (incl. partial-success) and the delete→Undo affordance.
  const [toast, setToast] = useState(null);

  const reload = useCallback(() => setInternalRefresh((n) => n + 1), []);

  // Apply a view requested by a Home shortcut (library_view / find_guide tool).
  // Best-effort mapping onto the existing folder/search/filter/sort controls.
  useEffect(() => {
    const view = initialView?.view;
    if (!view) return;
    if (view.startsWith("folder:")) {
      setSelectedFolder(view.slice(7) || "all");
      setQ("");
      setFilters(emptyFilters);
    } else if (view.startsWith("search:")) {
      setSelectedFolder("all");
      setQ(view.slice(7));
      setFilters(emptyFilters);
    } else if (view.startsWith("tag:")) {
      setSelectedFolder("all");
      setQ(view.slice(4));
      setFilters(emptyFilters);
    } else if (view === "failed") {
      setSelectedFolder("all");
      setQ("");
      const failed = data.jobs.map((j) => j.status).find((s) => String(s || "").includes("failed"));
      setFilters({ ...emptyFilters, status: failed || "" });
      setSort("newest");
    } else {
      // recent / all / pinned / favorites — favorites already float to the top.
      setSelectedFolder("all");
      setQ("");
      setFilters(emptyFilters);
      setSort("newest");
    }
    // Re-run only when a new view request arrives (nonce changes), not on every
    // data refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialView?.nonce]);

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

  useEffect(() => {
    let cancelled = false;
    getTrash()
      .then((result) => !cancelled && setTrashJobs(result.jobs ?? []))
      .catch(() => !cancelled && setTrashJobs([]));
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

  // Switching folder / search / filters changes which jobs are visible. Clear
  // the selection on a view change so bulk actions can never operate on jobs the
  // user can no longer see (chosen as the safest, least-surprising behavior).
  useEffect(() => {
    setSelectedIds((prev) => (prev.size ? new Set() : prev));
  }, [selectedFolder, q, filters]);

  // Drop selected trash ids that no longer exist after a reload (restored/purged).
  useEffect(() => {
    setSelectedTrashIds((prev) => {
      if (prev.size === 0) return prev;
      const existing = new Set(trashJobs.map((job) => job.id));
      const next = new Set();
      prev.forEach((id) => existing.has(id) && next.add(id));
      return next.size === prev.size ? prev : next;
    });
  }, [trashJobs]);

  // Drop selected folder ids that no longer exist after a reload (deleted).
  useEffect(() => {
    setSelectedFolderIds((prev) => {
      if (prev.size === 0) return prev;
      const existing = new Set(data.folders.map((folder) => folder.id));
      const next = new Set();
      prev.forEach((id) => existing.has(id) && next.add(id));
      return next.size === prev.size ? prev : next;
    });
  }, [data.folders]);

  // Auto-dismiss the toast. Undo toasts (those with an action) linger longer so
  // the undo is actually reachable.
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), toast.action ? 8000 : 4000);
    return () => clearTimeout(timer);
  }, [toast]);

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
    // Favorites float to the top regardless of sort; Array.prototype.sort is
    // stable, so the chosen ordering is preserved within each group.
    list = [...list].sort((a, b) => (b.favorite ? 1 : 0) - (a.favorite ? 1 : 0));
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

  const handleToggleFavorite = useCallback(async (jobId, nextValue) => {
    // Optimistic: flip locally so the list re-orders immediately, then reconcile
    // with the server's confirmed value (reverting on failure).
    const apply = (value) =>
      setData((prev) => ({
        ...prev,
        jobs: prev.jobs.map((job) => (job.id === jobId ? { ...job, favorite: value } : job))
      }));
    apply(nextValue);
    try {
      const result = await setJobFavorite(jobId, nextValue);
      apply(Boolean(result.favorite));
    } catch (err) {
      apply(!nextValue);
      setError(err.message || "Could not update favorite.");
    }
  }, []);

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

  // Bulk move via the canonical /api/jobs/bulk/move. A whole-request failure
  // (e.g. unknown folder → 404) is thrown by bulkMoveJobs: we keep the selection
  // and the list untouched. A 200 may still carry per-id failures, so we clear
  // only the ids that succeeded and keep failed ones selected.
  const handleBatchMove = useCallback(
    async (folderId) => {
      const ids = [...selectedIds];
      if (ids.length === 0) return;
      setError(null);
      const destName =
        folderId === "unfiled" || !folderId ? "Unfiled" : folderMap[folderId]?.name || "folder";
      try {
        const response = await bulkMoveJobs(ids, folderId);
        const { ok, failed } = partitionResults(response);
        setSelectedIds(new Set(failed.map((result) => result.id)));
        reload();
        setToast({
          id: Date.now(),
          tone: failed.length ? "error" : "success",
          message:
            `Moved ${ok.length} guide${ok.length === 1 ? "" : "s"} to ${destName}` +
            (failed.length ? ` · ${failed.length} failed` : "")
        });
      } catch (err) {
        // Whole-request failure: do not touch the local list or selection.
        setToast({ id: Date.now(), tone: "error", message: err.message || "Could not move selected guides." });
      }
    },
    [selectedIds, folderMap, reload]
  );

  // Bulk soft-delete via /api/jobs/bulk/delete. Routes through the trash (B1);
  // `ok` ids were trashed by THIS action and are the ones Undo restores;
  // `skipped` were already in the trash; `error` ids stay selected. The reload
  // drops trashed jobs from the active list automatically.
  const performBulkDelete = useCallback(
    async (ids) => {
      const response = await bulkDeleteJobs(ids);
      const { ok, skipped, failed } = partitionResults(response);
      setSelectedIds(new Set(failed.map((result) => result.id)));
      reload();
      const parts = [`${ok.length} moved to trash`];
      if (skipped.length) parts.push(`${skipped.length} already trashed`);
      if (failed.length) parts.push(`${failed.length} failed`);
      setToast({
        id: Date.now(),
        tone: failed.length ? "error" : "success",
        message: parts.join(" · "),
        action: ok.length ? { label: "Undo", run: () => handleBulkUndo(ok) } : null
      });
    },
    [reload]
  );

  // Undo a bulk delete by restoring exactly the ids that were trashed.
  const handleBulkUndo = useCallback(
    async (ids) => {
      setToast(null);
      try {
        const response = await bulkRestoreJobs(ids);
        const { ok, failed } = partitionResults(response);
        reload();
        setToast({
          id: Date.now(),
          tone: failed.length ? "error" : "success",
          message:
            `Restored ${ok.length} guide${ok.length === 1 ? "" : "s"}` +
            (failed.length ? ` · ${failed.length} failed` : "")
        });
      } catch (err) {
        setToast({ id: Date.now(), tone: "error", message: err.message || "Could not restore guides." });
      }
    },
    [reload]
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

  // ── Folder multi-select (rail) ────────────────────────────────────────────
  const toggleFolderSelect = useCallback((folderId) => {
    setSelectedFolderIds((prev) => {
      const next = new Set(prev);
      next.has(folderId) ? next.delete(folderId) : next.add(folderId);
      return next;
    });
  }, []);

  const clearFolderSelection = useCallback(() => setSelectedFolderIds(new Set()), []);

  // Open the delete-folders modal, pre-counting how many ACTIVE guides live in
  // the selected folders (so Option B can tell the user what it will trash).
  const openFolderDelete = useCallback(() => {
    const folderIds = [...selectedFolderIds];
    if (folderIds.length === 0) return;
    const idSet = new Set(folderIds);
    const jobCount = data.jobs.filter((job) => idSet.has(job.folder_id)).length;
    setFolderDelete({ folderIds, jobCount });
  }, [selectedFolderIds, data.jobs]);

  // Run the staged folder delete. mode === "withGuides" first soft-deletes the
  // guides inside the selected folders via the existing /api/jobs/bulk/delete
  // (trash, NOT hard-delete), then removes the folders. mode === "foldersOnly"
  // just removes the folders (their guides fall back to Unfiled, backend default).
  async function performFolderDelete(mode) {
    if (!folderDelete) return;
    const { folderIds } = folderDelete;
    setFolderDeleteBusy(true);
    setError(null);
    let trashedCount = 0;
    try {
      if (mode === "withGuides") {
        const idSet = new Set(folderIds);
        const jobIds = data.jobs.filter((job) => idSet.has(job.folder_id)).map((job) => job.id);
        if (jobIds.length) {
          const resp = await bulkDeleteJobs(jobIds);
          trashedCount = partitionResults(resp).ok.length;
        }
      }
      const okFolders = [];
      const failFolders = [];
      for (const fid of folderIds) {
        try {
          await deleteFolder(fid);
          okFolders.push(fid);
        } catch {
          failFolders.push(fid);
        }
      }
      // Successful folders disappear from selection; failed ones stay selected.
      setSelectedFolderIds(new Set(failFolders));
      if (okFolders.includes(selectedFolder)) setSelectedFolder("all");
      reload();
      const parts = [`${okFolders.length} folder${okFolders.length === 1 ? "" : "s"} deleted`];
      if (mode === "withGuides") parts.push(`${trashedCount} guide${trashedCount === 1 ? "" : "s"} moved to trash`);
      if (failFolders.length) parts.push(`${failFolders.length} failed`);
      setToast({
        id: Date.now(),
        tone: failFolders.length ? "error" : "success",
        message: parts.join(" · ")
      });
    } catch (err) {
      setToast({ id: Date.now(), tone: "error", message: err.message || "Could not delete folders." });
    } finally {
      setFolderDeleteBusy(false);
      setFolderDelete(null);
    }
  }

  // ── Trash multi-select ────────────────────────────────────────────────────
  const toggleTrashSelect = useCallback((jobId) => {
    setSelectedTrashIds((prev) => {
      const next = new Set(prev);
      next.has(jobId) ? next.delete(jobId) : next.add(jobId);
      return next;
    });
  }, []);

  const clearTrashSelection = useCallback(() => setSelectedTrashIds(new Set()), []);

  const trashIds = useMemo(() => trashJobs.map((job) => job.id), [trashJobs]);
  const allTrashSelected = trashIds.length > 0 && trashIds.every((id) => selectedTrashIds.has(id));
  const toggleSelectAllTrash = useCallback(() => {
    setSelectedTrashIds((prev) => {
      const everySelected = trashIds.length > 0 && trashIds.every((id) => prev.has(id));
      return everySelected ? new Set() : new Set(trashIds);
    });
  }, [trashIds]);

  // Bulk restore selected trashed guides via /api/jobs/bulk/restore.
  const handleBulkRestore = useCallback(async () => {
    const ids = [...selectedTrashIds];
    if (ids.length === 0) return;
    setError(null);
    try {
      const response = await bulkRestoreJobs(ids);
      const { ok, failed } = partitionResults(response);
      setSelectedTrashIds(new Set(failed.map((result) => result.id)));
      reload();
      setToast({
        id: Date.now(),
        tone: failed.length ? "error" : "success",
        message:
          `Restored ${ok.length} guide${ok.length === 1 ? "" : "s"}` +
          (failed.length ? ` · ${failed.length} failed` : "")
      });
    } catch (err) {
      setToast({ id: Date.now(), tone: "error", message: err.message || "Could not restore guides." });
    }
  }, [selectedTrashIds, reload]);

  // Permanently delete the selected trashed guides via /api/jobs/bulk/purge.
  // Routed only after the strong confirm modal; succeeded ids leave the selection.
  const performBulkPurge = useCallback(
    async (ids) => {
      const response = await bulkPurgeJobs(ids);
      const { ok, failed } = partitionResults(response);
      setSelectedTrashIds(new Set(failed.map((result) => result.id)));
      reload();
      const parts = [`${ok.length} permanently deleted`];
      if (failed.length) parts.push(`${failed.length} failed`);
      setToast({ id: Date.now(), tone: failed.length ? "error" : "success", message: parts.join(" · ") });
    },
    [reload]
  );

  const inTrashView = selectedFolder === TRASH_VIEW;

  // Run the action staged in the confirm modal, then close it and reload.
  async function runConfirm() {
    if (!confirm) return;
    setConfirmBusy(true);
    setError(null);
    try {
      if (confirm.kind === "trash") {
        await trashJob(confirm.job.id);
        reload();
      } else if (confirm.kind === "purge") {
        await purgeTrashedJob(confirm.job.id);
        reload();
      } else if (confirm.kind === "emptyTrash") {
        await emptyTrash();
        reload();
      } else if (confirm.kind === "bulkTrash") {
        // performBulkDelete does its own reload + selection update + toast.
        await performBulkDelete(confirm.ids);
      } else if (confirm.kind === "bulkPurge") {
        // performBulkPurge does its own reload + selection update + toast.
        await performBulkPurge(confirm.ids);
      }
      setConfirm(null);
    } catch (err) {
      setError(err.message || "Action failed.");
      setConfirm(null);
    } finally {
      setConfirmBusy(false);
    }
  }

  async function handleRestore(jobId) {
    setError(null);
    try {
      await restoreJob(jobId);
      reload();
    } catch (err) {
      setError(err.message || "Could not restore guide.");
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
        trashCount={trashJobs.length}
        trashView={TRASH_VIEW}
        selectedFolderIds={selectedFolderIds}
        onToggleFolderSelect={toggleFolderSelect}
        onClearFolderSelection={clearFolderSelection}
        onDeleteFolders={openFolderDelete}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sg-page-head">
          <div>
            <h1>{inTrashView ? "Trash" : folderMap[selectedFolder]?.name || "Library"}</h1>
            <p>
              {inTrashView
                ? `${trashJobs.length} guide${trashJobs.length === 1 ? "" : "s"} in trash`
                : `${filteredJobs.length} of ${data.jobs.length} guide${data.jobs.length === 1 ? "" : "s"}`}
            </p>
          </div>
          {inTrashView ? (
            <button
              type="button"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-red-400/40 bg-red-500/10 px-3 text-sm font-bold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={trashJobs.length === 0}
              onClick={() => setConfirm({ kind: "emptyTrash", count: trashJobs.length })}
            >
              <Trash2 size={15} /> Empty Trash
            </button>
          ) : (
            <button type="button" className="sg-cta sg-press-btn" onClick={() => onOpenBuilder?.()}>
              <Plus size={16} stroke="#1A1206" strokeWidth={2.6} />
              New Guide
            </button>
          )}
        </div>

        {!inTrashView && (
          <Toolbar
            q={q}
            setQ={setQ}
            sort={sort}
            setSort={setSort}
            showFilters={showFilters}
            setShowFilters={setShowFilters}
            activeFilterCount={activeFilterCount}
          />
        )}

        {!inTrashView && showFilters && (
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

        {!inTrashView && selectedIds.size > 0 && (
          <BulkBar
            count={selectedIds.size}
            folders={moveTargets.filter((folder) => folder.id !== "unfiled")}
            onMove={handleBatchMove}
            onUnfile={() => handleBatchMove("unfiled")}
            onDelete={() => setConfirm({ kind: "bulkTrash", count: selectedIds.size, ids: [...selectedIds] })}
            onClear={clearSelection}
          />
        )}

        {!inTrashView && !loading && filteredJobs.length > 0 && (
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

        {inTrashView && selectedTrashIds.size > 0 && (
          <TrashBulkBar
            count={selectedTrashIds.size}
            onRestore={handleBulkRestore}
            onPurge={() =>
              setConfirm({ kind: "bulkPurge", count: selectedTrashIds.size, ids: [...selectedTrashIds] })
            }
            onClear={clearTrashSelection}
          />
        )}

        {inTrashView && trashJobs.length > 0 && (
          <label className="mt-3 inline-flex w-fit cursor-pointer items-center gap-2 px-0.5 text-xs font-semibold text-slate-400 hover:text-slate-200">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 accent-ember-500"
              checked={allTrashSelected}
              onChange={toggleSelectAllTrash}
            />
            Select all ({trashIds.length})
          </label>
        )}

        <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1">
          {inTrashView ? (
            trashJobs.length === 0 ? (
              <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-slate-400">
                <Trash2 className="h-6 w-6 opacity-60" />
                <span>Trash is empty.</span>
              </div>
            ) : (
              <div className="grid gap-2.5">
                {trashJobs.map((job) => (
                  <TrashCard
                    key={job.id}
                    job={job}
                    style={resolveStyle(job.prompt_name, styleLookup)}
                    selected={selectedTrashIds.has(job.id)}
                    onToggleSelect={toggleTrashSelect}
                    onRestore={() => handleRestore(job.id)}
                    onDeleteForever={() => setConfirm({ kind: "purge", job })}
                  />
                ))}
              </div>
            )
          ) : loading ? (
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
                  onTrash={() => setConfirm({ kind: "trash", job })}
                  selected={selectedIds.has(job.id)}
                  onToggleSelect={toggleSelect}
                  onToggleFavorite={handleToggleFavorite}
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

      {confirm && (
        <ConfirmModal
          confirm={confirm}
          busy={confirmBusy}
          onCancel={() => !confirmBusy && setConfirm(null)}
          onConfirm={runConfirm}
        />
      )}

      {folderDelete && (
        <DeleteFoldersModal
          folderDelete={folderDelete}
          busy={folderDeleteBusy}
          onCancel={() => !folderDeleteBusy && setFolderDelete(null)}
          onFoldersOnly={() => performFolderDelete("foldersOnly")}
          onWithGuides={() => performFolderDelete("withGuides")}
        />
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

// Transient bottom-center toast. Supports an optional action button (used for
// the bulk-delete Undo). Tone drives the accent color; not a new dependency.
function Toast({ toast, onClose }) {
  if (!toast) return null;
  const tone =
    toast.tone === "error"
      ? "border-red-400/40 bg-red-500/15 text-red-100"
      : toast.tone === "success"
      ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-100"
      : "border-white/15 bg-[#0B0F19] text-slate-100";
  return (
    <div className="fixed bottom-5 left-1/2 z-[70] -translate-x-1/2">
      <div className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 shadow-2xl ${tone}`}>
        <span className="text-sm font-semibold">{toast.message}</span>
        {toast.action && (
          <button
            type="button"
            onClick={toast.action.run}
            className="inline-flex items-center gap-1 rounded-lg border border-white/25 bg-white/10 px-2.5 py-1 text-xs font-bold text-white transition hover:bg-white/20"
          >
            <RotateCcw size={12} /> {toast.action.label}
          </button>
        )}
        <button type="button" onClick={onClose} className="text-slate-400 transition hover:text-white" aria-label="Dismiss">
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

function jobTitle(job) {
  return job?.title || "Untitled study guide";
}

// Modal for both the soft "Move to trash" confirm and the strong destructive
// permanent-delete confirms. Destructive variants use a red action button that
// is NOT the default-focused control (Cancel holds initial focus).
function ConfirmModal({ confirm, busy, onCancel, onConfirm }) {
  const destructive =
    confirm.kind === "purge" || confirm.kind === "emptyTrash" || confirm.kind === "bulkPurge";
  let heading;
  let body;
  let actionLabel;
  if (confirm.kind === "trash") {
    heading = "Move to trash?";
    body = "You can restore it later from the Trash.";
    actionLabel = "Move to Trash";
  } else if (confirm.kind === "bulkTrash") {
    heading = `Move ${confirm.count} guide${confirm.count === 1 ? "" : "s"} to trash?`;
    body = "You can undo right after, or restore later from the Trash.";
    actionLabel = "Move to Trash";
  } else if (confirm.kind === "purge") {
    heading = `Permanently delete '${jobTitle(confirm.job)}'?`;
    body = "This cannot be undone.";
    actionLabel = "Delete Forever";
  } else if (confirm.kind === "bulkPurge") {
    heading = `Permanently delete ${confirm.count} selected guide${confirm.count === 1 ? "" : "s"}?`;
    body = "This permanently removes them from Trash and cannot be undone.";
    actionLabel = "Delete Forever";
  } else {
    heading = `Permanently delete all ${confirm.count} guide${confirm.count === 1 ? "" : "s"} in trash?`;
    body = "This cannot be undone.";
    actionLabel = "Delete Forever";
  }
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Cancel"
        className="absolute inset-0 cursor-default bg-black/60"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-sm rounded-2xl border border-white/10 bg-[#0B0F19] p-5 shadow-2xl"
      >
        <div className="flex items-start gap-3">
          {destructive ? (
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
          ) : (
            <Trash2 className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
          )}
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-white">{heading}</h2>
            <p className="mt-1 text-sm text-slate-400">{body}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            autoFocus
            disabled={busy}
            onClick={onCancel}
            className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3.5 text-sm font-bold transition disabled:opacity-50 ${
              destructive
                ? "border border-red-400/50 bg-red-500/80 text-white hover:bg-red-500"
                : "border border-amber-300/40 bg-amber-400/20 text-amber-100 hover:bg-amber-400/30"
            }`}
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {actionLabel}
          </button>
        </div>
      </div>
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
  folderError,
  trashCount = 0,
  trashView,
  selectedFolderIds,
  onToggleFolderSelect,
  onClearFolderSelection,
  onDeleteFolders
}) {
  const trashActive = selectedFolder === trashView;
  const folderSelectionCount = selectedFolderIds.size;
  return (
    <aside className="flex w-56 shrink-0 flex-col rounded-2xl border border-white/10 bg-white/[0.035] p-3">
      <p className="px-1 pb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">Folders</p>
      <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
        {folders.map((folder) => {
          const active = selectedFolder === folder.id;
          const isRenaming = renaming?.id === folder.id;
          const selectable = !folder.system;
          const selected = selectable && selectedFolderIds.has(folder.id);
          return (
            <div key={folder.id} className="group flex items-center gap-1">
              {selectable && !isRenaming && (
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 shrink-0 accent-ember-500"
                  checked={selected}
                  onChange={() => onToggleFolderSelect(folder.id)}
                  aria-label={`Select folder ${folder.name}`}
                />
              )}
              {isRenaming ? (
                <div className="grid min-w-0 flex-1 gap-1.5 px-1 py-1">
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
                  className={`flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition ${
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

      {folderSelectionCount > 0 && (
        <div className="mt-2 rounded-lg border border-ember-500/40 bg-ember-500/[0.08] p-2">
          <p className="px-0.5 text-xs font-bold text-white">
            {folderSelectionCount} folder{folderSelectionCount === 1 ? "" : "s"} selected
          </p>
          <div className="mt-1.5 flex items-center gap-1.5">
            <button
              type="button"
              onClick={onDeleteFolders}
              className="inline-flex h-7 flex-1 items-center justify-center gap-1 rounded-lg border border-red-400/40 bg-red-500/10 px-2 text-xs font-bold text-red-200 transition hover:bg-red-500/20"
            >
              <Trash2 size={12} /> Delete
            </button>
            <button
              type="button"
              onClick={onClearFolderSelection}
              className="inline-flex h-7 items-center justify-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 text-xs font-bold text-slate-300 transition hover:text-white"
            >
              <X size={12} /> Clear
            </button>
          </div>
        </div>
      )}

      <div className="mt-2 border-t border-white/10 pt-2">
        <button
          type="button"
          onClick={() => onSelect(trashView)}
          className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition ${
            trashActive ? "bg-ember-500/[0.12] text-white" : "text-slate-300 hover:bg-white/[0.05]"
          }`}
        >
          <Trash2 size={15} color={trashActive ? "#F97316" : "#9098A8"} />
          <span className="min-w-0 flex-1 truncate">Trash</span>
          <span className="text-[11px] tabular-nums text-slate-500">{trashCount}</span>
        </button>
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

function JobCard({ job, style, folder, moveTargets, onMove, onDetails, onTrash, selected, onToggleSelect, onToggleFavorite }) {
  const availability = job.artifact_availability || {};
  const attachments = job.attachment_summary || {};
  const created = job.created_at || "";
  const favorite = Boolean(job.favorite);
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
      <button
        type="button"
        onClick={() => onToggleFavorite?.(job.id, !favorite)}
        title={favorite ? "Remove from favorites" : "Add to favorites"}
        aria-label={favorite ? "Remove from favorites" : "Add to favorites"}
        aria-pressed={favorite}
        className={`flex shrink-0 items-start pt-0.5 transition ${
          favorite ? "text-ember-400" : "text-slate-500 hover:text-ember-300"
        }`}
      >
        <Star size={16} fill={favorite ? "currentColor" : "none"} />
      </button>
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
          <button
            type="button"
            onClick={onTrash}
            title="Move to trash"
            aria-label={`Move ${job.title || "study guide"} to trash`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-400 transition hover:border-red-400/50 hover:text-red-300"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function TrashCard({ job, style, selected, onToggleSelect, onRestore, onDeleteForever }) {
  const attachments = job.attachment_summary || {};
  return (
    <div
      className={`flex gap-3 rounded-xl border p-3 transition ${
        selected ? "border-ember-500/60 bg-ember-500/[0.08]" : "border-white/10 bg-white/[0.025]"
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
          <p className="truncate text-sm font-bold text-slate-200">{job.title || "Untitled study guide"}</p>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            {[[job.provider, job.model].filter(Boolean).join(" / ") || "Study guide",
              job.trashed_at ? `trashed ${job.trashed_at}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {style && <StylePill style={style} />}
            {(attachments.count || 0) > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-bold text-emerald-200">
                <Paperclip size={11} /> {attachments.count}
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={onRestore}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
          >
            <RotateCcw size={13} /> Restore
          </button>
          <button
            type="button"
            onClick={onDeleteForever}
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-red-400/40 bg-red-500/10 px-2.5 text-xs font-bold text-red-200 transition hover:bg-red-500/20"
          >
            <Trash2 size={13} /> Delete forever
          </button>
        </div>
      </div>
    </div>
  );
}

function BulkBar({ count, folders, onMove, onUnfile, onDelete, onClear }) {
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
          onClick={onDelete}
          className="inline-flex h-8 items-center gap-1 rounded-lg border border-red-400/40 bg-red-500/10 px-2.5 text-xs font-bold text-red-200 transition hover:bg-red-500/20"
        >
          <Trash2 size={13} /> Delete
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

function TrashBulkBar({ count, onRestore, onPurge, onClear }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-ember-500/40 bg-ember-500/[0.08] px-3 py-2">
      <span className="text-sm font-bold text-white">{count} selected</span>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onRestore}
          className="inline-flex h-8 items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-xs font-bold text-slate-200 transition hover:border-ember-500/60 hover:text-white"
        >
          <RotateCcw size={13} /> Restore selected
        </button>
        <button
          type="button"
          onClick={onPurge}
          className="inline-flex h-8 items-center gap-1 rounded-lg border border-red-400/40 bg-red-500/10 px-2.5 text-xs font-bold text-red-200 transition hover:bg-red-500/20"
        >
          <Trash2 size={13} /> Delete forever
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

// Folder bulk-delete modal. Unlike the single-action ConfirmModal it offers TWO
// destructive paths: (A) delete folders only — their guides fall back to Unfiled;
// (B) delete folders AND move the guides inside them to Trash (soft-delete,
// reversible from the Trash view). Cancel holds initial focus.
function DeleteFoldersModal({ folderDelete, busy, onCancel, onFoldersOnly, onWithGuides }) {
  const { folderIds, jobCount } = folderDelete;
  const folderLabel = `${folderIds.length} folder${folderIds.length === 1 ? "" : "s"}`;
  const guideLabel = `${jobCount} guide${jobCount === 1 ? "" : "s"}`;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button type="button" aria-label="Cancel" className="absolute inset-0 cursor-default bg-black/60" onClick={onCancel} />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#0B0F19] p-5 shadow-2xl"
      >
        <div className="flex items-start gap-3">
          <FolderClosed className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-white">Delete {folderLabel}?</h2>
            <p className="mt-1 text-sm text-slate-400">
              {jobCount > 0
                ? `${guideLabel} are filed in ${folderIds.length === 1 ? "this folder" : "these folders"}. Choose what happens to them.`
                : "These folders have no guides filed in them."}
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onFoldersOnly}
            className="flex flex-col items-start rounded-lg border border-white/15 bg-white/[0.04] px-3.5 py-2.5 text-left transition hover:bg-white/[0.08] disabled:opacity-50"
          >
            <span className="text-sm font-bold text-slate-100">Delete folders only</span>
            <span className="text-xs text-slate-400">Guides are kept and become Unfiled.</span>
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onWithGuides}
            className="flex flex-col items-start rounded-lg border border-red-400/40 bg-red-500/10 px-3.5 py-2.5 text-left transition hover:bg-red-500/20 disabled:opacity-50"
          >
            <span className="flex items-center gap-1.5 text-sm font-bold text-red-100">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              Delete folders and move guides to Trash
            </span>
            <span className="text-xs text-red-200/80">
              {guideLabel} are soft-deleted to Trash (restorable). Not permanent.
            </span>
          </button>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            autoFocus
            disabled={busy}
            onClick={onCancel}
            className="inline-flex h-9 items-center rounded-lg border border-white/15 bg-white/[0.04] px-3.5 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
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
