// windows.jsx — Study Guide Generator for Windows
// Extrapolated desktop design: Windows 11 chrome (Mica-tinted), sidebar nav,
// multi-pane workspace. Two scenes:
//   1. Home — dashboard adapted to wide layout
//   2. Builder — composer (left) + live PDF preview (right)

// ──────────────────────────────────────────────────────────────
// Windows 11 window chrome — title bar, min/max/close, sidebar
// ──────────────────────────────────────────────────────────────
function WindowsFrame({ children, route = 'home' }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      // Mica-style backdrop: deep navy with subtle orange wash top-left
      background:
        'radial-gradient(ellipse 60% 50% at 0% 0%, rgba(249,115,22,0.10) 0%, transparent 50%),' +
        'radial-gradient(ellipse 50% 40% at 100% 100%, rgba(249,115,22,0.06) 0%, transparent 60%),' +
        '#0A0F1A',
      borderRadius: 10, overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      fontFamily: '"Inter", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif',
      color: '#F4F4F5',
      boxShadow: '0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)',
    }} className="sg">
      <TitleBar/>
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <Sidebar route={route}/>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          {children}
        </div>
      </div>
    </div>
  );
}

function TitleBar() {
  return (
    <div style={{
      height: 40, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 0 0 14px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      WebkitAppRegion: 'drag',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Tile size={20} radius={6}>
          <BookGlyph size={12}/>
        </Tile>
        <div style={{ fontSize: 12.5, color: '#D4D4D8', fontWeight: 500 }}>Study Guide Generator</div>
      </div>

      {/* Center: command bar */}
      <div style={{
        position: 'absolute', left: '50%', transform: 'translateX(-50%)',
        width: 480, height: 28, marginTop: 6,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 8,
        display: 'flex', alignItems: 'center', gap: 8, padding: '0 10px',
        fontSize: 12.5, color: '#9098A8',
      }}>
        <SearchI size={13} stroke="#9098A8" sw={2}/>
        <span style={{ flex: 1 }}>Search guides, styles, or paste a URL…</span>
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 10.5, color: '#6B7185',
          background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4,
        }}>Ctrl + K</span>
      </div>

      {/* Window controls */}
      <div style={{ display: 'flex', height: '100%' }}>
        <WinBtn><svg width="10" height="1" viewBox="0 0 10 1"><rect width="10" height="1" fill="#D4D4D8"/></svg></WinBtn>
        <WinBtn><svg width="10" height="10" viewBox="0 0 10 10"><rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="#D4D4D8"/></svg></WinBtn>
        <WinBtn close><svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 0L10 10M10 0L0 10" stroke="#D4D4D8" strokeWidth="1"/></svg></WinBtn>
      </div>
    </div>
  );
}

function WinBtn({ children, close }) {
  return (
    <button style={{
      width: 46, height: '100%', border: 0, background: 'transparent', cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      transition: 'background 0.12s',
    }}
    onMouseEnter={e => e.currentTarget.style.background = close ? '#E81123' : 'rgba(255,255,255,0.06)'}
    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      {children}
    </button>
  );
}

