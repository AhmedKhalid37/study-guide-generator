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
  Gauge,
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
  preflightPdf,
  previewApiUrl
} from "../api/client";
import {
  builderStateToPayload,
  INPUT_TO_SOURCE,
  pagesToLength,
  withSavedPrompt,
  clampSavedPrompt,
  MAX_SAVED_PROMPT_CHARS
} from "../shortcutMeta";
import {
  DIFFICULTY_OPTIONS,
  hasEnabledSections,
  normalizeSectionState,
  OUTPUT_DEPTH_OPTIONS,
  SECTION_GROUPS
} from "../sectionMeta";
import { FOLDER_PRESET_COLORS } from "../folderMeta";
import {
  isVisualPilotEffectivelyOn,
  isVisualPilotToggleEnabled,
  isVisualReferencesReady,
  visualPilotReadinessNote,
  visualPilotPayloadFields
} from "../visualPilotOptIn";
import {
  DUAL_EXPLANATION_LABEL,
  DUAL_EXPLANATION_HELPER,
  dualExplanationPayloadFields
} from "../dualExplanationOptIn";
import { presetCompat, presetModelLabel, providerIconFor, providerLabelFor } from "../presetMeta";
import {
  buildMaterialPageSelections,
  hasActiveMaterialSelections,
  parsePageListInput
} from "../materialPageSelections";
import { buildBuilderMaterialCoverageSummary } from "../materialCoverageWarnings";
import { Icon } from "./Icon";
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
  sections: "Optional extra sections to add where the source supports them. None are added unless you pick them.",
  visualReferences:
    "Experimental: when the source is a PDF with a usable extracted figure, add at most one figure image to the guide. Off by default and also requires the server-side pilot to be enabled."
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
  // Slice 55/57: per-job opt-in for the off-by-default visual markdown image pilot.
  // Default false ⇒ no extra field on the request ⇒ unchanged output. The actual
  // insertion ALSO requires server-side switches; visualPilotReady below mirrors the
  // backend readiness (master pilot flag AND local figure extraction, from
  // /api/options.capabilities) so the toggle renders enabled only when a new job
  // could actually produce + insert a figure, and disabled-with-a-calm-note
  // otherwise. visualPilotNote holds that calm explanation ("" when ready).
  const [enableVisualReferences, setEnableVisualReferences] = useState(false);
  // Slice 99: per-job opt-in for "Explain like I'm 10 / Exam answer" dual
  // explanation mode. Default off ⇒ field omitted from the payload ⇒ unchanged
  // generation behaviour. No server-capability gate (unlike the visual pilot).
  const [dualExplanationMode, setDualExplanationMode] = useState(false);
  const [visualPilotReady, setVisualPilotReady] = useState(false);
  const [visualPilotNote, setVisualPilotNote] = useState("");
  const [attachments, setAttachments] = useState([]);
  // Per-PDF preflight inspection results, keyed by a stable file signature (see
  // attachmentKey). Lives alongside the selected files only — never persisted to
  // a job. Drives the warning UI in AttachmentsPicker and the "blocked" gate in
  // validateInputs. Shape per entry: { status: "checking"|"done"|"error",
  // report?, error? }.
  const [attachmentPreflights, setAttachmentPreflights] = useState({});
  // PDF page selection (Slice 5): filename -> [[start, end], ...], 1-based
  // inclusive. Keyed by the original upload filename (file.name) — the same key the
  // backend plumbing matches on. Populated by the preflight card's "Process first N
  // pages" / "Choose page range" actions; default {} means "all pages" and
  // buildLlmPayload omits page_selections entirely. Lives beside the selected files
  // only (like attachmentPreflights) — not persisted to drafts/shortcuts, since the
  // attachments it refers to are not persisted either.
  const [pageSelections, setPageSelections] = useState({});
  // Per-attachment material page/slide exclusions (Slice 87). Keyed by the same
  // stable attachmentKey(file) signature as preflights so it survives add/remove,
  // mapping each attachment to the raw "exclude pages/slides" text the user typed.
  // This is SEPARATE from `pageSelections` (the load-bearing extraction page-range
  // field): at submit time it is converted by upload order into the safe
  // `material_page_selections` envelope (`attachment_<index>` keys, never filenames).
  // Default {} means "no exclusions" and the field is omitted from the request.
  const [materialExclusions, setMaterialExclusions] = useState({});
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
  // "Save as shortcut" dialog (replaces a bare window.prompt so we can offer the
  // opt-in "save prompt/source text" checkbox). Null when closed.
  const [shortcutDialog, setShortcutDialog] = useState(null);
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
        // Slice 57: mirror backend visual-pilot readiness (master flag AND local
        // figure extraction) so the Builder enables its per-job opt-in only when a
        // new job could honour it, and shows a calm note otherwise. Non-secret
        // on/off booleans + fixed safe copy only.
        setVisualPilotReady(isVisualReferencesReady(options?.capabilities));
        setVisualPilotNote(visualPilotReadinessNote(options?.capabilities));
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
        enableVisualReferences,
        dualExplanationMode,
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
      enableVisualReferences,
      dualExplanationMode,
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
      // Slice 87: convert the per-attachment exclusion inputs into the safe
      // `material_page_selections` envelope by UPLOAD ORDER (so keys are
      // `attachment_<index>`, never filenames). buildLlmPayload omits the field
      // unless at least one attachment carries an active exclusion.
      const materialPageSelections = buildMaterialPageSelections(
        attachments.map((file) => materialExclusions[attachmentKey(file)] ?? "")
      );
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
        enableVisualReferences,
        dualExplanationMode,
        attachments,
        length,
        includeSections,
        outputDepth,
        difficulty,
        folderId,
        outline: outlineEnabled ? { enabled: true, sections: outlineSections } : null,
        pageSelections,
        materialPageSelections
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
      // Opt-in saved prompt/source text: prefill the Builder source so a shortcut
      // that captured its prompt reopens ready to generate. Only when present, so a
      // settings-only shortcut never clears whatever the user already typed.
      if (typeof payload.saved_prompt === "string" && payload.saved_prompt) setText(payload.saved_prompt);
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

  function handleSaveShortcut() {
    if (shortcutSaving) return;
    const defaultName =
      title && title !== DEFAULT_TITLE
        ? title
        : `${selectedStyleOption?.name || selectedStyleOption?.label || "Study"} setup`;
    // Open the dialog (name + opt-in "save prompt" checkbox). The checkbox starts
    // OFF, so the default behavior — reusable settings only — is unchanged.
    setShortcutSaveError(null);
    setShortcutDialog({ name: defaultName, savePrompt: false });
  }

  async function commitSaveShortcut({ name, savePrompt }) {
    const trimmed = (name || "").trim();
    if (!trimmed) return;
    setShortcutSaving(true);
    setShortcutSaveError(null);
    try {
      // saved_prompt is opt-in: only attached when the checkbox is on and there is
      // typed source text to save. Uploaded files / attachments are never included.
      const payload = withSavedPrompt(buildShortcutSetup(), {
        savePrompt,
        sourceText: text
      });
      await createShortcut({
        name: trimmed,
        type: "builder_setup",
        description: `${selectedProvider?.display_name || provider} · ${
          selectedStyleOption?.name || selectedStyle
        }`,
        pinned: true,
        icon: "⭐",
        payload
      });
      setShortcutDialog(null);
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
      const blocked = attachments.find(
        (item) => attachmentPreflights[attachmentKey(item)]?.report?.verdict === "blocked"
      );
      if (blocked) {
        return `Remove "${blocked.name}" — it can't be read (corrupt or encrypted) and must be replaced before generating.`;
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
            <BuilderTabIcon id={tab.id} />
            {tab.label}
          </button>
        ))}
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
              enableVisualReferences={enableVisualReferences}
              setEnableVisualReferences={setEnableVisualReferences}
              dualExplanationMode={dualExplanationMode}
              setDualExplanationMode={setDualExplanationMode}
              visualPilotReady={visualPilotReady}
              visualPilotNote={visualPilotNote}
              attachments={attachments}
              setAttachments={setAttachments}
              attachmentPreflights={attachmentPreflights}
              setAttachmentPreflights={setAttachmentPreflights}
              pageSelections={pageSelections}
              setPageSelections={setPageSelections}
              materialExclusions={materialExclusions}
              setMaterialExclusions={setMaterialExclusions}
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
      {shortcutDialog && (
        <SaveShortcutDialog
          dialog={shortcutDialog}
          setDialog={setShortcutDialog}
          sourceText={text}
          saving={shortcutSaving}
          error={shortcutSaveError}
          onConfirm={commitSaveShortcut}
        />
      )}
    </div>
  );
}

