import React from "react";

export function Tile({ size = 44, radius, variant = "orange", glow = false, children, className = "" }) {
  const r = radius ?? Math.round(size * 0.28);
  return (
    <span
      className={`sg-tile sg-tile-${variant}${glow ? " sg-tile-glow" : ""} ${className}`}
      style={{ width: size, height: size, borderRadius: r }}
    >
      {children}
    </span>
  );
}

function Glyph({ size = 22, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      {children}
    </svg>
  );
}

export function BookGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M3 5.5C3 4.7 3.7 4 4.5 4H10C11.1 4 12 4.9 12 6V20C12 19.4 11.3 18 9.5 18H4.5C3.7 18 3 17.3 3 16.5V5.5Z" fill={color} />
      <path d="M21 5.5C21 4.7 20.3 4 19.5 4H14C12.9 4 12 4.9 12 6V20C12 19.4 12.7 18 14.5 18H19.5C20.3 18 21 17.3 21 16.5V5.5Z" fill={color} />
      <rect x="5" y="7" width="5" height="1.2" rx="0.6" fill="#FB923C" />
      <rect x="5" y="10" width="5" height="1.2" rx="0.6" fill="#FB923C" />
      <rect x="14" y="7" width="5" height="1.2" rx="0.6" fill="#FB923C" />
      <rect x="14" y="10" width="5" height="1.2" rx="0.6" fill="#FB923C" />
    </Glyph>
  );
}

export function BoltGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M13 2L4 14H11L10 22L20 9H12.5L13 2Z" fill={color} stroke={color} strokeWidth="0.8" strokeLinejoin="round" />
    </Glyph>
  );
}

export function DocGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M6 3H14L19 8V20C19 20.6 18.6 21 18 21H6C5.4 21 5 20.6 5 20V4C5 3.4 5.4 3 6 3Z" fill={color} />
      <path d="M14 3V8H19" fill="none" stroke="#FB923C" strokeWidth="1.2" />
      <rect x="8" y="11" width="7" height="1.2" rx="0.6" fill="#FB923C" />
      <rect x="8" y="14" width="7" height="1.2" rx="0.6" fill="#FB923C" />
      <rect x="8" y="17" width="4" height="1.2" rx="0.6" fill="#FB923C" />
    </Glyph>
  );
}

export function UploadGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M7 17H17C19.2 17 21 15.2 21 13C21 11.1 19.7 9.6 17.9 9.1C17.6 6.2 15.1 4 12 4C9.1 4 6.7 5.9 6.1 8.5C4.3 8.9 3 10.5 3 12.5C3 14.9 4.8 17 7 17Z" fill={color} />
      <path d="M12 19V12M12 12L9 15M12 12L15 15" stroke="#FB923C" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </Glyph>
  );
}

export function SparkleGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M12 3L13.5 8L18 9.5L13.5 11L12 16L10.5 11L6 9.5L10.5 8L12 3Z" fill={color} />
      <path d="M18 14L18.8 16.2L21 17L18.8 17.8L18 20L17.2 17.8L15 17L17.2 16.2L18 14Z" fill={color} opacity="0.8" />
      <path d="M6 14L6.6 15.6L8.2 16.2L6.6 16.8L6 18.4L5.4 16.8L3.8 16.2L5.4 15.6L6 14Z" fill={color} opacity="0.7" />
    </Glyph>
  );
}

export function LeafGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M12 21V11M12 11C12 11 8 8 8 5C8 5 12 4 13 7C13 7 14 4 18 5C18 8 14 11 12 11Z" stroke={color} strokeWidth="1.6" strokeLinejoin="round" fill={color} />
    </Glyph>
  );
}

export function ListGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <rect x="3" y="4" width="18" height="3.5" rx="1.2" fill={color} />
      <rect x="3" y="10.25" width="18" height="3.5" rx="1.2" fill={color} />
      <rect x="3" y="16.5" width="18" height="3.5" rx="1.2" fill={color} />
      <circle cx="6" cy="5.75" r="0.8" fill="#FB923C" />
      <circle cx="6" cy="12" r="0.8" fill="#FB923C" />
      <circle cx="6" cy="18.25" r="0.8" fill="#FB923C" />
    </Glyph>
  );
}

export function TrophyGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M7 4H17V9C17 11.8 14.8 14 12 14C9.2 14 7 11.8 7 9V4Z" fill={color} />
      <path d="M7 5H4V7C4 8.7 5.3 10 7 10" stroke={color} strokeWidth="1.6" fill="none" />
      <path d="M17 5H20V7C20 8.7 18.7 10 17 10" stroke={color} strokeWidth="1.6" fill="none" />
      <path d="M10 14V17H14V14" stroke={color} strokeWidth="1.6" />
      <rect x="7" y="17" width="10" height="3" rx="1" fill={color} />
    </Glyph>
  );
}

export function PDFGlyph({ size = 22, color = "#1B0F03" }) {
  return (
    <Glyph size={size}>
      <path d="M6 3H14L19 8V20C19 20.6 18.6 21 18 21H6C5.4 21 5 20.6 5 20V4C5 3.4 5.4 3 6 3Z" fill={color} />
      <path d="M14 3V8H19" stroke="#FB923C" strokeWidth="1.2" />
      <text x="12" y="17.5" textAnchor="middle" fontSize="5.5" fontWeight="700" fill="#FB923C" fontFamily="Inter, sans-serif">PDF</text>
    </Glyph>
  );
}

export function LineIcon({ size = 20, children, stroke = "currentColor", sw = 1.8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  );
}

export const SearchI = (props) => (
  <LineIcon {...props}><circle cx="11" cy="11" r="7" /><line x1="20" y1="20" x2="16.65" y2="16.65" /></LineIcon>
);

export const SettingsI = (props) => (
  <LineIcon {...props}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.09A1.65 1.65 0 0 0 10 3.09V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.09A1.65 1.65 0 0 0 20.91 10H21a2 2 0 0 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15Z" /></LineIcon>
);