function Sidebar({ route }) {
  const items = [
    { id: 'home', label: 'Home', icon: <TabHome active={route === 'home'}/> },
    { id: 'builder', label: 'Builder', icon: <BoltSidebar active={route === 'builder'}/> },
    { id: 'library', label: 'Library', icon: <TabLibrary active={route === 'library'}/> },
    { id: 'styles', label: 'Styles', icon: <StylesSidebar active={route === 'styles'}/> },
    { id: 'models', label: 'Models', icon: <TabModels active={route === 'models'}/> },
    { id: 'exports', label: 'Exports', icon: <ExportSidebar active={route === 'exports'}/> },
  ];
  return (
    <div style={{
      width: 220, flexShrink: 0,
      borderRight: '1px solid rgba(255,255,255,0.05)',
      padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 2,
      background: 'rgba(10,15,26,0.6)',
    }}>
      <div style={{ fontSize: 10.5, fontWeight: 600, color: '#6B7185', letterSpacing: '0.08em',
        textTransform: 'uppercase', padding: '6px 12px 4px' }}>
        Workspace
      </div>
      {items.map(it => {
        const active = it.id === route;
        return (
          <div key={it.id} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
            background: active ? 'rgba(249,115,22,0.10)' : 'transparent',
            border: `1px solid ${active ? 'rgba(249,115,22,0.25)' : 'transparent'}`,
            color: active ? '#F97316' : '#D4D4D8', fontSize: 13, fontWeight: 500,
            position: 'relative',
          }}>
            {active && <div style={{
              position: 'absolute', left: -12, top: '50%', transform: 'translateY(-50%)',
              width: 3, height: 18, borderRadius: 2, background: '#F97316',
            }}/>}
            {it.icon}
            {it.label}
          </div>
        );
      })}

      <div style={{ flex: 1 }}/>

      {/* Storage card */}
      <div style={{
        padding: 12, borderRadius: 12, marginBottom: 8,
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 11.5, fontWeight: 600, color: '#D4D4D8' }}>Library</span>
          <span style={{ fontSize: 11, color: '#9098A8' }}>32/100</span>
        </div>
        <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
          <div style={{ width: '32%', height: '100%', borderRadius: 2,
            background: 'linear-gradient(90deg, #FB923C, #F97316)' }}/>
        </div>
        <div style={{ fontSize: 11, color: '#6B7185', marginTop: 8 }}>32 guides created</div>
      </div>

      {/* User */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 6px',
        borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 12,
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: 8,
          background: 'linear-gradient(135deg, #FB923C, #C2410C)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700, color: '#1A1206',
        }}>A</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: '#F4F4F5' }}>Ahmed</div>
          <div style={{ fontSize: 11, color: '#9098A8' }}>Premium</div>
        </div>
        <SettingsI size={16} stroke="#6B7185" sw={2}/>
      </div>
    </div>
  );
}

// Side-bar icons (small variants)
function BoltSidebar({ active }) {
  const c = active ? '#F97316' : '#9098A8';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill={active ? c : 'none'} stroke={c} strokeWidth="1.8" strokeLinejoin="round">
      <path d="M13 2L4 14H11L10 22L20 9H12.5L13 2Z"/>
    </svg>
  );
}
function StylesSidebar({ active }) {
  const c = active ? '#F97316' : '#9098A8';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8">
      <rect x="3" y="3" width="7" height="7" rx="1"/>
      <rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/>
      <rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  );
}
function ExportSidebar({ active }) {
  const c = active ? '#F97316' : '#9098A8';
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v12"/><polyline points="7 8 12 3 17 8"/>
      <path d="M5 17v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3"/>
    </svg>
  );
}

