import React, { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { getJobArtifact } from "../api/client";
import {
  MATH_VERIFICATION_ARTIFACT,
  summarizeMathVerificationArtifact,
} from "../mathVerification";

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

function MathTile({ label, value, tone = "neutral" }) {
  return (
    <div className={`sg-tile${tone === "good" ? " good" : tone === "warn" ? " warn" : ""}`}>
      <div className="sg-tile-label">{label}</div>
      <div className="sg-tile-value">{value}</div>
    </div>
  );
}

function ClaimRow({ claim }) {
  return (
    <li className={`sg-mathv-claim ${claim.status}`}>
      <div className="sg-mathv-claim-head">
        <span className={`sg-tag ${claim.status === "ok" ? "sg-tag-green" : claim.status === "mismatch" ? "sg-tag-red" : "sg-tag-amber"}`}>
          {claim.status}
        </span>
        {claim.line && <span className="sg-mathv-line">line {claim.line}</span>}
        <span className="sg-mathv-id">{claim.id}</span>
      </div>
      <code>{claim.text}</code>
      {(claim.claimed || claim.computed) && (
        <div className="sg-mathv-values">
          {claim.claimed && <span>claimed: {claim.claimed}</span>}
          {claim.computed && <span>computed: {claim.computed}</span>}
        </div>
      )}
      {claim.reason && <p className="sg-hint">{claim.reason}</p>}
    </li>
  );
}

export default function MathVerificationPanel({ jobId }) {
  const [state, setState] = useState({ loading: true, artifact: null, error: null, missing: false, malformed: false });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, artifact: null, error: null, missing: false, malformed: false });
    getJobArtifact(jobId, MATH_VERIFICATION_ARTIFACT)
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
        <span>Loading math verification...</span>
      </div>
    );
  }

  if (state.missing) {
    return (
      <div className="sg-tab-stack">
        <section>
          <div className="sg-head-row">
            <h3>Math verification</h3>
            <span className="sg-tag sg-tag-amber">
              <AlertTriangle />
              Not available
            </span>
          </div>
          <p className="sg-notice sg-notice-amber" style={{ marginTop: 12 }}>
            This job does not have a math verification artifact. Older jobs may not include one.
          </p>
        </section>
      </div>
    );
  }

  if (state.malformed) {
    const view = summarizeMathVerificationArtifact(null);
    return (
      <div className="sg-tab-stack">
        <section>
          <div className="sg-head-row">
            <h3>Math verification</h3>
            <span className="sg-tag sg-tag-red">
              <AlertCircle />
              {view.label}
            </span>
          </div>
          <p className="sg-notice sg-notice-red" style={{ marginTop: 12 }}>
            The math verification artifact could not be parsed as JSON.
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
            <h3>Math verification</h3>
            <span className="sg-tag sg-tag-red">
              <AlertCircle />
              Fetch error
            </span>
          </div>
          <p className="sg-notice sg-notice-red" style={{ marginTop: 12 }}>
            Could not load the math verification artifact.
          </p>
        </section>
      </div>
    );
  }

  const view = summarizeMathVerificationArtifact(state.artifact);
  const isMalformed = view.state === "malformed";

  return (
    <div className="sg-tab-stack">
      <section>
        <div className="sg-head-row">
          <div>
            <h3>Math verification</h3>
            {view.source && <p className="sg-hint">Source: {view.source}</p>}
          </div>
          <span className={`sg-tag ${toneClass(isMalformed ? "bad" : view.tone)}`}>
            <StatusIcon tone={isMalformed ? "bad" : view.tone} />
            {view.label}
          </span>
        </div>

        <p className={`sg-notice ${view.tone === "good" ? "sg-notice-green" : isMalformed ? "sg-notice-red" : "sg-notice-amber"}`} style={{ marginTop: 12 }}>
          {view.message}
        </p>
      </section>

      {view.state === "completed" && (
        <>
          <section>
            <h3>Summary</h3>
            <div className="sg-grid-3" style={{ marginTop: 10 }}>
              <MathTile label="Total" value={String(view.summary.total)} />
              <MathTile label="Ok" value={String(view.summary.ok)} tone={view.summary.ok ? "good" : "neutral"} />
              <MathTile label="Mismatch" value={String(view.summary.mismatch)} tone={view.summary.mismatch ? "warn" : "neutral"} />
              <MathTile label="Unparseable" value={String(view.summary.unparseable)} tone={view.summary.unparseable ? "warn" : "neutral"} />
            </div>
          </section>

          <section>
            <h3>Claims</h3>
            {view.claims.length === 0 ? (
              <p className="sg-hint" style={{ marginTop: 10 }}>No numeric claims were reported.</p>
            ) : (
              <ul className="sg-mathv-list">
                {view.claims.map((claim) => (
                  <ClaimRow key={claim.id} claim={claim} />
                ))}
              </ul>
            )}
            {view.hiddenCount > 0 && (
              <p className="sg-hint" style={{ marginTop: 10 }}>
                {view.hiddenCount} additional claim{view.hiddenCount === 1 ? "" : "s"} hidden from this compact view.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
