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
  TABLE_CANDIDATES_MANIFEST_ARTIFACT,
  TABLE_RECONSTRUCTION_POLICY_ARTIFACT,
  GUIDE_QUALITY_REPORT_V2_ARTIFACT,
  buildMaterialCoverageFinalModel,
  isCoverageArtifactMissing,
} from "../materialCoverageDisplay";
import { buildJobMaterialCoverageNotes } from "../materialCoverageWarnings";

// Slice 97 — read-only JobDetails "Material coverage" FINAL panel.
//
// Builds on the Slice 88/89 panel and upgrades it into the final read-only coverage
// dashboard for the current material-coverage phase. It fetches the safe EXACT-name
// artifacts (source coverage, visual inclusion plan, table candidates manifest,
// table reconstruction policy, guide quality report v2) plus the safe job-response
// selection envelopes, and shows COUNTS and closed-vocab status/check tokens ONLY.
// It never surfaces filenames, paths, source titles, document / OCR / caption /
// table text, image / asset refs, image bytes, data URIs, base64, provider payloads,
// tokens, full URLs, or raw artifact warnings/errors. It makes no production
// decision and changes nothing about extraction, OCR routing, visual
// filtering/planning, table policy, rendering, exports, prompts, figure insertion,
// or providers. A 404 means "not generated for this job", treated as a normal
// "Not available", not an error.

function toneClass(tone) {
  if (tone === "good") return "sg-tag-green";
  if (tone === "bad") return "sg-tag-red";
  if (tone === "neutral") return "sg-tag-slate";
  return "sg-tag-amber";
}

