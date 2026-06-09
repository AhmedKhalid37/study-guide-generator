import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  Check,
  Copy,
  FileText,
  Footprints,
  Hammer,
  ListChecks,
  Loader2,
  Palette,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Trophy,
  Wand2,
  X,
  Zap
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

const REQUIRED_PLACEHOLDERS = ["{title}", "{mode}", "{source}"];

// Decorative-only icon per built-in style id (rebound to the GuideForge lucide
// set). Falls back to a neutral glyph for unknown/custom styles.
const BUILTIN_ICONS = {
  basic_study_guide: FileText,
  baby_steps: Footprints,
  exam_cram: Zap,
  mcq_training: ListChecks,
  final_solution: Trophy,
  claude_study_guide: Sparkles,
  master_longform: BookOpen
};

function iconForStyle(style, custom) {
  return BUILTIN_ICONS[style.id] || (custom ? Palette : Sparkles);
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
    <div className="sg-sty">
      <div className="sg-page-head">
        <div>
          <h1>Styles</h1>
          <p>Compare built-in prompt presets side by side, plus your own custom and AI-generated styles.</p>
        </div>
        <button type="button" className="sg-cta sg-press-btn" onClick={openCreate}>
          <Plus size={16} strokeWidth={2.4} />
          New custom style
        </button>
      </div>

      {loadError && (
        <div className="sg-sty-alert">
          <AlertCircle size={16} />
          <span>{loadError}</span>
        </div>
      )}

      <section className="sg-sty-section">
        <SectionHeading title="Built-in" right="Read-only · real prompt_name values" />
        <div className="sg-sty-grid">
          {data.builtin.map((style) => (
            <StyleCard
              key={style.id}
              style={style}
              active={selectedStyle === style.id}
              onUse={() => useStyle(style.id)}
              onBuild={() => buildWithStyle(style.id)}
              onClone={() => openClone(style)}
            />
          ))}
        </div>
      </section>

      <section className="sg-sty-section">
        <SectionHeading
          title="My Styles"
          right={loading ? "Loading…" : `${data.custom.length} custom style${data.custom.length === 1 ? "" : "s"}`}
        />
        {data.custom.length === 0 ? (
          <button type="button" className="sg-sty-empty" onClick={openCreate}>
            <span className="sg-sty-empty-icon">
              <Plus size={20} />
            </span>
            <span className="sg-sty-empty-text">
              <strong>Create your first custom style</strong>
              <span>Write a prompt by hand, clone a built-in, or generate a draft with AI.</span>
            </span>
          </button>
        ) : (
          <div className="sg-sty-grid">
            {data.custom.map((style) => (
              <StyleCard
                key={style.id}
                style={style}
                active={selectedStyle === style.id}
                custom
                onUse={() => useStyle(style.id)}
                onBuild={() => buildWithStyle(style.id)}
                onEdit={() => openEdit(style)}
                onDelete={() => setDeleteTarget(style)}
              />
            ))}
          </div>
        )}
      </section>

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

function StyleCard({ style, active, custom, onUse, onBuild, onEdit, onDelete, onClone }) {
  const Icon = iconForStyle(style, custom);
  return (
    <div className={`sg-sty-card ${active ? "active" : ""}`}>
      <div className="sg-sty-card-top">
        <span className={`sg-sty-icon ${active ? "active" : ""}`}>
          <Icon size={19} />
        </span>
        <div className="sg-sty-card-headings">
          <strong className="sg-sty-name">{style.name}</strong>
          <p className="sg-sty-desc">{style.description || (custom ? "Custom style" : "Built-in style")}</p>
        </div>
        <span className={`sg-sty-badge ${active ? "is-active" : custom ? "is-custom" : "is-builtin"}`}>
          {active ? "Selected" : custom ? "Custom" : "Built-in"}
        </span>
      </div>

      {custom && style.tags?.length > 0 && (
        <div className="sg-sty-tags">
          {style.tags.map((tag) => (
            <span key={tag} className="sg-sty-tag">{tag}</span>
          ))}
        </div>
      )}
      {custom && style.base_style && (
        <p className="sg-sty-base">Based on {style.base_style}</p>
      )}

      <div className="sg-sty-actions">
        <button
          type="button"
          className={`sg-btn-sm${active ? " accent" : ""}`}
          onClick={onUse}
          disabled={active}
        >
          {active ? <Check size={14} /> : null}
          {active ? "Selected" : "Use"}
        </button>
        {custom ? (
          <>
            <button type="button" className="sg-btn-sm sq" title="Edit" onClick={onEdit}>
              <Pencil size={14} />
            </button>
            <button type="button" className="sg-btn-sm sq danger" title="Delete" onClick={onDelete}>
              <Trash2 size={14} />
            </button>
          </>
        ) : (
          <button type="button" className="sg-btn-sm sq" title="Clone to custom" onClick={onClone}>
            <Copy size={14} />
          </button>
        )}
        <button type="button" className="sg-btn-sm accent sg-sty-build" onClick={onBuild}>
          <Hammer size={14} />
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
    <div className="sg-drawer-root">
      <button type="button" className="sg-drawer-scrim" onClick={onClose} aria-label="Close editor" />
      <aside className="sg-drawer-sheet sg-sty-drawer">
        <div className="sg-drawer-head">
          <div style={{ minWidth: 0 }}>
            <p className="sg-drawer-eyebrow">{isEdit ? "Edit custom style" : "New custom style"}</p>
            <h2 className="sg-drawer-title">{name || "Untitled style"}</h2>
            {editor.baseStyle && <p className="sg-drawer-id">Based on {editor.baseStyle}</p>}
          </div>
          <button type="button" className="sg-drawer-close" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="sg-sty-drawer-body">
          {editor.saving && !name && !content ? (
            <div className="sg-sty-drawer-loading">
              <Loader2 size={18} className="sg-spin" />
              <span>Loading style…</span>
            </div>
          ) : (
            <>
              {!isEdit && (
                <div className="sg-sty-gen">
                  <button
                    type="button"
                    className="sg-sty-gen-toggle"
                    onClick={() => setGenOpen((open) => !open)}
                  >
                    <span className="sg-sty-gen-toggle-label">
                      <Wand2 size={15} />
                      Generate a draft with AI
                    </span>
                    <span className="sg-sty-gen-toggle-state">{genOpen ? "Hide" : "Show"}</span>
                  </button>
                  {genOpen && (
                    <div className="sg-sty-gen-body">
                      {providers.length === 0 ? (
                        <p className="sg-sty-warn">
                          No LLM provider is configured on the server. Add a provider key in .env to enable generation.
                        </p>
                      ) : (
                        <>
                          <textarea
                            className="sg-source-textarea sg-sty-gen-area"
                            placeholder="Describe the study-guide style you want, e.g. 'A one-page cheat sheet, formulas only, heavy on tables.'"
                            value={genDescription}
                            onChange={(event) => setGenDescription(event.target.value)}
                          />
                          <div className="sg-sty-gen-selects">
                            <label className="sg-sty-field">
                              <span className="sg-sty-field-label">Provider</span>
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
                            <label className="sg-sty-field">
                              <span className="sg-sty-field-label">Model</span>
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
                          {genError && <p className="sg-sty-error">{genError}</p>}
                          <button
                            type="button"
                            className="sg-btn-sm accent sg-sty-gen-btn"
                            onClick={handleGenerate}
                            disabled={genLoading}
                          >
                            {genLoading ? (
                              <>
                                <Loader2 size={14} className="sg-spin" /> Generating…
                              </>
                            ) : (
                              <>
                                <Sparkles size={14} /> Generate draft
                              </>
                            )}
                          </button>
                          <p className="sg-sty-gen-hint">
                            The draft fills the fields below. Review and edit before saving — nothing is saved until you
                            click Save.
                          </p>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}

              <label className="sg-sty-field">
                <span className="sg-sty-field-label">Name</span>
                <input
                  className="sg-input sg-input-lg"
                  value={name}
                  maxLength={120}
                  placeholder="e.g. One-page cheat sheet"
                  onChange={(event) => setName(event.target.value)}
                />
              </label>

              <label className="sg-sty-field">
                <span className="sg-sty-field-label">Description</span>
                <input
                  className="sg-input sg-input-lg"
                  value={description}
                  maxLength={600}
                  placeholder="One sentence describing the style"
                  onChange={(event) => setDescription(event.target.value)}
                />
              </label>

              <label className="sg-sty-field">
                <span className="sg-sty-field-label">Tags (comma-separated)</span>
                <input
                  className="sg-input sg-input-lg"
                  value={tags}
                  placeholder="exam, fast, tables"
                  onChange={(event) => setTags(event.target.value)}
                />
              </label>

              <div className="sg-sty-field">
                <span className="sg-sty-field-label">Prompt template</span>
                <div className="sg-source-editor">
                  <textarea
                    className="sg-source-textarea"
                    value={content}
                    placeholder="Write the instruction template. Use {title}, {mode}, and {source} placeholders."
                    onChange={(event) => setContent(event.target.value)}
                  />
                </div>
                {missing.length > 0 ? (
                  <p className="sg-sty-hint warn">
                    <AlertCircle size={14} />
                    Missing placeholder{missing.length > 1 ? "s" : ""}: {missing.join(", ")} — the guide may ignore your
                    source without {"{source}"}.
                  </p>
                ) : (
                  <p className="sg-sty-hint ok">
                    <Check size={14} /> All required placeholders present.
                  </p>
                )}
              </div>

              {editor.error && <p className="sg-sty-error">{editor.error}</p>}
            </>
          )}
        </div>

        <div className="sg-sty-drawer-foot">
          <button type="button" className="sg-ghost-button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="sg-cta sg-press-btn" disabled={!canSave} onClick={() =>
            onSave({
              mode: editor.mode,
              id: editor.id,
              name: name.trim(),
              description: description.trim(),
              tags,
              content,
              baseStyle: editor.baseStyle
            })
          }>
            {editor.saving ? (
              <>
                <Loader2 size={15} className="sg-spin" /> Saving…
              </>
            ) : (
              <>
                <Check size={15} /> {isEdit ? "Save changes" : "Create style"}
              </>
            )}
          </button>
        </div>
      </aside>
    </div>
  );
}

function ConfirmDeleteModal({ target, onCancel, onConfirm }) {
  return (
    <div className="sg-modal-scrim">
      <button type="button" className="sg-scrim-bg" onClick={onCancel} aria-label="Cancel" />
      <div className="sg-modal">
        <div className="sg-modal-head">
          <Trash2 size={20} style={{ color: "#FCA5A5" }} />
          <div>
            <h2>Delete custom style?</h2>
            <p>“{target.name}” will be removed permanently.</p>
          </div>
        </div>
        {target.error && <p className="sg-modal-err">{target.error}</p>}
        <div className="sg-modal-actions">
          <button type="button" className="sg-ghost-button" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="sg-sty-danger-cta sg-press-btn" onClick={onConfirm}>
            <Trash2 size={15} /> Delete
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeading({ title, right }) {
  return (
    <div className="sg-sty-section-head">
      <h2>{title}</h2>
      {right && <span>{right}</span>}
    </div>
  );
}
