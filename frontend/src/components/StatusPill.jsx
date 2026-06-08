import React from "react";
import { statusBadge, shortcutBadge } from "../shortcutStatus";

// Shortcut validity pill. The label + tone come from shortcutStatus.js (the
// shared source of truth) — never reinvent the status→colour mapping here, and
// note there is deliberately no green "Ready" tone: `valid` reads quiet/neutral.
//
// Pass either a derived `status` ('valid' | 'degraded' | 'broken') or a whole
// `shortcut` object (preferred — it derives the status the same way every other
// surface does).
const TONE_CLASS = {
  valid: "pill-quiet",
  degraded: "pill-amber",
  broken: "pill-red"
};

export default function StatusPill({ status, shortcut, className = "", ...rest }) {
  const badge = shortcut !== undefined ? shortcutBadge(shortcut) : statusBadge(status);
  const toneClass = TONE_CLASS[badge.tone] || TONE_CLASS.valid;
  return (
    <span className={`pill ${toneClass} ${className}`.trim()} {...rest}>
      <span className="dot" />
      {badge.label}
    </span>
  );
}
