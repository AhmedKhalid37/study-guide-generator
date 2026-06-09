import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Check, KeyRound, Loader2, Plus, RefreshCw, Trash2, X } from "lucide-react";
import {
  clearProviderKey,
  fetchProviderModels,
  getProviderSettings,
  setDefaultProvider,
  testProviderSettings,
  updateProviderSettings
} from "../api/client";
import LocalModelsPanel from "./LocalModelsPanel";

// Providers / Settings workspace. Consumes the safe, server-side provider
// settings endpoints (Slice 1). The frontend only ever sees redacted status —
// raw API keys are write-only: typed into a password field, sent on Save, and
// never read back, prefilled, logged, or rendered. The Builder reads provider
// options independently from /api/options, so this page failing never breaks it.

const numToStr = (value) =>
  value === null || value === undefined || value === "" ? "" : String(value);

const parseNum = (raw) => {
  const trimmed = String(raw ?? "").trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
};

const norm = (value) => (value === undefined ? null : value);

const arraysEqual = (a, b) => {
  const x = Array.isArray(a) ? a : [];
  const y = Array.isArray(b) ? b : [];
  return x.length === y.length && x.every((v, i) => v === y[i]);
};

function draftFromProvider(p) {
  return {
    defaultModel: p.default_model || "",
    customModels: Array.isArray(p.custom_models) ? [...p.custom_models] : [],
    temperature: numToStr(p.temperature),
    topP: numToStr(p.top_p),
    maxTokens: numToStr(p.max_tokens),
    timeoutSeconds: numToStr(p.timeout_seconds),
    retryCount: numToStr(p.retry_count),
    thinking: p.thinking_default === true ? "on" : p.thinking_default === false ? "off" : "inherit",
    baseUrl: "", // write-mostly: blank keeps current (the host is shown read-only)
    apiKey: "", // write-only: blank keeps current; never prefilled
    newCustomModel: ""
  };
}

export default function ProviderSettingsWorkspace() {
  const [view, setView] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getProviderSettings()
      .then((data) => {
        setView(data);
        setError(null);
      })
      .catch((err) => setError(err?.message || "Failed to load provider settings."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const providers = view?.providers ?? [];

  // Replace a single provider DTO after a PATCH / clear-key returns it.
  const applyProvider = useCallback((updated) => {
    if (!updated || !updated.id) return;
    setView((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        providers: (prev.providers ?? []).map((p) => (p.id === updated.id ? updated : p))
      };
    });
  }, []);

  const handleSetDefault = useCallback((providerId) => {
    return setDefaultProvider(providerId || null)
      .then((data) => setView(data))
      .catch((err) => setError(err?.message || "Failed to set default provider."));
  }, []);

  const configuredCount = providers.filter((p) => p.configured).length;
  const hasLocalProvider = providers.some((p) => p.id === "local");

  // The Local Models panel is operational/read-only and links back here for any
  // config edit (Providers is the single writer). Scroll the Local provider card
  // into view and flash a brief highlight so the user lands on the right editor.
  const focusLocalProvider = useCallback(() => {
    const el = document.getElementById("provider-card-local");
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("sg-card-flash");
    window.setTimeout(() => el.classList.remove("sg-card-flash"), 1600);
  }, []);

  return (
    <div className="sg-mdl">
      <div className="sg-page-head">
        <div>
          <h1>Providers</h1>
          <p>Configure providers, models, and sampling defaults. Keys stay server-side and are write-only.</p>
        </div>
        <button type="button" className="sg-ghost-button" onClick={load} disabled={loading}>
          {loading ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="sg-mdl-alert">
          <AlertTriangle size={18} />
          <div className="sg-mdl-alert-body">
            <strong>Couldn’t load provider settings</strong>
            <p>
              {error} The Builder still works from <code>/api/options</code>; you can retry below.
            </p>
            <button type="button" className="sg-ghost-button" onClick={load}>
              Retry
            </button>
          </div>
        </div>
      )}

      {loading && !view && (
        <div className="sg-mdl-loading">
          <Loader2 size={16} className="sg-spin" /> Loading provider settings…
        </div>
      )}

      {view && (
        <>
          <div className="sg-mdl-default">
            <span className="sg-mdl-default-icon">
              <KeyRound size={18} />
            </span>
            <div className="sg-mdl-default-main">
              <span className="sg-mdl-default-label">Default provider</span>
              <DefaultProviderSelect
                value={view.default_provider || ""}
                providers={providers}
                onChange={handleSetDefault}
              />
            </div>
            <em>
              {configuredCount} of {providers.length} configured
            </em>
          </div>

          <div>
            <div className="sg-mdl-section-head">
              <h2>Providers</h2>
              <span>Raw keys never leave the server</span>
            </div>

            <div className="sg-mdl-provider-list">
              {providers.map((provider) => (
                <ProviderSettingsCard
                  key={provider.id}
                  provider={provider}
                  isDefault={view.default_provider === provider.id}
                  onSaved={applyProvider}
                />
              ))}
            </div>
          </div>

          <LocalModelsPanel
            onEditLocalProvider={hasLocalProvider ? focusLocalProvider : undefined}
          />
        </>
      )}
    </div>
  );
}