// "Save as shortcut" dialog: a name plus the opt-in "save prompt/source text"
// checkbox. The checkbox defaults OFF (reusable settings only). When ON, the
// current typed source text is included; the live char count surfaces the shared
// size limit so an over-limit prompt is caught before the server rejects it. Only
// typed source text is offered — uploaded files / attachments are never captured.
function SaveShortcutDialog({ dialog, setDialog, sourceText, saving, error, onConfirm }) {
  const willSave = dialog.savePrompt ? clampSavedPrompt(sourceText) : "";
  const len = (sourceText || "").length;
  const over = dialog.savePrompt && len > MAX_SAVED_PROMPT_CHARS;
  const nothingToSave = dialog.savePrompt && !willSave;
  return (
    <div className="sg-modal-scrim">
      <button
        type="button"
        aria-label="Close"
        className="sg-scrim-bg"
        onClick={() => !saving && setDialog(null)}
      />
      <div role="dialog" aria-modal="true" className="sg-modal">
        <h2>Save as shortcut</h2>
        <div className="sg-field-block" style={{ marginTop: 14 }}>
          <span className="sg-field-label">Name</span>
          <input
            className="sg-input"
            autoFocus
            value={dialog.name}
            maxLength={120}
            onChange={(e) => setDialog({ ...dialog, name: e.target.value })}
            placeholder="Name this shortcut"
          />
        </div>

        <div className="sg-modal-card">
          <label className="sg-checkrow">
            <input
              type="checkbox"
              checked={dialog.savePrompt}
              onChange={(e) => setDialog({ ...dialog, savePrompt: e.target.checked })}
            />
            <span>
              <span className="ttl">Save prompt/source text with this shortcut</span>
              <span className="sub">
                Includes the current prompt/text inside the shortcut export. Leave off for
                reusable settings only. This may contain private course material.
              </span>
            </span>
          </label>
          {dialog.savePrompt && (
            <div className={`sg-modal-count${over ? " over" : ""}`}>
              {len.toLocaleString()} / {MAX_SAVED_PROMPT_CHARS.toLocaleString()} chars
              {over ? " — too long; shorten the source text." : ""}
              {nothingToSave && !over ? " — no typed source text to save yet." : ""}
            </div>
          )}
        </div>

        {error && <p className="sg-modal-err">{error}</p>}

        <div className="sg-modal-actions">
          <button
            type="button"
            onClick={() => setDialog(null)}
            disabled={saving}
            className="sg-ghost-button"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm({ name: dialog.name, savePrompt: dialog.savePrompt })}
            disabled={saving || !dialog.name.trim() || over}
            className="sg-progress-btn"
            style={{ minWidth: 0, height: 40, padding: "0 18px" }}
          >
            <span className="sg-progress-label">
              {saving && <Loader2 className="sg-spin" />}
              Save
            </span>
          </button>
        </div>
      </div>
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

      <div className="sg-action-buttons">
        {artifacts.length > 0 && (
          <div className="sg-action-exports">
            {artifacts.map(([name, url]) => {
              const meta = artifactLabels[name];
              const ArtifactIcon = meta.icon;
              return (
                <a key={name} href={apiUrl(url)} className="sg-export-btn" title={`Download ${meta.label}`}>
                  <ArtifactIcon />
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
          className="sg-ghost-button"
        >
          {shortcutSaving ? (
            <Loader2 className="sg-spin" />
          ) : shortcutSaveError ? (
            <AlertCircle style={{ color: "var(--red)" }} />
          ) : shortcutSaved ? (
            <Check style={{ color: "var(--green)" }} />
          ) : (
            <Bookmark />
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
            className="sg-ghost-button"
          >
            <X />
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
        )}

        <GenerateProgressButton loading={loading} progress={progress} hasResult={hasResult} />
      </div>
    </div>
  );
}

function ActionChip({ icon: ChipIcon, kx, v, title, dot = false }) {
  return (
    <span className="sg-chip" title={title || `${kx}: ${v}`}>
      {dot ? <i className="dot" /> : ChipIcon ? <ChipIcon /> : null}
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
    <AlertCircle />
  ) : complete ? (
    <Check />
  ) : running ? (
    <Loader2 className="sg-spin" />
  ) : hasResult ? (
    <RefreshCw />
  ) : (
    <Sparkles />
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
    <div className="sg-banner sg-banner-amber">
      <AlertTriangle />
      <span className="sg-banner-text">
        The preview is outdated because settings changed.
      </span>
      <div className="sg-banner-actions">
        <button
          type="button"
          disabled={busy}
          onClick={onRegenerateFull}
          className="sg-mini-btn indigo"
        >
          <RefreshCw />
          Regenerate full guide
        </button>
        <button
          type="button"
          onClick={onRegenerateSections}
          className="sg-mini-btn"
        >
          <ListChecks />
          Regenerate changed sections only
        </button>
        <button
          type="button"
          onClick={onKeep}
          className="sg-mini-btn"
        >
          <X />
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
  enableVisualReferences,
  setEnableVisualReferences,
  dualExplanationMode = false,
  setDualExplanationMode,
  visualPilotReady = false,
  visualPilotNote = "",
  attachments,
  setAttachments,
  attachmentPreflights,
  setAttachmentPreflights,
  pageSelections,
  setPageSelections,
  materialExclusions,
  setMaterialExclusions,
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
            <p className="sg-note sg-note-warn">{modelNotice}</p>
          )}
          {selectedProvider?.discovery_error && (
            <p className="sg-note sg-note-err">
              Local discovery: {selectedProvider.discovery_error}
            </p>
          )}
          {selectedProvider?.supports_thinking && (
            <Toggle label="Qwen thinking mode" checked={qwenThinking} onChange={setQwenThinking} />
          )}
          <AttachmentsPicker
            attachments={attachments}
            setAttachments={setAttachments}
            attachmentPreflights={attachmentPreflights}
            setAttachmentPreflights={setAttachmentPreflights}
            pageSelections={pageSelections}
            setPageSelections={setPageSelections}
            materialExclusions={materialExclusions}
            setMaterialExclusions={setMaterialExclusions}
          />
          {attachments.some(isPaginatedFile) && (
            <MaterialCoverageControls
              exclusionInputs={attachments.map(
                (file) => materialExclusions[attachmentKey(file)] ?? ""
              )}
              onClearExclusions={() => setMaterialExclusions({})}
            />
          )}
          <Toggle label="Strict math" checked={strictMath} onChange={setStrictMath} tip={TOOLTIPS.strictMath} />
          {/* Slice 55/57: per-job opt-in for the experimental visual markdown image
              pilot. Disabled (and forced visually off) unless the server reports
              readiness (master pilot flag AND local figure extraction); even when
              checked the backend independently re-gates on both server switches. The
              calm note explains which server switch is missing when not ready. */}
          <Toggle
            label="Add one visual reference (experimental)"
            checked={isVisualPilotEffectivelyOn({ capabilityEnabled: visualPilotReady, requested: enableVisualReferences })}
            onChange={setEnableVisualReferences}
            tip={TOOLTIPS.visualReferences}
            disabled={!isVisualPilotToggleEnabled(visualPilotReady)}
          />
          {!visualPilotReady && visualPilotNote && (
            <p className="sg-note">{visualPilotNote}</p>
          )}
          {/* Slice 99: per-job opt-in for "Explain like I'm 10 / Exam answer" dual
              explanation mode. Default off; when on, generation adds a short
              beginner-friendly explanation plus a formal exam-ready answer for
              difficult / exam-important concepts. No server gate; the field is sent
              only when on (default request stays byte-equivalent). */}
          <Toggle
            label={DUAL_EXPLANATION_LABEL}
            checked={dualExplanationMode === true}
            onChange={setDualExplanationMode}
          />
          <p className="sg-note">{DUAL_EXPLANATION_HELPER}</p>
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
          <ChevronRight />
        </div>
        {source === "llm" && outlineEnabled && outlineCount > 0 && (
          <span className="pill pill-indigo" title="This guide will follow your outline">
            <ListChecks size={14} />
            Outline · {outlineCount}
          </span>
        )}
        <div className="sg-grow" />
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
          <Save />
          Save draft
        </button>
      </div>
    </>
  );
}

function FolderPicker({ folders = [], folderId, setFolderId, onCreateFolder }) {
  const [creating, setCreating] = useState(false);

  return (
    <div className="sg-folder">
      <label className="sg-folder-field" title="Choose a Library folder for this guide">
        <Folder />
        <span className="sg-folder-pre">Save to</span>
        <select
          value={folderId}
          onChange={(event) => setFolderId(event.target.value)}
        >
          <option value="unfiled">Unfiled</option>
          {folders.map((folder) => (
            <option key={folder.id} value={folder.id}>
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
          className="sg-folder-add"
        >
          <FolderPlus />
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
      <button type="button" className="sg-scrim-bg" style={{ position: "fixed", zIndex: 40, background: "transparent" }} aria-label="Close" onClick={onClose} />
      <div className="sg-popover">
        <div className="sg-popover-head">
          <span>New folder</span>
          <button type="button" onClick={onClose} className="sg-popover-x">
            <X />
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
          className="sg-input"
        />
        <div className="sg-swatches">
          {FOLDER_PRESET_COLORS.map((swatch) => {
            const active = swatch.toLowerCase() === color.toLowerCase();
            return (
              <button
                key={swatch}
                type="button"
                onClick={() => setColor(swatch)}
                aria-label={`Color ${swatch}`}
                className={`sg-swatch${active ? " active" : ""}`}
                style={{ backgroundColor: swatch }}
              />
            );
          })}
        </div>
        {error && <p className="sg-modal-err" style={{ marginTop: 8 }}>{error}</p>}
        <button
          type="button"
          onClick={submit}
          disabled={!name.trim() || busy}
          className="sg-mini-btn indigo"
          style={{ marginTop: 10, width: "100%", justifyContent: "center", height: 34 }}
        >
          {busy ? <Loader2 className="sg-spin" /> : <Check />}
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
      <div className="sg-template-row">
        <span className="sg-template-mark">
          {busy ? <Loader2 className="sg-spin" /> : <LayoutTemplate />}
        </span>
        <select
          value={selectedPreset || "custom"}
          disabled={busy}
          onChange={(event) => onApplyPreset?.(event.target.value)}
          className="sg-select"
        >
          <option value="custom">Custom (no template)</option>
          {presets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.name}
            </option>
          ))}
        </select>
      </div>
      <p className="field-hint">
        {active
          ? `${active.description} You can still edit the outline and style before generating.`
          : "Pick a template to pre-fill the outline and style. Custom leaves them as-is."}
      </p>
    </div>
  );
}

function DraftRestoreBanner({ draft, onRestore, onDiscard }) {
  return (
    <div className="sg-banner">
      <Clock />
      <span className="sg-banner-text">
        Restore unsaved draft from {formatDraftTime(draft.savedAt)}?
      </span>
      <div className="sg-banner-actions">
        <button type="button" onClick={onRestore} className="sg-mini-btn indigo">
          <RotateCcw />
          Restore
        </button>
        <button type="button" onClick={onDiscard} className="sg-mini-btn">
          <X />
          Discard
        </button>
      </div>
    </div>
  );
}

function BuilderTabIcon({ id }) {
  if (id === "outline") return Icon.library();
  if (id === "style") return Icon.styles();
  if (id === "preview") return Icon.eye();
  return Icon.builder();
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
    <div ref={tabsRef} className="sg-tabs" style={{ marginTop: 10 }}>
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
    <div className="sg-tab-stack">
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
    <div className="sg-tab-stack">
      <SectionHeader
        eyebrow="Preview"
        title="Exports and artifacts"
        description="Inspect the latest generated job and choose what to preview or download."
      />
      <div className="sg-infocard-grid">
        <InfoCard label="Preview" value={previewFormat === "sample" ? "Sample" : previewFormat.toUpperCase()} />
        <InfoCard label="Status" value={result?.status || "No generated job"} />
        <InfoCard label="Artifacts" value={`${artifacts.length} available`} />
      </div>
      <div className="sg-fpanel">
        <FieldLabel>Preview format</FieldLabel>
        <div className="sg-seg-row" style={{ marginTop: 8 }}>
          {["pdf", "html"].map((format) => (
            <button
              key={format}
              type="button"
              disabled={!result}
              onClick={() => setPreviewFormat(format)}
              className={`sg-seg-btn${previewFormat === format ? " active" : ""}`}
            >
              {format.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="sg-fpanel">
        <FieldLabel>Artifact availability</FieldLabel>
        {result ? (
          <div className="sg-avail-grid" style={{ marginTop: 8 }}>
            {Object.entries(artifactLabels).map(([name, artifact]) => {
              const available = Boolean(artifactUrls[name]);
              const AvailIcon = artifact.icon;
              return (
                <div key={name} className={`sg-avail-row ${available ? "ready" : "missing"}`}>
                  <span className="sg-avail-name">
                    <AvailIcon />
                    {artifact.label}
                  </span>
                  <span className="sg-avail-state">{available ? "Ready" : "Missing"}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="sg-hint-block" style={{ marginTop: 8 }}>
            Generate a guide first to enable PDF/HTML preview and artifact downloads.
          </div>
        )}
      </div>
      {result && (
        <AttachedSourcesSummary result={result} />
      )}
      {result && (
        <div className="sg-fpanel">
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
  const sz = size === "lg" ? "lg" : "sm";
  if (icon) {
    return (
      <span className={`sg-prov-badge ${sz}`} title={label}>
        <img
          src={icon}
          alt={`${label} logo`}
          loading="lazy"
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
        />
      </span>
    );
  }
  return <span className={`sg-prov-badge text ${sz}`}>{label}</span>;
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
      className={`sg-pick-card${selected ? " active" : ""}`}
    >
      <div className="sg-pick-head">
        <ProviderBadge provider={preset.provider} size="lg" />
        <div className="sg-pick-min">
          {modelLabel && (
            <div className="sg-pick-model" title={modelLabel}>
              {modelLabel}
            </div>
          )}
          <div className="sg-pick-name">{preset.name}</div>
        </div>
        {!available && <span className="sg-pick-tag">Unavailable</span>}
        {selected && <Check className="sg-pick-check" />}
      </div>
      {preset.purpose && <p className="sg-pick-purpose">{preset.purpose}</p>}
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
      <p className="sg-fpanel-sub">
        A full model-tuned system prompt with its own sampling params. Overrides the style below.
      </p>
      <div className="sg-pick-grid" style={{ marginTop: 8 }}>
        <button
          type="button"
          aria-pressed={!generatorPreset}
          onClick={() => onSelectGeneratorPreset?.("")}
          className={`sg-pick-card${!generatorPreset ? " active" : ""}`}
        >
          <div className="sg-pick-head">
            <span className="sg-pick-title">None</span>
            {!generatorPreset && <Check className="sg-pick-check" />}
          </div>
          <p className="sg-pick-purpose">
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
        <div className="sg-preset-note">
          <div>
            Tuned for <span className="accent">{active.model_hint}</span> · {fmtPresetParams(active.params)}
          </div>
          {compat.warn && (
            <div className="sg-preset-warn">
              <AlertTriangle />
              <span>
                This preset is tuned for {compat.hint}. It may still work with{" "}
                <span className="strong">{model || "your selected model"}</span>, but {compat.hint} is
                recommended. <span className="strong">Your model selection still applies.</span>
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
    <div className="sg-mini-style-grid" style={{ marginTop: 6 }}>
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
    <div className="sg-group-label">
      <span>{children}</span>
      <span className="rule" />
    </div>
  );
}

function LengthControls({ length, setLength }) {
  return (
    <div>
      <FieldLabel tip={TOOLTIPS.length}>Length</FieldLabel>
      <div className="sg-len-grid" style={{ marginTop: 6 }}>
        {lengthOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setLength(option.id)}
            className={`sg-len-card${length === option.id ? " active" : ""}`}
          >
            <div className="sg-len-label">{option.label}</div>
            <div className="sg-len-meta">{option.meta}</div>
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
    <div className="sg-axis-grid">
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
      <div className="sg-seg-row" style={{ marginTop: 6 }}>
        {options.map((option) => (
          <button
            key={option.value || "auto"}
            type="button"
            onClick={() => onChange(option.value)}
            className={`sg-seg-btn${value === option.value ? " active" : ""}`}
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
      <div className="sg-section-groups" style={{ marginTop: 6 }}>
        {SECTION_GROUPS.map((group) => (
          <div key={group.title}>
            <StyleGroupLabel>{group.title}</StyleGroupLabel>
            <div className="sg-pill-row" style={{ marginTop: 6 }}>
              {group.keys.map((entry) => {
                const active = Boolean(includeSections[entry.key]);
                const chip = (
                  <button
                    type="button"
                    onClick={() => toggleSection(entry.key)}
                    className={`sg-pill-toggle${active ? " active" : ""}`}
                  >
                    {active && <Check />}
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
        <span className="sg-drop-mark">{Icon.upload()}</span>
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

// Stable per-file signature for the preflight result map. Two adds of the same
// underlying file collapse to the same key; close enough for the picker.
function attachmentKey(file) {
  return `${file.name}-${file.size}-${file.lastModified ?? 0}`;
}

function isPdfFile(file) {
  return (file?.name || "").toLowerCase().endsWith(".pdf");
}

// Slice 87: only paginated source types (PDF pages / PPTX slides) get the
// per-attachment "exclude pages/slides" control. Other types have no page/slide
// concept, so the control is hidden for them (the backend still safely ignores
// any selection that lands on a non-paginated attachment).
function isPaginatedFile(file) {
  const name = (file?.name || "").toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".pptx");
}

// Format normalized 1-based inclusive ranges back to a compact human string:
// [[1,20],[35,42]] -> "1-20, 35-42"; a single-page range [[5,5]] -> "5".
function formatPageRanges(ranges) {
  if (!Array.isArray(ranges)) return "";
  return ranges
    .map(([start, end]) => (start === end ? `${start}` : `${start}-${end}`))
    .join(", ");
}

// Parse a user-typed page spec like "1-20" or "1-20, 35, 40-42" into 1-based
// inclusive [[start, end], ...]. Returns { ranges } on success or { error } on a
// bad token. A single page "5" becomes [5, 5]. `pageCount` (when known) only drives
// a soft `warning` — out-of-range pages are not rejected here (the backend
// normalizes/merges and extraction safely drops pages past the real page count).
function parsePageRanges(input, pageCount) {
  const tokens = String(input || "")
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean);
  if (tokens.length === 0) {
    return { error: "Enter at least one page or range, e.g. 1-20 or 1-20, 35-42." };
  }
  const ranges = [];
  for (const token of tokens) {
    const range = token.match(/^(\d+)\s*-\s*(\d+)$/);
    const single = token.match(/^(\d+)$/);
    let start;
    let end;
    if (range) {
      start = parseInt(range[1], 10);
      end = parseInt(range[2], 10);
    } else if (single) {
      start = parseInt(single[1], 10);
      end = start;
    } else {
      return { error: `Couldn't read "${token}". Use formats like 1-20, 5, or 1-20, 35-42.` };
    }
    if (start < 1 || end < 1) {
      return { error: "Page numbers must be 1 or greater." };
    }
    if (start > end) {
      return { error: `Range "${token}" must have start ≤ end.` };
    }
    ranges.push([start, end]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const exceeds = Number.isFinite(pageCount) && pageCount > 0 && ranges.some(([, end]) => end > pageCount);
  return {
    ranges,
    warning: exceeds
      ? `Some pages are beyond this ${pageCount}-page PDF; those pages will be ignored.`
      : ""
  };
}

const SCANNED_FLAG_LABEL = {
  text: "text PDF",
  mixed: "mixed text + scanned",
  image_heavy: "image-heavy / scanned"
};

function AttachmentsPicker({
  attachments,
  setAttachments,
  attachmentPreflights = {},
  setAttachmentPreflights,
  pageSelections = {},
  setPageSelections,
  materialExclusions = {},
  setMaterialExclusions
}) {
  // Slice 87: store the raw "exclude pages/slides" text per attachment, keyed by the
  // stable attachmentKey(file) signature (not the index, so it survives reordering /
  // removal). It is converted to safe `attachment_<index>` envelope keys only at
  // submit time. Empty/whitespace drops the entry — no exclusions for that file.
  function setFileExclusion(file, value) {
    const key = attachmentKey(file);
    setMaterialExclusions?.((current) => {
      const next = { ...current };
      if (!value || !value.trim()) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
  }
  // Page selections are keyed by the original upload filename (file.name) — the
  // exact key the backend matches attachments on. Setting `ranges` to null/[] drops
  // the entry, which means "all pages" again.
  function setFileSelection(name, ranges) {
    setPageSelections?.((current) => {
      const next = { ...current };
      if (!ranges || ranges.length === 0) {
        delete next[name];
      } else {
        next[name] = ranges;
      }
      return next;
    });
  }
  // Read-only preflight (see docs/LARGE_PDF_PREFLIGHT_DESIGN.md, Slice 2). Runs
  // per added PDF; the result is stored beside the selected file only and never
  // sent to a job yet. A failure degrades to a soft warning — it never blocks
  // generation (only a "blocked" verdict does, gated in validateInputs).
  function runPreflight(file) {
    const key = attachmentKey(file);
    setAttachmentPreflights?.((current) => ({ ...current, [key]: { status: "checking" } }));
    preflightPdf(file)
      .then((report) => {
        setAttachmentPreflights?.((current) => ({ ...current, [key]: { status: "done", report } }));
      })
      .catch(() => {
        setAttachmentPreflights?.((current) => ({ ...current, [key]: { status: "error" } }));
      });
  }

  function addFiles(fileList) {
    const incoming = Array.from(fileList || []);
    if (incoming.length === 0) return;
    const room = Math.max(0, 5 - attachments.length);
    const added = incoming.slice(0, room);
    if (added.length === 0) return;
    setAttachments((current) => [...current, ...added].slice(0, 5));
    added.forEach((file) => {
      if (isPdfFile(file)) runPreflight(file);
    });
  }

  function removeFile(index) {
    const target = attachments[index];
    setAttachments((current) => current.filter((_, fileIndex) => fileIndex !== index));
    if (target && setAttachmentPreflights) {
      const key = attachmentKey(target);
      setAttachmentPreflights((current) => {
        if (!(key in current)) return current;
        const next = { ...current };
        delete next[key];
        return next;
      });
    }
    // Drop this file's page selection too — but only if no OTHER remaining
    // attachment shares the same filename (selections are keyed by name, so a
    // duplicate-named sibling legitimately still uses it).
    if (target && setPageSelections) {
      const stillPresent = attachments.some(
        (file, fileIndex) => fileIndex !== index && file.name === target.name
      );
      if (!stillPresent) setFileSelection(target.name, null);
    }
    // Drop this file's material exclusions too. Keyed by attachmentKey (a per-file
    // signature), so a removed file's entry is always safe to delete directly.
    if (target && setMaterialExclusions) {
      const key = attachmentKey(target);
      setMaterialExclusions((current) => {
        if (!(key in current)) return current;
        const next = { ...current };
        delete next[key];
        return next;
      });
    }
  }

  function acknowledge(file) {
    const key = attachmentKey(file);
    setAttachmentPreflights?.((current) => {
      const entry = current[key];
      if (!entry) return current;
      return { ...current, [key]: { ...entry, acknowledged: true } };
    });
  }

  return (
    <div className="sg-attachments">
      <FieldLabel tip={TOOLTIPS.attachments}>Attachments</FieldLabel>
      <label className="sg-attach-drop">
        <span className="sg-attach-mark">
          <Upload />
        </span>
        <span className="sg-attach-drop-body">
          <span className="sg-attach-drop-title">Attach source files</span>
          <span className="sg-attach-drop-sub">txt, md, csv, tsv, docx, pptx, pdf · max 5 files</span>
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
        <div className="sg-attach-list">
          {attachments.map((file, index) => (
            <div key={`${file.name}-${file.size}-${index}`}>
              <div className="sg-attach-row">
                <FileText className="sg-attach-file-icon" />
                <span className="sg-attach-name">{file.name}</span>
                <span className="sg-attach-size">{formatFileSize(file.size)}</span>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="sg-mini-btn"
                >
                  Remove
                </button>
              </div>
              {isPdfFile(file) && (
                <PreflightCard
                  entry={attachmentPreflights[attachmentKey(file)]}
                  selection={pageSelections[file.name]}
                  onRemove={() => removeFile(index)}
                  onAcknowledge={() => acknowledge(file)}
                  onSelectFirstN={(n) => setFileSelection(file.name, [[1, n]])}
                  onSelectRange={(ranges) => setFileSelection(file.name, ranges)}
                  onClearSelection={() => setFileSelection(file.name, null)}
                />
              )}
              {isPaginatedFile(file) && (
                <MaterialExclusionField
                  value={materialExclusions[attachmentKey(file)] ?? ""}
                  onChange={(value) => setFileExclusion(file, value)}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Closed-vocabulary local hints → short human copy. Keeps the warning surface
// generic: it never echoes the raw token the user typed (no-leak invariant).
const MATERIAL_EXCLUSION_HINTS = {
  page_token_invalid: "Some entries weren't valid page numbers and were ignored.",
  page_range_invalid: "Some ranges weren't valid and were ignored.",
  page_range_reversed: "A reversed range (e.g. 6-2) was ignored.",
  page_number_invalid: "Page numbers must be 1 or greater; those were ignored."
};

// Slice 87: per-attachment "exclude pages/slides" control. Pure-presentational —
// it owns no envelope state; the parent stores the raw text keyed by attachmentKey
// and converts everything to the safe `attachment_<index>` envelope at submit time.
// Live parse drives a calm "Excluding pages …" confirmation plus generic hint text
// for any invalid tokens (never the raw value).
function MaterialExclusionField({ value, onChange }) {
  const { pages, warnings } = parsePageListInput(value);
  return (
    <div className="sg-attach-exclude">
      <label className="sg-attach-exclude-label">
        Exclude pages/slides
        <input
          type="text"
          value={value}
          inputMode="numeric"
          placeholder="e.g. 2, 4-6, 10"
          onChange={(event) => onChange(event.target.value)}
          className="sg-attach-exclude-input"
        />
      </label>
      <p className="sg-attach-exclude-help">
        These pages will be skipped from guide content and visual/table planning.
      </p>
      {pages.length > 0 && (
        <p className="sg-attach-exclude-note">Excluding pages {pages.join(", ")}.</p>
      )}
      {warnings.map((token) => (
        <p key={token} className="sg-attach-exclude-warn">
          {MATERIAL_EXCLUSION_HINTS[token] ?? "Some entries were ignored."}
        </p>
      ))}
    </div>
  );
}

// Slice 89: compact Builder-side material coverage review/warning block, rendered
// once below the attachment list whenever at least one paginated attachment is
// present. Purely presentational over the safe positional summary — it shows the
// active/inactive state, attachment + total excluded page counts, a generic invalid-
// token hint (never the raw value), the scope explanation, and honest limitation
// copy (full figure insertion / table reconstruction are NOT enabled yet). The
// optional "Clear exclusions" button resets the parent's raw-input state; it never
// changes the submit payload shape (the envelope is still built at submit time).
function MaterialCoverageControls({ exclusionInputs = [], onClearExclusions }) {
  const summary = buildBuilderMaterialCoverageSummary({ exclusionInputs });
  const attachmentWord = summary.attachmentsWithExclusions === 1 ? "attachment has" : "attachments have";
  return (
    <div className="sg-coverage-controls">
      <div className="sg-coverage-controls-head">
        <Gauge className="sg-coverage-controls-icon" />
        <span className="sg-coverage-controls-title">Page/slide coverage</span>
        <span className={`sg-tag ${summary.active ? "sg-tag-green" : "sg-tag-slate"}`}>
          {summary.active ? "Active" : "No exclusions"}
        </span>
        {summary.active && onClearExclusions && (
          <button type="button" className="sg-mini-btn" onClick={onClearExclusions}>
            Clear exclusions
          </button>
        )}
      </div>
      <p className="sg-coverage-controls-summary">
        {summary.active
          ? `${summary.attachmentsWithExclusions} ${attachmentWord} exclusions. ${summary.totalExcludedPages} pages/slides will be skipped.`
          : "No page/slide exclusions set. All pages/slides will be included."}
      </p>
      {summary.hasInvalidTokens && (
        <p className="sg-coverage-controls-warn">
          Some entries were ignored. Use numbers or ranges like 2, 4-6, 10.
        </p>
      )}
      <p className="sg-coverage-controls-help">
        Exclusions apply to guide source text and visual/table coverage planning.
      </p>
      <p className="sg-coverage-controls-note">
        Full figure insertion and table reconstruction are not enabled yet; this job will still record coverage signals for them.
      </p>
    </div>
  );
}

// Compact warning surface for a single PDF's preflight result. Stays quiet for
// ordinary (verdict "ok", no warnings) PDFs; shows an amber card for "warn" and
// a red, non-dismissable card for "blocked". For "warn" it offers the real
// page-selection actions (Slice 5): "Process first N pages" and "Choose page
// range" (inline editor). An active selection collapses the warning into a calm
// "Using pages …" bar with a "Use all pages" reset.
function PreflightCard({
  entry,
  selection,
  onRemove,
  onAcknowledge,
  onSelectFirstN,
  onSelectRange,
  onClearSelection
}) {
  const [rangeOpen, setRangeOpen] = useState(false);
  const [rangeText, setRangeText] = useState("");
  const [rangeError, setRangeError] = useState("");

  if (!entry) return null;

  if (entry.status === "checking") {
    return (
      <div className="sg-pf sg-pf-quiet">
        <Loader2 className="sg-spin" style={{ width: 13, height: 13 }} />
        Inspecting PDF…
      </div>
    );
  }

  if (entry.status === "error") {
    return (
      <div className="sg-pf sg-pf-warn">
        <div className="sg-pf-row">
          <AlertTriangle />
          <span>Could not inspect this PDF; it will be processed normally.</span>
        </div>
      </div>
    );
  }

  const report = entry.report || {};
  const verdict = report.verdict || "ok";
  const warnings = report.warnings || [];
  const blocked = verdict === "blocked";
  const hasIssue = verdict === "warn" || blocked || warnings.length > 0;
  const pageCount = Number.isFinite(report.page_count) ? report.page_count : null;
  const selectionActive = Array.isArray(selection) && selection.length > 0;

  const allowed = report.allowed_actions || [];
  const showFirstN = allowed.includes("process_first_n");
  const showRange = allowed.includes("choose_page_range");
  const defaultFirstN = report.limits?.default_first_n ?? 20;
  // Cap "first N" by the real page count when we know it, so a 12-page deck never
  // asks for pages 1-20. N stays 1-based inclusive: [[1, N]].
  const firstN = pageCount ? Math.min(defaultFirstN, pageCount) : defaultFirstN;

  function openRangeEditor() {
    setRangeText(selectionActive ? formatPageRanges(selection) : `1-${firstN}`);
    setRangeError("");
    setRangeOpen(true);
  }

  function applyRange() {
    const { ranges, error } = parsePageRanges(rangeText, pageCount);
    if (error) {
      setRangeError(error);
      return;
    }
    onSelectRange?.(ranges);
    setRangeError("");
    setRangeOpen(false);
  }

  function cancelRange() {
    setRangeError("");
    setRangeOpen(false);
  }

  // Calm confirmation shown whenever a selection is active. "blocked" PDFs never
  // carry a selection, so this only appears for ok/warn files.
  const selectionBar = selectionActive ? (
    <div className="sg-pf sg-pf-ok">
      <div className="sg-pf-bar">
        <Check style={{ width: 13, height: 13 }} />
        <span style={{ fontWeight: 600, color: "var(--text)" }}>Using pages {formatPageRanges(selection)}</span>
        {pageCount && <span style={{ opacity: 0.8 }}>of {pageCount}</span>}
        <div className="sg-pf-spacer">
          {showRange && (
            <button type="button" onClick={openRangeEditor} className="sg-mini-btn">
              Edit range
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              onClearSelection?.();
              cancelRange();
            }}
            className="sg-mini-btn"
          >
            Use all pages
          </button>
        </div>
      </div>
    </div>
  ) : null;

  // Inline range editor, opened from the warning card or the selection bar.
  const rangeEditor = rangeOpen ? (
    <div className="sg-range-editor">
      <label>
        Pages to include{pageCount ? ` (1-${pageCount})` : ""}
      </label>
      <input
        type="text"
        value={rangeText}
        onChange={(event) => {
          setRangeText(event.target.value);
          setRangeError("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            applyRange();
          }
        }}
        placeholder="e.g. 1-20 or 1-20, 35-42"
      />
      {rangeError && <p className="sg-range-err">{rangeError}</p>}
      <p className="sg-range-help">
        1-based and inclusive; separate multiple ranges with commas.
      </p>
      <div className="sg-pf-actions">
        <button type="button" onClick={applyRange} className="sg-mini-btn indigo">
          Apply
        </button>
        <button type="button" onClick={cancelRange} className="sg-mini-btn">
          Cancel
        </button>
      </div>
    </div>
  ) : null;

  // Main body: blocked always shows the red card; warn shows the amber card unless
  // a selection is active or the user dismissed it.
  const showFullWarning = blocked || (hasIssue && !selectionActive && !entry.acknowledged);
  const showCollapsedAck =
    entry.acknowledged && !blocked && !selectionActive && !showFullWarning;

  // Nothing to surface: ordinary PDF, no selection, editor closed.
  if (!selectionBar && !rangeEditor && !showFullWarning && !showCollapsedAck) {
    return null;
  }

  const facts = [];
  if (report.file_size_mb) facts.push(`${report.file_size_mb} MB`);
  if (report.page_count) facts.push(`${report.page_count} pages`);
  if (report.scanned_flag && report.scanned_flag !== "unknown") {
    facts.push(SCANNED_FLAG_LABEL[report.scanned_flag] || report.scanned_flag);
  }
  if (report.is_estimate && report.ocr_pages_estimate) {
    facts.push(`~${report.ocr_pages_estimate} OCR pages (est.)`);
  }

  const recommended = blocked
    ? "Remove it or upload an unlocked, repaired copy."
    : showFirstN || showRange
      ? `Recommended: process the first ${firstN} pages, or choose a page range to limit OCR/extraction.`
      : "";

  const ToneIcon = blocked ? AlertCircle : AlertTriangle;

  return (
    <>
      {selectionBar}
      {rangeEditor}
      {showCollapsedAck && (
        <div className="sg-pf sg-pf-quiet">
          <Check style={{ width: 13, height: 13, color: "var(--green)" }} />
          Continuing with this PDF despite the warning.
        </div>
      )}
      {showFullWarning && (
        <div className={`sg-pf ${blocked ? "sg-pf-block" : "sg-pf-warn"}`}>
          <div className="sg-pf-row">
            <ToneIcon />
            <div style={{ minWidth: 0, flex: 1 }}>
              <p className="sg-pf-title">
                {blocked ? "This PDF can't be processed" : "Heads up before you generate"}
              </p>
              {facts.length > 0 && (
                <p className="sg-pf-facts">{facts.join(" · ")}</p>
              )}
              {warnings.length > 0 && (
                <ul className="sg-pf-list">
                  {warnings.map((message, idx) => (
                    <li key={idx}>• {message}</li>
                  ))}
                </ul>
              )}
              {recommended && <p className="sg-pf-rec">{recommended}</p>}

              <div className="sg-pf-actions">
                {!blocked && (
                  <button type="button" onClick={onAcknowledge} className="sg-mini-btn">
                    Continue anyway
                  </button>
                )}
                {showFirstN && (
                  <button type="button" onClick={() => onSelectFirstN?.(firstN)} className="sg-mini-btn indigo">
                    Process first {firstN} pages
                  </button>
                )}
                {showRange && (
                  <button type="button" onClick={openRangeEditor} className="sg-mini-btn indigo">
                    Choose page range
                  </button>
                )}
                <button type="button" onClick={onRemove} className="sg-mini-btn">
                  Remove file
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MiniStyle({ style, active, onClick }) {
  const StyleIcon = style.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`sg-mini-style${active ? " active" : ""}`}
    >
      <span className="glyph">
        <StyleIcon />
      </span>
      <span className="lbl">{style.label}</span>
    </button>
  );
}

function OptionCard({ option, active, disabled = false, onClick }) {
  const OptionIcon = option.icon;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`sg-option-card ${active ? "active" : ""}`}
    >
      <span className="sg-option-mark">
        <OptionIcon />
      </span>
      <span className="sg-option-body">
        <span className="sg-option-title">{option.label}</span>
        <span className="sg-option-meta">{option.meta}</span>
      </span>
    </button>
  );
}

function SectionHeader({ eyebrow, title, description }) {
  return (
    <div className="sg-shead">
      <div className="sg-shead-eyebrow">{eyebrow}</div>
      <h2 className="sg-shead-title">{title}</h2>
      <p className="sg-shead-desc">{description}</p>
    </div>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="sg-infocard">
      <div className="sg-infocard-k">{label}</div>
      <div className="sg-infocard-v">{value}</div>
    </div>
  );
}

function MetaRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[9px] border px-3 py-2" style={{ borderColor: "var(--card-border)", background: "var(--card-2)" }}>
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <span className="truncate font-mono text-[11px] font-semibold" style={{ color: "var(--text)" }}>{value}</span>
    </div>
  );
}

function PreviewFormatTabs({ result, previewFormat, setPreviewFormat }) {
  return (
    <div className="sg-format-tabs">
      {["pdf", "html"].map((format) => (
        <button
          key={format}
          type="button"
          disabled={!result}
          onClick={() => setPreviewFormat(format)}
          className={`sg-format-tab${previewFormat === format ? " active" : ""}`}
        >
          {format.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function ArtifactDownloadGrid({ artifacts, compact = false }) {
  return (
    <div className={`sg-dl-grid ${compact ? "" : "cols"}`}>
      {artifacts.length === 0 && (
        <div className="sg-dl-empty">
          No artifacts available yet.
        </div>
      )}
      {artifacts.map(([name, url]) => {
        const artifact = artifactLabels[name];
        const ArtifactIcon = artifact.icon;
        const label = name === "final.html" ? "View HTML" : name === "final.pdf" ? "Download PDF" : artifact.label;
        return (
          <a key={name} href={apiUrl(url)} className="sg-dl-link">
            <span className="sg-dl-label">
              <ArtifactIcon className="sg-dl-lead" />
              {label}
            </span>
            <Download className="sg-dl-trail" />
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
    <div className={`sg-sources${compact ? " compact" : ""}`}>
      <div className="sg-sources-head">
        <FieldLabel>Attached sources</FieldLabel>
        <div className="sg-sources-pills">
          <span className="pill pill-green">
            <span className="dot" />
            {attachments.length} {attachments.length === 1 ? "source" : "sources"}
          </span>
          {warnings.length > 0 && (
            <span className="pill pill-amber">
              <span className="dot" />
              {warnings.length} warning{warnings.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>
      <div className={`sg-sources-list${compact ? " scroll-y" : ""}`}>
        {attachments.map((attachment, index) => {
          const itemWarnings = attachment.warnings ?? [];
          const extracted = Number(attachment.extracted_chars || 0);
          return (
            <div key={`${attachment.filename}-${index}`} className="sg-source-item">
              <div className="sg-source-item-top">
                <span className="sg-source-item-name">{attachment.filename}</span>
                <span className={`pill ${attachment.status === "extracted" ? "pill-green" : "pill-amber"}`}>
                  <span className="dot" />
                  {attachment.status || "unknown"}
                </span>
              </div>
              <div className="sg-source-item-meta">
                <span>{attachment.mode || attachment.extension || "unsupported"}</span>
                <span>{extracted.toLocaleString()} chars</span>
                {attachment.truncated && <span>truncated</span>}
              </div>
              {itemWarnings.length > 0 && (
                <div className="sg-source-warn">
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
          <div className="sg-paper-pad">
            <div className="sg-paper-eyebrow">
              {styleLabel} · {lengthLabel}
            </div>
            <div className="sg-paper-title">{title}</div>
            <div className="sg-paper-note">Sample preview · not sent to backend</div>
            <div className="sg-paper-rule" />
            <SamplePreview />
            <div className="sg-paper-foot">
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
          <div className="sg-download-head">
            <span className="t">Downloads</span>
            <span className="n">{artifacts.length} files</span>
          </div>
          <ArtifactDownloadGrid artifacts={artifacts} compact />
        </div>
      )}

      {result && <AttachedSourcesSummary result={result} compact />}

      <div className="sg-preview-actions">
        <a
          href={primaryPdf ? apiUrl(primaryPdf) : undefined}
          className={`sg-pa${primaryPdf ? "" : " disabled"}`}
        >
          <Download />
          Export PDF
        </a>
        <button type="button" onClick={onOpenDetails} className="sg-pa">
          <Share2 />
          Details
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
        className="sg-paper-frame"
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
        className="sg-paper-frame"
      />
    );
  }

  return <PreviewUnavailable />;
}

function PreviewUnavailable() {
  return (
    <div className="sg-paper-empty">
      <div>
        <FileText />
        <p className="t">Preview not available yet.</p>
        <p className="s">Choose PDF or HTML after the artifact is generated.</p>
      </div>
    </div>
  );
}

function SamplePreview() {
  return (
    <>
      <div className="sg-paper-h">1 · Definitions</div>
      <div className="sg-paper-p">
        A limit describes the value a function approaches as its input approaches some value c.
      </div>
      <div className="sg-paper-eq">lim x→c f(x) = L</div>
      <div className="sg-paper-h">2 · Continuity</div>
      <div className="sg-paper-p">
        f is continuous at c if lim x→c f(x) = f(c). Three conditions must hold:
      </div>
      <ul className="sg-paper-ul">
        <li>f(c) is defined</li>
        <li>The limit exists</li>
        <li>They are equal</li>
      </ul>
      <div className="sg-paper-cue">
        <div className="cue-label">MEMORY CUE</div>
        <div className="cue-body">
          <strong>D-L-E</strong>: Defined · Limit exists · Equal
        </div>
      </div>
    </>
  );
}

function FieldLabel({ children, tip, tipLabel }) {
  return (
    <div className="sg-field-label">
      <span>{children}</span>
      {tip && <InfoTip text={tip} label={tipLabel || (typeof children === "string" ? children : "")} />}
    </div>
  );
}

function Toggle({ label, checked, onChange, tip, disabled = false }) {
  return (
    <label className="sg-toggle" data-disabled={disabled ? "true" : undefined}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
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
    <span className="sg-infotip">
      <button
        type="button"
        aria-label={label ? `Help: ${label}` : "More information"}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
      >
        <Info />
      </button>
      <span role="tooltip" className="sg-infotip-bubble">
        {text}
      </span>
    </span>
  );
}

function ErrorMessage({ error }) {
  return (
    <div className="sg-error">
      <AlertCircle />
      <div>
        <p style={{ fontWeight: 600 }}>{error.message || "Could not generate guide."}</p>
        {error.details && (
          <details style={{ marginTop: 8 }}>
            <summary>Details</summary>
            <pre>{error.details}</pre>
          </details>
        )}
      </div>
    </div>
  );
}

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
  enableVisualReferences = false,
  dualExplanationMode = false,
  attachments,
  length,
  includeSections = {},
  outputDepth = "",
  difficulty = "",
  folderId = "unfiled",
  outline = null,
  pageSelections = {},
  materialPageSelections = null
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
        enableVisualReferences,
        dualExplanationMode,
        attachments,
        length,
        includeSections,
        outputDepth,
        difficulty,
        folderId,
        outline,
        pageSelections,
        materialPageSelections
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
  enableVisualReferences = false,
  dualExplanationMode = false,
  attachments = [],
  length,
  includeSections = {},
  outputDepth = "",
  difficulty = "",
  folderId = "unfiled",
  outline = null,
  pageSelections = {},
  materialPageSelections = null
}) {
  const hasOutline = outline?.enabled && (outline.sections || []).some((section) => section.title?.trim());
  // PDF page selections (Slice 3): include only when the Builder actually carries a
  // selection. No page-range UI exists yet, so this is {} for every normal request
  // and the field is omitted entirely — keeping the default request byte-equivalent.
  const hasPageSelections = pageSelections && Object.keys(pageSelections).length > 0;
  // Slice 87: only attach the per-attachment material exclusions envelope when it
  // carries at least one active exclusion, so a default request stays unchanged.
  // The backend re-normalizes it; we never send filenames/paths as keys.
  const hasMaterialSelections = hasActiveMaterialSelections(materialPageSelections);
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
    ...(hasPageSelections ? { page_selections: pageSelections } : {}),
    ...(hasMaterialSelections ? { material_page_selections: materialPageSelections } : {}),
    // Slice 55: only send the per-job visual-pilot opt-in when actually on, so a
    // default/opted-out request stays byte-equivalent to before this slice. The
    // backend env master switch still gates whether it has any effect.
    ...visualPilotPayloadFields(enableVisualReferences),
    // Slice 99: only send the per-job dual-explanation opt-in when actually on, so a
    // default/opted-out request stays byte-equivalent to before this slice.
    ...dualExplanationPayloadFields(dualExplanationMode),
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