// ──────────────────────────────────────────────────────────────
// Scene 1: Windows Home dashboard
// ──────────────────────────────────────────────────────────────
function WindowsHomeScreen() {
  return (
    <WindowsFrame route="home">
      <div style={{ flex: 1, overflow: 'auto', padding: '32px 40px 40px' }}>
        {/* Greeting */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 32, gap: 24 }}>
          <div style={{ flex: '1 1 auto', minWidth: 0 }}>
            <div style={{
              fontFamily: 'var(--serif)', fontSize: 34, fontWeight: 700, letterSpacing: '-0.025em', lineHeight: 1.1,
              whiteSpace: 'nowrap',
            }}>
              Good evening, Ahmed
            </div>
            <div style={{ color: '#9098A8', fontSize: 15, marginTop: 6 }}>
              What will we create today?
            </div>
          </div>
          <button className="sg-cta" style={{
            width: 200, height: 44, borderRadius: 12, fontSize: 14.5,
          }}>
            <Plus size={16} stroke="#1A1206" sw={2.6}/>
            New Guide
          </button>
        </div>

        {/* Quick actions — three large cards in a row */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 36,
        }}>
          <BigAction icon={<DocGlyph size={28}/>} label="Paste Text" desc="Drop in raw text and we'll structure it."/>
          <BigAction icon={<UploadGlyph size={28}/>} label="Upload Markdown" desc="Bring your notes, lectures, and PDFs."/>
          <BigAction icon={<SparkleGlyph size={28}/>} label="Generate with AI" desc="Start from a topic or syllabus prompt."/>
        </div>

        {/* Two-column: Guide Styles + Recent Guides */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28 }}>
          <div>
            <SectionHeadW title="Guide Styles" right="Browse all"/>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 14 }}>
              <StyleCard glyph={<LeafGlyph size={20} color="#65A30D"/>} name="Baby-step" tag="Beginners"/>
              <StyleCard glyph={<BoltGlyph size={20}/>} name="Exam Cram" tag="Popular" active/>
              <StyleCard glyph={<ListGlyph size={20}/>} name="MCQ Training" tag="Practice"/>
              <StyleCard glyph={<TrophyGlyph size={20}/>} name="Final Revision" tag="Finals"/>
              <StyleCard glyph={<SparkleGlyph size={20}/>} name="Editorial" tag="Premium"/>
              <StyleCard glyph={<CaseGlyph size={20}/>} name="Last-minute" tag="Quick"/>
            </div>
          </div>

          <div>
            <SectionHeadW title="Recent Guides" right="View all"/>
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { title: 'Calculus I — Exam Cram', meta: 'Generated 2h ago  •  24 pages', style: 'Exam Cram' },
                { title: 'Physics — MCQ Training', meta: 'Generated 1d ago  •  48 pages', style: 'MCQ' },
                { title: 'Data Structures — Editorial', meta: 'Generated 3d ago  •  36 pages', style: 'Editorial' },
                { title: 'Organic Chem — Final Revision', meta: 'Generated 4d ago  •  72 pages', style: 'Final' },
              ].map((r, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10,
                  cursor: 'pointer',
                }}>
                  <Tile size={36} radius={9}><DocGlyph size={20}/></Tile>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600, color: '#F4F4F5' }}>{r.title}</div>
                    <div style={{ fontSize: 11.5, color: '#9098A8', marginTop: 2 }}>{r.meta}</div>
                  </div>
                  <span className="sg-pill" style={{ height: 24, fontSize: 11, padding: '0 8px' }}>{r.style}</span>
                  <Kebab size={16} stroke="#6B7185"/>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </WindowsFrame>
  );
}