function DefaultProviderSelect({ value, providers, onChange }) {
  return (
    <select
      className="sg-select"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">First configured (auto)</option>
      {providers.map((p) => (
        <option key={p.id} value={p.id} disabled={!p.configured}>
          {p.display_name}
          {p.configured ? "" : " · not configured"}
        </option>
      ))}
    </select>
  );
}

function ProviderSettingsCard({ provider, isDefault, onSaved }) {
  const [draft, setDraft] = useState(() => draftFromProvider(provider));
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [notice, setNotice] = useState(null); // { kind: "ok"|"error", text }
  // Only reflects a Test pressed in THIS session — never a stale persisted
  // last_test — so a prior failure never lingers after save/clear/edits.
  const [testResult, setTestResult] = useState(null);
  // Read-only model discovery result for THIS session. Fetched ids are never
  // auto-saved — the user adds them to custom models deliberately, then Save.
  const [fetching, setFetching] = useState(false);
  const [fetchResult, setFetchResult] = useState(null); // { ok, models, error }

  // Re-seed the draft whenever the provider DTO changes identity (after a save,
  // clear-key, or refresh). This also clears the write-only key + base-url inputs.
  useEffect(() => {
    setDraft(draftFromProvider(provider));
    setFetchResult(null); // a refreshed/saved DTO invalidates a prior fetch list
  }, [provider]);

  const set = (field) => (event) => {
    const value = event && event.target ? event.target.value : event;
    setDraft((d) => ({ ...d, [field]: value }));
    // Editing any connectivity-relevant field invalidates a shown test result.
    if (field !== "newCustomModel") setTestResult(null);
  };

  const models = useMemo(() => {
    const base = Array.isArray(provider.available_models) ? provider.available_models : [];
    const merged = [...base];
    draft.customModels.forEach((m) => {
      if (m && !merged.includes(m)) merged.push(m);
    });
    if (draft.defaultModel && !merged.includes(draft.defaultModel)) merged.push(draft.defaultModel);
    return merged;
  }, [provider.available_models, draft.customModels, draft.defaultModel]);

  const buildPatch = useCallback(() => {
    const patch = {};
    if (draft.baseUrl.trim()) patch.base_url = draft.baseUrl.trim();
    if (draft.defaultModel !== (provider.default_model || "")) patch.default_model = draft.defaultModel;
    if (!arraysEqual(draft.customModels, provider.custom_models || [])) {
      patch.custom_models = draft.customModels;
    }
    const numericFields = [
      ["temperature", draft.temperature, provider.temperature],
      ["top_p", draft.topP, provider.top_p],
      ["max_tokens", draft.maxTokens, provider.max_tokens],
      ["timeout_seconds", draft.timeoutSeconds, provider.timeout_seconds],
      ["retry_count", draft.retryCount, provider.retry_count]
    ];
    numericFields.forEach(([key, raw, original]) => {
      const parsed = parseNum(raw);
      if (!Object.is(parsed, norm(original))) patch[key] = parsed;
    });
    if (provider.supports_thinking) {
      const thinkingVal = draft.thinking === "on" ? true : draft.thinking === "off" ? false : null;
      if (!Object.is(thinkingVal, norm(provider.thinking_default))) patch.thinking_default = thinkingVal;
    }
    if (draft.apiKey.trim()) patch.api_key = draft.apiKey.trim();
    return patch;
  }, [draft, provider]);

  const handleSave = async () => {
    const patch = buildPatch();
    if (Object.keys(patch).length === 0) {
      setNotice({ kind: "ok", text: "No changes to save." });
      return;
    }
    const setKey = "api_key" in patch;
    setSaving(true);
    setNotice(null);
    try {
      const updated = await updateProviderSettings(provider.id, patch);
      onSaved(updated);
      setTestResult(null); // a prior test no longer reflects the saved settings
      setNotice({ kind: "ok", text: setKey ? "Settings saved · key updated." : "Settings saved." });
    } catch (err) {
      // requestJson surfaces the server's redacted `detail`; never a raw key.
      setNotice({ kind: "error", text: err?.message || "Save failed." });
    } finally {
      setSaving(false);
    }
  };

  const handleClearKey = async () => {
    const ok = window.confirm(
      `Clear the saved API key for ${provider.display_name}?\n\n` +
        "This removes only the key saved in the app. It does NOT disconnect the " +
        "provider: if an .env fallback key exists, the provider keeps using that."
    );
    if (!ok) return;
    setClearing(true);
    setNotice(null);
    try {
      const updated = await clearProviderKey(provider.id);
      onSaved(updated);
      setTestResult(null); // the cleared key invalidates any prior test result
      const fellBack = updated?.key_source === "env";
      setNotice({
        kind: "ok",
        text: fellBack ? "Saved key cleared — now using the .env key." : "Saved key cleared."
      });
    } catch (err) {
      setNotice({ kind: "error", text: err?.message || "Clear saved key failed." });
    } finally {
      setClearing(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setNotice(null);
    try {
      const result = await testProviderSettings(provider.id);
      setTestResult(result);
    } catch (err) {
      // Network/4xx failures: show the redacted message only.
      setTestResult({ ok: false, category: "error", message: err?.message || "Test failed." });
    } finally {
      setTesting(false);
    }
  };

  const addCustomModel = () => {
    const id = draft.newCustomModel.trim();
    if (!id || draft.customModels.includes(id)) {
      setDraft((d) => ({ ...d, newCustomModel: "" }));
      return;
    }
    setDraft((d) => ({ ...d, customModels: [...d.customModels, id], newCustomModel: "" }));
    setTestResult(null);
  };

  const removeCustomModel = (id) => {
    setDraft((d) => ({ ...d, customModels: d.customModels.filter((m) => m !== id) }));
    setTestResult(null);
  };

  // Read-only fetch: hit the provider's /models endpoint and show the ids for
  // review. Nothing is saved here — adding to custom models is a separate,
  // deliberate step below. Failures show only the backend's redacted message.
  const handleFetchModels = async () => {
    setFetching(true);
    setFetchResult(null);
    setNotice(null);
    try {
      const result = await fetchProviderModels(provider.id);
      setFetchResult(result);
    } catch (err) {
      // requestJson surfaces the server's redacted `detail`; never a raw key.
      setFetchResult({ ok: false, models: [], error: { category: "error", message: err?.message || "Fetch failed." } });
    } finally {
      setFetching(false);
    }
  };

  // Models already in the dropdown (registry ∪ current custom drafts ∪ default).
  const knownModelSet = useMemo(() => new Set(models), [models]);
  // Fetched ids not already known — the only ones worth adding to custom models.
  const newFetchedModels = useMemo(() => {
    if (!fetchResult?.ok || !Array.isArray(fetchResult.models)) return [];
    return fetchResult.models.filter((m) => m && !knownModelSet.has(m));
  }, [fetchResult, knownModelSet]);

  const addFetchedModel = (id) => {
    if (!id || draft.customModels.includes(id)) return;
    setDraft((d) => ({ ...d, customModels: [...d.customModels, id] }));
    setTestResult(null);
  };

  const addAllNewModels = () => {
    if (newFetchedModels.length === 0) return;
    setDraft((d) => {
      const additions = newFetchedModels.filter((m) => !d.customModels.includes(m));
      if (additions.length === 0) return d;
      return { ...d, customModels: [...d.customModels, ...additions] };
    });
    setTestResult(null);
  };

  const keyPlaceholder =
    provider.key_source === "store"
      ? `Saved key ····${provider.key_hint || ""} — leave blank to keep`
      : provider.key_source === "env"
        ? "Using .env fallback key — paste to override"
        : "No key set — paste to add";

  return (
    <div id={`provider-card-${provider.id}`} className="sg-mdl-card">
      <div className="sg-mdl-card-top">
        <span className="sg-mdl-avatar">{provider.display_name.slice(0, 1)}</span>
        <div className="sg-mdl-card-headings">
          <strong>{provider.display_name}</strong>
          <p>
            {provider.kind || "cloud"}
            {isDefault ? " · default" : ""}
            {provider.base_url_host ? ` · ${provider.base_url_host}` : ""}
          </p>
          {/* Status sits in normal flow under the name — never pinned to the
              card's right edge, so it can't clip or overlap the icon. */}
          <div className="sg-mdl-card-status">
            <StatusPill provider={provider} />
          </div>
        </div>
      </div>

      {provider.discovery_error && (
        <p className="sg-mdl-discovery-error">
          Discovery error: {provider.discovery_error}
        </p>
      )}

      {/* API key — write-only */}
      <Field label="API key" hint={provider.key_source ? `source: ${provider.key_source}` : null}>
        <input
          type="password"
          autoComplete="off"
          className="sg-mdl-input"
          placeholder={keyPlaceholder}
          value={draft.apiKey}
          onChange={set("apiKey")}
        />
        {provider.key_source === "store" ? (
          <button
            type="button"
            className="sg-mdl-link"
            onClick={handleClearKey}
            disabled={clearing}
          >
            {clearing ? <Loader2 size={12} className="sg-spin" /> : <Trash2 size={12} />}
            {clearing ? "Clearing…" : "Clear saved key"}
          </button>
        ) : provider.key_source === "env" ? (
          <p className="sg-mdl-help dim">
            Using the .env fallback key — no saved key to clear. Paste a key above to save one in the app.
          </p>
        ) : null}
      </Field>

      {/* Base URL — host shown read-only; blank input keeps current */}
      <Field label="Base URL override" hint={provider.base_url_host ? `current: ${provider.base_url_host}` : "using default"}>
        <input
          type="text"
          className="sg-mdl-input"
          placeholder="Leave blank to keep current"
          value={draft.baseUrl}
          onChange={set("baseUrl")}
        />
      </Field>

      {/* Default model */}
      <Field label="Default model">
        <select className="sg-mdl-select" value={draft.defaultModel} onChange={set("defaultModel")}>
          {models.length === 0 && <option value="">No models</option>}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </Field>

      {/* Custom models */}
      <Field label="Custom models">
        <div className="sg-mdl-chips">
          {draft.customModels.length === 0 && (
            <span className="sg-mdl-chip-empty">None</span>
          )}
          {draft.customModels.map((m) => (
            <span key={m} className="sg-mdl-chip">
              {m}
              <button type="button" className="sg-mdl-chip-x" onClick={() => removeCustomModel(m)}>
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
        <div className="sg-mdl-addrow">
          <input
            type="text"
            className="sg-mdl-input"
            placeholder="Add model id"
            value={draft.newCustomModel}
            onChange={set("newCustomModel")}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addCustomModel();
              }
            }}
          />
          <button type="button" className="sg-icon-button" title="Add model" onClick={addCustomModel}>
            <Plus size={14} />
          </button>
        </div>
      </Field>

      {/* Refresh models — read-only discovery; fetched ids are review-only and
          only added to custom models on an explicit Add (then Save). */}
      <Field
        label="Discover models"
        hint={fetchResult?.base_url_host ? `from: ${fetchResult.base_url_host}` : null}
      >
        <button
          type="button"
          className="sg-ghost-button"
          onClick={handleFetchModels}
          disabled={fetching}
        >
          {fetching ? <Loader2 size={14} className="sg-spin" /> : <RefreshCw size={14} />}
          <span>{fetching ? "Fetching…" : "Refresh models"}</span>
        </button>
        {fetchResult && (
          <FetchedModelsPanel
            result={fetchResult}
            newModels={newFetchedModels}
            knownModelSet={knownModelSet}
            customModels={draft.customModels}
            onAdd={addFetchedModel}
            onAddAll={addAllNewModels}
          />
        )}
      </Field>

      {/* Sampling + runtime */}
      <div className="sg-mdl-axes">
        <NumField label="Temperature" value={draft.temperature} onChange={set("temperature")} step="0.1" min="0" max="2" />
        <NumField label="Top P" value={draft.topP} onChange={set("topP")} step="0.05" min="0" max="1" />
        <NumField label="Max tokens" value={draft.maxTokens} onChange={set("maxTokens")} step="1" min="1" />
        <NumField label="Timeout (s)" value={draft.timeoutSeconds} onChange={set("timeoutSeconds")} step="1" min="1" max="600" />
        <NumField label="Retries" value={draft.retryCount} onChange={set("retryCount")} step="1" min="0" max="10" />
        {provider.supports_thinking && (
          <Field label="Thinking">
            <select className="sg-mdl-select" value={draft.thinking} onChange={set("thinking")}>
              <option value="inherit">Provider default</option>
              <option value="on">On</option>
              <option value="off">Off</option>
            </select>
          </Field>
        )}
      </div>

      {testResult && <TestChip result={testResult} />}
      {notice && (
        <p className={`sg-mdl-notice ${notice.kind === "error" ? "error" : "ok"}`}>
          {notice.text}
        </p>
      )}

      <div className="sg-mdl-card-actions">
        <button type="button" className="sg-btn-sm accent" onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 size={14} className="sg-spin" /> : <Check size={14} />}
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" className="sg-btn-sm" onClick={handleTest} disabled={testing}>
          {testing ? <Loader2 size={14} className="sg-spin" /> : null}
          <span>{testing ? "Testing…" : "Test connection"}</span>
        </button>
      </div>
    </div>
  );
}

function StatusPill({ provider }) {
  const configured = Boolean(provider.configured);
  return (
    <span className={`sg-mdl-pill ${configured ? "is-ok" : "is-neutral"}`}>
      {configured ? <Check size={11} /> : <X size={11} />}
      {configured ? "Configured" : "Not configured"}
    </span>
  );
}

function TestChip({ result }) {
  const ok = Boolean(result.ok);
  return (
    <div className={`sg-mdl-callout ${ok ? "ok" : "error"}`}>
      {ok ? <Check size={14} /> : <AlertTriangle size={14} />}
      <div className="sg-mdl-callout-body">
        <strong>
          {ok ? "Connection OK" : "Connection failed"}
          {result.category ? ` · ${result.category}` : ""}
          {Number.isFinite(result.latency_ms) ? ` · ${result.latency_ms}ms` : ""}
        </strong>
        {result.message && <span className="sg-mdl-callout-sub">{result.message}</span>}
        {result.model && <span className="sg-mdl-callout-meta">model: {result.model}</span>}
      </div>
    </div>
  );
}

function FetchedModelsPanel({ result, newModels, knownModelSet, customModels, onAdd, onAddAll }) {
  // Failure: only the backend's redacted { category, message } — never a key,
  // full base URL, or userinfo.
  if (!result.ok) {
    const err = result.error || {};
    return (
      <div className="sg-mdl-callout error">
        <AlertTriangle size={14} />
        <div className="sg-mdl-callout-body">
          <strong>
            Couldn’t fetch models{err.category ? ` · ${err.category}` : ""}
          </strong>
          {err.message && <span className="sg-mdl-callout-sub">{err.message}</span>}
        </div>
      </div>
    );
  }

  const models = Array.isArray(result.models) ? result.models : [];
  // Calm empty state when the provider returned nothing.
  if (models.length === 0) {
    return (
      <p className="sg-mdl-help dim">
        No models returned. Nothing to add — your saved models are unchanged.
      </p>
    );
  }

  const newCount = newModels.length;

  return (
    <div className="sg-mdl-fetched">
      <div className="sg-mdl-fetched-head">
        <span>
          {models.length} fetched · {newCount} new
        </span>
        {newCount > 0 && (
          <button type="button" className="sg-mdl-link ok" onClick={onAddAll}>
            <Plus size={12} /> Add all new
          </button>
        )}
      </div>
      <div className="sg-mdl-chips">
        {models.map((m) => {
          const added = customModels.includes(m);
          const known = knownModelSet.has(m);
          return (
            <span key={m} className="sg-mdl-chip">
              {m}
              {added || known ? (
                <span className="sg-mdl-chip-tag">{added ? "added" : "in list"}</span>
              ) : (
                <button
                  type="button"
                  className="sg-mdl-chip-add"
                  title="Add to custom models"
                  onClick={() => onAdd(m)}
                >
                  <Plus size={11} />
                </button>
              )}
            </span>
          );
        })}
      </div>
      <p className="sg-mdl-fetched-foot">
        Review only — added models are saved with the provider on <strong>Save</strong>.
      </p>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="sg-mdl-field">
      <span className="sg-mdl-field-label">
        {label}
        {hint && <em>{hint}</em>}
      </span>
      {children}
    </label>
  );
}

function NumField({ label, value, onChange, ...rest }) {
  return (
    <Field label={label}>
      <input
        type="number"
        className="sg-mdl-input"
        placeholder="—"
        value={value}
        onChange={onChange}
        {...rest}
      />
    </Field>
  );
}
