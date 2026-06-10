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
  downloadExportBundle,
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
  { id: "title_desc", label: "Title Z–A" },
  { id: "status", label: "Status" }
];

const emptyFilters = { status: "", provider: "", style: "", mode: "", favorite: false, hasAttachments: false, hasWarnings: false };

// Special pseudo-folder id for the Trash view.
const TRASH_VIEW = "__trash__";

function statusTone(status) {
  if (status === "done") return "pill-green";
  if (String(status || "").includes("failed")) return "pill-red";
  return "pill-amber";
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
  // True while a bulk "Export selected" ZIP bundle is being built/downloaded.
  const [exporting, setExporting] = useState(false);
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
    } else if (view === "favorites") {
      // Home "View all favorites" deep-link: preset the favorites filter (only
      // favourites shown) and reveal the filter bar so it's visible/clearable.
      setSelectedFolder("all");
      setQ("");
      setFilters({ ...emptyFilters, favorite: true });
      setSort("newest");
      setShowFilters(true);
    } else {
      // recent / all / pinned — favourites still float to the top within sort.
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
    (filters.favorite ? 1 : 0) +
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
      if (filters.favorite && !job.favorite) return false;
      if (filters.hasAttachments && !((job.attachment_summary?.count || 0) > 0)) return false;
      if (filters.hasWarnings && !(job.attachment_summary?.has_warnings || job.error)) return false;
      return true;
    });

    const created = (job) => String(job.created_at || job.id || "");
    if (sort === "oldest") list = [...list].sort((a, b) => created(a).localeCompare(created(b)));
    else if (sort === "title") list = [...list].sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")));
    else if (sort === "title_desc") list = [...list].sort((a, b) => String(b.title || "").localeCompare(String(a.title || "")));
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

  // Bulk export selected active guides as a ZIP via the existing
  // POST /api/exports/bundle (the same endpoint the Exports center uses). We
  // request the PDF artifact (the BundleRequest default); the backend silently
  // skips any selected guide that lacks one and only 404s if NONE are available.
  // The helper streams the ZIP straight into a browser download. Selection is
  // preserved on both success and failure so the user can retry or refine.
  const handleBulkExport = useCallback(async () => {
    const ids = [...selectedIds];
    if (ids.length === 0 || exporting) return;
    setExporting(true);
    setError(null);
    try {
      const { filename } = await downloadExportBundle(ids, ["pdf"]);
      setToast({
        id: Date.now(),
        tone: "success",
        message: `Exported ${ids.length} guide${ids.length === 1 ? "" : "s"} · ${filename}`
      });
    } catch (err) {
      setToast({ id: Date.now(), tone: "error", message: err.message || "Could not export selected guides." });
    } finally {
      setExporting(false);
    }
  }, [selectedIds, exporting]);

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
    <div className="sg-library">
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

      <div className="sg-lib-main">
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
              className="sg-btn-sm danger"
              style={{ height: 42, padding: "0 14px" }}
              disabled={trashJobs.length === 0}
              onClick={() => setConfirm({ kind: "emptyTrash", count: trashJobs.length })}
            >
              <Trash2 size={15} /> Empty Trash
            </button>
          ) : (
            <button type="button" className="sg-cta sg-press-btn" onClick={() => onOpenBuilder?.()}>
              <Plus size={16} stroke="#111" strokeWidth={2.6} />
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
          <div className="sg-lib-error">
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
            onExport={handleBulkExport}
            exporting={exporting}
            onDelete={() => setConfirm({ kind: "bulkTrash", count: selectedIds.size, ids: [...selectedIds] })}
            onClear={clearSelection}
          />
        )}

        {!inTrashView && !loading && filteredJobs.length > 0 && (
          <label className="sg-selectall">
            <input
              type="checkbox"
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
          <label className="sg-selectall">
            <input
              type="checkbox"
              checked={allTrashSelected}
              onChange={toggleSelectAllTrash}
            />
            Select all ({trashIds.length})
          </label>
        )}

        <div className="sg-lib-list">
          {inTrashView ? (
            trashJobs.length === 0 ? (
              <div className="sg-lib-empty">
                <Trash2 />
                <span>Trash is empty.</span>
              </div>
            ) : (
              <div className="sg-lib-cards">
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
            <div className="sg-lib-loading">
              <Loader2 className="sg-spin" />
              <span>Loading library…</span>
            </div>
          ) : filteredJobs.length === 0 ? (
            <div className="sg-lib-empty">
              <Layers3 />
              <span>No guides match this view.</span>
            </div>
          ) : (
            <div className="sg-lib-cards">
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
  const tone = toast.tone === "error" ? "error" : toast.tone === "success" ? "success" : "";
  return (
    <div className="sg-toast-wrap">
      <div className={`sg-toast ${tone}`.trim()}>
        <span>{toast.message}</span>
        {toast.action && (
          <button type="button" onClick={toast.action.run} className="sg-toast-action">
            <RotateCcw size={12} /> {toast.action.label}
          </button>
        )}
        <button type="button" onClick={onClose} className="sg-toast-x" aria-label="Dismiss">
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
    <div className="sg-modal-scrim">
      <button type="button" aria-label="Cancel" className="sg-scrim-bg" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="sg-modal" style={{ maxWidth: 400 }}>
        <div className="sg-modal-head">
          {destructive ? (
            <AlertTriangle style={{ color: "var(--red)" }} />
          ) : (
            <Trash2 style={{ color: "var(--amber)" }} />
          )}
          <div style={{ minWidth: 0 }}>
            <h2>{heading}</h2>
            <p>{body}</p>
          </div>
        </div>
        <div className="sg-modal-actions">
          <button type="button" autoFocus disabled={busy} onClick={onCancel} className="sg-ghost-button">
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className={`sg-ghost-button ${destructive ? "danger" : "accent"}`}
          >
            {busy && <Loader2 className="sg-spin" />}
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
  // System folders (All Guides / Unfiled) stay pinned near the top alongside
  // Trash; only the custom folders below scroll. This keeps the header, system
  // rows, selection action bar, and create controls in predictable places.
  const systemFolders = folders.filter((folder) => folder.system);
  const customFolders = folders.filter((folder) => !folder.system);

  const renderFolderLine = (folder) => {
    const active = selectedFolder === folder.id;
    const isRenaming = renaming?.id === folder.id;
    const selectable = !folder.system;
    const selected = selectable && selectedFolderIds.has(folder.id);
    return (
      <div key={folder.id} className="sg-folder-line">
        {selectable && !isRenaming && (
          <input
            type="checkbox"
            className="sg-folder-check"
            checked={selected}
            onChange={() => onToggleFolderSelect(folder.id)}
            aria-label={`Select folder ${folder.name}`}
          />
        )}
        {isRenaming ? (
          <div className="sg-folder-rename">
            <div className="sg-folder-rename-row">
              <input
                autoFocus
                className="sg-input compact"
                value={renaming.name}
                onChange={(event) => setRenaming({ ...renaming, name: event.target.value })}
                onKeyDown={(event) => {
                  if (event.key === "Enter") onRename();
                  if (event.key === "Escape") setRenaming(null);
                }}
              />
              <button type="button" className="sg-icon-button" onClick={onRename} title="Save">
                <Plus size={15} />
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
            className={`sg-folder-btn${active ? " active" : ""}`}
          >
            <FolderGlyph folder={folder} />
            <span className="sg-folder-name">{folder.name}</span>
            <span className="sg-folder-count">{folder.count}</span>
            {!folder.system && (
              <span className="sg-folder-tools">
                <span
                  role="button"
                  tabIndex={0}
                  className="sg-folder-tool"
                  onClick={(event) => {
                    event.stopPropagation();
                    setRenaming({ id: folder.id, name: folder.name, color: folder.color || FOLDER_PRESET_COLORS[0] });
                  }}
                  title="Rename"
                >
                  <Pencil size={13} />
                </span>
                <span
                  role="button"
                  tabIndex={0}
                  className="sg-folder-tool danger"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(folder);
                  }}
                  title="Delete"
                >
                  <Trash2 size={13} />
                </span>
              </span>
            )}
          </button>
        )}
      </div>
    );
  };

  return (
    <aside className="sg-folder-rail">
      <p className="sg-folder-rail-title">Folders</p>

      {/* System rows + Trash — pinned near the top, never pushed down. */}
      <div className="sg-folder-system">
        {systemFolders.map(renderFolderLine)}
        <div className="sg-folder-line">
          <button
            type="button"
            onClick={() => onSelect(trashView)}
            className={`sg-folder-btn${trashActive ? " active" : ""}`}
          >
            <Trash2 size={16} color={trashActive ? "var(--indigo)" : "var(--muted)"} />
            <span className="sg-folder-name">Trash</span>
            <span className="sg-folder-count">{trashCount}</span>
          </button>
        </div>
      </div>

      {/* Folder selection action bar — directly above the custom folder list. */}
      {folderSelectionCount > 0 && (
        <div className="sg-folder-selbar">
          <p>
            {folderSelectionCount} folder{folderSelectionCount === 1 ? "" : "s"} selected
          </p>
          <div className="sg-folder-selbar-row">
            <button type="button" onClick={onDeleteFolders} className="sg-btn-sm danger" style={{ flex: 1 }}>
              <Trash2 size={13} /> Delete
            </button>
            <button type="button" onClick={onClearFolderSelection} className="sg-btn-sm">
              <X size={13} /> Clear
            </button>
          </div>
        </div>
      )}

      {/* Only the custom folder list scrolls when it overflows. */}
      <div className="sg-folder-scroll">{customFolders.map(renderFolderLine)}</div>

      <div className="sg-folder-sep">
        <div className="sg-folder-create-row">
          <input
            className="sg-input compact"
            placeholder="New folder…"
            value={newFolderName}
            onChange={(event) => setNewFolderName(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && onCreate()}
          />
          <button type="button" className="sg-icon-button" onClick={onCreate} title="Create folder">
            <FolderPlus size={15} />
          </button>
        </div>
        <div style={{ marginTop: 10, paddingLeft: 2 }}>
          <ColorSwatches value={newFolderColor} onChange={setNewFolderColor} />
        </div>
        {folderError && <p className="sg-folder-err">{folderError}</p>}
      </div>
    </aside>
  );
}

function FolderGlyph({ folder }) {
  const color = folder.color || (folder.system ? "var(--muted)" : "var(--indigo)");
  if (folder.id === "all") return <Layers3 size={16} color="var(--indigo)" />;
  return <FolderClosed size={16} color={color} />;
}

function ColorSwatches({ value, onChange }) {
  return (
    <div className="sg-cswatches">
      {FOLDER_PRESET_COLORS.map((color) => {
        const active = (value || "").toLowerCase() === color.toLowerCase();
        return (
          <button
            key={color}
            type="button"
            onClick={() => onChange(color)}
            title={color}
            aria-label={`Folder color ${color}`}
            className={`sg-cswatch${active ? " active" : ""}`}
            style={{ backgroundColor: color }}
          />
        );
      })}
    </div>
  );
}

function Toolbar({ q, setQ, sort, setSort, showFilters, setShowFilters, activeFilterCount }) {
  return (
    <div className="sg-lib-toolbar">
      <div className="sg-search">
        <Search size={15} />
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
        className={`sg-filter-btn${activeFilterCount > 0 || showFilters ? " active" : ""}`}
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

function FilterBar({ filters, setFilters, statuses, providers, styleChoices, modes, onClear }) {
  const set = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  return (
    <div className="sg-filterbar">
      <FilterSelect label="Status" value={filters.status} onChange={(value) => set("status", value)} options={statuses} />
      <FilterSelect label="Provider" value={filters.provider} onChange={(value) => set("provider", value)} options={providers} />
      <FilterSelect
        label="Style"
        value={filters.style}
        onChange={(value) => set("style", value)}
        options={styleChoices.map(([id, name]) => ({ value: id, label: name }))}
      />
      <FilterSelect label="Input" value={filters.mode} onChange={(value) => set("mode", value)} options={modes} />
      <ToggleChip active={filters.favorite} onClick={() => set("favorite", !filters.favorite)}>
        <Star size={12} /> Favorites
      </ToggleChip>
      <ToggleChip active={filters.hasAttachments} onClick={() => set("hasAttachments", !filters.hasAttachments)}>
        <Paperclip size={12} /> Attachments
      </ToggleChip>
      <ToggleChip active={filters.hasWarnings} onClick={() => set("hasWarnings", !filters.hasWarnings)}>
        <AlertCircle size={12} /> Warnings
      </ToggleChip>
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

function ToggleChip({ active, onClick, children }) {
  return (
    <button type="button" onClick={onClick} className={`sg-toggle-chip${active ? " active" : ""}`}>
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
    <div className={`sg-job-card${selected ? " selected" : ""}`}>
      <label className="sg-job-check" onClick={(event) => event.stopPropagation()}>
        <input
          type="checkbox"
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
        className={`sg-job-fav${favorite ? " on" : ""}`}
      >
        <Star size={16} fill={favorite ? "currentColor" : "none"} />
      </button>
      <div className="sg-job-body">
        <div className="sg-job-main">
          <p className="sg-job-title">{job.title || "Untitled study guide"}</p>
          <p className="sg-job-sub">
            {[[job.provider, job.model].filter(Boolean).join(" / ") || "Study guide", created].filter(Boolean).join(" · ")}
          </p>
          <div className="sg-job-meta">
            <span className={`pill ${statusTone(job.status)}`}>{job.status || "unknown"}</span>
            {style && <StylePill style={style} />}
            {folder && folder.id !== "unfiled" && <FolderPill folder={folder} />}
            {(attachments.count || 0) > 0 && (
              <span className="pill pill-green">
                <Paperclip size={11} /> {attachments.count}
              </span>
            )}
            {attachments.has_warnings && (
              <span className="pill pill-amber">
                <AlertCircle size={11} /> {attachments.warning_count || 1}
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
          {availability.clean_md && (
            <a href={artifactUrl(job.id, "clean.md")} className="sg-btn-sm">
              <Download size={13} /> MD
            </a>
          )}
          <MoveMenu job={job} folders={moveTargets} onMove={onMove} />
          <button type="button" onClick={onDetails} className="sg-btn-sm accent">
            Details
          </button>
          <button
            type="button"
            onClick={onTrash}
            title="Move to trash"
            aria-label={`Move ${job.title || "study guide"} to trash`}
            className="sg-btn-sm sq danger"
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
    <div className={`sg-job-card${selected ? " selected" : ""}`}>
      <label className="sg-job-check" onClick={(event) => event.stopPropagation()}>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(job.id)}
          aria-label={`Select ${job.title || "study guide"}`}
        />
      </label>
      <div className="sg-job-body">
        <div className="sg-job-main">
          <p className="sg-job-title">{job.title || "Untitled study guide"}</p>
          <p className="sg-job-sub">
            {[[job.provider, job.model].filter(Boolean).join(" / ") || "Study guide",
              job.trashed_at ? `trashed ${job.trashed_at}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <div className="sg-job-meta">
            {style && <StylePill style={style} />}
            {(attachments.count || 0) > 0 && (
              <span className="pill pill-green">
                <Paperclip size={11} /> {attachments.count}
              </span>
            )}
          </div>
        </div>
        <div className="sg-job-actions">
          <button type="button" onClick={onRestore} className="sg-btn-sm">
            <RotateCcw size={13} /> Restore
          </button>
          <button type="button" onClick={onDeleteForever} className="sg-btn-sm danger">
            <Trash2 size={13} /> Delete forever
          </button>
        </div>
      </div>
    </div>
  );
}

function BulkBar({ count, folders, onMove, onUnfile, onExport, exporting, onDelete, onClear }) {
  return (
    <div className="sg-bulkbar">
      <span className="sg-bulk-count">{count} selected</span>
      <div className="sg-bulk-actions">
        <BatchMoveMenu folders={folders} onMove={onMove} />
        <button type="button" onClick={onUnfile} className="sg-btn-sm">
          <FolderClosed size={13} /> Move to Unfiled
        </button>
        <button type="button" onClick={onExport} disabled={exporting || count === 0} className="sg-btn-sm">
          {exporting ? <Loader2 size={13} className="sg-spin" /> : <Download size={13} />}
          {exporting ? "Exporting…" : "Export selected"}
        </button>
        <button type="button" onClick={onDelete} className="sg-btn-sm danger">
          <Trash2 size={13} /> Delete
        </button>
        <button type="button" onClick={onClear} className="sg-btn-sm">
          <X size={13} /> Clear
        </button>
      </div>
    </div>
  );
}

function TrashBulkBar({ count, onRestore, onPurge, onClear }) {
  return (
    <div className="sg-bulkbar">
      <span className="sg-bulk-count">{count} selected</span>
      <div className="sg-bulk-actions">
        <button type="button" onClick={onRestore} className="sg-btn-sm">
          <RotateCcw size={13} /> Restore selected
        </button>
        <button type="button" onClick={onPurge} className="sg-btn-sm danger">
          <Trash2 size={13} /> Delete forever
        </button>
        <button type="button" onClick={onClear} className="sg-btn-sm">
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
    <div className="sg-modal-scrim">
      <button type="button" aria-label="Cancel" className="sg-scrim-bg" onClick={onCancel} />
      <div role="dialog" aria-modal="true" className="sg-modal" style={{ maxWidth: 460 }}>
        <div className="sg-modal-head">
          <FolderClosed style={{ color: "var(--amber)" }} />
          <div style={{ minWidth: 0 }}>
            <h2>Delete {folderLabel}?</h2>
            <p>
              {jobCount > 0
                ? `${guideLabel} are filed in ${folderIds.length === 1 ? "this folder" : "these folders"}. Choose what happens to them.`
                : "These folders have no guides filed in them."}
            </p>
          </div>
        </div>
        <div className="sg-modal-choices">
          <button type="button" disabled={busy} onClick={onFoldersOnly} className="sg-choice">
            <span className="t">Delete folders only</span>
            <span className="d">Guides are kept and become Unfiled.</span>
          </button>
          <button type="button" disabled={busy} onClick={onWithGuides} className="sg-choice danger">
            <span className="t">
              {busy && <Loader2 className="sg-spin" style={{ width: 16, height: 16 }} />}
              Delete folders and move guides to Trash
            </span>
            <span className="d">{guideLabel} are soft-deleted to Trash (restorable). Not permanent.</span>
          </button>
        </div>
        <div className="sg-modal-actions">
          <button type="button" autoFocus disabled={busy} onClick={onCancel} className="sg-ghost-button">
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
    <div className="sg-menu-wrap">
      <button type="button" onClick={() => setOpen((value) => !value)} className="sg-btn-sm accent">
        <FolderClosed size={13} /> Move to folder <ChevronDown size={12} />
      </button>
      {open && (
        <>
          <button type="button" className="sg-menu-scrim" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="sg-menu">
            {folders.length === 0 && <p className="sg-menu-empty">No folders yet.</p>}
            {folders.map((folder) => (
              <button
                key={folder.id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  onMove(folder.id);
                }}
                className="sg-menu-item"
              >
                <FolderClosed size={13} color={folderColor(folder)} />
                <span className="name">{folder.name}</span>
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
    <div className="sg-menu-wrap">
      <button type="button" onClick={() => setOpen((value) => !value)} className="sg-btn-sm">
        <FolderClosed size={13} /> Move <ChevronDown size={12} />
      </button>
      {open && (
        <>
          <button type="button" className="sg-menu-scrim" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="sg-menu">
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
                  className="sg-menu-item"
                >
                  <FolderClosed size={13} color={folder.color || "var(--muted)"} />
                  <span className="name">{folder.name}</span>
                  {current && <span className="cur">current</span>}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