function SectionHeadW({ title, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
      <div style={{ fontFamily: 'var(--serif)', fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', whiteSpace: 'nowrap' }}>{title}</div>
      {right && <button style={{
        background: 'transparent', border: 0, color: '#F97316', fontSize: 13, fontWeight: 500, cursor: 'pointer',
      }}>{right}</button>}
    </div>
  );
}

function BigAction({ icon, label, desc }) {
  return (
    <div style={{
      padding: 18, borderRadius: 16,
      background: 'linear-gradient(180deg, rgba(255,255,255,0.035) 0%, rgba(255,255,255,0.01) 100%)',
      border: '1px solid rgba(255,255,255,0.07)',
      cursor: 'pointer', position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: -20, right: -20, width: 100, height: 100, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(249,115,22,0.10) 0%, transparent 70%)',
      }}/>
      <Tile size={48} radius={13}>{icon}</Tile>
      <div style={{ fontSize: 15.5, fontWeight: 600, marginTop: 14, letterSpacing: '-0.01em' }}>{label}</div>
      <div style={{ fontSize: 12.5, color: '#9098A8', marginTop: 4, lineHeight: 1.4 }}>{desc}</div>
    </div>
  );
}

function StyleCard({ glyph, name, tag, active }) {
  return (
    <div style={{
      padding: 12, borderRadius: 12, cursor: 'pointer',
      background: active ? 'linear-gradient(180deg, rgba(249,115,22,0.14), rgba(249,115,22,0.04))' : 'rgba(255,255,255,0.02)',
      border: `1px solid ${active ? 'rgba(249,115,22,0.4)' : 'rgba(255,255,255,0.06)'}`,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <Tile size={32} radius={9} variant={active ? 'orange' : 'dark'}>
        {React.cloneElement(glyph, { color: active ? '#1B0F03' : '#F97316' })}
      </Tile>
      <div>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: '#F4F4F5' }}>{name}</div>
        <div style={{ fontSize: 10.5, color: '#9098A8', marginTop: 2 }}>{tag}</div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Scene 2: Windows Builder — composer + preview
// ──────────────────────────────────────────────────────────────
function WindowsBuilderScreen() {
  return (
    <WindowsFrame route="builder">
      {/* Breadcrumb tabs */}
      <div style={{
        height: 44, flexShrink: 0, padding: '0 28px',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        display: 'flex', alignItems: 'center', gap: 18,
      }}>
        <Crumb label="Builder" active/>
        <Crumb label="Outline"/>
        <Crumb label="Style"/>
        <Crumb label="Preview"/>
        <div style={{ flex: 1 }}/>
        <span className="sg-pill" style={{ height: 26, fontSize: 11.5 }}>
          <span style={{ width: 6, height: 6, borderRadius: 3, background: '#22C55E' }}/>
          Auto-saved · 2s ago
        </span>
      </div>

      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Composer (left) */}
        <div style={{
          flex: '1 1 0', minWidth: 0,
          padding: '28px 36px', display: 'flex', flexDirection: 'column', gap: 22,
          borderRight: '1px solid rgba(255,255,255,0.05)',
          overflow: 'auto',
        }}>
          <div>
            <FieldLabel>Title</FieldLabel>
            <input defaultValue="Calculus I — Limits & Continuity"
              style={fieldStyle('lg')}/>
          </div>

          {/* Source tabs */}
          <div>
            <FieldLabel>Source</FieldLabel>
            <div style={{ display: 'flex', gap: 4, marginTop: 6, padding: 4,
              background: 'rgba(255,255,255,0.03)', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.06)',
              width: 'fit-content',
            }}>
              {['Paste text', 'Upload .md', 'AI prompt', 'URL'].map((t, i) => (
                <button key={i} style={{
                  height: 32, padding: '0 12px', borderRadius: 7, border: 0, cursor: 'pointer',
                  background: i === 0 ? 'linear-gradient(180deg, #FB923C, #EA580C)' : 'transparent',
                  color: i === 0 ? '#1A1206' : '#D4D4D8',
                  fontSize: 12.5, fontWeight: i === 0 ? 600 : 500,
                  boxShadow: i === 0 ? 'inset 0 1px 0 rgba(255,255,255,0.3)' : 'none',
                }}>{t}</button>
              ))}
            </div>

            {/* Code-like textarea */}
            <div style={{
              marginTop: 10, padding: 14, minHeight: 200,
              background: '#070B14', borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.08)',
              fontFamily: 'var(--mono)', fontSize: 12.5, lineHeight: 1.7,
              position: 'relative',
            }}>
              <div style={{ color: '#F97316' }}># Limits & Continuity</div>
              <div style={{ color: '#6B7185' }}>A limit describes the value a function approaches as the</div>
              <div style={{ color: '#6B7185' }}>input approaches some value. Formally, lim x→c f(x) = L if…</div>
              <div style={{ color: '#F97316', marginTop: 8 }}>## Definitions</div>
              <div style={{ color: '#D4D4D8' }}>- One-sided limits: lim x→c⁻ f(x) and lim x→c⁺ f(x)</div>
              <div style={{ color: '#D4D4D8' }}>- Two-sided: equal one-sided limits</div>
              <div style={{ color: '#F97316', marginTop: 8 }}>## Continuity</div>
              <div style={{ color: '#D4D4D8' }}>A function f is continuous at c if lim x→c f(x) = f(c).</div>
              <span style={{
                display: 'inline-block', width: 8, height: 14, background: '#F97316',
                verticalAlign: 'text-bottom', animation: 'blink 1s steps(2) infinite',
              }}/>
              <div style={{
                position: 'absolute', bottom: 8, right: 12, fontSize: 11, color: '#6B7185', fontFamily: 'var(--sans)',
              }}>4,218 / 50,000 chars</div>
            </div>
          </div>

          {/* Style + length row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 16 }}>
            <div>
              <FieldLabel>Style</FieldLabel>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginTop: 6 }}>
                <MiniStyle glyph={<LeafGlyph size={16} color="#65A30D"/>} name="Baby"/>
                <MiniStyle glyph={<BoltGlyph size={16}/>} name="Cram" active/>
                <MiniStyle glyph={<ListGlyph size={16}/>} name="MCQ"/>
                <MiniStyle glyph={<TrophyGlyph size={16}/>} name="Final"/>
                <MiniStyle glyph={<SparkleGlyph size={16}/>} name="Editorial"/>
              </div>
            </div>
            <div>
              <FieldLabel>Length</FieldLabel>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 6 }}>
                {[['Short', '~10'], ['Medium', '~20'], ['Long', '~30+']].map(([n, m], i) => (
                  <div key={i} style={{
                    padding: '8px 6px', borderRadius: 9, textAlign: 'center', cursor: 'pointer',
                    background: i === 1 ? 'rgba(249,115,22,0.12)' : 'transparent',
                    border: `1px solid ${i === 1 ? 'rgba(249,115,22,0.45)' : 'rgba(255,255,255,0.08)'}`,
                  }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600 }}>{n}</div>
                    <div style={{ fontSize: 10.5, color: '#9098A8' }}>{m} pages</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Advanced toggles */}
          <div>
            <FieldLabel>Include</FieldLabel>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
              {['Key concepts', 'Mnemonics', 'Examples', 'Diagrams', 'MCQ practice', 'Glossary', 'TL;DR'].map((t, i) => (
                <span key={i} className={i < 4 ? 'sg-pill sg-pill-orange' : 'sg-pill'}
                  style={{ height: 28, fontSize: 12 }}>
                  {i < 4 && <span style={{ fontSize: 10 }}>✓</span>}{t}
                </span>
              ))}
            </div>
          </div>

          {/* Model + actions */}
          <div style={{
            marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 12,
            paddingTop: 18, borderTop: '1px solid rgba(255,255,255,0.05)',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 10,
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: 4, background: '#F97316',
                boxShadow: '0 0 8px rgba(249,115,22,0.8)',
              }}/>
              <span style={{ fontSize: 12.5, fontWeight: 500 }}>Best for accuracy</span>
              <ChevronRight size={14} stroke="#9098A8" sw={2}/>
            </div>
            <div style={{ flex: 1 }}/>
            <button style={{
              height: 40, padding: '0 16px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.1)',
              background: 'transparent', color: '#D4D4D8', fontSize: 13, fontWeight: 500, cursor: 'pointer',
            }}>Save draft</button>
            <button className="sg-cta" style={{
              width: 200, height: 40, borderRadius: 10, fontSize: 14,
            }}>
              <SparkleGlyph size={18} color="#1A1206"/>
              Generate Guide
            </button>
          </div>
        </div>

        {/* Preview (right) */}
        <div style={{
          width: 420, flexShrink: 0,
          background: 'linear-gradient(180deg, #060A12 0%, #0A0F1A 100%)',
          padding: '24px 24px', display: 'flex', flexDirection: 'column', gap: 14,
          position: 'relative',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: '#D4D4D8' }}>Live preview</div>
            <div style={{ display: 'flex', gap: 4 }}>
              <PreviewBtn>1×</PreviewBtn>
              <PreviewBtn active>2×</PreviewBtn>
              <PreviewBtn>Fit</PreviewBtn>
            </div>
          </div>

          {/* PDF mock */}
          <div style={{
            flex: 1, borderRadius: 8, padding: 22,
            background: '#FAF7F2',
            color: '#1F1A14', fontFamily: 'var(--serif)',
            boxShadow: '0 30px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)',
            overflow: 'hidden', position: 'relative',
          }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#A78050', letterSpacing: '0.15em' }}>
              EXAM CRAM · MEDIUM
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.1, marginTop: 6 }}>
              Limits &amp; Continuity
            </div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 10.5, color: '#6B5A3F', marginTop: 4 }}>
              Calculus I · Chapter 2 · 18 min read
            </div>
            <div style={{
              height: 1, marginTop: 14,
              background: 'linear-gradient(90deg, #C2410C, transparent)',
            }}/>

            <div style={{ fontSize: 13, fontWeight: 700, marginTop: 14 }}>1 · Definitions</div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 10.5, lineHeight: 1.55, color: '#3A3528', marginTop: 6 }}>
              A limit describes the value a function approaches as its input approaches some value c.
            </div>
            <div style={{
              marginTop: 10, padding: '10px 12px', borderLeft: '2px solid #F97316',
              background: 'rgba(249,115,22,0.07)', fontFamily: 'var(--mono)', fontSize: 10.5, color: '#7A4A1C',
            }}>
              lim x→c f(x) = L
            </div>

            <div style={{ fontSize: 13, fontWeight: 700, marginTop: 14 }}>2 · Continuity</div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 10.5, lineHeight: 1.55, color: '#3A3528', marginTop: 6 }}>
              f is continuous at c if lim x→c f(x) = f(c). Three conditions must hold:
            </div>
            <ul style={{ fontFamily: 'var(--sans)', fontSize: 10.5, color: '#3A3528', margin: '6px 0 0 0', paddingLeft: 18 }}>
              <li>f(c) is defined</li>
              <li>The limit exists</li>
              <li>They are equal</li>
            </ul>

            <div style={{
              marginTop: 14, padding: 10, borderRadius: 6,
              background: 'rgba(249,115,22,0.10)',
              border: '1px dashed rgba(194,65,12,0.4)',
            }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#A78050', letterSpacing: '0.1em' }}>MEMORY CUE</div>
              <div style={{ fontFamily: 'var(--sans)', fontSize: 11, color: '#3A3528', marginTop: 2 }}>
                <strong>D-L-E</strong>: Defined · Limit exists · Equal
              </div>
            </div>

            {/* Page footer */}
            <div style={{
              position: 'absolute', bottom: 16, left: 22, right: 22,
              display: 'flex', justifyContent: 'space-between',
              fontFamily: 'var(--mono)', fontSize: 9, color: '#A78050',
            }}>
              <span>STUDY GUIDE</span>
              <span>03 / 20</span>
            </div>
          </div>

          {/* Footer actions */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={previewActionStyle}>
              <PDFGlyph size={16}/>
              <span style={{ marginLeft: 8 }}>Export PDF</span>
            </button>
            <button style={previewActionStyle}>
              <Share size={14} stroke="#D4D4D8" sw={2}/>
              <span style={{ marginLeft: 8 }}>Share</span>
            </button>
          </div>
        </div>
      </div>
    </WindowsFrame>
  );
}

