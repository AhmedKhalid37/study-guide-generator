import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Info,
  Loader2,
} from "lucide-react";
import { artifactUrl, getJobArtifact } from "../api/client";
import {
  SOURCE_COVERAGE_ARTIFACT,
  VISUAL_INCLUSION_PLAN_ARTIFACT,
  buildMaterialCoverageDisplayModel,
  isCoverageArtifactMissing,
} from "../materialCoverageDisplay";

// Slice 88 — read-only Job Details "Material coverage" display.
//
// Surfaces the already-produced Full Material Coverage signals using EXACT-name
// artifact fetches plus the safe job-response selection envelopes. It shows COUNTS
// and closed-vocab status ONLY, never filenames, paths, source titles, document /
// OCR / caption / table text, image / asset refs, image bytes, data URIs, base64,
// provider payloads, tokens, or full URLs. It makes no production decision and
// changes nothing about extraction, OCR routing, visual filtering/planning, table
// policy, rendering, exports, prompts, or providers. A 404 means "not generated for
// this job", treated as a normal "not available", not an error.

function toneClass(tone) {
  if (tone === "good") return "sg-tag-green";
  if (tone === "bad") return "sg-tag-red";
  if (tone === "neutral") return "sg-tag-slate";
  return "sg-tag-amber";
}

function Tile({ label, value, tone = "neutral" }) {
  return (
    <div className={`sg-tile${tone === "good" ? " good" : tone === "warn" ? " warn" : ""}`}>
      <div className="sg-tile-label">{label}</div>
      <div className="sg-tile-value">{value}</div>
    </div>
  );
}

