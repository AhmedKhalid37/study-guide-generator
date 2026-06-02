import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bookmark,
  Check,
  ChevronRight,
  Clock,
  Download,
  FileCode2,
  FileJson,
  FileText,
  Folder,
  FolderPlus,
  Info,
  LayoutTemplate,
  Leaf,
  ListChecks,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  Share2,
  Sparkles,
  Trophy,
  Upload,
  Wand2,
  X,
  Zap
} from "lucide-react";
import {
  apiUrl,
  applyPreset,
  createFolder,
  createLlmJob,
  createPasteJob,
  createShortcut,
  cancelJob,
  createUploadMarkdownJob,
  getFolders,
  getJob,
  getJobProgress,
  getJobs,
  getOptions,
  getPresets,
  getStyles,
  previewApiUrl
} from "../api/client";
import {
  builderStateToPayload,
  INPUT_TO_SOURCE,
  pagesToLength
} from "../shortcutMeta";
import {
  DIFFICULTY_OPTIONS,
  hasEnabledSections,
  normalizeSectionState,
  OUTPUT_DEPTH_OPTIONS,
  SECTION_GROUPS
} from "../sectionMeta";
import { FOLDER_PRESET_COLORS } from "../folderMeta";
import { presetCompat, presetModelLabel, providerIconFor, providerLabelFor } from "../presetMeta";
import {
  BoltGlyph,
  DocGlyph,
  LeafGlyph,
  ListGlyph,
  PDFGlyph,
  SparkleGlyph,
  Tile,
  TrophyGlyph,
  UploadGlyph
} from "./ClaudeIcons";
import { JobDetailsDrawer } from "./RecentJobsPanel";
import { BUILTIN_STYLE_NAMES } from "../styleMeta";
import OutlineEditor from "./OutlineEditor";

const sourceTabs = [
  { id: "llm", label: "AI prompt" },
  { id: "paste", label: "Paste text" },
  { id: "upload", label: "Upload .md" },
  { id: "url", label: "URL", disabled: true }
];

const builderTabs = [
  { id: "builder", label: "Builder" },
  { id: "outline", label: "Outline" },
  { id: "style", label: "Style" },
  { id: "preview", label: "Preview" }
];

const builtinStyleMeta = {
  basic_study_guide: { label: "Basic", icon: FileText },
  baby_steps: { label: "Baby", icon: Leaf },
  exam_cram: { label: "Cram", icon: Zap },
  mcq_training: { label: "MCQ", icon: ListChecks },
  final_solution: { label: "Final", icon: Trophy },
  claude_study_guide: { label: "Editorial", icon: Sparkles },
  master_longform: { label: "Master", icon: Wand2 }
};

// Static fallback used until /api/styles resolves (and as the built-in icon source).
const styleChips = Object.entries(builtinStyleMeta).map(([promptName, meta]) => ({
  promptName,
  label: meta.label,
  name: BUILTIN_STYLE_NAMES[promptName] || meta.label,
  icon: meta.icon,
  custom: false
}));

function styleRecordToChip(style) {
  const meta = builtinStyleMeta[style.id];
  const isCustom = style.source === "custom";
  const name = style.name || BUILTIN_STYLE_NAMES[style.id] || style.id;
  let label = meta?.label || name;
  if (!meta && label.length > 12) {
    label = `${label.slice(0, 11)}…`;
  }
  return {
    promptName: style.id,
    label,
    name,
    icon: meta?.icon || (isCustom ? Sparkles : FileText),
    custom: isCustom
  };
}

const lengthOptions = [
  { id: "short", label: "Short", meta: "~10 pages" },
  { id: "medium", label: "Medium", meta: "~20 pages" },
  { id: "long", label: "Long", meta: "~30+ pages" }
];

const DRAFT_KEY = "builder_draft_v1";
const DEFAULT_TITLE = "Generated Study Guide";

function draftHasContent(draft) {
  if (!draft) return false;
  const title = (draft.title || "").trim();
  const text = (draft.text || "").trim();
  const sections = draft.outline?.sections || [];
  return Boolean(
    text ||
      (title && title !== DEFAULT_TITLE) ||
      sections.some((section) => (section?.title || "").trim())
  );
}

function formatDraftTime(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const diffMs = Date.now() - then.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin === 1) return "1 minute ago";
  if (diffMin < 60) return `${diffMin} minutes ago`;
  return then.toLocaleString();
}

// Short, plain-language tooltip copy. Placeholder wording — final copy TBD.
// Per-section help lives alongside the canonical keys in sectionMeta.js; this
// table only covers the non-section Builder controls + the generation axes.
const TOOLTIPS = {
  provider: "Which AI service generates the guide. Only configured providers can run.",
  model: "The specific model used for generation. Larger models are slower but stronger.",
  generatorPreset: "Controls the main system prompt and guide structure. Overrides the style below.",
  modelCompat: "Each preset is tuned for a specific model. This is only a suggestion — your selected model is always used and Generate stays enabled.",
  style: "The built-in or custom prompt that shapes tone and layout of the guide.",
  length: "Target output depth — roughly how many pages the guide should aim for.",
  strictMath: "Validate every formula and fail loudly on broken math instead of guessing.",
  attachments: "Extra source files. PDFs/scans are read with OCR/VLM when there is no text layer.",
  outputDepth: "How deep the whole guide goes — quick & high-yield, balanced, or exhaustive. Auto leaves it to the style.",
  difficulty: "How the material is pitched — beginner, normal, exam-level, or advanced. Auto leaves it to the style.",
  sections: "Optional extra sections to add where the source supports them. None are added unless you pick them."
};

// Terminal generation statuses: once the progress endpoint reports one of these,
// the UI stops polling. ``status`` (not ``stage``) is the source of truth.
const TERMINAL_STATUSES = new Set([
  "done",
  "completed_with_warnings",
  "failed",
  "cancelled"
]);

function isTerminalStatus(status) {
  return Boolean(status) && TERMINAL_STATUSES.has(status);
}

const fallbackProviderDetails = [
  {
    id: "deepseek",
    display_name: "DeepSeek",
    configured: false,
    available_models: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    default_model: "deepseek-v4-flash",
    supports_thinking: false
  },
  {
    id: "qwen",
    display_name: "Qwen",
    configured: false,
    available_models: ["qwen3.7-max", "qwen3.6-plus", "qwen3-max", "qwen3.6-max-preview", "qwen-plus", "qwen-max"],
    default_model: "qwen3.7-max",
    supports_thinking: true
  },
  {
    id: "local",
    display_name: "Local llama.cpp",
    configured: false,
    available_models: [],
    default_model: "",
    supports_thinking: false
  }
];

const artifactLabels = {
  "final.pdf": { label: "PDF", icon: Download },
  "final.docx": { label: "DOCX", icon: FileText },
  "clean.md": { label: "Markdown", icon: FileText },
  "final.html": { label: "HTML", icon: FileCode2 },
  "validation.json": { label: "validation.json", icon: FileJson },
  "render.log": { label: "render.log", icon: FileText }
};