function Crumb({ label, active }) {
  return (
    <div style={{
      fontSize: 13, fontWeight: 500, padding: '14px 2px',
      color: active ? '#F4F4F5' : '#9098A8',
      borderBottom: active ? '2px solid #F97316' : '2px solid transparent',
      marginBottom: -1, cursor: 'pointer',
    }}>{label}</div>
  );
}

function FieldLabel({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, color: '#9098A8', letterSpacing: '0.06em',
      textTransform: 'uppercase', marginBottom: 6,
    }}>{children}</div>
  );
}

function fieldStyle(sz = 'md') {
  const h = sz === 'lg' ? 44 : 36;
  return {
    width: '100%', height: h, padding: '0 14px',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10, outline: 'none',
    color: '#F4F4F5', fontFamily: 'var(--sans)',
    fontSize: sz === 'lg' ? 16 : 13.5, fontWeight: 500,
    letterSpacing: '-0.01em',
  };
}

function MiniStyle({ glyph, name, active }) {
  return (
    <div style={{
      padding: '6px 4px', borderRadius: 8, cursor: 'pointer',
      background: active ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.02)',
      border: `1px solid ${active ? 'rgba(249,115,22,0.45)' : 'rgba(255,255,255,0.06)'}`,
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
    }}>
      <Tile size={26} radius={7} variant={active ? 'orange' : 'dark'}>
        {React.cloneElement(glyph, { color: active ? '#1B0F03' : '#F97316' })}
      </Tile>
      <div style={{ fontSize: 10.5, fontWeight: 500 }}>{name}</div>
    </div>
  );
}

function PreviewBtn({ children, active }) {
  return (
    <button style={{
      height: 24, padding: '0 8px', fontSize: 11, fontWeight: 500, cursor: 'pointer',
      background: active ? 'rgba(249,115,22,0.14)' : 'transparent',
      color: active ? '#F97316' : '#9098A8',
      border: `1px solid ${active ? 'rgba(249,115,22,0.4)' : 'rgba(255,255,255,0.08)'}`,
      borderRadius: 6,
    }}>{children}</button>
  );
}

const previewActionStyle = {
  flex: 1, height: 36, borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)',
  background: 'rgba(255,255,255,0.03)', color: '#D4D4D8', fontSize: 12.5, fontWeight: 500,
  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
};

// blink for caret
if (typeof document !== 'undefined' && !document.getElementById('sg-anim')) {
  const s = document.createElement('style');
  s.id = 'sg-anim';
  s.textContent = '@keyframes blink { 50% { opacity: 0 } }';
  document.head.appendChild(s);
}

Object.assign(window, { WindowsHomeScreen, WindowsBuilderScreen });
