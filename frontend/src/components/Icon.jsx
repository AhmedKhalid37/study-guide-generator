import React from "react";

// GuideForge icon set — line icons (Lucide-style), 24x24 stroke geometry.
// ES-module port of the design prototype's `window.Icon` map. Each entry is a
// function returning an SVG element; stroke inherits `currentColor` so colour
// is controlled by the surrounding CSS (.nav-item, .icon-btn, etc.). Call as a
// function — `{Icon.home()}` — or pass props through — `{Icon.logo({ width: 30 })}`.

// Base wrapper for the line glyphs (everything except the brand logo).
function S({ children, fill = "none", stroke = 2, ...rest }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill={fill}
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flex: "none" }}
      {...rest}
    >
      {children}
    </svg>
  );
}

export const Icon = {
  // brand mark — abstract "stacked pages / forge"
  logo: (p) => (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" {...p}>
      <path d="M5 7.5 12 4l7 3.5-7 3.5-7-3.5Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M5 12l7 3.5L19 12" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M5 16.5 12 20l7-3.5" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  ),
  home: (p) => <S {...p}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /><path d="M9.5 21v-6h5v6" /></S>,
  builder: (p) => <S {...p}><path d="M4 6h11" /><path d="M4 12h16" /><path d="M4 18h9" /><circle cx="18.5" cy="6" r="2" /><circle cx="16.5" cy="18" r="2" /></S>,
  library: (p) => <S {...p}><rect x="3" y="4" width="5" height="16" rx="1" /><rect x="10" y="4" width="5" height="16" rx="1" /><path d="m17.5 5.5 3.2 1 .4 14.3-3.6-1.1z" /></S>,
  ask: (p) => <S {...p}><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.2A8 8 0 1 1 21 12Z" /><path d="M9 11h6M9 14h4" /></S>,
  styles: (p) => <S {...p}><path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-.9 2-2 0-1.3-1-1.6-1-2.6 0-.8.7-1.4 1.6-1.4H17a4 4 0 0 0 4-4c0-4.4-4-8-9-8Z" /><circle cx="7.5" cy="11" r="1" /><circle cx="11" cy="7.5" r="1" /><circle cx="15.5" cy="8" r="1" /></S>,
  models: (p) => <S {...p}><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M9 9h6v6H9z" /><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" /></S>,
  exports: (p) => <S {...p}><path d="M12 15V3" /><path d="m8 7 4-4 4 4" /><path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5" /></S>,
  help: (p) => <S {...p}><circle cx="12" cy="12" r="9" /><path d="M9.2 9.3a2.8 2.8 0 0 1 5.4 1c0 1.8-2.6 2.2-2.6 4" /><circle cx="12" cy="17" r=".6" fill="currentColor" /></S>,
  moon: (p) => <S {...p}><path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5Z" /></S>,
  settings: (p) => <S {...p}><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2.4" /><circle cx="8" cy="17" r="2.4" /></S>,
  signout: (p) => <S {...p}><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" /><path d="M10 12H3" /><path d="m6 8-4 4 4 4" /></S>,
  search: (p) => <S {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></S>,
  sparkle: (p) => <S stroke={1.7} {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.4 2.4M15.3 15.3l2.4 2.4M17.7 6.3l-2.4 2.4M8.7 15.3l-2.4 2.4" /></S>,
  history: (p) => <S {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 4v4h4" /><path d="M12 8v4l3 2" /></S>,
  mail: (p) => <S {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></S>,
  bell: (p) => <S {...p}><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" /><path d="M10 19a2 2 0 0 0 4 0" /></S>,
  play: (p) => <S {...p}><circle cx="12" cy="12" r="9" /><path d="M10 8.5v7l5.5-3.5z" fill="currentColor" stroke="none" /></S>,
  chat: (p) => <S {...p}><path d="M20 11.5a7.5 7.5 0 0 1-10.8 6.7L4 19l1-4.2A7.5 7.5 0 1 1 20 11.5Z" /></S>,
  // stat icons
  book: (p) => <S stroke={1.8} {...p}><path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 0-2 2z" /><path d="M5 18.5A2 2 0 0 1 7 17h11" /></S>,
  quiz: (p) => <S stroke={1.8} {...p}><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8.5 9.5a2 2 0 1 1 2.7 1.9c-.5.2-.7.5-.7 1.1" /><circle cx="10.5" cy="15" r=".6" fill="currentColor" /><path d="M14 8h3M14 15h3" /></S>,
  upload: (p) => <S stroke={1.8} {...p}><path d="M5 16v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3" /><path d="M12 3v12" /><path d="m7.5 7.5 4.5-4.5 4.5 4.5" /></S>,
  download: (p) => <S stroke={1.8} {...p}><path d="M5 16v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3" /><path d="M12 16V4" /><path d="m7.5 11.5 4.5 4.5 4.5-4.5" /></S>,
  // misc
  folder: (p) => <S {...p}><path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></S>,
  trash: (p) => <S {...p}><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" /></S>,
  file: (p) => <S {...p}><path d="M6 3h8l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M14 3v5h5" /></S>,
  plus: (p) => <S {...p}><path d="M12 5v14M5 12h14" /></S>,
  check: (p) => <S {...p}><path d="m5 13 4 4 10-11" /></S>,
  arrowR: (p) => <S {...p}><path d="M5 12h14M13 6l6 6-6 6" /></S>,
  zap: (p) => <S {...p}><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" /></S>,
  cpu: (p) => <S {...p}><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9.5 9.5h5v5h-5z" /><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" /></S>,
  cloud: (p) => <S {...p}><path d="M7 18a4 4 0 0 1-.5-7.97A6 6 0 0 1 18 9.5 3.5 3.5 0 0 1 17.5 18Z" /></S>,
  server: (p) => <S {...p}><rect x="3" y="4" width="18" height="7" rx="2" /><rect x="3" y="13" width="18" height="7" rx="2" /><path d="M7 7.5h.01M7 16.5h.01" /></S>,
  grid: (p) => <S {...p}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></S>,
  zip: (p) => <S {...p}><path d="M6 3h12a1 1 0 0 1 1 1v17a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M11 3v2h2V3M11 7v2h2V7M11 11v2h2v-2" /></S>,
  filter: (p) => <S {...p}><path d="M4 5h16l-6 7v6l-4 2v-8L4 5Z" /></S>,
  dot: (p) => <S stroke={1.6} {...p}><circle cx="12" cy="12" r="9" /></S>,
  refresh: (p) => <S {...p}><path d="M4 11a8 8 0 0 1 14-5l2 2" /><path d="M20 4v4h-4" /><path d="M20 13a8 8 0 0 1-14 5l-2-2" /><path d="M4 20v-4h4" /></S>,
  eye: (p) => <S {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></S>,
  clock: (p) => <S {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></S>,
  paperclip: (p) => <S {...p}><path d="M20 11.5 12 19.5a5 5 0 0 1-7-7l8-8a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-3-3l7.5-7.5" /></S>,
  send: (p) => <S {...p}><path d="M4 12 20 4l-6 16-3-7-7-1Z" /></S>
};

export default Icon;
