import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Info,
  Loader2,
} from "lucide-react";
import { artifactUrl, getJobArtifact } from "../api/client";
import {
  VISUAL_MANIFEST_ARTIFACT,
  VISUAL_PLAN_ARTIFACT,
  VISUAL_SCORING_ARTIFACT,
  isArtifactMissing,
  summarizeVisualManifest,
  summarizeVisualReplacementPlan,
  summarizeVisualScoring,
} from "../visualAdvisoryArtifacts";

// Slice 50 — read-only Job Details "Visual advisory" diagnostics.
//
// Surfaces the advisory visual artifact chain (manifest → scoring → replacement
// plan) using EXACT-name artifact fetches only. It shows safe COUNTS and
// closed-vocab status, never raw OCR text, captions, source text, image bytes,
// data URIs, base64, provider payloads, paths, tokens, or private document
// content. It makes no production include/omit decision and changes nothing about
// guide generation, prompts, extraction, OCR routing, rendering, or exports. A 404
// is treated as a normal "not generated for this job", not an error.

function toneClass(tone) {
  if (tone === "good") return "sg-tag-green";
  if (tone === "bad") return "sg-tag-red";
  return "sg-tag-amber";
}

function StatusIcon({ tone }) {
  if (tone === "good") return <CheckCircle2 />;
  if (tone === "bad") return <AlertCircle />;
  return <AlertTriangle />;
}

function Tile({ label, value, tone = "neutral" }) {
  return (
    <div className={`sg-tile${tone === "good" ? " good" : tone === "warn" ? " warn" : ""}`}>
      <div className="sg-tile-label">{label}</div>
      <div className="sg-tile-value">{value}</div>
    </div>
  );
}

