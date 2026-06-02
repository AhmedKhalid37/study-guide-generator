import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  Copy,
  Loader2,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Wand2,
  X
} from "lucide-react";
import {
  createStyle,
  deleteStyle,
  generateStyle,
  getOptions,
  getStyle,
  getStyles,
  updateStyle
} from "../api/client";
import {
  BoltGlyph,
  BookGlyph,
  DocGlyph,
  LeafGlyph,
  ListGlyph,
  SparkleGlyph,
  Tile,
  TrophyGlyph
} from "./ClaudeIcons";

const REQUIRED_PLACEHOLDERS = ["{title}", "{mode}", "{source}"];

const BUILTIN_GLYPHS = {
  basic_study_guide: DocGlyph,
  baby_steps: LeafGlyph,
  exam_cram: BoltGlyph,
  mcq_training: ListGlyph,
  final_solution: TrophyGlyph,
  claude_study_guide: SparkleGlyph,
  master_longform: BookGlyph
};

function glyphForStyle(style) {
  return BUILTIN_GLYPHS[style.id] || SparkleGlyph;
}

function missingPlaceholders(content) {
  return REQUIRED_PLACEHOLDERS.filter((token) => !content.includes(token));
}

const emptyEditor = {
  open: false,
  mode: "create",
  id: null,
  name: "",
  description: "",
  tags: "",
  content: "",
  baseStyle: null,
  saving: false,
  error: null
};