export default function BuilderWorkspace({
  initialSource = "llm",
  selectedStyle = "exam_cram",
  onSelectStyle,
  latestJob,
  onJobCreated,
  prefill = null,
  onReportSetup
}) {
  const [activeBuilderTab, setActiveBuilderTab] = useState("builder");
  const [source, setSource] = useState(initialSource);
  const [title, setTitle] = useState("Generated Study Guide");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState(fallbackProviderDetails[0].default_model);
  const [providerDetails, setProviderDetails] = useState(fallbackProviderDetails);
  // True once the server's real provider list has loaded (or failed to). The
  // shortcut-prefill model resolver waits for this so it validates the saved
  // model against the real model list, not the fallback.
  const [providersLoaded, setProvidersLoaded] = useState(false);
  // Set when the model loaded from a shortcut wasn't valid for its provider, so
  // we can surface the fallback instead of silently swapping models.
  const [modelNotice, setModelNotice] = useState(null);
  // Holds a shortcut's { provider, model } while we wait for that provider's
  // model list to load; the resolver effect below applies it once ready.
  const pendingPrefillRef = useRef(null);
  const [pendingModelNonce, setPendingModelNonce] = useState(0);
  const [qwenThinking, setQwenThinking] = useState(true);
  const [strictMath, setStrictMath] = useState(true);
  const [attachments, setAttachments] = useState([]);
  const [folderId, setFolderId] = useState("unfiled");
  const [folders, setFolders] = useState([]);
  const [styleOptions, setStyleOptions] = useState(styleChips);
  const [generatorPresets, setGeneratorPresets] = useState([]);
  const [generatorPreset, setGeneratorPreset] = useState("");
  const [length, setLength] = useState("medium");
  // Canonical output-section toggles (dict-of-bool of enabled keys only). Default
  // none — a fresh Builder sends no include_sections (keeps the default request
  // byte-equivalent on this axis).
  const [includeSections, setIncludeSections] = useState({});
  // Global generation axes (C2). "" is the unset sentinel — omitted from the
  // request and stored as null in a shortcut.
  const [outputDepth, setOutputDepth] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [outlineEnabled, setOutlineEnabled] = useState(false);
  const [outlineSections, setOutlineSections] = useState([]);
  const [presets, setPresets] = useState([]);
  const [selectedPreset, setSelectedPreset] = useState("");
  const [presetBusy, setPresetBusy] = useState(false);
  const [restoreDraft, setRestoreDraft] = useState(null);
  const [draftSavedAt, setDraftSavedAt] = useState(null);
  const saveTimerRef = useRef(null);
  const [result, setResult] = useState(latestJob);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewFormat, setPreviewFormat] = useState("sample");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsInitialTab, setDetailsInitialTab] = useState("details");
  const [jobDetails, setJobDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);
  // Live generation progress from GET /api/jobs/{id}/progress (null when idle).
  const [progress, setProgress] = useState(null);
  // Id of the in-flight job once the poller has discovered it (null until then).
  // Needed so the Cancel button has a target — the create-job POST is blocking
  // and doesn't hand back the id until it resolves.
  const [activeJobId, setActiveJobId] = useState(null);
  // True from the moment the user clicks Cancel until the run resolves.
  const [cancelling, setCancelling] = useState(false);
  // True once settings change after a guide has been generated.
  const [dirty, setDirty] = useState(false);
  // Transient confirmation + error for the "save as shortcut" action.
  const [shortcutSaved, setShortcutSaved] = useState(false);
  const [shortcutSaveError, setShortcutSaveError] = useState(null);
  const [shortcutSaving, setShortcutSaving] = useState(false);
  const pollStateRef = useRef(null);
  const pollTimerRef = useRef(null);
  const completeTimerRef = useRef(null);
  const shortcutTimerRef = useRef(null);
  // Signature of the settings that produced the current result; null until a
  // guide is generated in this session. Used to detect a "dirty" preview.
  const baselineRef = useRef(null);

  useEffect(() => {
    setSource(initialSource);
    setError(null);
    setActiveBuilderTab("builder");
  }, [initialSource]);

  useEffect(() => {
    if (latestJob) {
      setResult(latestJob);
    }
  }, [latestJob]);

  useEffect(() => {
    let cancelled = false;
    getOptions()
      .then((options) => {
        if (cancelled) return;
        const details = normalizeProviderDetails(options);
        setProviderDetails(details);
        setGeneratorPresets(options.generator_presets ?? []);
        setProvidersLoaded(true);
        // A shortcut prefill owns the provider+model; don't override it with the
        // default-provider pick. The resolver effect applies the saved model.
        if (pendingPrefillRef.current) return;
        const selected = chooseInitialProvider(details, provider);
        setProvider(selected.id);
        setModel(selectDefaultModel(selected, model));
      })
      .catch(() => {
        if (!cancelled) {
          setProviderDetails(fallbackProviderDetails);
          setProvidersLoaded(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getStyles()
      .then((result) => {
        if (cancelled) return;
        const all = [...(result.builtin ?? []), ...(result.custom ?? [])];
        if (all.length > 0) {
          setStyleOptions(all.map(styleRecordToChip));
        }
      })
      .catch(() => {
        if (!cancelled) setStyleOptions(styleChips);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Only real folders are selectable here; "All Guides"/"Unfiled" are virtual
  // system views the API marks with `system: true`.
  const loadFolders = useCallback(
    () =>
      getFolders()
        .then((result) => {
          const real = (result.folders ?? []).filter((folder) => !folder.system);
          setFolders(real);
          return real;
        })
        .catch(() => {
          setFolders([]);
          return [];
        }),
    []
  );

  useEffect(() => {
    loadFolders();
  }, [loadFolders]);

  const handleCreateFolder = useCallback(
    async ({ name, color }) => {
      // Throws on invalid/duplicate so the popover can surface the message.
      const created = await createFolder({ name, color });
      await loadFolders();
      setFolderId(created.id);
      return created;
    },
    [loadFolders]
  );

  useEffect(() => {
    let cancelled = false;
    getPresets()
      .then((result) => {
        if (!cancelled) setPresets(result.presets ?? []);
      })
      .catch(() => {
        if (!cancelled) setPresets([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Selecting a template pre-fills the outline + style; "Custom" clears the
  // template selection without touching the user's current outline/style.
  const handleApplyPreset = useCallback(
    async (presetId) => {
      if (!presetId || presetId === "custom") {
        setSelectedPreset("");
        return;
      }
      setPresetBusy(true);
      try {
        const applied = await applyPreset(presetId);
        const sections = applied.outline?.sections ?? [];
        setOutlineSections(sections);
        setOutlineEnabled(Boolean(applied.outline?.enabled) && sections.length > 0);
        if (applied.style) onSelectStyle?.(applied.style);
        setSelectedPreset(presetId);
      } catch (presetError) {
        setError(normalizeError(presetError));
      } finally {
        setPresetBusy(false);
      }
    },
    [onSelectStyle]
  );

  const buildDraft = useCallback(
    () => ({
      savedAt: new Date().toISOString(),
      title,
      text,
      source,
      outline: { enabled: outlineEnabled, sections: outlineSections },
      style: selectedStyle,
      folderId,
      template: selectedPreset,
      length,
      // Canonical generation options (C3): persist the section toggles + axes so a
      // restored draft reproduces the same generate request. Stored as-is; restore
      // re-normalizes against the known key set.
      includeSections,
      outputDepth,
      difficulty
    }),
    [
      title,
      text,
      source,
      outlineEnabled,
      outlineSections,
      selectedStyle,
      folderId,
      selectedPreset,
      length,
      includeSections,
      outputDepth,
      difficulty
    ]
  );

  const clearDraft = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    try {
      window.localStorage.removeItem(DRAFT_KEY);
    } catch {
      // localStorage unavailable (private mode / SSR) — nothing to clear.
    }
    setDraftSavedAt(null);
    setRestoreDraft(null);
  }, []);

  // On mount, surface (but never auto-apply) any saved draft with real content.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (draftHasContent(parsed)) setRestoreDraft(parsed);
    } catch {
      // Corrupt/unavailable draft — ignore it.
    }
  }, []);

  // Debounced autosave. Only writes when there is meaningful content so an empty
  // form on first mount can never clobber a real saved draft before the user
  // decides whether to restore it.
  useEffect(() => {
    const draft = buildDraft();
    if (!draftHasContent(draft)) return undefined;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
        setDraftSavedAt(draft.savedAt);
      } catch {
        // Ignore quota / unavailable storage.
      }
    }, 800);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [buildDraft]);

  const handleSaveDraft = useCallback(() => {
    const draft = buildDraft();
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
      setDraftSavedAt(draft.savedAt);
    } catch {
      // Ignore quota / unavailable storage.
    }
  }, [buildDraft]);

  const handleRestoreDraft = useCallback(() => {
    const draft = restoreDraft;
    if (!draft) return;
    setTitle(draft.title ?? DEFAULT_TITLE);
    setText(draft.text ?? "");
    if (draft.source) setSource(draft.source);
    setOutlineEnabled(Boolean(draft.outline?.enabled));
    setOutlineSections(Array.isArray(draft.outline?.sections) ? draft.outline.sections : []);
    if (draft.style) onSelectStyle?.(draft.style);
    if (draft.folderId) setFolderId(draft.folderId);
    setSelectedPreset(draft.template || "");
    if (draft.length) setLength(draft.length);
    // Canonical generation options (C3). Re-normalize sections against the known
    // key set (drops anything the Builder no longer exposes); axes fall back to
    // the unset sentinel when absent/garbage so restore is deterministic.
    setIncludeSections(normalizeSectionState(draft.includeSections));
    setOutputDepth(typeof draft.outputDepth === "string" ? draft.outputDepth : "");
    setDifficulty(typeof draft.difficulty === "string" ? draft.difficulty : "");
    setRestoreDraft(null);
  }, [restoreDraft, onSelectStyle]);

  const artifactEntries = useMemo(() => {
    if (!result?.artifact_urls) {
      return [];
    }
    return Object.entries(result.artifact_urls).filter(([name]) => artifactLabels[name]);
  }, [result]);

  const artifactUrls = useMemo(() => result?.artifact_urls ?? {}, [result]);
  const selectedStyleOption =
    styleOptions.find((style) => style.promptName === selectedStyle) ||
    styleChips.find((style) => style.promptName === selectedStyle);
  const builderStyleLookup = useMemo(
    () =>
      Object.fromEntries(
        styleOptions.map((style) => [
          style.promptName,
          { name: style.name, source: style.custom ? "custom" : "builtin" }
        ])
      ),
    [styleOptions]
  );
  const selectedLengthOption = lengthOptions.find((option) => option.id === length);
  const selectedProvider = useMemo(
    () => providerDetails.find((item) => item.id === provider) ?? providerDetails[0],
    [providerDetails, provider]
  );
  const selectedProviderModels = selectedProvider?.available_models?.length
    ? selectedProvider.available_models
    : selectedProvider?.default_model
      ? [selectedProvider.default_model]
      : [];

  // A stable fingerprint of every setting that affects generation output. When it
  // drifts from the baseline captured at generation time, the preview is stale.
  const settingsSignature = useMemo(
    () =>
      JSON.stringify({
        selectedStyle,
        generatorPreset,
        provider,
        model,
        length,
        includeSections,
        outputDepth,
        difficulty,
        strictMath,
        qwenThinking,
        outlineEnabled,
        outlineSections
      }),
    [
      selectedStyle,
      generatorPreset,
      provider,
      model,
      length,
      includeSections,
      outputDepth,
      difficulty,
      strictMath,
      qwenThinking,
      outlineEnabled,
      outlineSections
    ]
  );

  useEffect(() => {
    // Only flag dirtiness once a guide has actually been generated this session.
    if (!result || baselineRef.current === null) {
      setDirty(false);
      return;
    }
    setDirty(settingsSignature !== baselineRef.current);
  }, [settingsSignature, result]);

  // Tidy up timers / stop polling if the component unmounts mid-generation.
  useEffect(
    () => () => {
      if (pollStateRef.current) pollStateRef.current.active = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
      if (completeTimerRef.current) clearTimeout(completeTimerRef.current);
      if (shortcutTimerRef.current) clearTimeout(shortcutTimerRef.current);
    },
    []
  );

  useEffect(() => {
    if (!result) {
      setPreviewFormat("sample");
      return;
    }
    if (artifactUrls["final.pdf"]) {
      setPreviewFormat("pdf");
    } else if (artifactUrls["final.html"]) {
      setPreviewFormat("html");
    } else {
      setPreviewFormat("pdf");
    }
  }, [result, artifactUrls]);

  function handleSubmit(event) {
    event.preventDefault();
    runGeneration();
  }

  // Starts a background poller that discovers the in-flight job (the create-job
  // POST is blocking, so we only learn its id by diffing the jobs list) and then
  // polls its coarse progress until a terminal status. Returns a stop handle.
  function startProgressPolling(knownIds) {
    const state = { active: true, jobId: null };
    pollStateRef.current = state;

    const tick = async () => {
      if (!state.active) return;
      try {
        if (!state.jobId) {
          const { jobs = [] } = await getJobs();
          const fresh = jobs.find((job) => {
            const id = job.id || job.job_id;
            return id && !knownIds.has(id);
          });
          if (fresh) {
            state.jobId = fresh.id || fresh.job_id;
            // Surface the id so the Cancel button has a target to act on.
            if (state.active) setActiveJobId(state.jobId);
          }
        }
        if (state.jobId) {
          const snapshot = await getJobProgress(state.jobId);
          if (state.active) setProgress(snapshot);
          if (isTerminalStatus(snapshot.status)) {
            // The blocking POST will resolve with the authoritative job shortly.
            return;
          }
        }
      } catch {
        // Transient (job not yet on disk, momentary 404) — keep polling.
      }
      if (state.active) pollTimerRef.current = setTimeout(tick, 300);
    };

    // First sweep slightly delayed so Job.create has written job.json.
    pollTimerRef.current = setTimeout(tick, 600);
    return state;
  }

  async function runGeneration() {
    const validation = validateInputs();
    if (validation) {
      setError({ message: validation });
      return;
    }

    setLoading(true);
    setError(null);
    setActiveJobId(null);
    setCancelling(false);
    if (completeTimerRef.current) clearTimeout(completeTimerRef.current);
    setProgress({ status: "running", stage: "preparing", stage_label: "Starting…", progress: 5 });

    // Snapshot existing ids so we can spot the newly-created (running) job.
    let knownIds = new Set();
    try {
      const { jobs = [] } = await getJobs();
      knownIds = new Set(jobs.map((job) => job.id || job.job_id).filter(Boolean));
    } catch {
      // Discovery is best-effort; progress simply stays at "Starting…".
    }
    const pollState = startProgressPolling(knownIds);
    const stopPolling = () => {
      pollState.active = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };

    const signatureAtSubmit = settingsSignature;
    try {
      const { kind, payload } = buildBuilderPayload({
        source,
        text,
        file,
        title,
        selectedStyle,
        generatorPreset,
        provider,
        model,
        strictMath,
        qwenThinking,
        attachments,
        length,
        includeSections,
        outputDepth,
        difficulty,
        folderId,
        outline: outlineEnabled ? { enabled: true, sections: outlineSections } : null
      });
      assertBuilderPayload(kind, payload, { text, title, length });
      const job = await createJob(kind, payload);
      stopPolling();
      if (job.status === "cancelled") {
        // The run was cancelled cooperatively. Do NOT present it as a finished
        // guide and do NOT clear the draft — the Builder inputs/selections stay
        // so the user can simply Generate again.
        setProgress({
          status: "cancelled",
          stage_label: "Generation cancelled",
          progress: 100
        });
        completeTimerRef.current = setTimeout(() => setProgress(null), 1800);
        return;
      }
      // Show a completed state briefly, then return the button to normal.
      setProgress({
        status: job.status || "done",
        stage: "complete",
        stage_label: "Complete",
        progress: 100
      });
      setResult(job);
      onJobCreated?.(job);
      clearDraft();
      baselineRef.current = signatureAtSubmit;
      setDirty(false);
      completeTimerRef.current = setTimeout(() => setProgress(null), 1400);
    } catch (requestError) {
      stopPolling();
      setProgress({ status: "failed", stage_label: "Generation failed", progress: 100 });
      setError(normalizeError(requestError));
    } finally {
      setLoading(false);
      setActiveJobId(null);
      setCancelling(false);
    }
  }

  // Request cooperative cancellation of the in-flight job. Targets the id the
  // poller discovered; the running job stops at its next safe checkpoint and
  // resolves with status "cancelled" (handled in runGeneration). Never blocks
  // and never clears the user's inputs.
  async function handleCancel() {
    if (!activeJobId || cancelling) return;
    setCancelling(true);
    setProgress((prev) => ({
      ...(prev || {}),
      stage_label: "Cancelling…"
    }));
    try {
      await cancelJob(activeJobId);
    } catch {
      // Best-effort: if the request fails the job simply continues; the poller
      // keeps reporting real status and the button stays available.
      setCancelling(false);
    }
  }

  // Capture the live Builder configuration as a backend builder_setup payload.
  // This is the inverse of applyBuilderPrefill below — keep the two symmetric.
  const buildShortcutSetup = useCallback(
    () =>
      builderStateToPayload({
        source,
        provider,
        model,
        generatorPreset,
        style: selectedStyle,
        length,
        includeSections,
        outputDepth,
        difficulty,
        strictMath
      }),
    [source, provider, model, generatorPreset, selectedStyle, length, includeSections, outputDepth, difficulty, strictMath]
  );

  // Apply a builder_setup payload from a Home shortcut into the live form. Reuses
  // the same state-setters the user drives by hand (no parallel prefill path).
  const applyBuilderPrefill = useCallback(
    (payload) => {
      if (!payload || typeof payload !== "object") return;
      const nextSource = INPUT_TO_SOURCE[payload.input_type];
      if (nextSource) setSource(nextSource);
      setModelNotice(null);
      if (payload.provider) {
        // Apply the provider now, but defer the model: it's derived from the
        // provider, so the options loader / provider default would otherwise
        // stomp an explicit saved model. The resolver effect applies the saved
        // model once this provider's real model list is loaded.
        setProvider(payload.provider);
        pendingPrefillRef.current = { provider: payload.provider, model: payload.model || null };
        setPendingModelNonce((nonce) => nonce + 1);
      } else if (payload.model) {
        setModel(payload.model);
      }
      if (payload.generator_preset !== undefined) setGeneratorPreset(payload.generator_preset || "");
      if (payload.style) onSelectStyle?.(payload.style);
      if (typeof payload.strict_math === "boolean") setStrictMath(payload.strict_math);
      if (payload.target_pages) setLength(pagesToLength(payload.target_pages));
      // Canonical output sections + axes. The backend bridges legacy `modules`
      // into `include_sections` on read, so we only read the canonical field and
      // ignore any `modules`. Applied deterministically (cleared when absent) so a
      // subsequent generate sends exactly what the shortcut saved.
      setIncludeSections(normalizeSectionState(payload.include_sections));
      setOutputDepth(typeof payload.output_depth === "string" ? payload.output_depth : "");
      setDifficulty(typeof payload.difficulty === "string" ? payload.difficulty : "");
      setActiveBuilderTab("builder");
      setError(null);
    },
    [onSelectStyle]
  );

  // Fire prefill whenever a new shortcut nonce arrives from Home.
  useEffect(() => {
    if (prefill?.payload) applyBuilderPrefill(prefill.payload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill?.nonce]);

  // Resolve a shortcut's saved model once its provider's real model list has
  // loaded. Running after the provider's default selection has settled means the
  // explicit saved model wins over the auto-default (the prefill bug was the
  // reverse). If the saved model is no longer valid for the provider, fall back
  // to its default and surface that rather than silently loading another model.
  useEffect(() => {
    const pending = pendingPrefillRef.current;
    if (!pending || !providersLoaded) return;
    if (provider !== pending.provider) return; // wait for the provider state to settle
    const detail = providerDetails.find((item) => item.id === pending.provider);
    if (!detail) return;
    if (pending.model) {
      const models = detail.available_models || [];
      if (models.includes(pending.model)) {
        setModel(pending.model);
      } else {
        const fallback = detail.default_model || models[0] || "";
        setModel(fallback);
        setModelNotice(
          `"${pending.model}" isn't available for ${detail.display_name || pending.provider} — using ${
            fallback || "the provider default"
          } instead.`
        );
      }
    } else {
      setModel(selectDefaultModel(detail));
    }
    pendingPrefillRef.current = null;
  }, [providersLoaded, providerDetails, provider, pendingModelNonce]);

  // Report the current setup upward so the Home customize modal can "Capture
  // from current Builder". Cheap: just a payload snapshot, no side effects.
  useEffect(() => {
    onReportSetup?.(buildShortcutSetup());
  }, [onReportSetup, buildShortcutSetup]);

  async function handleSaveShortcut() {
    if (shortcutSaving) return;
    const defaultName =
      title && title !== DEFAULT_TITLE
        ? title
        : `${selectedStyleOption?.name || selectedStyleOption?.label || "Study"} setup`;
    const name = window.prompt("Name this shortcut", defaultName);
    if (name === null) return; // cancelled
    const trimmed = name.trim();
    if (!trimmed) return;
    setShortcutSaving(true);
    setShortcutSaveError(null);
    try {
      await createShortcut({
        name: trimmed,
        type: "builder_setup",
        description: `${selectedProvider?.display_name || provider} · ${
          selectedStyleOption?.name || selectedStyle
        }`,
        pinned: true,
        icon: "⭐",
        payload: buildShortcutSetup()
      });
      setShortcutSaved(true);
      if (shortcutTimerRef.current) clearTimeout(shortcutTimerRef.current);
      shortcutTimerRef.current = setTimeout(() => setShortcutSaved(false), 1600);
    } catch (saveError) {
      setShortcutSaveError(saveError?.message || "Could not save shortcut.");
      if (shortcutTimerRef.current) clearTimeout(shortcutTimerRef.current);
      shortcutTimerRef.current = setTimeout(() => setShortcutSaveError(null), 3200);
    } finally {
      setShortcutSaving(false);
    }
  }

  function handleKeepCurrentOutput() {
    // Accept the changed settings as the new baseline so the notice dismisses
    // and only future changes re-flag the preview as stale.
    baselineRef.current = settingsSignature;
    setDirty(false);
  }

  function validateInputs() {
    if (source === "paste" && !text.trim()) {
      return "No text provided.";
    }
    if (source === "upload") {
      if (!file) {
        return "No file selected.";
      }
      if (!isMarkdownFile(file)) {
        return "Upload a .md or .markdown file.";
      }
    }
    if (source === "llm") {
      if (!title.trim()) {
        return "No title provided.";
      }
      if (!text.trim()) {
        return "No source text provided.";
      }
      if (!selectedProvider?.configured) {
        return `${selectedProvider?.display_name || "Selected provider"} is not configured on the server.`;
      }
      if (!model) {
        return "No model selected.";
      }
    }
    return "";
  }

  function createJob(kind, payload) {
    if (kind === "upload") {
      return createUploadMarkdownJob(payload);
    }
    if (kind === "llm") {
      return createLlmJob(payload);
    }
    return createPasteJob(payload);
  }

  function handleProviderSelect(nextProvider) {
    // A manual provider change discards any pending shortcut prefill and the
    // saved-model fallback notice, then auto-picks the provider's default model.
    pendingPrefillRef.current = null;
    setModelNotice(null);
    setProvider(nextProvider);
    const detail = providerDetails.find((item) => item.id === nextProvider);
    setModel(selectDefaultModel(detail));
  }

  function toggleSection(key) {
    setIncludeSections((current) => {
      const next = { ...current };
      if (next[key]) {
        delete next[key];
      } else {
        next[key] = true;
      }
      return next;
    });
  }

  async function openJobDetails(tab = "details") {
    const jobId = result?.job_id || result?.id;
    if (!jobId) {
      return;
    }
    setDetailsInitialTab(typeof tab === "string" ? tab : "details");
    setDetailsOpen(true);
    setDetailsLoading(true);
    setDetailsError(null);
    try {
      setJobDetails(await getJob(jobId));
    } catch (requestError) {
      setDetailsError(requestError);
      setJobDetails(null);
    } finally {
      setDetailsLoading(false);
    }
  }

  return (
    <div className="sg-builder">
      <div className="sg-builder-tabs">
        {builderTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveBuilderTab(tab.id)}
            className={activeBuilderTab === tab.id ? "active" : ""}
          >
            <BuilderTabIcon id={tab.id} active={activeBuilderTab === tab.id} />
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <span className="sg-autosave">
          <i />
          {draftSavedAt ? `Draft saved · ${formatDraftTime(draftSavedAt)}` : "Unsaved draft"}
        </span>
      </div>

      {restoreDraft && (
        <DraftRestoreBanner
          draft={restoreDraft}
          onRestore={handleRestoreDraft}
          onDiscard={clearDraft}
        />
      )}

      <div className="sg-builder-body">
        <form
          onSubmit={handleSubmit}
          className="sg-builder-pane"
        >
          <BuilderActionBar
            source={source}
            selectedProvider={selectedProvider}
            provider={provider}
            model={model}
            generatorPresets={generatorPresets}
            generatorPreset={generatorPreset}
            selectedStyleOption={selectedStyleOption}
            includeSections={includeSections}
            outputDepth={outputDepth}
            difficulty={difficulty}
            selectedLengthOption={selectedLengthOption}
            outlineEnabled={outlineEnabled}
            outlineCount={outlineSections.filter((section) => section.title.trim()).length}
            artifacts={artifactEntries}
            hasResult={Boolean(result)}
            loading={loading}
            progress={progress}
            onCancel={handleCancel}
            canCancel={Boolean(activeJobId)}
            cancelling={cancelling}
            onSaveShortcut={handleSaveShortcut}
            shortcutSaved={shortcutSaved}
            shortcutSaving={shortcutSaving}
            shortcutSaveError={shortcutSaveError}
          />

          {dirty && (
            <DirtyNotice
              busy={loading}
              onRegenerateFull={runGeneration}
              onRegenerateSections={() => openJobDetails("sections")}
              onKeep={handleKeepCurrentOutput}
            />
          )}

          {activeBuilderTab === "builder" && (
            <BuilderComposer
              title={title}
              setTitle={setTitle}
              source={source}
              setSource={setSource}
              text={text}
              setText={setText}
              file={file}
              setFile={setFile}
              setError={setError}
              provider={provider}
              providerDetails={providerDetails}
              selectedProvider={selectedProvider}
              selectedProviderModels={selectedProviderModels}
              handleProviderSelect={handleProviderSelect}
              model={model}
              setModel={setModel}
              modelNotice={modelNotice}
              qwenThinking={qwenThinking}
              setQwenThinking={setQwenThinking}
              strictMath={strictMath}
              setStrictMath={setStrictMath}
              attachments={attachments}
              setAttachments={setAttachments}
              folders={folders}
              folderId={folderId}
              setFolderId={setFolderId}
              onCreateFolder={handleCreateFolder}
              outlineEnabled={outlineEnabled}
              outlineCount={outlineSections.filter((section) => section.title.trim()).length}
              presets={presets}
              selectedPreset={selectedPreset}
              onApplyPreset={handleApplyPreset}
              presetBusy={presetBusy}
              onSaveDraft={handleSaveDraft}
              draftSavedAt={draftSavedAt}
              error={error}
              loading={loading}
            />
          )}

          {activeBuilderTab === "outline" && (
            <OutlineEditor
              enabled={outlineEnabled}
              setEnabled={setOutlineEnabled}
              sections={outlineSections}
              setSections={setOutlineSections}
              source={source}
              text={text}
              title={title}
              provider={provider}
              model={model}
            />
          )}

          {activeBuilderTab === "style" && (
            <StyleSettings
              selectedStyle={selectedStyle}
              onSelectStyle={onSelectStyle}
              styleOptions={styleOptions}
              generatorPresets={generatorPresets}
              generatorPreset={generatorPreset}
              onSelectGeneratorPreset={setGeneratorPreset}
              model={model}
              length={length}
              setLength={setLength}
              includeSections={includeSections}
              toggleSection={toggleSection}
              outputDepth={outputDepth}
              setOutputDepth={setOutputDepth}
              difficulty={difficulty}
              setDifficulty={setDifficulty}
            />
          )}

          {activeBuilderTab === "preview" && (
            <PreviewWorkspacePanel
              result={result}
              artifacts={artifactEntries}
              artifactUrls={artifactUrls}
              previewFormat={previewFormat}
              setPreviewFormat={setPreviewFormat}
            />
          )}
        </form>

        <LivePreviewPanel
          result={result}
          artifacts={artifactEntries}
          selectedStyle={selectedStyle}
          styleOptions={styleOptions}
          length={length}
          previewFormat={previewFormat}
          setPreviewFormat={setPreviewFormat}
          onOpenDetails={openJobDetails}
        />
      </div>
      <JobDetailsDrawer
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        loading={detailsLoading}
        error={detailsError}
        details={jobDetails}
        styleLookup={builderStyleLookup}
        onRetry={openJobDetails}
        initialTab={detailsInitialTab}
      />
    </div>
  );
}

// Persistent across every Builder section: read-only chips summarizing the
// current setup, the live-progress Generate button, the (stubbed) shortcut
// capture, and export links once the job has artifacts.
function BuilderActionBar({
  source,
  selectedProvider,
  provider,
  model,
  generatorPresets = [],
  generatorPreset,
  selectedStyleOption,
  includeSections = {},
  outputDepth = "",
  difficulty = "",
  selectedLengthOption,
  outlineEnabled,
  outlineCount,
  artifacts = [],
  hasResult,
  loading,
  progress,
  onCancel,
  canCancel = false,
  cancelling = false,
  onSaveShortcut,
  shortcutSaved,
  shortcutSaving,
  shortcutSaveError
}) {
  const sourceLabel = sourceTabs.find((tab) => tab.id === source)?.label || source;
  const providerModel =
    source === "llm"
      ? `${selectedProvider?.display_name || provider} · ${model || "No model"}`
      : "Markdown pipeline";
  const presetName = generatorPreset
    ? generatorPresets.find((preset) => preset.id === generatorPreset)?.name || generatorPreset
    : null;
  const styleName = selectedStyleOption?.name || selectedStyleOption?.label || "—";
  const lengthText = selectedLengthOption
    ? `${selectedLengthOption.label} · ${selectedLengthOption.meta}`
    : "—";
  const sectionKeys = Object.keys(includeSections).filter((key) => includeSections[key]);
  const sectionsText = sectionKeys.length
    ? `${sectionKeys.length} section${sectionKeys.length === 1 ? "" : "s"}`
    : "None";
  const depthLabel = OUTPUT_DEPTH_OPTIONS.find((option) => option.value === outputDepth)?.label;
  const difficultyLabel = DIFFICULTY_OPTIONS.find((option) => option.value === difficulty)?.label;
  const axisText = [outputDepth ? depthLabel : null, difficulty ? difficultyLabel : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="sg-action-bar">
      <div className="sg-action-chips">
        <ActionChip dot kx="Source" v={sourceLabel} />
        <ActionChip dot kx="Model" v={providerModel} title={providerModel} />
        {presetName ? (
          <ActionChip icon={Wand2} kx="Preset" v={presetName} />
        ) : (
          <ActionChip icon={Sparkles} kx="Style" v={styleName} />
        )}
        {outlineEnabled && outlineCount > 0 && (
          <ActionChip icon={ListChecks} kx="Outline" v={`${outlineCount}`} />
        )}
        <ActionChip icon={ListChecks} kx="Sections" v={sectionsText} title={sectionKeys.join(", ")} />
        {axisText && <ActionChip icon={Sparkles} kx="Axes" v={axisText} title={axisText} />}
        <ActionChip icon={FileText} kx="Length" v={lengthText} />
      </div>

      {artifacts.length > 0 && (
        <div className="sg-action-exports">
          {artifacts.map(([name, url]) => {
            const meta = artifactLabels[name];
            const Icon = meta.icon;
            return (
              <a key={name} href={apiUrl(url)} className="sg-export-btn" title={`Download ${meta.label}`}>
                <Icon className="h-3.5 w-3.5 text-[#F97316]" />
                {meta.label}
              </a>
            );
          })}
        </div>
      )}

      <button
        type="button"
        onClick={onSaveShortcut}
        disabled={shortcutSaving}
        title={
          shortcutSaveError ||
          "Save the current builder setup as a pinned shortcut on Home"
        }
        className="sg-ghost-button inline-flex items-center gap-1.5 disabled:opacity-60"
      >
        {shortcutSaving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : shortcutSaveError ? (
          <AlertCircle className="h-4 w-4 text-red-300" />
        ) : shortcutSaved ? (
          <Check className="h-4 w-4 text-emerald-300" />
        ) : (
          <Bookmark className="h-4 w-4" />
        )}
        {shortcutSaving
          ? "Saving…"
          : shortcutSaveError
            ? "Save failed"
            : shortcutSaved
              ? "Saved to Home"
              : "Save as shortcut"}
      </button>

      {loading && (
        <button
          type="button"
          onClick={onCancel}
          disabled={!canCancel || cancelling}
          title={
            canCancel
              ? "Stop this generation at the next safe step (your inputs are kept)"
              : "Preparing… cancel becomes available once the job starts"
          }
          className="sg-ghost-button inline-flex items-center gap-1.5 disabled:opacity-60"
        >
          <X className="h-4 w-4" />
          {cancelling ? "Cancelling…" : "Cancel"}
        </button>
      )}

      <GenerateProgressButton loading={loading} progress={progress} hasResult={hasResult} />
    </div>
  );
}

function ActionChip({ icon: Icon, kx, v, title, dot = false }) {
  return (
    <span className="sg-chip" title={title || `${kx}: ${v}`}>
      {dot ? <i className="dot" /> : Icon ? <Icon className="h-3 w-3 text-[#F97316]" /> : null}
      <span className="sg-chip-key">{kx}</span>
      <span className="sg-chip-val">{v}</span>
    </span>
  );
}

// The Generate button doubles as a live progress bar. It fills left-to-right by
// the backend `progress` percent (CSS-animated so big jumps glide), and its text
// is the verbatim `stage_label` from /api/jobs/{id}/progress — never invented.
function GenerateProgressButton({ loading, progress, hasResult }) {
  const failed = progress?.status === "failed";
  const complete = !loading && !failed && progress?.progress === 100;
  const running = loading;
  const pct = failed
    ? 100
    : running
      ? Math.max(progress?.progress ?? 5, 5)
      : complete
        ? 100
        : 0;
  const label = failed
    ? "Generation failed"
    : complete
      ? "Complete"
      : running
        ? progress?.stage_label || "Starting…"
        : hasResult
          ? "Regenerate Guide"
          : "Generate Guide";
  const icon = failed ? (
    <AlertCircle className="h-4 w-4" />
  ) : complete ? (
    <Check className="h-4 w-4" />
  ) : running ? (
    <Loader2 className="h-4 w-4 animate-spin" />
  ) : hasResult ? (
    <RefreshCw className="h-[17px] w-[17px]" />
  ) : (
    <Sparkles className="h-[18px] w-[18px]" />
  );

  return (
    <button
      type="submit"
      disabled={running}
      aria-live="polite"
      className={`sg-progress-btn${running ? " running" : ""}${failed ? " failed" : ""}${
        complete ? " complete" : ""
      }`}
    >
      <span className="sg-progress-fill" style={{ width: `${pct}%` }} />
      <span className="sg-progress-label">
        {icon}
        <span className="truncate">{label}</span>
        {running && progress?.progress != null && (
          <span className="sg-progress-pct">{Math.round(progress.progress)}%</span>
        )}
      </span>
    </button>
  );
}

// Non-blocking notice shown after a guide exists and a setting has since changed.
function DirtyNotice({ onRegenerateFull, onRegenerateSections, onKeep, busy }) {
  return (
    <div className="sg-dirty-notice">
      <AlertTriangle className="h-4 w-4 shrink-0 text-[#F8B57E]" />
      <span className="min-w-0 flex-1 text-[12.5px] font-medium text-[#F4F4F5]">
        The preview is outdated because settings changed.
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onRegenerateFull}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[rgba(249,115,22,0.5)] bg-[rgba(249,115,22,0.16)] px-3 text-[12px] font-semibold text-[#F97316] transition hover:bg-[rgba(249,115,22,0.24)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Regenerate full guide
        </button>
        <button
          type="button"
          onClick={onRegenerateSections}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/[0.12] bg-white/[0.04] px-3 text-[12px] font-semibold text-[#D4D4D8] transition hover:text-white"
        >
          <ListChecks className="h-3.5 w-3.5" />
          Regenerate changed sections only
        </button>
        <button
          type="button"
          onClick={onKeep}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 text-[12px] font-semibold text-[#9098A8] transition hover:text-[#F4F4F5]"
        >
          <X className="h-3.5 w-3.5" />
          Keep current output
        </button>
      </div>
    </div>
  );
}

function BuilderComposer({
  title,
  setTitle,
  source,
  setSource,
  text,
  setText,
  file,
  setFile,
  setError,
  provider,
  providerDetails,
  selectedProvider,
  selectedProviderModels,
  handleProviderSelect,
  model,
  setModel,
  modelNotice,
  qwenThinking,
  setQwenThinking,
  strictMath,
  setStrictMath,
  attachments,
  setAttachments,
  folders,
  folderId,
  setFolderId,
  onCreateFolder,
  outlineEnabled,
  outlineCount,
  presets = [],
  selectedPreset = "",
  onApplyPreset,
  presetBusy = false,
  onSaveDraft,
  error,
  loading
}) {
  return (
    <>
      <div className="sg-field-block">
        <FieldLabel>Title</FieldLabel>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Enter guide title..."
          className="sg-input sg-input-lg"
        />
      </div>

      <TemplatePicker
        presets={presets}
        selectedPreset={selectedPreset}
        onApplyPreset={onApplyPreset}
        busy={presetBusy}
      />

      <div className="sg-field-block">
        <FieldLabel>Source</FieldLabel>
        <SourceTabs source={source} setSource={setSource} setError={setError} />

        <SourceEditor
          source={source}
          text={text}
          setText={setText}
          file={file}
          setFile={setFile}
          setError={setError}
        />
      </div>

      {source === "llm" && (
        <div className="sg-llm-panel">
          <div>
            <FieldLabel tip={TOOLTIPS.provider}>Provider</FieldLabel>
            <div className="sg-option-grid">
              {providerDetails.map((detail) => (
                <OptionCard
                  key={detail.id}
                  option={providerOptionFromDetail(detail)}
                  active={provider === detail.id}
                  disabled={!detail.configured}
                  onClick={() => handleProviderSelect(detail.id)}
                />
              ))}
            </div>
          </div>
          <label>
            <FieldLabel tip={TOOLTIPS.model}>Model</FieldLabel>
            <select
              value={model}
              disabled={!selectedProvider?.configured || selectedProviderModels.length === 0}
              onChange={(event) => setModel(event.target.value)}
              className="sg-select"
            >
              {selectedProviderModels.map((modelId) => (
                <option key={modelId} value={modelId}>
                  {modelId}
                </option>
              ))}
            </select>
          </label>
          {modelNotice && (
            <p className="text-[12px] leading-5 text-[#FCD34D]">{modelNotice}</p>
          )}
          {selectedProvider?.discovery_error && (
            <p className="text-[12px] leading-5 text-[#FCA5A5]">
              Local discovery: {selectedProvider.discovery_error}
            </p>
          )}
          {selectedProvider?.supports_thinking && (
            <Toggle label="Qwen thinking mode" checked={qwenThinking} onChange={setQwenThinking} />
          )}
          <AttachmentsPicker attachments={attachments} setAttachments={setAttachments} />
          <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} tip={TOOLTIPS.strictMath} />
        </div>
      )}

      {source !== "llm" && (
        <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} tip={TOOLTIPS.strictMath} />
      )}
      {error && <ErrorMessage error={error} />}

      <div className="sg-generate-bar">
        <div className="sg-model-chip">
          <i />
          <span>{source === "llm" ? `${selectedProvider?.display_name || provider} · ${model || "No model"}` : "Markdown pipeline"}</span>
          <ChevronRight className="h-3.5 w-3.5 text-[#9098A8]" />
        </div>
        {source === "llm" && outlineEnabled && outlineCount > 0 && (
          <span
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-[rgba(168,85,247,0.4)] bg-[rgba(168,85,247,0.12)] px-3 text-[12px] font-semibold text-[#D8B4FE]"
            title="This guide will follow your outline"
          >
            <ListChecks className="h-3.5 w-3.5" />
            Outline · {outlineCount}
          </span>
        )}
        <div className="flex-1" />
        <FolderPicker
          folders={folders}
          folderId={folderId}
          setFolderId={setFolderId}
          onCreateFolder={onCreateFolder}
        />
        <button
          type="button"
          onClick={onSaveDraft}
          className="sg-ghost-button"
        >
          <Save className="h-4 w-4" />
          Save draft
        </button>
      </div>
    </>
  );
}

function FolderPicker({ folders = [], folderId, setFolderId, onCreateFolder }) {
  const [creating, setCreating] = useState(false);

  return (
    <div className="relative inline-flex items-center gap-1">
      <label
        className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] pl-3 pr-2 text-[12.5px] font-medium text-[#D4D4D8]"
        title="Choose a Library folder for this guide"
      >
        <Folder className="h-3.5 w-3.5 text-[#F97316]" />
        <span className="text-[#9098A8]">Save to</span>
        <select
          value={folderId}
          onChange={(event) => setFolderId(event.target.value)}
          className="h-7 max-w-[150px] truncate rounded-md border-0 bg-transparent pr-1 text-[12.5px] font-semibold text-[#F4F4F5] outline-none"
        >
          <option value="unfiled" className="bg-[#0B1220]">Unfiled</option>
          {folders.map((folder) => (
            <option key={folder.id} value={folder.id} className="bg-[#0B1220]">
              {folder.name}
            </option>
          ))}
        </select>
      </label>
      {onCreateFolder && (
        <button
          type="button"
          onClick={() => setCreating((open) => !open)}
          title="Create folder"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[#9098A8] transition hover:border-[rgba(249,115,22,0.45)] hover:text-[#F97316]"
        >
          <FolderPlus className="h-4 w-4" />
        </button>
      )}
      {creating && (
        <CreateFolderPopover
          onClose={() => setCreating(false)}
          onCreateFolder={onCreateFolder}
        />
      )}
    </div>
  );
}

function CreateFolderPopover({ onClose, onCreateFolder }) {
  const [name, setName] = useState("");
  const [color, setColor] = useState(FOLDER_PRESET_COLORS[0]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onCreateFolder({ name: trimmed, color });
      onClose();
    } catch (err) {
      setError(err?.message || "Could not create folder.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className="fixed inset-0 z-40 cursor-default" aria-label="Close" onClick={onClose} />
      <div className="absolute bottom-11 right-0 z-50 w-64 rounded-xl border border-white/10 bg-[#0B1220] p-3 shadow-2xl">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#9098A8]">New folder</span>
          <button type="button" onClick={onClose} className="text-[#9098A8] hover:text-white">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <input
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
            if (event.key === "Escape") onClose();
          }}
          placeholder="Folder name…"
          className="h-8 w-full rounded-md border border-white/[0.1] bg-[#070B14] px-2 text-[13px] text-[#F4F4F5] outline-none focus:border-[rgba(249,115,22,0.45)]"
        />
        <div className="mt-2 flex items-center gap-1.5">
          {FOLDER_PRESET_COLORS.map((swatch) => {
            const active = swatch.toLowerCase() === color.toLowerCase();
            return (
              <button
                key={swatch}
                type="button"
                onClick={() => setColor(swatch)}
                aria-label={`Color ${swatch}`}
                className={`h-4 w-4 rounded-full border transition ${
                  active ? "ring-2 ring-white/70 ring-offset-1 ring-offset-[#0B1220]" : "border-white/20"
                }`}
                style={{ backgroundColor: swatch }}
              />
            );
          })}
        </div>
        {error && <p className="mt-2 text-[11px] text-red-300">{error}</p>}
        <button
          type="button"
          onClick={submit}
          disabled={!name.trim() || busy}
          className="mt-2.5 inline-flex h-8 w-full items-center justify-center gap-1.5 rounded-md border border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.14)] text-[12.5px] font-semibold text-[#F97316] transition disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          Create &amp; select
        </button>
      </div>
    </>
  );
}

function TemplatePicker({ presets = [], selectedPreset = "", onApplyPreset, busy = false }) {
  const active = presets.find((preset) => preset.id === selectedPreset);
  return (
    <div className="sg-field-block">
      <FieldLabel>Template</FieldLabel>
      <div className="flex items-center gap-2">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[#F97316]">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LayoutTemplate className="h-4 w-4" />}
        </span>
        <select
          value={selectedPreset || "custom"}
          disabled={busy}
          onChange={(event) => onApplyPreset?.(event.target.value)}
          className="h-9 min-w-0 flex-1 rounded-lg border border-white/[0.08] bg-[#070B14] px-3 text-[13px] font-medium text-[#F4F4F5] outline-none disabled:opacity-60"
        >
          <option value="custom" className="bg-[#0B1220]">Custom (no template)</option>
          {presets.map((preset) => (
            <option key={preset.id} value={preset.id} className="bg-[#0B1220]">
              {preset.name}
            </option>
          ))}
        </select>
      </div>
      <p className="mt-1.5 text-[11.5px] leading-4 text-[#9098A8]">
        {active
          ? `${active.description} You can still edit the outline and style before generating.`
          : "Pick a template to pre-fill the outline and style. Custom leaves them as-is."}
      </p>
    </div>
  );
}

function DraftRestoreBanner({ draft, onRestore, onDiscard }) {
  return (
    <div className="mx-1 mb-1 flex flex-wrap items-center gap-3 rounded-xl border border-[rgba(249,115,22,0.35)] bg-[rgba(249,115,22,0.10)] px-4 py-2.5">
      <Clock className="h-4 w-4 shrink-0 text-[#F97316]" />
      <span className="min-w-0 flex-1 text-[12.5px] font-medium text-[#F4F4F5]">
        Restore unsaved draft from {formatDraftTime(draft.savedAt)}?
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRestore}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[rgba(249,115,22,0.5)] bg-[rgba(249,115,22,0.16)] px-3 text-[12px] font-semibold text-[#F97316] transition hover:bg-[rgba(249,115,22,0.24)]"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Restore
        </button>
        <button
          type="button"
          onClick={onDiscard}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 text-[12px] font-semibold text-[#9098A8] transition hover:text-[#F4F4F5]"
        >
          <X className="h-3.5 w-3.5" />
          Discard
        </button>
      </div>
    </div>
  );
}

function BuilderTabIcon({ id, active }) {
  const color = active ? "#F97316" : "#6B7185";
  if (id === "outline") return <ListGlyph size={14} color={color} />;
  if (id === "style") return <SparkleGlyph size={14} color={color} />;
  if (id === "preview") return <PDFGlyph size={14} color={color} />;
  return <DocGlyph size={14} color={color} />;
}

function SourceTabs({ source, setSource, setError }) {
  const activeIndex = Math.max(0, sourceTabs.findIndex((tab) => tab.id === source));
  const tabsRef = React.useRef(null);
  const [slider, setSlider] = useState({ x: 4, w: 0 });

  useEffect(() => {
    const root = tabsRef.current;
    if (!root) return;
    const button = root.querySelectorAll("button.sg-tab")[activeIndex];
    if (!button) return;
    setSlider({ x: button.offsetLeft, w: button.offsetWidth });
  }, [activeIndex]);

  return (
    <div ref={tabsRef} className="sg-tabs mt-1.5">
      <span className="sg-tab-slider" style={{ transform: `translateX(${slider.x}px)`, width: slider.w }} />
      {sourceTabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          disabled={tab.disabled}
          onClick={() => {
            setSource(tab.id);
            setError(null);
          }}
          className={`sg-tab ${source === tab.id ? "active" : ""}`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function StyleSettings({
  selectedStyle,
  onSelectStyle,
  styleOptions,
  generatorPresets = [],
  generatorPreset = "",
  onSelectGeneratorPreset,
  model,
  length,
  setLength,
  includeSections,
  toggleSection,
  outputDepth,
  setOutputDepth,
  difficulty,
  setDifficulty
}) {
  const presetActive = Boolean(generatorPreset);
  return (
    <div className="grid gap-5">
      <SectionHeader
        eyebrow="Guide design"
        title="Style and depth"
        description="Tune the preset, target length, generation depth/difficulty, and output sections."
      />
      <GeneratorPresetControls
        generatorPresets={generatorPresets}
        generatorPreset={generatorPreset}
        onSelectGeneratorPreset={onSelectGeneratorPreset}
        model={model}
      />
      {/* A generator preset replaces the system prompt + sampling params, so the
          style below is ignored while one is active. */}
      <div className={presetActive ? "pointer-events-none opacity-45" : ""}>
        <StyleControls selectedStyle={selectedStyle} onSelectStyle={onSelectStyle} styleOptions={styleOptions} />
      </div>
      <LengthControls length={length} setLength={setLength} />
      <AxisControls
        outputDepth={outputDepth}
        setOutputDepth={setOutputDepth}
        difficulty={difficulty}
        setDifficulty={setDifficulty}
      />
      <SectionControls includeSections={includeSections} toggleSection={toggleSection} />
    </div>
  );
}

function PreviewWorkspacePanel({ result, artifacts, artifactUrls, previewFormat, setPreviewFormat }) {
  return (
    <div className="grid gap-4">
      <SectionHeader
        eyebrow="Preview"
        title="Exports and artifacts"
        description="Inspect the latest generated job and choose what to preview or download."
      />
      <div className="grid gap-3 xl:grid-cols-3">
        <InfoCard label="Preview" value={previewFormat === "sample" ? "Sample" : previewFormat.toUpperCase()} />
        <InfoCard label="Status" value={result?.status || "No generated job"} />
        <InfoCard label="Artifacts" value={`${artifacts.length} available`} />
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <FieldLabel>Preview format</FieldLabel>
        <div className="mt-2 flex gap-1.5">
          {["pdf", "html"].map((format) => (
            <button
              key={format}
              type="button"
              disabled={!result}
              onClick={() => setPreviewFormat(format)}
              className={`h-8 rounded-md border px-3 text-[12px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${
                previewFormat === format
                  ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.14)] text-[#F97316]"
                  : "border-white/[0.08] bg-white/[0.03] text-[#9098A8] hover:text-[#D4D4D8]"
              }`}
            >
              {format.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
        <FieldLabel>Artifact availability</FieldLabel>
        {result ? (
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {Object.entries(artifactLabels).map(([name, artifact]) => {
              const available = Boolean(artifactUrls[name]);
              const Icon = artifact.icon;
              return (
                <div
                  key={name}
                  className={`flex items-center justify-between rounded-[10px] border px-3 py-2 ${
                    available
                      ? "border-[rgba(249,115,22,0.25)] bg-[rgba(249,115,22,0.08)]"
                      : "border-white/[0.06] bg-[#070B14] opacity-70"
                  }`}
                >
                  <span className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#D4D4D8]">
                    <Icon className="h-3.5 w-3.5 text-[#F97316]" />
                    {artifact.label}
                  </span>
                  <span className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-[#9098A8]">
                    {available ? "Ready" : "Missing"}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-2 rounded-[10px] border border-white/[0.06] bg-[#070B14] p-4 text-[12.5px] leading-5 text-[#9098A8]">
            Generate a guide first to enable PDF/HTML preview and artifact downloads.
          </div>
        )}
      </div>
      {result && (
        <AttachedSourcesSummary result={result} />
      )}
      {result && (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
          <FieldLabel>Downloads</FieldLabel>
          <ArtifactDownloadGrid artifacts={artifacts} />
        </div>
      )}
    </div>
  );
}

// Provider logo chip. Uses a local SVG when one ships for the provider, otherwise
// a styled text badge. Logos render on a light chip so near-black marks (Qwen /
// Local) stay visible against the dark UI. A missing/broken icon never blocks the
// card — `onError` hides the img and the chip background stays. `size="lg"` is the
// prominent card identity icon; the default stays compact for any inline use.
function ProviderBadge({ provider, size = "sm" }) {
  const icon = providerIconFor(provider);
  const label = providerLabelFor(provider);
  const lg = size === "lg";
  if (icon) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center overflow-hidden bg-white ring-1 ring-white/20 ${
          lg ? "h-12 w-12 rounded-xl p-2" : "h-6 w-6 rounded-md p-[3px]"
        }`}
        title={label}
      >
        <img
          src={icon}
          alt={`${label} logo`}
          loading="lazy"
          className="h-full w-full object-contain"
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
        />
      </span>
    );
  }
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center bg-white/[0.08] font-bold uppercase tracking-[0.06em] text-[#D4D4D8] ring-1 ring-white/10 ${
        lg ? "h-12 min-w-12 rounded-xl px-2.5 text-[11px]" : "h-6 rounded-md px-2 text-[10px]"
      }`}
    >
      {label}
    </span>
  );
}

const fmtPresetParams = (params = {}) => {
  const parts = [`temp ${params.temperature}`];
  if (params.top_p != null) parts.push(`top_p ${params.top_p}`);
  if (params.max_tokens != null) parts.push(`max ${params.max_tokens}`);
  if (params.thinking) parts.push("thinking on");
  return parts.join(" · ");
};

// One generator-preset card (C4d: compact, scan-first). A large provider icon +
// bold model name form the identity ("Gemma 4 → Claude-Exam"); the preset name
// sits directly under it and `purpose` is the single one-line subtitle. The dense
// description / "Best for" blocks were removed. Still pure display of backend
// metadata; selecting it sets the same `generatorPreset` id as before.
function GeneratorPresetCard({ preset, selected, onSelect }) {
  const available = preset.available !== false;
  const modelLabel = presetModelLabel(preset);
  return (
    <button
      type="button"
      disabled={!available}
      aria-pressed={selected}
      onClick={() => onSelect?.(preset.id)}
      title={available ? undefined : "This preset's prompt could not be loaded."}
      className={`flex flex-col gap-2.5 rounded-xl border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-40 ${
        selected
          ? "border-[rgba(249,115,22,0.5)] bg-[rgba(249,115,22,0.08)] ring-1 ring-[rgba(249,115,22,0.35)]"
          : "border-white/[0.08] bg-[#070B14] hover:border-white/20"
      }`}
    >
      <div className="flex items-center gap-3">
        <ProviderBadge provider={preset.provider} size="lg" />
        <div className="min-w-0 flex-1">
          {modelLabel && (
            <div className="truncate text-[13.5px] font-bold leading-tight text-[#F4F4F5]" title={modelLabel}>
              {modelLabel}
            </div>
          )}
          <div className="mt-0.5 truncate text-[12px] font-semibold leading-tight text-[#F8B57E]">
            {preset.name}
          </div>
        </div>
        {!available && (
          <span className="shrink-0 rounded-md bg-white/[0.06] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-[#9098A8]">
            Unavailable
          </span>
        )}
        {selected && <Check className="h-4 w-4 shrink-0 text-[#F97316]" />}
      </div>
      {preset.purpose && (
        <p className="text-[11.5px] leading-4 text-[#9098A8]">{preset.purpose}</p>
      )}
    </button>
  );
}

function GeneratorPresetControls({ generatorPresets = [], generatorPreset = "", onSelectGeneratorPreset, model }) {
  if (!generatorPresets.length) return null;

  const active = generatorPresets.find((preset) => preset.id === generatorPreset) || null;
  // Advisory only: warn when the selected model doesn't match the preset's soft
  // `model_hint`. Never blocks generation or auto-switches the model.
  const compat = active ? presetCompat(active, model) : { warn: false };

  return (
    <div>
      <FieldLabel tip={TOOLTIPS.generatorPreset}>Generator preset</FieldLabel>
      <p className="mt-1 text-[11.5px] leading-4 text-[#9098A8]">
        A full model-tuned system prompt with its own sampling params. Overrides the style below.
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <button
          type="button"
          aria-pressed={!generatorPreset}
          onClick={() => onSelectGeneratorPreset?.("")}
          className={`flex flex-col justify-center gap-1 rounded-xl border p-3 text-left transition ${
            !generatorPreset
              ? "border-[rgba(249,115,22,0.5)] bg-[rgba(249,115,22,0.08)] ring-1 ring-[rgba(249,115,22,0.35)]"
              : "border-white/[0.08] bg-[#070B14] hover:border-white/20"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-[#F4F4F5]">None</span>
            {!generatorPreset && <Check className="h-4 w-4 text-[#F97316]" />}
          </div>
          <p className="text-[11.5px] leading-4 text-[#9098A8]">
            Use the style below instead of a tuned generator preset.
          </p>
        </button>
        {generatorPresets.map((preset) => (
          <GeneratorPresetCard
            key={preset.id}
            preset={preset}
            selected={generatorPreset === preset.id}
            onSelect={onSelectGeneratorPreset}
          />
        ))}
      </div>
      {active && (
        <div className="mt-2 rounded-[10px] border border-white/[0.06] bg-[#070B14] p-3 text-[12px] leading-5 text-[#9098A8]">
          <div className="text-[11.5px]">
            Tuned for <span className="text-[#D4D4D8]">{active.model_hint}</span> · {fmtPresetParams(active.params)}
          </div>
          {compat.warn && (
            <div className="mt-2 flex items-start gap-1.5 rounded-[8px] border border-[rgba(249,115,22,0.35)] bg-[rgba(249,115,22,0.08)] px-2.5 py-1.5 text-[11.5px] text-[#F8B57E]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                This preset is tuned for {compat.hint}. It may still work with{" "}
                <span className="font-semibold">{model || "your selected model"}</span>, but {compat.hint} is
                recommended. <span className="text-[#C9A27A]">Your model selection still applies.</span>
                <InfoTip text={TOOLTIPS.modelCompat} label="Model compatibility" />
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StyleControls({ selectedStyle, onSelectStyle, styleOptions = styleChips }) {
  const builtinStyles = styleOptions.filter((style) => !style.custom);
  const customStyles = styleOptions.filter((style) => style.custom);

  const renderGrid = (styles) => (
    <div className="mt-1.5 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
      {styles.map((style) => (
        <MiniStyle
          key={style.promptName}
          style={style}
          active={selectedStyle === style.promptName}
          onClick={() => onSelectStyle?.(style.promptName)}
        />
      ))}
    </div>
  );

  return (
    <div>
      <FieldLabel tip={TOOLTIPS.style}>Style</FieldLabel>
      <StyleGroupLabel>Built-in</StyleGroupLabel>
      {renderGrid(builtinStyles)}
      {customStyles.length > 0 && (
        <>
          <StyleGroupLabel>Custom</StyleGroupLabel>
          {renderGrid(customStyles)}
        </>
      )}
    </div>
  );
}

function StyleGroupLabel({ children }) {
  return (
    <div className="mt-2.5 mb-0.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[#9098A8]">
      <span>{children}</span>
      <span className="h-px flex-1 bg-white/10" />
    </div>
  );
}

function LengthControls({ length, setLength }) {
  return (
    <div>
      <FieldLabel tip={TOOLTIPS.length}>Length</FieldLabel>
      <div className="mt-1.5 grid grid-cols-3 gap-1.5">
        {lengthOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setLength(option.id)}
            className={`rounded-[9px] border px-1.5 py-2 text-center ${
              length === option.id
                ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.12)]"
                : "border-white/[0.08] bg-transparent"
            }`}
          >
            <div className="text-[12.5px] font-semibold">{option.label}</div>
            <div className="text-[10.5px] text-[#9098A8]">{option.meta}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

// Global generation axes — depth + difficulty. These MODIFY the whole guide
// (how deep / how it is pitched) rather than ADD sections. "Auto" is the unset
// state and omits the field from the request. Voice/tone is intentionally absent
// (owned by Styles). Rendered as two segmented rows matching LengthControls.
function AxisControls({ outputDepth, setOutputDepth, difficulty, setDifficulty }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <SegmentedAxis
        label="Output depth"
        tip={TOOLTIPS.outputDepth}
        value={outputDepth}
        onChange={setOutputDepth}
        options={OUTPUT_DEPTH_OPTIONS}
      />
      <SegmentedAxis
        label="Difficulty"
        tip={TOOLTIPS.difficulty}
        value={difficulty}
        onChange={setDifficulty}
        options={DIFFICULTY_OPTIONS}
      />
    </div>
  );
}

function SegmentedAxis({ label, tip, value, onChange, options }) {
  return (
    <div>
      <FieldLabel tip={tip}>{label}</FieldLabel>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {options.map((option) => (
          <button
            key={option.value || "auto"}
            type="button"
            onClick={() => onChange(option.value)}
            className={`inline-flex h-8 items-center rounded-[9px] border px-3 text-[12px] font-semibold transition ${
              value === option.value
                ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.12)] text-[#F97316]"
                : "border-white/[0.08] bg-transparent text-[#9098A8] hover:text-[#D4D4D8]"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// Canonical output-section toggles, grouped only for readability. Each chip's
// `key` is the backend `include_sections` key (sent verbatim); the label is
// cosmetic. No sections are selected by default.
function SectionControls({ includeSections, toggleSection }) {
  return (
    <div>
      <FieldLabel tip={TOOLTIPS.sections}>Output sections</FieldLabel>
      <div className="mt-1.5 grid gap-3">
        {SECTION_GROUPS.map((group) => (
          <div key={group.title}>
            <StyleGroupLabel>{group.title}</StyleGroupLabel>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {group.keys.map((entry) => {
                const active = Boolean(includeSections[entry.key]);
                const chip = (
                  <button
                    type="button"
                    onClick={() => toggleSection(entry.key)}
                    className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs font-medium ${
                      active
                        ? "border-[rgba(249,115,22,0.35)] bg-[rgba(249,115,22,0.10)] text-[#FB923C]"
                        : "border-white/10 bg-white/[0.04] text-[#F4F4F5]"
                    }`}
                  >
                    {active && <span className="text-[10px]">✓</span>}
                    {entry.label}
                  </button>
                );
                if (!entry.tip) {
                  return <React.Fragment key={entry.key}>{chip}</React.Fragment>;
                }
                return (
                  <span key={entry.key} className="inline-flex items-center gap-1">
                    {chip}
                    <InfoTip text={entry.tip} label={entry.label} />
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SourceEditor({ source, text, setText, file, setFile, setError }) {
  if (source === "upload") {
    return (
      <label className="sg-source-drop">
        <Tile size={46} radius={12}><UploadGlyph size={22} /></Tile>
        <span>
          {file ? file.name : "Choose a .md or .markdown file"}
        </span>
        <em>Upload Markdown and generate a PDF-ready guide.</em>
        <input
          type="file"
          accept=".md,.markdown"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setError(null);
          }}
          className="sr-only"
        />
      </label>
    );
  }

  return (
    <div className="sg-source-editor">
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        aria-label={source === "llm" ? "AI prompt and source material" : "Pasted source text"}
        placeholder={
          source === "llm"
            ? "Describe the guide you want and paste the real source material here."
            : "# Your notes\n\nPaste Markdown or plain text here."
        }
        className="sg-source-textarea"
      />
      <div className="sg-char-count">
        {text.length.toLocaleString()} / 50,000 chars
      </div>
    </div>
  );
}

function AttachmentsPicker({ attachments, setAttachments }) {
  function addFiles(fileList) {
    const nextFiles = Array.from(fileList || []);
    if (nextFiles.length === 0) return;
    setAttachments((current) => [...current, ...nextFiles].slice(0, 5));
  }

  function removeFile(index) {
    setAttachments((current) => current.filter((_, fileIndex) => fileIndex !== index));
  }

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
      <FieldLabel tip={TOOLTIPS.attachments}>Attachments</FieldLabel>
      <label className="mt-2 flex cursor-pointer items-center gap-3 rounded-[10px] border border-dashed border-white/[0.12] bg-[#070B14] p-3 transition hover:border-[rgba(249,115,22,0.35)]">
        <span className="grid h-9 w-9 place-items-center rounded-[9px] border border-[rgba(255,180,120,0.16)] bg-[#111A2B] text-[#F97316]">
          <Upload className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12.5px] font-semibold text-[#F4F4F5]">Attach source files</span>
          <span className="block text-[11px] text-[#9098A8]">txt, md, csv, tsv, docx, pptx, pdf · max 5 files</span>
        </span>
        <input
          type="file"
          multiple
          accept=".txt,.md,.markdown,.csv,.tsv,.docx,.pptx,.pdf"
          onChange={(event) => {
            addFiles(event.target.files);
            event.target.value = "";
          }}
          className="sr-only"
        />
      </label>
      {attachments.length > 0 && (
        <div className="mt-2 grid gap-1.5">
          {attachments.map((file, index) => (
            <div
              key={`${file.name}-${file.size}-${index}`}
              className="flex items-center gap-2 rounded-[9px] border border-white/[0.06] bg-white/[0.03] px-2.5 py-2 text-[12px]"
            >
              <FileText className="h-3.5 w-3.5 text-[#F97316]" />
              <span className="min-w-0 flex-1 truncate text-[#D4D4D8]">{file.name}</span>
              <span className="text-[10.5px] text-[#9098A8]">{formatFileSize(file.size)}</span>
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="rounded-md border border-white/[0.08] px-2 py-1 text-[10.5px] font-semibold text-[#9098A8] transition hover:text-[#F4F4F5]"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MiniStyle({ style, active, onClick }) {
  const Icon = style.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`sg-mini-style ${active ? "active" : ""}`}
    >
      <span
        className={`grid h-[26px] w-[26px] place-items-center rounded-[7px] border ${
          active
            ? "border-[rgba(255,180,120,0.4)] bg-gradient-to-br from-[#FB923C] via-[#F97316] to-[#C2410C] text-[#1B0F03]"
            : "border-[rgba(255,180,120,0.18)] bg-gradient-to-br from-[#1F2A40] to-[#131B2C] text-[#F97316]"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="text-[10.5px] font-medium">{style.label}</span>
    </button>
  );
}

function OptionCard({ option, active, disabled = false, onClick }) {
  const Icon = option.icon;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`sg-option-card ${active ? "active" : ""} ${disabled ? "opacity-55" : ""}`}
    >
      <span
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-[8px] border ${
          active
            ? "border-[rgba(255,180,120,0.4)] bg-gradient-to-br from-[#FB923C] via-[#F97316] to-[#C2410C] text-[#1B0F03]"
            : "border-[rgba(255,180,120,0.16)] bg-[#111A2B] text-[#F97316]"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0">
        <span className="block text-[12.5px] font-semibold text-[#F4F4F5]">{option.label}</span>
        <span className="block truncate text-[10.5px] text-[#9098A8]">{option.meta}</span>
      </span>
    </button>
  );
}

function SectionHeader({ eyebrow, title, description }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-4">
      <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#F97316]">
        {eyebrow}
      </div>
      <h2 className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-[#F4F4F5]">{title}</h2>
      <p className="mt-1 max-w-2xl text-[12.5px] leading-5 text-[#9098A8]">{description}</p>
    </div>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
      <div className="font-mono text-[9.5px] font-semibold uppercase tracking-[0.12em] text-[#6B7185]">
        {label}
      </div>
      <div className="mt-1 truncate text-[13px] font-semibold text-[#F4F4F5]">{value}</div>
    </div>
  );
}

function MetaRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[9px] border border-white/[0.06] bg-[#070B14] px-3 py-2">
      <span className="text-[#9098A8]">{label}</span>
      <span className="truncate font-mono text-[11px] font-semibold text-[#F4F4F5]">{value}</span>
    </div>
  );
}

function PreviewFormatTabs({ result, previewFormat, setPreviewFormat }) {
  return (
    <div className="flex gap-1">
      {["pdf", "html"].map((format) => (
        <button
          key={format}
          type="button"
          disabled={!result}
          onClick={() => setPreviewFormat(format)}
          className={`h-7 rounded-md border px-2.5 text-[11.5px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${
            previewFormat === format
              ? "border-[rgba(249,115,22,0.45)] bg-[rgba(249,115,22,0.14)] text-[#F97316]"
              : "border-white/[0.08] bg-white/[0.03] text-[#9098A8] hover:text-[#D4D4D8]"
          }`}
        >
          {format.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function ArtifactDownloadGrid({ artifacts, compact = false }) {
  return (
    <div className={`grid gap-1.5 ${compact ? "" : "sm:grid-cols-2"}`}>
      {artifacts.length === 0 && (
        <div className="rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-[12px] text-[#9098A8]">
          No artifacts available yet.
        </div>
      )}
      {artifacts.map(([name, url]) => {
        const artifact = artifactLabels[name];
        const Icon = artifact.icon;
        const label = name === "final.html" ? "View HTML" : name === "final.pdf" ? "Download PDF" : artifact.label;
        return (
          <a
            key={name}
            href={apiUrl(url)}
            className="flex items-center justify-between rounded-md border border-white/[0.08] bg-white/[0.035] px-3 py-2 text-[12px] font-semibold text-[#D4D4D8] transition hover:border-[rgba(249,115,22,0.45)] hover:text-white"
          >
            <span className="inline-flex items-center gap-2">
              <Icon className="h-3.5 w-3.5 text-[#F97316]" />
              {label}
            </span>
            <Download className="h-3.5 w-3.5 text-[#6B7185]" />
          </a>
        );
      })}
    </div>
  );
}

function AttachedSourcesSummary({ result, compact = false }) {
  const attachments = result?.attachments ?? [];
  if (attachments.length === 0) {
    return null;
  }

  const warnings = result?.extraction_warnings ?? attachments.flatMap((item) => item.warnings ?? []);
  return (
    <div className={`rounded-xl border border-white/[0.06] bg-white/[0.025] ${compact ? "mt-3 p-3" : "p-4"}`}>
      <div className="flex items-center justify-between gap-3">
        <FieldLabel>Attached sources</FieldLabel>
        <div className="flex flex-wrap justify-end gap-1.5">
          <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 text-[10.5px] font-bold text-emerald-200">
            <FileText className="h-3 w-3" />
            {attachments.length} {attachments.length === 1 ? "source" : "sources"}
          </span>
          {warnings.length > 0 && (
            <span className="inline-flex h-6 items-center gap-1.5 rounded-full border border-amber-300/30 bg-amber-300/10 px-2 text-[10.5px] font-bold text-amber-100">
              <AlertCircle className="h-3 w-3" />
              {warnings.length} warning{warnings.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>
      <div className={`mt-2 grid gap-2 ${compact ? "max-h-36 overflow-auto pr-1" : ""}`}>
        {attachments.map((attachment, index) => {
          const itemWarnings = attachment.warnings ?? [];
          const extracted = Number(attachment.extracted_chars || 0);
          return (
            <div key={`${attachment.filename}-${index}`} className="rounded-[10px] border border-white/[0.06] bg-[#070B14] p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-[12px] font-semibold text-[#F4F4F5]">{attachment.filename}</span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                  attachment.status === "extracted"
                    ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200"
                    : "border-amber-300/30 bg-amber-300/10 text-amber-100"
                }`}>
                  {attachment.status || "unknown"}
                </span>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10.5px] font-semibold text-[#9098A8]">
                <span>{attachment.mode || attachment.extension || "unsupported"}</span>
                <span>{extracted.toLocaleString()} chars</span>
                {attachment.truncated && <span>truncated</span>}
              </div>
              {itemWarnings.length > 0 && (
                <div className="mt-2 grid gap-1 text-[11px] leading-4 text-amber-100">
                  {itemWarnings.map((warning, warningIndex) => (
                    <p key={warningIndex}>{warning}</p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LivePreviewPanel({
  result,
  artifacts,
  selectedStyle,
  styleOptions = styleChips,
  length,
  previewFormat,
  setPreviewFormat,
  onOpenDetails
}) {
  const artifactUrls = result?.artifact_urls ?? {};
  const primaryPdf = artifactUrls["final.pdf"];
  const title = result?.title || "Sample Guide Preview";
  const matchedStyle = styleOptions.find((style) => style.promptName === selectedStyle);
  const styleLabel = (matchedStyle?.name || matchedStyle?.label || "Exam Cram").toUpperCase();
  const lengthLabel = lengthOptions.find((option) => option.id === length)?.label?.toUpperCase() || "MEDIUM";

  return (
    <aside className="sg-preview-pane">
      <div className="sg-preview-top">
        <div>
          <div className="sg-preview-title">Live preview</div>
          <PreviewFormatTabs
            result={result}
            previewFormat={previewFormat}
            setPreviewFormat={setPreviewFormat}
          />
        </div>
      </div>

      <div className="sg-paper-preview">
        {!result ? (
          <div className="relative h-full overflow-hidden p-[10px] font-serif">
            <div className="font-mono text-[9px] tracking-[0.15em] text-[#A78050]">
              {styleLabel} · {lengthLabel}
            </div>
            <div className="mt-1.5 text-[22px] font-bold leading-[1.1] tracking-[-0.02em]">
              {title}
            </div>
            <div className="mt-1 font-sans text-[10.5px] text-[#6B5A3F]">
              Sample preview · not sent to backend
            </div>
            <div className="mt-3.5 h-px bg-gradient-to-r from-[#C2410C] to-transparent" />
            <SamplePreview />
            <div className="absolute bottom-0 left-[10px] right-[10px] flex justify-between font-mono text-[9px] text-[#A78050]">
              <span>STUDY GUIDE</span>
              <span>03 / 20</span>
            </div>
          </div>
        ) : (
          <ArtifactPreview
            format={previewFormat}
            artifactUrls={artifactUrls}
          />
        )}
      </div>

      {result && (
        <div className="sg-download-panel">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12.5px] font-semibold text-[#D4D4D8]">Downloads</span>
            <span className="font-mono text-[10px] text-[#6B7185]">{artifacts.length} files</span>
          </div>
          <ArtifactDownloadGrid artifacts={artifacts} compact />
        </div>
      )}

      {result && <AttachedSourcesSummary result={result} compact />}

      <div className="sg-preview-actions">
        <a
          href={primaryPdf ? apiUrl(primaryPdf) : undefined}
          className={`flex h-9 flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[12.5px] font-medium text-[#D4D4D8] ${
            primaryPdf ? "" : "pointer-events-none opacity-55"
          }`}
        >
          <Download className="h-4 w-4" />
          <span className="ml-2">Export PDF</span>
        </a>
        <button
          type="button"
          onClick={onOpenDetails}
          className="flex h-9 flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-[12.5px] font-medium text-[#D4D4D8]"
        >
          <Share2 className="h-3.5 w-3.5" />
          <span className="ml-2">Details</span>
        </button>
      </div>
    </aside>
  );
}

function ArtifactPreview({ format, artifactUrls }) {
  if (format === "pdf") {
    if (!artifactUrls["final.pdf"]) {
      return <PreviewUnavailable />;
    }
    return (
      <iframe
        title="Generated PDF preview"
        src={previewApiUrl(artifactUrls["final.pdf"])}
        className="h-full w-full rounded-md border-0 bg-white"
      />
    );
  }

  if (format === "html") {
    if (!artifactUrls["final.html"]) {
      return <PreviewUnavailable />;
    }
    return (
      <iframe
        title="Generated HTML preview"
        src={previewApiUrl(artifactUrls["final.html"])}
        sandbox="allow-same-origin"
        className="h-full w-full rounded-md border-0 bg-white"
      />
    );
  }

  return <PreviewUnavailable />;
}

function PreviewUnavailable() {
  return (
    <div className="grid h-full place-items-center rounded-md bg-white p-6 text-center">
      <div>
        <FileText className="mx-auto h-8 w-8 text-[#C2410C]" />
        <p className="mt-3 text-sm font-bold text-slate-900">Preview not available yet.</p>
        <p className="mt-1 text-xs text-slate-500">Choose PDF or HTML after the artifact is generated.</p>
      </div>
    </div>
  );
}

function SamplePreview() {
  return (
    <>
      <div className="mt-3.5 text-[13px] font-bold">1 · Definitions</div>
      <div className="mt-1.5 font-sans text-[10.5px] leading-[1.55] text-[#3A3528]">
        A limit describes the value a function approaches as its input approaches some value c.
      </div>
      <div className="mt-2.5 border-l-2 border-[#F97316] bg-[rgba(249,115,22,0.07)] px-3 py-2.5 font-mono text-[10.5px] text-[#7A4A1C]">
        lim x→c f(x) = L
      </div>
      <div className="mt-3.5 text-[13px] font-bold">2 · Continuity</div>
      <div className="mt-1.5 font-sans text-[10.5px] leading-[1.55] text-[#3A3528]">
        f is continuous at c if lim x→c f(x) = f(c). Three conditions must hold:
      </div>
      <ul className="mt-1.5 list-disc pl-[18px] font-sans text-[10.5px] text-[#3A3528]">
        <li>f(c) is defined</li>
        <li>The limit exists</li>
        <li>They are equal</li>
      </ul>
      <div className="mt-3.5 rounded-md border border-dashed border-[rgba(194,65,12,0.4)] bg-[rgba(249,115,22,0.10)] p-2.5">
        <div className="font-mono text-[9px] tracking-[0.1em] text-[#A78050]">MEMORY CUE</div>
        <div className="mt-0.5 font-sans text-[11px] text-[#3A3528]">
          <strong>D-L-E</strong>: Defined · Limit exists · Equal
        </div>
      </div>
    </>
  );
}

function FieldLabel({ children, tip, tipLabel }) {
  return (
    <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-[#9098A8]">
      <span>{children}</span>
      {tip && <InfoTip text={tip} label={tipLabel || (typeof children === "string" ? children : "")} />}
    </div>
  );
}

function Toggle({ label, checked, onChange, tip }) {
  return (
    <label className="flex items-center gap-2 rounded-[10px] border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-[12.5px] font-medium text-[#D4D4D8]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-[#F97316]"
      />
      <span className="inline-flex items-center gap-1.5">
        {label}
        {tip && <InfoTip text={tip} label={typeof label === "string" ? label : ""} />}
      </span>
    </label>
  );
}

// Small keyboard-accessible "?" info icon. The bubble is absolutely positioned so
// it never affects layout, and shows on hover OR focus (group-focus-within). The
// trigger swallows clicks so it never toggles a surrounding <label> control.
function InfoTip({ text, label }) {
  return (
    <span className="sg-infotip group">
      <button
        type="button"
        aria-label={label ? `Help: ${label}` : "More information"}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        className="grid h-4 w-4 place-items-center rounded-full border border-white/15 text-[#9098A8] outline-none transition hover:border-[rgba(249,115,22,0.5)] hover:text-[#F4F4F5] focus-visible:border-[rgba(249,115,22,0.6)] focus-visible:text-[#F4F4F5] focus-visible:ring-1 focus-visible:ring-[rgba(249,115,22,0.5)]"
      >
        <Info className="h-2.5 w-2.5" />
      </button>
      <span role="tooltip" className="sg-infotip-bubble">
        {text}
      </span>
    </span>
  );
}

function ErrorMessage({ error }) {
  return (
    <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-[12.5px] text-red-100">
      <div className="flex items-start gap-2.5">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">{error.message || "Could not generate guide."}</p>
          {error.details && (
            <details className="mt-2 text-red-100/80">
              <summary className="cursor-pointer font-semibold">Details</summary>
              <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-2 text-[11px]">
                {error.details}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

const fieldClass =
  "h-11 w-full rounded-[10px] border border-white/[0.08] bg-white/[0.03] px-3.5 text-base font-medium tracking-[-0.01em] text-[#F4F4F5] outline-none transition focus:border-[rgba(249,115,22,0.45)]";

const selectClass =
  "h-9 w-full rounded-[10px] border border-white/[0.08] bg-[#070B14] px-3 text-[13.5px] font-medium text-[#F4F4F5] outline-none";

function normalizeProviderDetails(options) {
  const details = options?.provider_details ?? options?.providers_v2;
  if (Array.isArray(details) && details.length > 0) {
    return details.map((detail) => ({
      id: detail.id,
      display_name: detail.display_name || detail.name || detail.id,
      configured: Boolean(detail.configured),
      available_models: Array.isArray(detail.available_models) ? detail.available_models : [],
      default_model: detail.default_model || "",
      base_url: detail.base_url || "",
      discovery_error: detail.discovery_error || "",
      supports_thinking: Boolean(detail.supports_thinking)
    }));
  }
  return fallbackProviderDetails;
}

function chooseInitialProvider(details, currentProvider) {
  return (
    details.find((detail) => detail.id === currentProvider && detail.configured) ||
    details.find((detail) => detail.configured) ||
    details.find((detail) => detail.id === currentProvider) ||
    details[0] ||
    fallbackProviderDetails[0]
  );
}

function selectDefaultModel(detail, currentModel = "") {
  if (!detail) {
    return currentModel || "";
  }
  const models = detail.available_models || [];
  if (currentModel && models.includes(currentModel)) {
    return currentModel;
  }
  return detail.default_model || models[0] || "";
}

function providerOptionFromDetail(detail) {
  const modelCount = detail.available_models?.length || 0;
  return {
    id: detail.id,
    label: detail.display_name || detail.id,
    meta: detail.configured
      ? `${modelCount || 1} model${modelCount === 1 ? "" : "s"} available`
      : detail.base_url
        ? "Configured, discovery needs a model"
        : "Not configured",
    icon: detail.id === "qwen" ? Sparkles : detail.id === "local" ? Zap : Wand2
  };
}

function isMarkdownFile(file) {
  const name = file.name.toLowerCase();
  return name.endsWith(".md") || name.endsWith(".markdown");
}

function normalizeError(error) {
  const message = error?.message || "Could not generate guide.";
  if (message.startsWith("{") || message.includes("Traceback") || message.length > 180) {
    return { message: "Could not generate guide.", details: message };
  }
  return { message };
}

export function buildBuilderPayload({
  source,
  text,
  file,
  title,
  selectedStyle,
  generatorPreset = "",
  provider,
  model,
  strictMath,
  qwenThinking,
  attachments,
  length,
  includeSections = {},
  outputDepth = "",
  difficulty = "",
  folderId = "unfiled",
  outline = null
}) {
  if (source === "upload") {
    return {
      kind: "upload",
      payload: {
        file,
        theme: "claude_clean",
        strictMath,
        folderId
      }
    };
  }

  if (source === "llm") {
    return {
      kind: "llm",
      payload: buildLlmPayload({
        text,
        title,
        selectedStyle,
        generatorPreset,
        provider,
        model,
        strictMath,
        qwenThinking,
        attachments,
        length,
        includeSections,
        outputDepth,
        difficulty,
        folderId,
        outline
      })
    };
  }

  return {
    kind: "paste",
    payload: {
      text,
      theme: "claude_clean",
      strictMath,
      folderId
    }
  };
}

export function buildLlmPayload({
  text,
  title,
  mode = "study_guide",
  selectedStyle,
  generatorPreset = "",
  provider,
  model,
  strictMath,
  qwenThinking,
  attachments = [],
  length,
  includeSections = {},
  outputDepth = "",
  difficulty = "",
  folderId = "unfiled",
  outline = null
}) {
  const hasOutline = outline?.enabled && (outline.sections || []).some((section) => section.title?.trim());
  // Send the canonical fields only when they carry intent: omit include_sections
  // entirely when nothing is enabled, and omit each axis when unset. This keeps a
  // default/fresh generate request free of include_sections/output_depth/difficulty.
  const enabledSections = normalizeSectionState(includeSections);
  return {
    source_text: augmentSourceText(text, length),
    title,
    mode,
    prompt_name: selectedStyle,
    // When set, the backend uses this as the system prompt + sampling params and
    // ignores prompt_name; omitted entirely otherwise to preserve the style path.
    ...(generatorPreset ? { generator_preset: generatorPreset } : {}),
    provider,
    model,
    theme: "claude_clean",
    strict_math: strictMath,
    qwen_thinking: qwenThinking,
    folder_id: folderId,
    ...(hasOutline ? { outline } : {}),
    ...(hasEnabledSections(enabledSections) ? { include_sections: enabledSections } : {}),
    ...(outputDepth ? { output_depth: outputDepth } : {}),
    ...(difficulty ? { difficulty } : {}),
    attachments
  };
}

function formatFileSize(size) {
  if (!Number.isFinite(size)) {
    return "";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function assertBuilderPayload(kind, payload, state) {
  if (kind === "paste" && payload.text !== state.text) {
    throw new Error("Builder payload mismatch: paste text does not match editor text.");
  }

  if (kind === "llm") {
    const expectedSource = augmentSourceText(state.text, state.length);
    if (payload.title !== state.title) {
      throw new Error("Builder payload mismatch: title does not match title field.");
    }
    if (payload.source_text !== expectedSource) {
      throw new Error("Builder payload mismatch: source text does not match editor text.");
    }
  }
}

function augmentSourceText(text, length) {
  const lengthLabel = lengthOptions.find((option) => option.id === length)?.meta || "~20 pages";
  // Output sections now flow through the canonical `include_sections` request
  // field (and prompt assembly), so they are no longer appended as free text here.
  return `${text.trim()}\n\nAdditional builder instructions:\nRequested length: ${lengthLabel}.`;
}
