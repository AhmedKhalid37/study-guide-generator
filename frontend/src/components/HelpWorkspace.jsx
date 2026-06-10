import React, { useCallback, useEffect, useState } from "react";
import { BookOpen, MessageSquareText, Server, ShieldCheck, Terminal } from "lucide-react";
import { getLocalModelCommandProfile } from "../api/client";
import {
  COPY_COPIED,
  COPY_FAILED,
  COPY_IDLE,
  commandAvailable,
  commandNotes,
  commandProfiles,
  profileById,
} from "../localModelCommand";
import { CommandHelper } from "./LocalModelsPanel";

// Help workspace (frontend-only). Today it hosts the manual local-model /
// llama-server setup guidance that used to live inside Ask Your Guide, plus a
// short, safe explanation of how Ask works. It owns the command-profile fetch +
// copy state so Ask no longer has to. Nothing here executes anything — the
// CommandHelper only renders a copyable command (model path is a placeholder;
// the backend never embeds a raw key, full URL, token, or host path).
export default function HelpWorkspace({ onNavigate }) {
  const [commandData, setCommandData] = useState(null);
  const [selectedProfileId, setSelectedProfileId] = useState(null);
  const [copyState, setCopyState] = useState(COPY_IDLE);

  useEffect(() => {
    let cancelled = false;
    getLocalModelCommandProfile()
      .then((data) => {
        if (!cancelled) setCommandData(data);
      })
      .catch(() => {
        if (!cancelled) setCommandData(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeProfile = profileById(commandData, selectedProfileId);
  const profiles = commandProfiles(commandData);
  const helperNotes = commandNotes(commandData);
  const canCopy = commandAvailable(activeProfile);

  const onCopyCommand = useCallback(async () => {
    if (!activeProfile?.command) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(activeProfile.command);
        setCopyState(COPY_COPIED);
      } else {
        setCopyState(COPY_FAILED);
      }
    } catch {
      setCopyState(COPY_FAILED);
    }
    setTimeout(() => setCopyState(COPY_IDLE), 2600);
  }, [activeProfile]);

  return (
    <div className="sg-help">
      <div className="sg-page-head">
        <div>
          <h1>Help &amp; setup</h1>
          <p>Guides for getting the most out of GuideForge, starting with local-model chat.</p>
        </div>
      </div>

      <section className="sg-help-section">
        <div className="sg-help-section-head">
          <span className="sg-help-section-ico"><Server size={16} /></span>
          <div>
            <h2>Local model · llama-server setup</h2>
            <p>Ask Your Guide runs entirely on a local model. Start an OpenAI-compatible server on your host, then use it from the Models and Ask workspaces.</p>
          </div>
        </div>

        <div className="sg-help-grid">
          <div className="sg-help-step">
            <span className="sg-help-step-n">1</span>
            <div>
              <strong>Install a local server</strong>
              <p>Use <code>llama-server</code> (from llama.cpp) or another OpenAI-compatible local server. GuideForge never installs or launches it for you.</p>
            </div>
          </div>
          <div className="sg-help-step">
            <span className="sg-help-step-n">2</span>
            <div>
              <strong>Start it on your host</strong>
              <p>Copy the command below, point it at your downloaded model file, and run it in a terminal on your own machine.</p>
            </div>
          </div>
          <div className="sg-help-step">
            <span className="sg-help-step-n">3</span>
            <div>
              <strong>Point GuideForge at it</strong>
              <p>Set the Local provider base URL in <button type="button" className="sg-help-inline-link" onClick={() => onNavigate?.("models")}>Models</button>, then refresh local status. When it&rsquo;s reachable, chat unlocks in <button type="button" className="sg-help-inline-link" onClick={() => onNavigate?.("ask")}>Ask Guide</button>.</p>
            </div>
          </div>
        </div>

        <div className="sg-help-command">
          {canCopy ? (
            <CommandHelper
              prominent
              profiles={profiles}
              activeProfile={activeProfile}
              selectedProfileId={selectedProfileId}
              onSelectProfile={(id) => {
                setSelectedProfileId(id);
                setCopyState(COPY_IDLE);
              }}
              copyState={copyState}
              onCopy={onCopyCommand}
              notes={helperNotes}
            />
          ) : (
            <div className="sg-help-command-empty">
              <Terminal size={16} />
              <div>
                <strong>Command helper unavailable</strong>
                <p>The start-command helper could not be loaded right now. You can still run any OpenAI-compatible local server and set its base URL in Models.</p>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="sg-help-section">
        <div className="sg-help-section-head">
          <span className="sg-help-section-ico"><MessageSquareText size={16} /></span>
          <div>
            <h2>How Ask Your Guide works</h2>
            <p>A quick tour of the grounded, local-only chat flow.</p>
          </div>
        </div>

        <div className="sg-help-grid">
          <div className="sg-help-step">
            <span className="sg-help-step-ico"><BookOpen size={15} /></span>
            <div>
              <strong>Choose a guide</strong>
              <p>Pick a generated guide. Ask reads its artifacts read-only — it never edits the guide or its source.</p>
            </div>
          </div>
          <div className="sg-help-step">
            <span className="sg-help-step-ico"><Server size={15} /></span>
            <div>
              <strong>Prepare context</strong>
              <p>GuideForge builds a safe chunk index of the guide and extracted source. Only counts and citation labels are shown — never the underlying text.</p>
            </div>
          </div>
          <div className="sg-help-step">
            <span className="sg-help-step-ico"><ShieldCheck size={15} /></span>
            <div>
              <strong>Ask &mdash; locally</strong>
              <p>Questions and answers run only through your local model. Answers are grounded in retrieved chunks and cited; unsupported citations are removed automatically.</p>
            </div>
          </div>
        </div>

        <p className="sg-help-note">
          <ShieldCheck size={14} />
          Ask Your Guide is local-only by design. There is no cloud fallback or provider switching for chat, and chat history is never auto-exported.
        </p>
      </section>
    </div>
  );
}
