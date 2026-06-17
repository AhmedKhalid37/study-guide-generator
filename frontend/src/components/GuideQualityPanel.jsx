import React, { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, ExternalLink, HelpCircle, Info, Loader2, MinusCircle } from "lucide-react";
import { getJobArtifact } from "../api/client";
import {
  GUIDE_QUALITY_QA_GATE_ARTIFACT,
  GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT,
  GUIDE_QUALITY_REPORT_V2_ARTIFACT,
  GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT,
  MATH_VERIFICATION_ARTIFACT,
  QUALITY_SAFETY_ARTIFACT,
  SOURCE_COVERAGE_ARTIFACT,
  summarizeGuideQualityPanelModel,
} from "../guideQualityDisplay";

// Read-only / advisory. Surfaces the already-sanitized deterministic guide-quality
// signals (Slices 102/103 + the older coverage/math measurements). It changes no
// generation behavior, calls no LLM, inspects no PDF/image, and never auto-rejects
// or regenerates. Each artifact is fetched on its own lifecycle; a 404 or any other
// error degrades that section to a calm "unavailable" state — older jobs without
// these artifacts still render.

const ADVISORY_COPY =
  "This is an advisory deterministic QA signal, not semantic grading. It does not block generation yet.";

const QA_GATE_STATUS_LABEL = {
  passed: "Passed",
  warning: "Warning",
  partial: "Partial",
  skipped: "Skipped",
  unknown: "Unavailable",
};

const CHECK_KIND_LABEL = {
  reasoning_leak: "Reasoning leak",
  required_structure: "Required structure",
  math_verification: "Math verification",
  source_coverage: "Source coverage",
  quality_report_v2: "Quality report v2",
};

const CHECK_STATUS_LABEL = {
  passed: "Passed",
  warning: "Warning",
  unknown: "Unknown",
  not_applicable: "Not applicable",
};

const RUBRIC_STATUS_LABEL = {
  completed: "Completed",
  partial: "Partial",
  skipped: "Skipped",
};

const RUBRIC_AXIS_LABEL = {
  reasoning_hygiene: "Reasoning hygiene",
  required_structure: "Required structure",
  exam_focus: "Exam focus",
  reference_tables: "Reference tables",
  math_verification: "Math verification",
  source_coverage: "Source coverage",
  coverage_signal_alignment: "Coverage signal alignment",
  visual_table_honesty: "Visual/table honesty",
  beginner_scaffolding: "Beginner scaffolding",
  worked_example_completeness: "Worked example completeness",
};

const RUBRIC_CONFIDENCE_LABEL = {
  deterministic: "Deterministic",
  advisory: "Advisory",
  unsupported: "Unsupported",
};

const QUALITY_SAFETY_STATUS_LABEL = {
  passed: "Passed",
  warning: "Warning",
  failed: "Failed",
  skipped: "Skipped",
  partial: "Partial",
  unknown: "Unknown",
  missing: "Missing",
  unavailable: "Unavailable",
};

const QUALITY_SAFETY_COMPONENT_LABEL = {
  layer1: "Layer 1",
  recompute: "Recompute",
  canonical: "Canonical",
  leak: "Leak",
  unknown: "Unknown",
};

const QUALITY_SAFETY_AXIS_LABEL = {
  accuracy: "Accuracy",
  coverage: "Coverage",
  solved_problem: "Solved problem",
  clarity: "Clarity",
};

const QUALITY_SAFETY_COUNT_LABEL = {
  blocking_failure_count: "Blocking failures",
  warning_count: "Warnings",
  numeric_blocking_failure_count: "Numeric blockers",
  leak_blocking_failure_count: "Leak blockers",
  verified_recompute_count: "Verified recompute",
  verified_canonical_count: "Verified canonical",
  failed_recompute_count: "Failed recompute",
  failed_canonical_count: "Failed canonical",
  unverified_fact_count: "Unverified facts",
  unknown_context_leak_count: "Unknown leak context",
};

function toneClass(tone) {
  if (tone === "good") return "sg-tag-green";
  if (tone === "bad") return "sg-tag-red";
  return "sg-tag-amber";
}

