import React, { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";
import { getJobArtifact } from "../api/client";
import { GUIDE_LINT_ARTIFACT, summarizeGuideLintArtifact } from "../guideLintArtifact";

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

function severityTagClass(severity) {
  if (severity === "error") return "sg-tag-red";
  if (severity === "warning") return "sg-tag-amber";
  return "";
}

function LintTile({ label, value, tone = "neutral" }) {
  return (
    <div className={`sg-tile${tone === "good" ? " good" : tone === "warn" ? " warn" : ""}`}>
      <div className="sg-tile-label">{label}</div>
      <div className="sg-tile-value">{value}</div>
    </div>
  );
}

function FindingRow({ finding }) {
  return (
    <li className={`sg-mathv-claim ${finding.severity}`}>
      <div className="sg-mathv-claim-head">
        <span className={`sg-tag ${severityTagClass(finding.severity)}`}>{finding.severity}</span>
        <span className="sg-mathv-id">{finding.rule}</span>
        {finding.line ? <span className="sg-mathv-line">line {finding.line}</span> : null}
      </div>
      {finding.message && <p className="sg-hint" style={{ marginTop: 0 }}>{finding.message}</p>}
      {finding.excerpt && <code>{finding.excerpt}</code>}
    </li>
  );
}

export default function GuideLintPanel({ jobId }) {
  const [state, setState] = useState({ loading: true, artifact: null, error: null, missing: false, malformed: false });

  // Lazy fetch: this component is only mounted when the Guide Lint tab is the
  // active drawer tab, so the artifact request fires only when the tab opens.
  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, artifact: null, error: null, missing: false, malformed: false });
    getJobArtifact(jobId, GUIDE_LINT_ARTIFACT)
      .then((artifact) => {
        if (!cancelled) {
          setState({ loading: false, artifact, error: null, missing: false, malformed: false });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            loading: false,
            artifact: null,
            error,
            missing: error?.status === 404,
            malformed: error?.code === "invalid_json",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (state.loading) {
    return (
      <div className="recent-state">
        <Loader2 className="sg-spin" />
        <span>Loading guide lint...</span>
      </div>
    );
  }

  if (state.missing) {
    return (
      <div className="sg-tab-stack">
        <section>
          <div className="sg-head-row">
            <h3>Guide lint</h3>
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          </div>
          <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
            No guide-lint artifact is available for this job. Older jobs may not include one.
          </p>
        </section>
      </div>
    );
  }

  if (state.malformed) {
    return (
      <div className="sg-tab-stack">
        <section>
          <div className="sg-head-row">
            <h3>Guide lint</h3>
            <span className="sg-tag sg-tag-red">
              <AlertCircle />
              Unexpected artifact
            </span>
          </div>
          <p className="sg-notice sg-notice-red" style={{ marginTop: 12 }}>
            The guide-lint artifact could not be read.
          </p>
        </section>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="sg-tab-stack">
        <section>
          <div className="sg-head-row">
            <h3>Guide lint</h3>
            <span className="sg-tag sg-tag-red">
              <AlertCircle />
              Fetch error
            </span>
          </div>
          <p className="sg-notice sg-notice-red" style={{ marginTop: 12 }}>
            Could not load the guide-lint artifact.
          </p>
        </section>
      </div>
    );
  }

  const view = summarizeGuideLintArtifact(state.artifact);
  const isMalformed = view.state === "malformed";

  if (isMalformed) {
    return (
      <div className="sg-tab-stack">
        <section>
          <div className="sg-head-row">
            <h3>Guide lint</h3>
            <span className="sg-tag sg-tag-red">
              <AlertCircle />
              {view.label}
            </span>
          </div>
          <p className="sg-notice sg-notice-red" style={{ marginTop: 12 }}>
            The guide-lint artifact could not be read.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="sg-tab-stack">
      <section>
        <div className="sg-head-row">
          <div>
            <h3>Guide lint</h3>
            {view.source && <p className="sg-hint">Source: {view.source}</p>}
          </div>
          <span className={`sg-tag ${toneClass(view.tone)}`}>
            <StatusIcon tone={view.tone} />
            {view.label}
          </span>
        </div>

        <p className={`sg-notice ${noticeClass(view.tone)}`} style={{ marginTop: 12 }}>
          {view.message}
        </p>
        <p className="sg-hint" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <Info style={{ width: 14, height: 14, flex: "none" }} />
          Advisory only: checks structure, formatting, and math-render risk — not whether the content is correct.
        </p>
      </section>

      {view.state === "skipped" && (
        <section>
          <p className="sg-notice sg-notice-amber">{view.message}</p>
        </section>
      )}

      {view.state === "completed" && (
        <>
          <section>
            <h3>Summary</h3>
            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              <LintTile label="Total" value={String(view.summary.total)} />
              <LintTile label="Errors" value={String(view.summary.error)} tone={view.summary.error ? "warn" : "neutral"} />
              <LintTile label="Warnings" value={String(view.summary.warning)} tone={view.summary.warning ? "warn" : "neutral"} />
              <LintTile label="Info" value={String(view.summary.info)} />
            </div>
          </section>

          <section>
            <h3>Top findings</h3>
            {view.findings.length === 0 ? (
              <p className="sg-hint" style={{ marginTop: 10 }}>No structural findings were reported.</p>
            ) : (
              <ul className="sg-mathv-list">
                {view.findings.map((finding) => (
                  <FindingRow key={finding.id} finding={finding} />
                ))}
              </ul>
            )}
            {view.hiddenCount > 0 && (
              <p className="sg-hint" style={{ marginTop: 10 }}>
                {view.hiddenCount} additional finding{view.hiddenCount === 1 ? "" : "s"} hidden from this compact view.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
