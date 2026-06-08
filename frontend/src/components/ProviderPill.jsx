import React from "react";

// Indigo tag pill for a provider label (DeepSeek / Qwen / Local). `icon` is an
// optional leading slot (e.g. a small Icon glyph or provider mark).
export default function ProviderPill({ provider, name, icon, className = "", ...rest }) {
  const label = provider ?? name;
  return (
    <span className={`pill pill-indigo ${className}`.trim()} {...rest}>
      {icon}
      {label}
    </span>
  );
}