function noticeClass(tone) {
  if (tone === "good") return "sg-notice-green";
  if (tone === "bad") return "sg-notice-red";
  return "sg-notice-amber";
}

function StatusIcon({ tone }) {
  if (tone === "good") return <CheckCircle2 />;
  if (tone === "bad") return <AlertCircle />;
  return <AlertTriangle />;
}

function checkStatusTagClass(status) {
  if (status === "passed") return "sg-tag-green";
  if (status === "warning" || status === "failed") return "sg-tag-red";
  return "sg-tag-amber"; // unknown / not_applicable
}

function CheckStatusIcon({ status }) {
  if (status === "passed") return <CheckCircle2 />;
  if (status === "warning" || status === "failed") return <AlertCircle />;
  if (status === "not_applicable") return <MinusCircle />;
  return <HelpCircle />;
}

function QualityTile({ label, value, tone = "neutral" }) {
  return (
    <div className={`sg-tile${tone === "good" ? " good" : tone === "warn" ? " warn" : ""}`}>
      <div className="sg-tile-label">{label}</div>
      <div className="sg-tile-value">{value}</div>
    </div>
  );
}

function NotAvailableNotice({ children }) {
  return (
    <p className="sg-notice sg-notice-amber" style={{ marginTop: 10 }}>
      {children}
    </p>
  );
}

// Fetch one exact-name artifact, resolving to its JSON or ``null`` on any error
// (404 = not generated; non-JSON / network = unavailable). Never surfaces raw
// error text or URLs.
function fetchArtifactOrNull(jobId, artifactName) {
  return getJobArtifact(jobId, artifactName).then(
    (artifact) => artifact,
    () => null,
  );
}

