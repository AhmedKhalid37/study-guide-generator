// icons.jsx — SVG icon library for the Study Guide Generator
// Conventions:
//   <Icon size={20} stroke="currentColor" />  for line glyphs
//   <Tile size={48} variant="orange"><BookGlyph/></Tile>  for tile-mounted icons
// All icons follow a consistent 24×24 viewBox unless noted.

// ──────────────────────────────────────────────────────────────
// Tile — rounded square with orange gradient + glossy highlight
// Looks like the 3D-ish tiles in the reference shots.
// ──────────────────────────────────────────────────────────────
function Tile({ size = 44, radius, variant = 'orange', glow = false, children, style = {} }) {
  const r = radius ?? Math.round(size * 0.28);
  const palettes = {
    orange: {
      bg: 'linear-gradient(160deg, #FB923C 0%, #F97316 55%, #C2410C 100%)',
      stroke: 'rgba(255,180,120,0.4)',
      inset: 'inset 0 1px 0 rgba(255,255,255,0.35), inset 0 -1px 0 rgba(0,0,0,0.25)',
      shadow: '0 8px 18px -6px rgba(249,115,22,0.6)',
    },
    dark: {
      bg: 'linear-gradient(160deg, #1F2A40 0%, #131B2C 100%)',
      stroke: 'rgba(255,180,120,0.18)',
      inset: 'inset 0 1px 0 rgba(255,255,255,0.06), inset 0 -1px 0 rgba(0,0,0,0.35)',
      shadow: '0 8px 18px -6px rgba(0,0,0,0.5)',
    },
    soft: {
      bg: 'linear-gradient(160deg, rgba(249,115,22,0.18) 0%, rgba(249,115,22,0.06) 100%)',
      stroke: 'rgba(249,115,22,0.28)',
      inset: 'inset 0 1px 0 rgba(255,255,255,0.05)',
      shadow: 'none',
    },
  };
  const p = palettes[variant];
  return (
    <div style={{
      width: size, height: size, borderRadius: r,
      background: p.bg,
      border: `1px solid ${p.stroke}`,
      boxShadow: `${p.inset}, ${p.shadow}${glow ? ', 0 0 24px rgba(249,115,22,0.45)' : ''}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      position: 'relative', flexShrink: 0,
      ...style,
    }}>
      {children}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Tile glyphs — drawn at 24×24, scaled by the tile via size prop
// ──────────────────────────────────────────────────────────────
const G = ({ size = 22, children, fill = '#1B0F03', op = 1 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ opacity: op }}>
    {children}
  </svg>
);
const Gd = ({ size = 22, children }) => ( // dark variant — orange glyph on dark tile
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">{children}</svg>
);

// Book — open book glyph (orange tile, dark stroke)
function BookGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M3 5.5C3 4.7 3.7 4 4.5 4H10C11.1 4 12 4.9 12 6V20C12 19.4 11.3 18 9.5 18H4.5C3.7 18 3 17.3 3 16.5V5.5Z" fill={color}/>
      <path d="M21 5.5C21 4.7 20.3 4 19.5 4H14C12.9 4 12 4.9 12 6V20C12 19.4 12.7 18 14.5 18H19.5C20.3 18 21 17.3 21 16.5V5.5Z" fill={color}/>
      <rect x="5" y="7" width="5" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="5" y="10" width="5" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="5" y="13" width="3.5" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="14" y="7" width="5" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="14" y="10" width="5" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="14" y="13" width="3.5" height="1.2" rx="0.6" fill="#FB923C"/>
    </G>
  );
}

// Bolt — lightning
function BoltGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M13 2L4 14H11L10 22L20 9H12.5L13 2Z" fill={color} stroke={color} strokeWidth="0.8" strokeLinejoin="round"/>
    </G>
  );
}

// Document
function DocGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M6 3H14L19 8V20C19 20.6 18.6 21 18 21H6C5.4 21 5 20.6 5 20V4C5 3.4 5.4 3 6 3Z" fill={color}/>
      <path d="M14 3V8H19" fill="none" stroke="#FB923C" strokeWidth="1.2"/>
      <rect x="8" y="11" width="7" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="8" y="14" width="7" height="1.2" rx="0.6" fill="#FB923C"/>
      <rect x="8" y="17" width="4" height="1.2" rx="0.6" fill="#FB923C"/>
    </G>
  );
}

// Cloud upload
function UploadGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M7 17H17C19.2 17 21 15.2 21 13C21 11.1 19.7 9.6 17.9 9.1C17.6 6.2 15.1 4 12 4C9.1 4 6.7 5.9 6.1 8.5C4.3 8.9 3 10.5 3 12.5C3 14.9 4.8 17 7 17Z" fill={color}/>
      <path d="M12 19V12M12 12L9 15M12 12L15 15" stroke="#FB923C" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </G>
  );
}

// Multi-sparkle (Generate w/ AI)
function SparkleGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M12 3L13.5 8L18 9.5L13.5 11L12 16L10.5 11L6 9.5L10.5 8L12 3Z" fill={color}/>
      <path d="M18 14L18.8 16.2L21 17L18.8 17.8L18 20L17.2 17.8L15 17L17.2 16.2L18 14Z" fill={color} opacity="0.8"/>
      <path d="M6 14L6.6 15.6L8.2 16.2L6.6 16.8L6 18.4L5.4 16.8L3.8 16.2L5.4 15.6L6 14Z" fill={color} opacity="0.7"/>
    </G>
  );
}

// Leaf / sprout (Baby-step)
function LeafGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size} fill={color}>
      <path d="M12 21V11M12 11C12 11 8 8 8 5C8 5 12 4 13 7C13 7 14 4 18 5C18 8 14 11 12 11Z" stroke={color} strokeWidth="1.6" strokeLinejoin="round" fill={color}/>
    </G>
  );
}

// List/check (MCQ training, key concepts)
function ListGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <rect x="3" y="4" width="18" height="3.5" rx="1.2" fill={color}/>
      <rect x="3" y="10.25" width="18" height="3.5" rx="1.2" fill={color}/>
      <rect x="3" y="16.5" width="18" height="3.5" rx="1.2" fill={color}/>
      <circle cx="6" cy="5.75" r="0.8" fill="#FB923C"/>
      <circle cx="6" cy="12" r="0.8" fill="#FB923C"/>
      <circle cx="6" cy="18.25" r="0.8" fill="#FB923C"/>
    </G>
  );
}

// Trophy (Final revision)
function TrophyGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M7 4H17V9C17 11.8 14.8 14 12 14C9.2 14 7 11.8 7 9V4Z" fill={color}/>
      <path d="M7 5H4V7C4 8.7 5.3 10 7 10" stroke={color} strokeWidth="1.6" fill="none"/>
      <path d="M17 5H20V7C20 8.7 18.7 10 17 10" stroke={color} strokeWidth="1.6" fill="none"/>
      <path d="M10 14V17H14V14" stroke={color} strokeWidth="1.6"/>
      <rect x="7" y="17" width="10" height="3" rx="1" fill={color}/>
    </G>
  );
}

// Briefcase (Last-minute review)
function CaseGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <rect x="3" y="7" width="18" height="13" rx="2.5" fill={color}/>
      <path d="M9 7V5C9 4.4 9.4 4 10 4H14C14.6 4 15 4.4 15 5V7" stroke={color} strokeWidth="1.6" fill="none"/>
      <rect x="3" y="11" width="18" height="1.5" fill="#FB923C"/>
    </G>
  );
}

// Plus / memory cue (Fast memory cues — mnemonic cross)
function CueGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M12 3L13.5 9L19 7.5L15.5 12L21 13.5L15 15L17 20L12 16.5L7 20L9 15L3 13.5L8.5 12L5 7.5L10.5 9L12 3Z" fill={color}/>
    </G>
  );
}

// Notes/condensed
function NotesGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <rect x="4" y="3" width="16" height="18" rx="2" fill={color}/>
      <rect x="7" y="7" width="10" height="1.4" rx="0.7" fill="#FB923C"/>
      <rect x="7" y="10" width="10" height="1.4" rx="0.7" fill="#FB923C"/>
      <rect x="7" y="13" width="6" height="1.4" rx="0.7" fill="#FB923C"/>
      <rect x="7" y="16.5" width="8" height="1.4" rx="0.7" fill="#FB923C" opacity="0.6"/>
    </G>
  );
}

// PDF
function PDFGlyph({ size = 22, color = '#1B0F03' }) {
  return (
    <G size={size}>
      <path d="M6 3H14L19 8V20C19 20.6 18.6 21 18 21H6C5.4 21 5 20.6 5 20V4C5 3.4 5.4 3 6 3Z" fill={color}/>
      <path d="M14 3V8H19" stroke="#FB923C" strokeWidth="1.2"/>
      <text x="12" y="17.5" textAnchor="middle" fontSize="5.5" fontWeight="700" fill="#FB923C" fontFamily="Inter, sans-serif">PDF</text>
    </G>
  );
}

// ──────────────────────────────────────────────────────────────
// UI line icons — currentColor stroke
// ──────────────────────────────────────────────────────────────
function LineIcon({ size = 22, children, stroke = 'currentColor', sw = 1.6, fill = 'none' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}
const ChevronLeft = (p) => <LineIcon {...p}><polyline points="15 6 9 12 15 18"/></LineIcon>;
const ChevronRight = (p) => <LineIcon {...p}><polyline points="9 6 15 12 9 18"/></LineIcon>;
const ArrowRight = (p) => <LineIcon {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="13 6 19 12 13 18"/></LineIcon>;
const Heart = (p) => <LineIcon {...p}><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></LineIcon>;
const Share = (p) => <LineIcon {...p}><path d="M12 3v14"/><polyline points="7 8 12 3 17 8"/><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/></LineIcon>;
const Bell = (p) => <LineIcon {...p}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></LineIcon>;
const Star = (p) => <LineIcon {...p} fill="currentColor"><polygon points="12 2 15 9 22 9 17 14 19 22 12 17 5 22 7 14 2 9 9 9 12 2"/></LineIcon>;
const Shield = (p) => <LineIcon {...p}><path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6l8-3z"/><polyline points="9 12 11 14 15 10"/></LineIcon>;
const Plus = (p) => <LineIcon {...p}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></LineIcon>;
const Kebab = (p) => <LineIcon {...p} fill="currentColor" sw={0}><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></LineIcon>;
const SearchI = (p) => <LineIcon {...p}><circle cx="11" cy="11" r="7"/><line x1="20" y1="20" x2="16.65" y2="16.65"/></LineIcon>;
const SettingsI = (p) => <LineIcon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></LineIcon>;

// Mobile tab icons — match the reference exactly:
// Home: filled house with cut-out doorway · Library: two book spines ·
// Models: 3-node Y-graph · Profile: head + shoulders silhouette.
// Active uses solid orange fill; inactive uses muted line stroke.
function TabHome({ active }) {
  const c = active ? '#F97316' : '#B7BCC9';
  return active ? (
    <svg width="26" height="26" viewBox="0 0 26 26" fill={c}>
      <path d="M13 2.5L2.5 11.5V22.5C2.5 23 2.9 23.5 3.5 23.5H10V16.5C10 15.95 10.45 15.5 11 15.5H15C15.55 15.5 16 15.95 16 16.5V23.5H22.5C23.1 23.5 23.5 23 23.5 22.5V11.5L13 2.5Z"/>
    </svg>
  ) : (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round">
      <path d="M13 2.5L2.5 11.5V22.5C2.5 23 2.9 23.5 3.5 23.5H10V16.5C10 15.95 10.45 15.5 11 15.5H15C15.55 15.5 16 15.95 16 16.5V23.5H22.5C23.1 23.5 23.5 23 23.5 22.5V11.5L13 2.5Z"/>
    </svg>
  );
}

function TabLibrary({ active }) {
  const c = active ? '#F97316' : '#B7BCC9';
  // Two upright book spines, slight visual interest with thin top caps
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round">
      <rect x="5" y="4" width="6.5" height="18" rx="1.2"/>
      <rect x="14.5" y="4" width="6.5" height="18" rx="1.2"/>
      <line x1="7" y1="8.5" x2="9.5" y2="8.5"/>
      <line x1="16.5" y1="8.5" x2="19" y2="8.5"/>
    </svg>
  );
}

function TabModels({ active }) {
  const c = active ? '#F97316' : '#B7BCC9';
  // Three-node Y graph — top center, bottom-left, bottom-right, lines joining
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round">
      <line x1="13" y1="6.5" x2="13" y2="11"/>
      <line x1="13" y1="13" x2="6" y2="19"/>
      <line x1="13" y1="13" x2="20" y2="19"/>
      <circle cx="13" cy="5.5" r="2.4" fill={active ? c : 'none'} stroke={c} strokeWidth="1.7"/>
      <circle cx="6" cy="20" r="2.4" fill={active ? c : 'none'} stroke={c} strokeWidth="1.7"/>
      <circle cx="20" cy="20" r="2.4" fill={active ? c : 'none'} stroke={c} strokeWidth="1.7"/>
    </svg>
  );
}

function TabProfile({ active }) {
  const c = active ? '#F97316' : '#B7BCC9';
  // Head (circle) + shoulders (rounded rect)
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill={active ? c : 'none'} stroke={c} strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round">
      <circle cx="13" cy="9" r="4"/>
      <path d="M5 22 C5 17 8.5 14.5 13 14.5 C17.5 14.5 21 17 21 22"/>
    </svg>
  );
}

Object.assign(window, {
  Tile,
  BookGlyph, BoltGlyph, DocGlyph, UploadGlyph, SparkleGlyph, LeafGlyph,
  ListGlyph, TrophyGlyph, CaseGlyph, CueGlyph, NotesGlyph, PDFGlyph,
  ChevronLeft, ChevronRight, ArrowRight, Heart, Share, Bell, Star, Shield, Plus, Kebab, SearchI, SettingsI,
  TabHome, TabLibrary, TabModels, TabProfile,
});
