import React from "react";

// Small chip (.chip) for meta / counts / selectable tokens. `icon` is an
// optional leading glyph; `selected` applies the filled `.sel` style. Renders a
// real <button> when `onClick` is supplied, otherwise a static <span>.
export default function Chip({ icon, children, selected = false, onClick, className = "", ...rest }) {
  const cls = ["chip", selected ? "sel" : "", className].filter(Boolean).join(" ");
  if (onClick) {
    return (
      <button type="button" className={`btn-reset ${cls}`} onClick={onClick} {...rest}>
        {icon}
        {children}
      </button>
    );
  }
  return (
    <span className={cls} {...rest}>
      {icon}
      {children}
    </span>
  );
}