export default function GuideQualityPanel({ jobId }) {
  const [state, setState] = useState({ loading: true, model: null });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, model: null });
    Promise.all([
      fetchArtifactOrNull(jobId, GUIDE_QUALITY_QA_GATE_ARTIFACT),
      fetchArtifactOrNull(jobId, GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT),
      fetchArtifactOrNull(jobId, GUIDE_QUALITY_REPORT_V2_ARTIFACT),
      fetchArtifactOrNull(jobId, MATH_VERIFICATION_ARTIFACT),
      fetchArtifactOrNull(jobId, SOURCE_COVERAGE_ARTIFACT),
      fetchArtifactOrNull(jobId, GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT),
      fetchArtifactOrNull(jobId, QUALITY_SAFETY_ARTIFACT),
    ]).then(([qaGate, contractLint, guideQualityReportV2, mathVerification, sourceCoverageReport, rubricScore, qualitySafetyArtifact]) => {
      if (cancelled) return;
      const model = summarizeGuideQualityPanelModel({
        qaGate,
        contractLint,
        guideQualityReportV2,
        mathVerification,
        sourceCoverageReport,
        rubricScore,
        qualitySafetyArtifact,
      });
      setState({ loading: false, model });
    });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (state.loading || !state.model) {
    return (
      <div className="recent-state">
        <Loader2 className="sg-spin" />
        <span>Loading guide quality...</span>
      </div>
    );
  }

  const model = state.model;
  const gate = model.qaGate;
  const lint = model.contractLint;
  const math = model.mathVerification;
  const coverage = model.sourceCoverage;
  const reportV2 = model.guideQualityReportV2;
  const rubric = model.rubricScore;
  const qualitySafety = model.qualitySafety;

  return (
    <div className="sg-tab-stack">
      {/* 1. Overall QA gate */}
      <section>
        <div className="sg-head-row">
          <div>
            <h3>Guide quality</h3>
            <p className="sg-hint">Advisory, read-only quality signals — generation is never blocked.</p>
          </div>
          {model.qaGateAvailable ? (
            <span className={`sg-tag ${toneClass(gate.tone)}`}>
              <StatusIcon tone={gate.tone} />
              {QA_GATE_STATUS_LABEL[gate.status] || "Unavailable"}
            </span>
          ) : (
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          )}
        </div>

        {model.qaGateAvailable ? (
          <>
            <div className="sg-grid-3" style={{ marginTop: 12 }}>
              <QualityTile label="Checks" value={String(gate.checkCount)} />
              <QualityTile label="Passed" value={String(gate.passedCount)} tone={gate.passedCount ? "good" : "neutral"} />
              <QualityTile label="Warnings" value={String(gate.warningCount)} tone={gate.warningCount ? "warn" : "neutral"} />
              <QualityTile label="Unknown" value={String(gate.unknownCount)} />
              <QualityTile label="Blocking" value={gate.blocking ? "Yes" : "No"} />
              <QualityTile label="Scope" value={gate.comprehensive ? "Comprehensive" : "Standard"} />
            </div>
            <p className="sg-hint" style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 6 }}>
              <Info style={{ width: 14, height: 14, flex: "none" }} />
              {ADVISORY_COPY}
            </p>
          </>
        ) : (
          <NotAvailableNotice>
            No guide-quality QA gate is available for this job. Older jobs may not include one.
          </NotAvailableNotice>
        )}
      </section>

      {/* 2. Rubric score */}
      <section>
        <div className="sg-head-row">
          <div>
            <h3>Rubric score</h3>
            <p className="sg-hint">
              This rubric is deterministic and advisory. Unsupported semantic axes stay unknown instead of being fake-scored.
            </p>
          </div>
          {model.rubricScoreAvailable && rubric.state !== "malformed" ? (
            <span className={`sg-tag ${toneClass(rubric.tone)}`}>
              <StatusIcon tone={rubric.tone} />
              {RUBRIC_STATUS_LABEL[rubric.status] || "Skipped"}
            </span>
          ) : (
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          )}
        </div>
        {model.rubricScoreAvailable && rubric.state !== "malformed" ? (
          <>
            <div className="sg-grid-3" style={{ marginTop: 12 }}>
              <QualityTile label="Score" value={`${rubric.scoreTotal}/${rubric.scorePossible}`} />
              <QualityTile label="Known axes" value={String(rubric.knownAxisCount)} />
              <QualityTile label="Unknown axes" value={String(rubric.unknownAxisCount)} tone={rubric.unknownAxisCount ? "warn" : "neutral"} />
              <QualityTile label="Warning axes" value={String(rubric.warningAxisCount)} tone={rubric.warningAxisCount ? "warn" : "neutral"} />
              <QualityTile label="Rubric axes" value={String(rubric.rubricAxisCount)} />
              <QualityTile label="Blocking" value={rubric.blocking ? "Yes" : "No"} />
            </div>
            {rubric.axes.length > 0 ? (
              <ul className="sg-mathv-list" style={{ marginTop: 10 }}>
                {rubric.axes.map((axis, index) => (
                  <li key={`${axis.kind}-${index}`} className="sg-mathv-claim">
                    <div className="sg-mathv-claim-head">
                      <span className={`sg-tag ${checkStatusTagClass(axis.status)}`}>
                        <CheckStatusIcon status={axis.status} />
                        {CHECK_STATUS_LABEL[axis.status] || "Unknown"}
                      </span>
                      <span className="sg-mathv-id">{RUBRIC_AXIS_LABEL[axis.kind] || "Rubric axis"}</span>
                      <span className="sg-tag sg-tag-slate">{RUBRIC_CONFIDENCE_LABEL[axis.confidence] || "Unsupported"}</span>
                      <span className="sg-tag sg-tag-slate">{axis.score === null ? "Score n/a" : `Score ${axis.score}`}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="sg-hint" style={{ marginTop: 10 }}>No rubric axes are available for this job.</p>
            )}
          </>
        ) : (
          <NotAvailableNotice>
            No guide-quality rubric score is available for this job. Older jobs may not include one.
          </NotAvailableNotice>
        )}
      </section>

      {/* 3. Quality Safety advisory floor */}
      <section>
        <div className="sg-head-row">
          <div>
            <h3>Quality Safety</h3>
            <p className="sg-hint">Advisory deterministic safety floor; read-only and non-blocking.</p>
          </div>
          {model.qualitySafetyAvailable ? (
            <span className={`sg-tag ${toneClass(qualitySafety.tone)}`}>
              <StatusIcon tone={qualitySafety.tone} />
              {QUALITY_SAFETY_STATUS_LABEL[qualitySafety.status] || "Unknown"}
            </span>
          ) : (
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          )}
        </div>
        {model.qualitySafetyAvailable ? (
          <>
            <div className="sg-grid-3" style={{ marginTop: 12 }}>
              <QualityTile label="Artifact" value={QUALITY_SAFETY_STATUS_LABEL[qualitySafety.artifactStatus] || "Loaded"} />
              <QualityTile label="Advisory" value={formatQualitySafetyBool(qualitySafety.advisory)} />
              <QualityTile label="Unified status" value={QUALITY_SAFETY_STATUS_LABEL[qualitySafety.status] || "Unknown"} />
              <QualityTile label="Shippable" value={formatQualitySafetyBool(qualitySafety.shippable)} />
              <QualityTile
                label="Safety floor green"
                value={formatQualitySafetyBool(qualitySafety.safetyFloorGreen)}
                tone={qualitySafety.safetyFloorGreen === false ? "warn" : qualitySafety.safetyFloorGreen === true ? "good" : "neutral"}
              />
            </div>

            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              {Object.entries(qualitySafety.componentStatuses).map(([component, status]) => (
                <QualityTile
                  key={component}
                  label={QUALITY_SAFETY_COMPONENT_LABEL[component] || "Component"}
                  value={QUALITY_SAFETY_STATUS_LABEL[status] || "Unknown"}
                  tone={status === "passed" ? "good" : status === "failed" || status === "warning" ? "warn" : "neutral"}
                />
              ))}
            </div>

            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              {Object.entries(qualitySafety.axes).map(([axis, value]) => (
                <QualityTile
                  key={axis}
                  label={QUALITY_SAFETY_AXIS_LABEL[axis] || "Axis"}
                  value={value === null ? "Unavailable" : `${value}/5`}
                  tone={value !== null && value >= 4 ? "good" : value !== null && value < 3 ? "warn" : "neutral"}
                />
              ))}
            </div>

            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              {Object.entries(qualitySafety.summary).map(([key, value]) => (
                <QualityTile
                  key={key}
                  label={QUALITY_SAFETY_COUNT_LABEL[key] || key}
                  value={String(value)}
                  tone={value > 0 && (key.includes("failure") || key.includes("failed") || key.includes("warning") || key.includes("unknown")) ? "warn" : "neutral"}
                />
              ))}
            </div>

            {qualitySafety.blockingFailures.length > 0 ? (
              <ul className="sg-mathv-list" style={{ marginTop: 10 }}>
                {qualitySafety.blockingFailures.map((failure, index) => (
                  <li key={`${failure.component}-${failure.checkId}-${index}`} className="sg-mathv-claim">
                    <div className="sg-mathv-claim-head">
                      <span className={`sg-tag ${checkStatusTagClass(failure.status)}`}>
                        <CheckStatusIcon status={failure.status} />
                        {QUALITY_SAFETY_STATUS_LABEL[failure.status] || "Unknown"}
                      </span>
                      <span className="sg-mathv-id">{QUALITY_SAFETY_COMPONENT_LABEL[failure.component] || "Unknown"}</span>
                      <span className="sg-tag sg-tag-slate">{failure.checkId}</span>
                      <span className="sg-tag sg-tag-slate">{failure.severity}</span>
                      <span className="sg-tag sg-tag-slate">{failure.verificationStatus}</span>
                      {failure.count ? <span className="sg-tag sg-tag-slate">Count {failure.count}</span> : null}
                      {failure.factIds?.length ? <span className="sg-tag sg-tag-slate">Facts {failure.factIds.join(", ")}</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="sg-hint" style={{ marginTop: 10 }}>No Quality Safety blocking rows are available.</p>
            )}

            {qualitySafety.warningTokens.length > 0 ? (
              <div className="sg-mathv-claim-head" style={{ marginTop: 10 }}>
                {qualitySafety.warningTokens.map((token) => (
                  <span key={token} className="sg-tag sg-tag-amber">{token}</span>
                ))}
              </div>
            ) : (
              <p className="sg-hint" style={{ marginTop: 10 }}>No Quality Safety warning tokens are available.</p>
            )}
          </>
        ) : (
          <NotAvailableNotice>
            Quality Safety artifact not available yet.
          </NotAvailableNotice>
        )}
      </section>

      {/* 4. Prompt contract lint */}
      <section>
        <div className="sg-head-row">
          <h3>Prompt contract lint</h3>
          {model.contractLintAvailable && lint.state === "available" ? (
            <span className={`sg-tag ${toneClass(lint.tone)}`}>
              <StatusIcon tone={lint.tone} />
              {lint.status === "warning" ? "Warnings" : "Clean"}
            </span>
          ) : (
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          )}
        </div>
        {model.contractLintAvailable && lint.state === "available" ? (
          <div className="sg-grid-3" style={{ marginTop: 12 }}>
            <QualityTile
              label="Reasoning leaks"
              value={String(lint.reasoningLeakCount)}
              tone={lint.reasoningLeakCount ? "warn" : "good"}
            />
            <QualityTile
              label="Required sections"
              value={lint.comprehensive ? `${lint.requiredSectionPresentCount}/${lint.requiredSectionCount}` : "n/a"}
              tone={lint.requiredStructureStatus === "warning" ? "warn" : "neutral"}
            />
            <QualityTile label="Exam alerts" value={String(lint.examAlertCount)} />
            <QualityTile label="Tables" value={String(lint.tableCount)} />
            <QualityTile label="Warnings" value={String(lint.warningCount)} tone={lint.warningCount ? "warn" : "neutral"} />
          </div>
        ) : (
          <NotAvailableNotice>
            No prompt-contract lint is available for this job.
          </NotAvailableNotice>
        )}
      </section>

      {/* 5. Math verification */}
      <section>
        <div className="sg-head-row">
          <h3>Math verification</h3>
          {model.mathVerificationAvailable && math.state === "available" ? (
            <span className={`sg-tag ${toneClass(math.tone)}`}>
              <StatusIcon tone={math.tone} />
              {math.mismatchCount || math.unparseableCount ? "Issues" : "Clean"}
            </span>
          ) : (
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          )}
        </div>
        {model.mathVerificationAvailable && math.state === "available" ? (
          <>
            <div className="sg-grid-3" style={{ marginTop: 12 }}>
              <QualityTile label="Checked" value={String(math.checkedCount)} />
              <QualityTile label="OK" value={String(math.okCount)} tone={math.okCount ? "good" : "neutral"} />
              <QualityTile label="Mismatch" value={String(math.mismatchCount)} tone={math.mismatchCount ? "warn" : "neutral"} />
              <QualityTile label="Unparseable" value={String(math.unparseableCount)} tone={math.unparseableCount ? "warn" : "neutral"} />
            </div>
            <p className="sg-hint" style={{ marginTop: 8 }}>
              Summary of the existing numeric verification — counts only; no formulas or values are shown here.
            </p>
          </>
        ) : (
          <NotAvailableNotice>
            No math-verification artifact is available for this job.
          </NotAvailableNotice>
        )}
      </section>

      {/* 6. Coverage / completeness signals */}
      <section>
        <div className="sg-head-row">
          <h3>Coverage &amp; completeness</h3>
          {model.sourceCoverageAvailable && coverage && coverage.state !== "malformed" ? (
            <span className={`sg-tag ${toneClass(coverage.tone)}`}>
              <StatusIcon tone={coverage.tone} />
              {coverage.status === "skipped" ? "Skipped" : coverage.status}
            </span>
          ) : (
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          )}
        </div>
        {model.sourceCoverageAvailable && coverage && coverage.state !== "malformed" ? (
          <div className="sg-grid-3" style={{ marginTop: 12 }}>
            <QualityTile label="Sources" value={String(coverage.sourceCount)} />
            <QualityTile
              label="Unreadable pages"
              value={String(coverage.unreadablePages)}
              tone={coverage.unreadablePages ? "warn" : "neutral"}
            />
            <QualityTile
              label="Unreadable sources"
              value={String(model.unreadableSourceCount)}
              tone={model.unreadableSourceCount ? "warn" : "neutral"}
            />
          </div>
        ) : (
          <NotAvailableNotice>No source-coverage report is available for this job.</NotAvailableNotice>
        )}
        {model.guideQualityReportV2Available && reportV2 && reportV2.state !== "malformed" ? (
          <div className="sg-grid-3" style={{ marginTop: 10 }}>
            <QualityTile
              label="Report v2 warnings"
              value={String(reportV2.warningCount)}
              tone={reportV2.warningCount ? "warn" : "neutral"}
            />
            <QualityTile label="Source page signals" value={String(reportV2.sourcePageSignalCount)} />
            <QualityTile label="Coverage signals" value={String(reportV2.coverageSignalCount)} />
          </div>
        ) : (
          <NotAvailableNotice>No guide quality report v2 is available for this job.</NotAvailableNotice>
        )}
      </section>

      {/* 7. Quality checks (closed-kind chips from the QA gate) */}
      <section>
        <h3>Quality checks</h3>
        {model.qualityChecks.length === 0 ? (
          <p className="sg-hint" style={{ marginTop: 10 }}>No quality checks are available for this job.</p>
        ) : (
          <ul className="sg-mathv-list" style={{ marginTop: 10 }}>
            {model.qualityChecks.map((check, index) => (
              <li key={`${check.kind}-${index}`} className="sg-mathv-claim">
                <div className="sg-mathv-claim-head">
                  <span className={`sg-tag ${checkStatusTagClass(check.status)}`}>
                    <CheckStatusIcon status={check.status} />
                    {CHECK_STATUS_LABEL[check.status] || "Unknown"}
                  </span>
                  <span className="sg-mathv-id">{CHECK_KIND_LABEL[check.kind] || check.kind}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 8. Artifacts (fixed exact-name links) */}
      <section>
        <h3>Artifacts</h3>
        <div className="sg-stack" style={{ marginTop: 10 }}>
          {model.artifactLinks.map((entry) => (
            <ArtifactRow key={entry.artifact} jobId={jobId} entry={entry} model={model} />
          ))}
        </div>
      </section>
    </div>
  );
}

// Renders a fixed exact-name artifact label. When the corresponding section had no
// artifact we show "Not available" instead of a dead link. The href is built from
// the job id + the fixed exact-name filename only (no raw URL is ever read from the
// artifact body).
function ArtifactRow({ jobId, entry, model }) {
  const available = artifactIsAvailable(entry.artifact, model);
  const href = `/api/jobs/${encodeURIComponent(jobId)}/artifacts/${entry.artifact}`;
  return (
    <div className="sg-art-row">
      <div className="sg-art-top">
        <span className="sg-art-name">
          <span className="truncate">{entry.label}</span>
        </span>
        <span className={`pill ${available ? "pill-green" : "pill-soft"}`}>
          {available ? "ready" : "not available"}
        </span>
      </div>
      {available && (
        <div className="sg-art-actions">
          <a href={href} target="_blank" rel="noreferrer">
            <ExternalLink style={{ width: 14, height: 14 }} />
            Open JSON
          </a>
        </div>
      )}
    </div>
  );
}

function artifactIsAvailable(artifact, model) {
  if (artifact === GUIDE_QUALITY_QA_GATE_ARTIFACT) return model.qaGateAvailable;
  if (artifact === GUIDE_QUALITY_CONTRACT_LINT_ARTIFACT) return model.contractLintAvailable;
  if (artifact === GUIDE_QUALITY_REPORT_V2_ARTIFACT) return model.guideQualityReportV2Available;
  if (artifact === GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT) return model.rubricScoreAvailable;
  if (artifact === QUALITY_SAFETY_ARTIFACT) return model.qualitySafetyAvailable;
  if (artifact === MATH_VERIFICATION_ARTIFACT) return model.mathVerificationAvailable;
  if (artifact === SOURCE_COVERAGE_ARTIFACT) return model.sourceCoverageAvailable;
  return false;
}

function formatQualitySafetyBool(value) {
  if (value === true) return "True";
  if (value === false) return "False";
  return "Unknown";
}