export default function StylesWorkspace({ selectedStyle, onSelectStyle, onOpenBuilder }) {
  const [data, setData] = useState({ builtin: [], custom: [] });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [editor, setEditor] = useState(emptyEditor);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [providers, setProviders] = useState([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getStyles();
      setData({ builtin: result.builtin ?? [], custom: result.custom ?? [] });
      setLoadError(null);
    } catch (error) {
      setLoadError(error.message || "Could not load styles.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    getOptions()
      .then((options) => {
        if (cancelled) return;
        const details = options?.provider_details ?? options?.providers_v2 ?? [];
        setProviders(details.filter((item) => item.configured));
      })
      .catch(() => !cancelled && setProviders([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const openCreate = useCallback(() => {
    setEditor({ ...emptyEditor, open: true, mode: "create" });
  }, []);

  const openClone = useCallback(async (style) => {
    setEditor({ ...emptyEditor, open: true, mode: "create", saving: true });
    try {
      const full = await getStyle(style.id);
      setEditor({
        ...emptyEditor,
        open: true,
        mode: "create",
        name: `${full.name} (copy)`.slice(0, 120),
        description: full.description || "",
        content: full.content || "",
        baseStyle: style.id
      });
    } catch (error) {
      setEditor({ ...emptyEditor, open: true, mode: "create", error: error.message });
    }
  }, []);

  const openEdit = useCallback(async (style) => {
    setEditor({ ...emptyEditor, open: true, mode: "edit", id: style.id, saving: true });
    try {
      const full = await getStyle(style.id);
      setEditor({
        ...emptyEditor,
        open: true,
        mode: "edit",
        id: full.id,
        name: full.name || "",
        description: full.description || "",
        tags: (full.tags || []).join(", "),
        content: full.content || "",
        baseStyle: full.base_style || null
      });
    } catch (error) {
      setEditor({ ...emptyEditor, open: true, mode: "edit", id: style.id, error: error.message });
    }
  }, []);

  const closeEditor = useCallback(() => setEditor(emptyEditor), []);

  const handleSave = useCallback(
    async (payload) => {
      setEditor((current) => ({ ...current, saving: true, error: null }));
      try {
        const tags = payload.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean);
        let saved;
        if (payload.mode === "edit") {
          saved = await updateStyle(payload.id, {
            name: payload.name,
            description: payload.description,
            content: payload.content,
            tags
          });
        } else {
          saved = await createStyle({
            name: payload.name,
            description: payload.description,
            content: payload.content,
            baseStyle: payload.baseStyle,
            tags
          });
        }
        await refresh();
        onSelectStyle?.(saved.id);
        setEditor(emptyEditor);
      } catch (error) {
        setEditor((current) => ({ ...current, saving: false, error: error.message || "Could not save style." }));
      }
    },
    [refresh, onSelectStyle]
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await deleteStyle(deleteTarget.id);
      setDeleteTarget(null);
      await refresh();
    } catch (error) {
      setDeleteTarget((current) => (current ? { ...current, error: error.message } : current));
    }
  }, [deleteTarget, refresh]);

  const useStyle = useCallback((id) => onSelectStyle?.(id), [onSelectStyle]);
  const buildWithStyle = useCallback(
    (id) => {
      onSelectStyle?.(id);
      onOpenBuilder?.("llm");
    },
    [onSelectStyle, onOpenBuilder]
  );

  return (
    <div className="sg-page">
      <div className="sg-page-head">
        <div>
          <h1>Styles</h1>
          <p>Compare built-in prompt presets side by side, plus your own custom and AI-generated styles.</p>
        </div>
        <button type="button" className="sg-cta sg-press-btn" onClick={openCreate}>
          <Plus size={16} stroke="#1A1206" strokeWidth={2.6} />
          New custom style
        </button>
      </div>

      {loadError && (
        <div className="sg-style-alert">
          <AlertCircle size={15} />
          <span>{loadError}</span>
        </div>
      )}

      <SectionHeading title="Built-in" right="Read-only · real prompt_name values" />
      <div className="sg-style-grid">
        {data.builtin.map((style, index) => (
          <StyleCard
            key={style.id}
            style={style}
            active={selectedStyle === style.id}
            delay={index * 30}
            onUse={() => useStyle(style.id)}
            onBuild={() => buildWithStyle(style.id)}
            onClone={() => openClone(style)}
          />
        ))}
      </div>

      <SectionHeading
        title="My Styles"
        right={loading ? "Loading…" : `${data.custom.length} custom style${data.custom.length === 1 ? "" : "s"}`}
      />
      {data.custom.length === 0 ? (
        <div className="sg-custom-style-row">
          <button type="button" className="sg-add-custom sg-add-custom-btn" onClick={openCreate}>
            <Tile size={36} radius={10} variant="soft">
              <Plus size={18} stroke="#F97316" />
            </Tile>
            <div>
              <strong>Create your first custom style</strong>
              <p>Write a prompt by hand, clone a built-in, or generate a draft with AI.</p>
            </div>
          </button>
        </div>
      ) : (
        <div className="sg-style-grid">
          {data.custom.map((style, index) => (
            <StyleCard
              key={style.id}
              style={style}
              active={selectedStyle === style.id}
              delay={index * 30}
              custom
              onUse={() => useStyle(style.id)}
              onBuild={() => buildWithStyle(style.id)}
              onEdit={() => openEdit(style)}
              onDelete={() => setDeleteTarget(style)}
            />
          ))}
        </div>
      )}

      {editor.open && (
        <StyleEditorDrawer
          editor={editor}
          providers={providers}
          onClose={closeEditor}
          onSave={handleSave}
        />
      )}

      {deleteTarget && (
        <ConfirmDeleteModal
          target={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={confirmDelete}
        />
      )}
    </div>
  );
}

function StyleCard({ style, active, delay, custom, onUse, onBuild, onEdit, onDelete, onClone }) {
  const Glyph = glyphForStyle(style);
  return (
    <div className={`sg-style-big sg-recent-row ${active ? "active" : ""}`} style={{ animationDelay: `${delay}ms` }}>
      <div className="sg-style-big-top">
        <Tile size={40} radius={11} variant={active ? "orange" : "dark"}>
          <Glyph size={20} color={active ? "#1B0F03" : "#F97316"} />
        </Tile>
        <div>
          <strong>{style.name}</strong>
          <p>{style.description || (custom ? "Custom style" : "Built-in style")}</p>
        </div>
        <span>{active ? "Selected" : custom ? "Custom" : "Built-in"}</span>
      </div>

      {custom && style.tags?.length > 0 && (
        <div className="sg-style-tags">
          {style.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      )}
      {custom && style.base_style && (
        <p className="sg-style-base">Based on {style.base_style}</p>
      )}

      <div className="sg-style-actions">
        <button type="button" className="sg-ghost-button" onClick={onUse}>
          {active ? "Selected" : "Use"}
        </button>
        {custom ? (
          <>
            <button type="button" className="sg-icon-button" title="Edit" onClick={onEdit}>
              <Pencil size={14} />
            </button>
            <button type="button" className="sg-icon-button danger" title="Delete" onClick={onDelete}>
              <Trash2 size={14} />
            </button>
          </>
        ) : (
          <button type="button" className="sg-icon-button" title="Clone to custom" onClick={onClone}>
            <Copy size={14} />
          </button>
        )}
        <button type="button" className="sg-cta compact" onClick={onBuild}>
          Build
        </button>
      </div>
    </div>
  );
}

function StyleEditorDrawer({ editor, providers, onClose, onSave }) {
  const isEdit = editor.mode === "edit";
  const [name, setName] = useState(editor.name);
  const [description, setDescription] = useState(editor.description);
  const [tags, setTags] = useState(editor.tags);
  const [content, setContent] = useState(editor.content);

  const [genOpen, setGenOpen] = useState(false);
  const [genDescription, setGenDescription] = useState("");
  const [genProvider, setGenProvider] = useState(providers[0]?.id ?? "");
  const [genModel, setGenModel] = useState(providers[0]?.default_model ?? "");
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState(null);

  // Keep local fields in sync when an async clone/edit load resolves.
  useEffect(() => {
    setName(editor.name);
    setDescription(editor.description);
    setTags(editor.tags);
    setContent(editor.content);
  }, [editor.name, editor.description, editor.tags, editor.content]);

  // Default the generate provider once the configured list arrives.
  useEffect(() => {
    if (!genProvider && providers[0]) {
      setGenProvider(providers[0].id);
      setGenModel(providers[0].default_model ?? "");
    }
  }, [providers, genProvider]);

  const selectedGenProvider = useMemo(
    () => providers.find((item) => item.id === genProvider) ?? providers[0],
    [providers, genProvider]
  );
  const genModels = selectedGenProvider?.available_models?.length
    ? selectedGenProvider.available_models
    : selectedGenProvider?.default_model
      ? [selectedGenProvider.default_model]
      : [];

  const missing = missingPlaceholders(content);
  const canSave = name.trim() && content.trim() && !editor.saving;

  async function handleGenerate() {
    if (!genDescription.trim()) {
      setGenError("Describe the style you want first.");
      return;
    }
    setGenLoading(true);
    setGenError(null);
    try {
      const draft = await generateStyle({
        description: genDescription,
        baseStyle: editor.baseStyle,
        provider: genProvider || null,
        model: genModel || null
      });
      setName(draft.name || name);
      setDescription(draft.description || description);
      setContent(draft.content || content);
    } catch (error) {
      setGenError(error.message || "Could not generate a draft.");
    } finally {
      setGenLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-sm">
      <button type="button" className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Close editor" />
      <aside className="relative flex h-full w-full max-w-[720px] flex-col border-l border-white/10 bg-[#090D16]/95 shadow-[-24px_0_80px_rgba(0,0,0,0.45)]">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 p-5">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-ember-500">
              {isEdit ? "Edit custom style" : "New custom style"}
            </p>
            <h2 className="mt-1 truncate text-2xl font-bold text-white">{name || "Untitled style"}</h2>
            {editor.baseStyle && (
              <p className="mt-1 text-xs text-slate-500">Based on {editor.baseStyle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {editor.saving && !name && !content ? (
            <div className="flex min-h-72 items-center justify-center gap-3 text-slate-300">
              <Loader2 className="h-5 w-5 animate-spin text-ember-500" />
              <span>Loading style…</span>
            </div>
          ) : (
            <div className="grid gap-4">
              {!isEdit && (
                <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between text-left"
                    onClick={() => setGenOpen((open) => !open)}
                  >
                    <span className="flex items-center gap-2 text-sm font-semibold text-white">
                      <Wand2 className="h-4 w-4 text-ember-500" />
                      Generate a draft with AI
                    </span>
                    <span className="text-xs text-slate-400">{genOpen ? "Hide" : "Show"}</span>
                  </button>
                  {genOpen && (
                    <div className="mt-3 grid gap-3">
                      {providers.length === 0 ? (
                        <p className="text-xs text-amber-300">
                          No LLM provider is configured on the server. Add a provider key in .env to enable generation.
                        </p>
                      ) : (
                        <>
                          <textarea
                            className="sg-source-textarea !min-h-[88px] rounded-xl border border-white/10 bg-[#070B14] p-3"
                            placeholder="Describe the study-guide style you want, e.g. 'A one-page cheat sheet, formulas only, heavy on tables.'"
                            value={genDescription}
                            onChange={(event) => setGenDescription(event.target.value)}
                          />
                          <div className="grid grid-cols-2 gap-2">
                            <label className="grid gap-1 text-xs text-slate-400">
                              Provider
                              <select
                                className="sg-select"
                                value={genProvider}
                                onChange={(event) => {
                                  const next = providers.find((item) => item.id === event.target.value);
                                  setGenProvider(event.target.value);
                                  setGenModel(next?.default_model ?? "");
                                }}
                              >
                                {providers.map((item) => (
                                  <option key={item.id} value={item.id}>
                                    {item.display_name}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label className="grid gap-1 text-xs text-slate-400">
                              Model
                              <select
                                className="sg-select"
                                value={genModel}
                                onChange={(event) => setGenModel(event.target.value)}
                              >
                                {genModels.map((model) => (
                                  <option key={model} value={model}>
                                    {model}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>
                          {genError && <p className="text-xs text-red-300">{genError}</p>}
                          <button
                            type="button"
                            className="sg-ghost-button justify-center"
                            onClick={handleGenerate}
                            disabled={genLoading}
                          >
                            {genLoading ? (
                              <span className="flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin" /> Generating…
                              </span>
                            ) : (
                              <span className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4" /> Generate draft
                              </span>
                            )}
                          </button>
                          <p className="text-[11px] text-slate-500">
                            The draft fills the fields below. Review and edit before saving — nothing is saved until you click Save.
                          </p>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}

              <label className="grid gap-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Name</span>
                <input
                  className="sg-input sg-input-lg"
                  value={name}
                  maxLength={120}
                  placeholder="e.g. One-page cheat sheet"
                  onChange={(event) => setName(event.target.value)}
                />
              </label>

              <label className="grid gap-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Description</span>
                <input
                  className="sg-input sg-input-lg"
                  value={description}
                  maxLength={600}
                  placeholder="One sentence describing the style"
                  onChange={(event) => setDescription(event.target.value)}
                />
              </label>

              <label className="grid gap-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Tags (comma-separated)</span>
                <input
                  className="sg-input sg-input-lg"
                  value={tags}
                  placeholder="exam, fast, tables"
                  onChange={(event) => setTags(event.target.value)}
                />
              </label>

              <div className="grid gap-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Prompt template</span>
                <div className="sg-source-editor">
                  <textarea
                    className="sg-source-textarea"
                    value={content}
                    placeholder="Write the instruction template. Use {title}, {mode}, and {source} placeholders."
                    onChange={(event) => setContent(event.target.value)}
                  />
                </div>
                {missing.length > 0 ? (
                  <p className="flex items-center gap-1.5 text-[11.5px] text-amber-300">
                    <AlertCircle className="h-3.5 w-3.5" />
                    Missing placeholder{missing.length > 1 ? "s" : ""}: {missing.join(", ")} — the guide may ignore your source without {"{source}"}.
                  </p>
                ) : (
                  <p className="flex items-center gap-1.5 text-[11.5px] text-emerald-300">
                    <Check className="h-3.5 w-3.5" /> All required placeholders present.
                  </p>
                )}
              </div>

              {editor.error && <p className="text-sm text-red-300">{editor.error}</p>}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-white/10 p-4">
          <button type="button" className="sg-ghost-button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="sg-cta"
            disabled={!canSave}
            onClick={() =>
              onSave({
                mode: editor.mode,
                id: editor.id,
                name: name.trim(),
                description: description.trim(),
                tags,
                content,
                baseStyle: editor.baseStyle
              })
            }
          >
            {editor.saving ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Saving…
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Check className="h-4 w-4" /> {isEdit ? "Save changes" : "Create style"}
              </span>
            )}
          </button>
        </div>
      </aside>
    </div>
  );
}

function ConfirmDeleteModal({ target, onCancel, onConfirm }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <button type="button" className="absolute inset-0 cursor-default" onClick={onCancel} aria-label="Cancel" />
      <div className="relative w-full max-w-[420px] rounded-2xl border border-white/10 bg-[#0B0F19] p-6 shadow-2xl">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-red-500/15 text-red-300">
            <Trash2 className="h-5 w-5" />
          </span>
          <div>
            <h3 className="text-lg font-bold text-white">Delete custom style?</h3>
            <p className="text-sm text-slate-400">
              “{target.name}” will be removed permanently.
            </p>
          </div>
        </div>
        {target.error && <p className="mt-3 text-sm text-red-300">{target.error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="sg-ghost-button" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="sg-cta"
            style={{ background: "linear-gradient(180deg,#F87171,#DC2626)" }}
            onClick={onConfirm}
          >
            Delete
          </button>
        </div>
      </div>
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