// Independent fetch lifecycle per artifact so one missing/malformed artifact never
// blocks the other.
function useCoverageArtifact(jobId, artifactName) {
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
        if (isCoverageArtifactMissing(err)) {
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
  // Points ONLY at the exact-name artifact route — the single permitted URL, built
  // from the encoded job id + fixed artifact name (no source filename).
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

function Badge({ fetchState }) {
  if (fetchState.loading) {
    return (
      <span className="sg-tag sg-tag-amber">
        <Loader2 className="sg-spin" />
        Loading
      </span>
    );
  }
  if (fetchState.missing) {
    return (
      <span className="sg-tag sg-tag-slate">
        <Info />
        Not available
      </span>
    );
  }
  if (fetchState.error) {
    return (
      <span className="sg-tag sg-tag-amber">
        <AlertTriangle />
        Unavailable
      </span>
    );
  }
  return null;
}

function UnavailableNotice() {
  return (
    <p className="sg-notice" style={{ marginTop: 12 }}>
      Coverage artifact not available for this job yet.
    </p>
  );
}

export default function MaterialCoveragePanel({ jobId, job }) {
  const coverageState = useCoverageArtifact(jobId, SOURCE_COVERAGE_ARTIFACT);
  const planState = useCoverageArtifact(jobId, VISUAL_INCLUSION_PLAN_ARTIFACT);

  const model = buildMaterialCoverageDisplayModel({
    job,
    sourceCoverageReport: coverageState.artifact,
    visualInclusionPlan: planState.artifact,
  });

  const { selections, sourceCoverage, visualCoverage, tablePolicy } = model;

  const coverageResolved = !coverageState.loading && !coverageState.missing && !coverageState.error;
  const planResolved = !planState.loading && !planState.missing && !planState.error;

  return (
    <div className="sg-tab-stack">
      <section>
        <div className="sg-head-row">
          <h3>Material coverage</h3>
        </div>
        <p className="sg-hint" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <Info style={{ width: 14, height: 14, flex: "none" }} />
          Read-only coverage signals: safe counts and status only. They never change the generated guide and show no source filenames, page text, or captions.
        </p>
      </section>

      {/* Material page selections — from the safe job response, no artifact fetch. */}
      <section>
        <div className="sg-head-row">
          <h3>Material page selections</h3>
          <span className={`sg-tag ${selections.status === "active" ? "sg-tag-green" : "sg-tag-slate"}`}>
            {selections.status === "active" ? <CheckCircle2 /> : <Info />}
            {selections.status === "active" ? "Active" : "Inactive"}
          </span>
        </div>
        <div className="sg-grid-3" style={{ marginTop: 10 }}>
          <Tile label="Attachments with exclusions" value={String(selections.attachmentsWithSelections)} />
          <Tile label="Global selection" value={selections.globalActive ? "Set" : "All pages"} />
        </div>
      </section>

      {/* Source coverage — exact-name source_coverage_report.json. */}
      <section>
        <div className="sg-head-row">
          <h3>Source coverage</h3>
          {coverageResolved ? (
            <span className={`sg-tag ${toneClass(sourceCoverage.tone)}`}>
              {sourceCoverage.status === "completed" ? <CheckCircle2 /> : <Info />}
              {sourceCoverage.status}
            </span>
          ) : (
            <Badge fetchState={coverageState} />
          )}
        </div>
        {(coverageState.missing || coverageState.error) && <UnavailableNotice />}
        {coverageResolved && sourceCoverage.state === "malformed" && (
          <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
            The coverage report was not in the expected shape.
          </p>
        )}
        {coverageResolved && sourceCoverage.state !== "malformed" && (
          <>
            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              <Tile label="Sources" value={String(sourceCoverage.sourceCount)} />
              <Tile label="Total pages" value={String(sourceCoverage.totalPages)} />
              <Tile label="Covered" value={String(sourceCoverage.coveredPages)} tone="good" />
              <Tile label="Embedded text" value={String(sourceCoverage.embeddedTextPages)} />
              <Tile label="OCR" value={String(sourceCoverage.ocrPages)} />
              <Tile
                label="Unreadable / empty"
                value={String(sourceCoverage.unreadablePages)}
                tone={sourceCoverage.unreadablePages ? "warn" : "neutral"}
              />
            </div>
            <p className="sg-hint" style={{ marginTop: 10 }}>
              <ArtifactLink jobId={jobId} artifactName={SOURCE_COVERAGE_ARTIFACT} label="Open coverage report JSON" />
            </p>
          </>
        )}
      </section>

      {/* Visual coverage — exact-name visual_inclusion_plan.json. */}
      <section>
        <div className="sg-head-row">
          <h3>Visual coverage</h3>
          {planResolved ? (
            <span className={`sg-tag ${toneClass(visualCoverage.tone)}`}>
              {visualCoverage.status === "completed" ? <CheckCircle2 /> : <Info />}
              {visualCoverage.status}
            </span>
          ) : (
            <Badge fetchState={planState} />
          )}
        </div>
        {(planState.missing || planState.error) && <UnavailableNotice />}
        {planResolved && visualCoverage.state === "malformed" && (
          <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
            The visual inclusion plan was not in the expected shape.
          </p>
        )}
        {planResolved && visualCoverage.state !== "malformed" && (
          <>
            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              <Tile label="Candidates" value={String(visualCoverage.candidateCount)} />
              <Tile label="Planned (non-table)" value={String(visualCoverage.plannedUsefulCount)} tone="good" />
              <Tile label="Table-like skipped" value={String(visualCoverage.tableLikeSkippedCount)} />
              <Tile
                label="Unsafe / incomplete skipped"
                value={String(visualCoverage.unsafeSkippedCount)}
                tone={visualCoverage.unsafeSkippedCount ? "warn" : "neutral"}
              />
              <Tile label="Pages with planned visuals" value={String(visualCoverage.pagesWithPlannedVisuals)} />
            </div>
            <p className="sg-hint" style={{ marginTop: 10 }}>
              <ArtifactLink jobId={jobId} artifactName={VISUAL_INCLUSION_PLAN_ARTIFACT} label="Open visual inclusion plan JSON" />
            </p>
          </>
        )}
      </section>

      {/* Table policy — static deferred note (Slice 85 core only). */}
      <section>
        <div className="sg-head-row">
          <h3>Table policy</h3>
          <span className="sg-tag sg-tag-slate">
            <Info />
            Deferred
          </span>
        </div>
        <p className="sg-hint" style={{ marginTop: 10 }}>
          {tablePolicy.note}
        </p>
      </section>
    </div>
  );
}