// Map a closed guide-quality check status to a tag class. Anything unexpected has
// already been clamped to "unknown" by the helper before it reaches here.
function checkStatusClass(status) {
  if (status === "passed") return "sg-tag-green";
  if (status === "warning") return "sg-tag-amber";
  if (status === "not_applicable") return "sg-tag-slate";
  return "sg-tag-slate";
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
// blocks the others.
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

// A fixed exact-name artifact link row that calmly shows "Not available" when the
// artifact was not generated for this job (older jobs / non-PDF jobs).
function ArtifactLinkRow({ jobId, artifactName, label, fetchState }) {
  const resolved = !fetchState.loading && !fetchState.missing && !fetchState.error;
  return (
    <li className="sg-artifact-link-row">
      <span className="sg-artifact-link-label">{label}</span>
      {fetchState.loading ? (
        <span className="sg-tag sg-tag-amber">
          <Loader2 className="sg-spin" />
          Loading
        </span>
      ) : resolved ? (
        <ArtifactLink jobId={jobId} artifactName={artifactName} label="Open JSON" />
      ) : (
        <span className="sg-tag sg-tag-slate">
          <Info />
          Not available
        </span>
      )}
    </li>
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

const CHECK_LABELS = {
  source_pages: "Source pages",
  visuals: "Visuals",
  tables: "Tables",
  missing_material: "Missing material",
  coverage: "Coverage",
};

// Fixed deterministic order for the guide-quality check chips.
const GUIDE_QUALITY_CHECK_ORDER = [
  "source_pages",
  "visuals",
  "tables",
  "missing_material",
  "coverage",
];

export default function MaterialCoveragePanel({ jobId, job }) {
  const coverageState = useCoverageArtifact(jobId, SOURCE_COVERAGE_ARTIFACT);
  const planState = useCoverageArtifact(jobId, VISUAL_INCLUSION_PLAN_ARTIFACT);
  const tableManifestState = useCoverageArtifact(jobId, TABLE_CANDIDATES_MANIFEST_ARTIFACT);
  const tablePolicyState = useCoverageArtifact(jobId, TABLE_RECONSTRUCTION_POLICY_ARTIFACT);
  const guideQualityState = useCoverageArtifact(jobId, GUIDE_QUALITY_REPORT_V2_ARTIFACT);

  const model = buildMaterialCoverageFinalModel({
    job,
    sourceCoverageReport: coverageState.artifact,
    visualInclusionPlan: planState.artifact,
    tableCandidatesManifest: tableManifestState.artifact,
    tableReconstructionPolicy: tablePolicyState.artifact,
    guideQualityReportV2: guideQualityState.artifact,
  });

  const {
    selections,
    sourceCoverage,
    visualCoverage,
    tableCandidates,
    tableReconstructionPolicy,
    guideQuality,
  } = model;

  const coverageResolved = !coverageState.loading && !coverageState.missing && !coverageState.error;
  const planResolved = !planState.loading && !planState.missing && !planState.error;
  const tableManifestResolved =
    !tableManifestState.loading && !tableManifestState.missing && !tableManifestState.error;
  const tablePolicyResolved =
    !tablePolicyState.loading && !tablePolicyState.missing && !tablePolicyState.error;
  const guideQualityResolved =
    !guideQualityState.loading && !guideQualityState.missing && !guideQualityState.error;

  // Slice 89: closed-vocabulary, honest "what this means" notes. Only computed once
  // both base artifact fetches have settled so we never flash a premature note.
  const fetchesSettled = !coverageState.loading && !planState.loading;
  const coverageNotes = fetchesSettled ? buildJobMaterialCoverageNotes(model) : [];

  return (
    <div className="sg-tab-stack">
      <section>
        <div className="sg-head-row">
          <h3>Material coverage</h3>
        </div>
        <p className="sg-hint" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <Info style={{ width: 14, height: 14, flex: "none" }} />
          Read-only coverage signals: safe counts and status only. They never change the generated guide and show no source filenames, page text, captions, or table contents.
        </p>
      </section>

      {/* 1. Material page selections — from the safe job response, no artifact fetch. */}
      <section>
        <div className="sg-head-row">
          <h3>Material selections</h3>
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

      {/* 2. Source coverage — exact-name source_coverage_report.json. */}
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
        )}
      </section>

      {/* 3. Figures and diagrams — visual_inclusion_plan.json + observed refs from
          guide_quality_report_v2.json. */}
      <section>
        <div className="sg-head-row">
          <h3>Figures and diagrams</h3>
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
          <div className="sg-grid-3" style={{ marginTop: 10 }}>
            <Tile label="Planned (non-table)" value={String(visualCoverage.plannedUsefulCount)} tone="good" />
            <Tile
              label="Observed figure refs"
              value={
                guideQualityResolved && guideQuality.state !== "malformed"
                  ? String(guideQuality.safeImageRefCount)
                  : "—"
              }
            />
            <Tile
              label="Visual check"
              value={
                guideQualityResolved && guideQuality.state !== "malformed"
                  ? guideQuality.checks.visuals
                  : "—"
              }
              tone={
                guideQualityResolved && guideQuality.checks.visuals === "warning" ? "warn" : "neutral"
              }
            />
          </div>
        )}
        <p className="sg-hint" style={{ marginTop: 10 }}>
          Full insertion may be off for older/default jobs; planned visuals are not always inserted.
        </p>
      </section>

      {/* 4. Tables — table_candidates_manifest.json + table_reconstruction_policy.json. */}
      <section>
        <div className="sg-head-row">
          <h3>Tables</h3>
          {tablePolicyResolved ? (
            <span className={`sg-tag ${toneClass(tableReconstructionPolicy.tone)}`}>
              {tableReconstructionPolicy.status === "completed" ? <CheckCircle2 /> : <Info />}
              {tableReconstructionPolicy.status}
            </span>
          ) : (
            <Badge fetchState={tablePolicyState} />
          )}
        </div>
        {(tableManifestState.missing || tableManifestState.error) &&
          (tablePolicyState.missing || tablePolicyState.error) && <UnavailableNotice />}
        <div className="sg-grid-3" style={{ marginTop: 10 }}>
          <Tile
            label="Table candidates"
            value={
              tableManifestResolved && tableCandidates.state !== "malformed"
                ? String(tableCandidates.tableLikeCandidateCount)
                : "—"
            }
          />
          <Tile
            label="Policy items"
            value={
              tablePolicyResolved && tableReconstructionPolicy.state !== "malformed"
                ? String(tableReconstructionPolicy.policyItemCount)
                : "—"
            }
          />
          <Tile
            label="Screenshot inserts"
            value={
              tablePolicyResolved && tableReconstructionPolicy.state !== "malformed"
                ? tableReconstructionPolicy.screenshotInsertCount === 0
                  ? "Not used"
                  : String(tableReconstructionPolicy.screenshotInsertCount)
                : "Not used"
            }
          />
        </div>
        {tablePolicyResolved && tableReconstructionPolicy.state !== "malformed" && (
          <div className="sg-grid-3" style={{ marginTop: 10 }}>
            <Tile label="Reconstruct + original" value={String(tableReconstructionPolicy.reconstructWithOriginalCount)} />
            <Tile label="Simplify only" value={String(tableReconstructionPolicy.simplifyOnlyCount)} />
            <Tile label="Defer" value={String(tableReconstructionPolicy.deferCount)} />
            <Tile label="Skip unreadable" value={String(tableReconstructionPolicy.skipUnreadableCount)} />
            <Tile label="Skip unsafe" value={String(tableReconstructionPolicy.skipUnsafeCount)} />
          </div>
        )}
        <p className="sg-hint" style={{ marginTop: 10 }}>
          Tables are not inserted as screenshots. Reconstruction happens only when source text supports it.
        </p>
      </section>

      {/* 5. Missing material — status from guide_quality_report_v2.json. */}
      <section>
        <div className="sg-head-row">
          <h3>Missing material</h3>
          {guideQualityResolved && guideQuality.state !== "malformed" ? (
            <span className={`sg-tag ${checkStatusClass(guideQuality.checks.missing_material)}`}>
              <Info />
              {guideQuality.checks.missing_material}
            </span>
          ) : (
            <Badge fetchState={guideQualityState} />
          )}
        </div>
        {guideQualityResolved && guideQuality.state !== "malformed" && (
          <div className="sg-grid-3" style={{ marginTop: 10 }}>
            <Tile label="Missing-material items" value={String(guideQuality.missingMaterialItemCount)} />
            <Tile
              label="Missing-material check"
              value={guideQuality.checks.missing_material}
              tone={guideQuality.checks.missing_material === "warning" ? "warn" : "neutral"}
            />
          </div>
        )}
        <p className="sg-hint" style={{ marginTop: 10 }}>
          Unavailable diagrams/tables should be noted rather than guessed.
        </p>
      </section>

      {/* 6. Guide quality v2 — guide_quality_report_v2.json. */}
      <section>
        <div className="sg-head-row">
          <h3>Guide quality v2</h3>
          {guideQualityResolved ? (
            <span className={`sg-tag ${toneClass(guideQuality.tone)}`}>
              {guideQuality.status === "completed" ? <CheckCircle2 /> : <Info />}
              {guideQuality.status}
            </span>
          ) : (
            <Badge fetchState={guideQualityState} />
          )}
        </div>
        {(guideQualityState.missing || guideQualityState.error) && <UnavailableNotice />}
        {guideQualityResolved && guideQuality.state === "malformed" && (
          <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
            The guide quality report was not in the expected shape.
          </p>
        )}
        {guideQualityResolved && guideQuality.state !== "malformed" && (
          <>
            <div className="sg-coverage-checks" style={{ marginTop: 10 }}>
              {GUIDE_QUALITY_CHECK_ORDER.map((kind) => (
                <span key={kind} className={`sg-tag ${checkStatusClass(guideQuality.checks[kind])}`}>
                  {CHECK_LABELS[kind]}: {guideQuality.checks[kind]}
                </span>
              ))}
            </div>
            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              <Tile
                label="Warnings"
                value={String(guideQuality.warningCount)}
                tone={guideQuality.warningCount ? "warn" : "neutral"}
              />
            </div>
            <p className="sg-hint" style={{ marginTop: 10 }}>
              This is deterministic signal checking, not semantic grading.
            </p>
          </>
        )}
      </section>

      {/* 7. Artifact links — fixed exact-name links only; calm "Not available". */}
      <section>
        <div className="sg-head-row">
          <h3>Artifacts</h3>
        </div>
        <ul className="sg-artifact-links" style={{ marginTop: 10 }}>
          <ArtifactLinkRow
            jobId={jobId}
            artifactName={SOURCE_COVERAGE_ARTIFACT}
            label="Source coverage report"
            fetchState={coverageState}
          />
          <ArtifactLinkRow
            jobId={jobId}
            artifactName={VISUAL_INCLUSION_PLAN_ARTIFACT}
            label="Visual inclusion plan"
            fetchState={planState}
          />
          <ArtifactLinkRow
            jobId={jobId}
            artifactName={TABLE_CANDIDATES_MANIFEST_ARTIFACT}
            label="Table candidates manifest"
            fetchState={tableManifestState}
          />
          <ArtifactLinkRow
            jobId={jobId}
            artifactName={TABLE_RECONSTRUCTION_POLICY_ARTIFACT}
            label="Table reconstruction policy"
            fetchState={tablePolicyState}
          />
          <ArtifactLinkRow
            jobId={jobId}
            artifactName={GUIDE_QUALITY_REPORT_V2_ARTIFACT}
            label="Guide quality report v2"
            fetchState={guideQualityState}
          />
        </ul>
      </section>

      {/* Coverage notes — Slice 89 "what this means". Closed-vocabulary, honest copy
          only; never claims full figure insertion / table reconstruction is enabled,
          and never echoes raw artifact warning text. */}
      {coverageNotes.length > 0 && (
        <section>
          <div className="sg-head-row">
            <h3>What this means</h3>
          </div>
          <ul className="sg-coverage-notes">
            {coverageNotes.map((note) => (
              <li key={note.token} className="sg-coverage-note">
                {note.tone === "good" ? (
                  <CheckCircle2 className={`sg-coverage-note-icon good`} />
                ) : (
                  <Info className="sg-coverage-note-icon" />
                )}
                <span>{note.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
