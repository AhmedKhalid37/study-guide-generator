import React from "react";

// Real <button> primitives for the reskin. Every variant carries `.btn-reset`
// (neutralises native chrome) plus the matching design-system class, so callers
// get a semantic, keyboard-native button (Enter/Space handled by the platform)
// that still looks pixel-faithful.
//
// Variants:
//   white     → .btn .btn-white   (primary CTA)
//   ghost     → .btn .btn-ghost   (secondary)
//   assistant → .assistant-pill   (the top-bar "Ask Guide" pill)
//   icon      → .icon-btn         (square icon control; prefer <IconButton>)
//   bare      → reset only        (style entirely via className, e.g. nav rows)
const VARIANT_CLASS = {
  white: "btn btn-white",
  ghost: "btn btn-ghost",
  assistant: "assistant-pill",
  icon: "icon-btn",
  bare: ""
};

export function Button({ variant = "white", className = "", type = "button", children, ...rest }) {
  const variantClass = VARIANT_CLASS[variant] ?? "";
  const cls = ["btn-reset", variantClass, className].filter(Boolean).join(" ");
  return (
    <button type={type} className={cls} {...rest}>
      {children}
    </button>
  );
}

// Square icon-only control (.icon-btn). Pass an `aria-label` since there's no
// text content.
export function IconButton({ className = "", children, ...rest }) {
  return (
    <Button variant="icon" className={className} {...rest}>
      {children}
    </Button>
  );
}

export default Button;