// One artifact's fetch lifecycle. Independent so one missing/malformed artifact
// never blocks the others.
function useArtifact(jobId, artifactName) {
  const [state, setState] = useState({ loading: true, artifact: null, missing: false, error: false });
  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, artifact: null, missing: false, error: false });
    getJobArtifact(jobId, artifactName)
      .then((artifact) => {
        if (!cancelled) setState({ loading: false, artifact, missing: false, error: false });
      })
      .catch((err) => {
        if (cancelled) return;
        if (isArtifactMissing(err)) {
          setState({ loading: false, artifact: null, missing: true, error: false });
        } else {
          // Network / non-JSON / non-404: degrade to a calm "unavailable" notice;
          // never surface the raw error object or URL.
          setState({ loading: false, artifact: null, missing: false, error: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, artifactName]);
  return state;
}

function ArtifactLink({ jobId, artifactName, label }) {
  // Points ONLY at the exact-name artifact route — the single permitted URL.
  return (
    <a
      className="sg-artifact-link"
      href={artifactUrl(jobId, artifactName)}
      target="_blank"
      rel="noreferrer"
    >
      <ExternalLink style={{ width: 14, height: 14 }} />
      {label}
    </a>
  );
}

function ArtifactCard({ title, fetchState, view, jobId, artifactName, linkLabel, children }) {
  let badge;
  if (fetchState.loading) {
    badge = (
      <span className="sg-tag sg-tag-amber">
        <Loader2 className="sg-spin" />
        Loading
      </span>
    );
  } else if (fetchState.missing) {
    badge = (
      <span className="sg-tag sg-tag-amber">
        <AlertTriangle />
        Not available
      </span>
    );
  } else if (fetchState.error) {
    badge = (
      <span className="sg-tag sg-tag-amber">
        <AlertTriangle />
        Unavailable
      </span>
    );
  } else if (view) {
    badge = (
      <span className={`sg-tag ${toneClass(view.tone)}`}>
        <StatusIcon tone={view.tone} />
        {view.label}
      </span>
    );
  }

  return (
    <section>
      <div className="sg-head-row">
        <h3>{title}</h3>
        {badge}
      </div>
      {fetchState.missing && (
        <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
          Not generated for this job. Only PDF jobs with extracted visual signals produce this advisory artifact.
        </p>
      )}
      {fetchState.error && (
        <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
          The advisory artifact could not be read right now.
        </p>
      )}
      {!fetchState.loading && !fetchState.missing && !fetchState.error && view && view.state === "malformed" && (
        <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
          The advisory artifact was not in the expected shape.
        </p>
      )}
      {!fetchState.loading && !fetchState.missing && !fetchState.error && view && view.state === "skipped" && (
        <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
          Scoring/planning was skipped for this job ({view.reason}).
        </p>
      )}
      {!fetchState.loading && !fetchState.missing && !fetchState.error && view && view.state === "completed" && (
        <div style={{ marginTop: 10 }}>{children}</div>
      )}
      {!fetchState.loading && !fetchState.missing && !fetchState.error && view && (
        <p className="sg-hint" style={{ marginTop: 10 }}>
          <ArtifactLink jobId={jobId} artifactName={artifactName} label={linkLabel} />
        </p>
      )}
    </section>
  );
}

export default function VisualAdvisoryPanel({ jobId }) {
  const manifestState = useArtifact(jobId, VISUAL_MANIFEST_ARTIFACT);
  const scoringState = useArtifact(jobId, VISUAL_SCORING_ARTIFACT);
  const planState = useArtifact(jobId, VISUAL_PLAN_ARTIFACT);

  const manifestView = manifestState.artifact ? summarizeVisualManifest(manifestState.artifact) : null;
  const scoringView = scoringState.artifact ? summarizeVisualScoring(scoringState.artifact) : null;
  const planView = planState.artifact ? summarizeVisualReplacementPlan(planState.artifact) : null;

  return (
    <div className="sg-tab-stack">
      <section>
        <div className="sg-head-row">
          <h3>Visual advisory</h3>
        </div>
        <p className="sg-hint" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <Info style={{ width: 14, height: 14, flex: "none" }} />
          Advisory only: candidate visual diagnostics. They never change the generated guide, never embed visuals, and make no include/omit decision.
        </p>
      </section>

      <ArtifactCard
        title="Detected visual candidates"
        fetchState={manifestState}
        view={manifestView}
        jobId={jobId}
        artifactName={VISUAL_MANIFEST_ARTIFACT}
        linkLabel="Open manifest JSON"
      >
        {manifestView && (
          <div className="sg-grid-3">
            <Tile label="Candidates" value={String(manifestView.assetCount)} />
            <Tile label="Pages with signals" value={String(manifestView.pagesWithVisualSignals)} />
            <Tile label="Extracted figures" value={String(manifestView.extractedFigureCount)} />
          </div>
        )}
      </ArtifactCard>

      <ArtifactCard
        title="Asset scoring"
        fetchState={scoringState}
        view={scoringView}
        jobId={jobId}
        artifactName={VISUAL_SCORING_ARTIFACT}
        linkLabel="Open scoring JSON"
      >
        {scoringView && (
          <div className="sg-grid-3">
            <Tile label="Scored" value={String(scoringView.scoreCount)} />
            <Tile label="High" value={String(scoringView.highPriorityCount)} tone={scoringView.highPriorityCount ? "warn" : "neutral"} />
            <Tile label="Medium" value={String(scoringView.mediumPriorityCount)} />
            <Tile label="Low" value={String(scoringView.lowPriorityCount)} />
            <Tile label="Unknown" value={String(scoringView.unknownPriorityCount)} />
          </div>
        )}
      </ArtifactCard>

      <ArtifactCard
        title="Replacement plan"
        fetchState={planState}
        view={planView}
        jobId={jobId}
        artifactName={VISUAL_PLAN_ARTIFACT}
        linkLabel="Open replacement plan JSON"
      >
        {planView && (
          <>
            <div className="sg-grid-3">
              <Tile label="Items" value={String(planView.itemCount)} />
              <Tile label="Include as figure" value={String(planView.includeAsFigureCount)} />
              <Tile label="Convert to table" value={String(planView.convertToTableCount)} />
              <Tile label="Summarize as text" value={String(planView.summarizeAsTextCount)} />
              <Tile label="Review only" value={String(planView.reviewOnlyCount)} />
              <Tile label="Unknown" value={String(planView.unknownCount)} />
            </div>
            {planView.chandraBlockedPresent && (
              <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
                Some candidate items are advisory/blocked: Chandra-derived extraction remains blocked, so these are review-only candidates and are not acted on.
              </p>
            )}
          </>
        )}
      </ArtifactCard>
    </div>
  );
}
