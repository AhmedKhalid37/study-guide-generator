import React from "react";

// Pastel stat card: icon top-left, big number, label. `fill` selects one of the
// four design-system pastel fills.
const FILL_VAR = {
  bluegray: "var(--pastel-bluegray)",
  sage: "var(--pastel-sage)",
  cream: "var(--pastel-cream)",
  lavender: "var(--pastel-lavender)"
};

export default function StatCard({ icon, value, label, fill = "bluegray", className = "", ...rest }) {
  const background = FILL_VAR[fill] || FILL_VAR.bluegray;
  return (
    <div className={`stat-card ${className}`.trim()} style={{ background }} {...rest}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-num">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
