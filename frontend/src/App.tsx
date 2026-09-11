import { useEffect, useRef, useState, useCallback } from 'react'
import SolderPasteScan from './SolderPasteScan'
import { HistoryView, ReportsView } from './CaseWorkspace'

// ─── Global scroll state ───────────────────────────────────────────────────────
function useScrollY() {
  const [scrollY, setScrollY] = useState(0)
  useEffect(() => {
    const onScroll = () => setScrollY(window.scrollY)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return scrollY
}

// ─── Per-section parallax: background image moves slower than viewport ────────
function useParallaxBg(speed = 0.35) {
  const ref = useRef<HTMLElement>(null)
  const [bgOffset, setBgOffset] = useState(0)

  const update = useCallback(() => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    // How far the section center is from viewport center
    const relCenter = rect.top + rect.height / 2 - window.innerHeight / 2
    setBgOffset(relCenter * speed)
  }, [speed])

  useEffect(() => {
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    update()
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [update])

  return { ref, bgOffset }
}

// ─── Foreground floating element parallax (inverse of bg, faster) ─────────────
function useParallaxFg(speed = -0.08) {
  const ref = useRef<HTMLDivElement>(null)
  const [fgOffset, setFgOffset] = useState(0)

  const update = useCallback(() => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const relCenter = rect.top + rect.height / 2 - window.innerHeight / 2
    setFgOffset(relCenter * speed)
  }, [speed])

  useEffect(() => {
    window.addEventListener('scroll', update, { passive: true })
    update()
    return () => window.removeEventListener('scroll', update)
  }, [update])

  return { ref, fgOffset }
}

// ─── Intersection for fade-in ──────────────────────────────────────────────────
function useInView(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setInView(true) },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return { ref, inView }
}

type AppView = 'home' | 'scan' | 'reports' | 'history'

const NAV_ITEMS: { label: string; view: AppView }[] = [
  { label: 'Dashboard', view: 'home' },
  { label: 'Upload/Describe', view: 'scan' },
  { label: 'Reports', view: 'reports' },
  { label: 'History', view: 'history' },
]

// ─── Nav ───────────────────────────────────────────────────────────────────────
function Nav({
  view,
  onNavigate,
  forceSolid = false,
}: {
  view: AppView
  onNavigate: (view: AppView) => void
  forceSolid?: boolean
}) {
  const scrollY = useScrollY()
  const scrolled = forceSolid || scrollY > 40 || view !== 'home'

  return (
    <nav
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 40px', height: 64,
        background: scrolled ? 'rgba(255,255,255,0.88)' : 'transparent',
        backdropFilter: scrolled ? 'blur(16px)' : 'none',
        borderBottom: scrolled ? '1px solid rgba(11,104,115,0.1)' : 'none',
        transition: 'background 0.3s, backdrop-filter 0.3s, border-color 0.3s',
      }}
    >
      <button
        type="button"
        onClick={() => onNavigate('home')}
        style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
      >
        <div style={{ width: 32, height: 32, borderRadius: 8, background: '#0B6873', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 12L6 6L9 9L12 4" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="12" cy="4" r="1.5" fill="white" />
          </svg>
        </div>
        <span style={{ fontWeight: 800, fontSize: 17, color: scrolled ? '#1F2033' : 'white', letterSpacing: '-0.03em', transition: 'color 0.3s' }}>DARA</span>
      </button>

      <div style={{ display: 'flex', gap: 32 }}>
        {NAV_ITEMS.map(item => {
          const active = view === item.view
          const idle = scrolled ? 'rgba(31,32,51,0.6)' : 'rgba(255,255,255,0.75)'
          const hover = scrolled ? '#1F2033' : 'white'
          return (
            <button
              key={item.label}
              type="button"
              onClick={() => onNavigate(item.view)}
              style={{
                fontSize: 13,
                fontWeight: active ? 700 : 500,
                color: active ? (scrolled ? '#0B6873' : 'white') : idle,
                textDecoration: 'none',
                transition: 'color 0.3s',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                borderBottom: active ? `2px solid ${scrolled ? '#0B6873' : 'rgba(255,255,255,0.85)'}` : '2px solid transparent',
                paddingBottom: 2,
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.color = hover }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.color = idle }}
            >
              {item.label}
            </button>
          )
        })}
      </div>

      <button
        type="button"
        onClick={() => onNavigate('scan')}
        style={{ background: '#D66A2C', color: 'white', border: 'none', borderRadius: 999, padding: '9px 22px', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'background 0.2s, transform 0.2s' }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#B85320'; (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)' }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = '#D66A2C'; (e.currentTarget as HTMLButtonElement).style.transform = '' }}
      >Get Started</button>
    </nav>
  )
}

// ─── Hero — cinematic parallax hero for PCB solder-paste inspection ──────────
function Hero({ onStartScan }: { onStartScan: () => void }) {
  const { ref, bgOffset } = useParallaxBg(0.45)
  const { ref: cardRef, fgOffset } = useParallaxFg(-0.12)
  const scrollY = useScrollY()
  // Fade hero text as user scrolls
  const heroOpacity = Math.max(0, 1 - scrollY / 500)
  const heroScale = 1 - scrollY * 0.0002

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      style={{
        position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
        background: '#102A43',
      }}
    >
      {/* Background photo layer — moves slower than scroll */}
      <div style={{
        position: 'absolute', inset: '-20%',
        transform: `translateY(${bgOffset}px)`,
        willChange: 'transform',
      }}>
        <img
          src="https://images.unsplash.com/photo-1518770660439-4636190af475?w=1800&h=1200&fit=crop&auto=format"
          alt="Printed circuit board for solder-paste inspection"
          style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center' }}
        />
        {/* Navy and teal overlay for technical text legibility */}
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(160deg, rgba(16,42,67,0.88) 0%, rgba(11,104,115,0.58) 60%, rgba(16,42,67,0.92) 100%)' }} />
      </div>

      {/* Floating particle dots */}
      <div style={{ position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)', backgroundSize: '28px 28px', pointerEvents: 'none' }} />

      {/* Hero content — fades and scales out on scroll */}
      <div style={{
        position: 'relative', zIndex: 10, textAlign: 'center', maxWidth: 780, padding: '0 32px',
        marginTop: 80, /* <-- Add this line */
        opacity: heroOpacity, transform: `scale(${heroScale})`,
        willChange: 'transform, opacity',
      }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(255,255,255,0.12)', backdropFilter: 'blur(8px)', borderRadius: 999, padding: '6px 16px', marginBottom: 28, border: '1px solid rgba(255,255,255,0.18)' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#F2A65A', display: 'inline-block' }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.85)', letterSpacing: '0.05em' }}>SOLDER-PASTE DISPENSING INTELLIGENCE</span>
        </div>

        <h1 style={{ fontSize: 'clamp(2.6rem, 6vw, 4.2rem)', fontWeight: 900, color: 'white', lineHeight: 1.08, letterSpacing: '-0.04em', margin: '0 0 24px' }}>
          Solder-paste dispensing,<br />
          <span style={{ color: '#F2A65A' }}>root cause</span> at scale
        </h1>

        <p style={{ fontSize: 18, color: 'rgba(255,255,255,0.65)', lineHeight: 1.65, marginBottom: 40, maxWidth: 580, margin: '0 auto 40px' }}>
          AI-powered inspection for PCB assembly teams: detect insufficient paste, bridging, misalignment, and volume variation before rework spreads.
        </p>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={onStartScan}
            style={{ background: '#D66A2C', color: 'white', border: 'none', borderRadius: 999, padding: '14px 32px', fontSize: 15, fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 8px 32px rgba(214,106,44,0.4)' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#B85320'; (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = '#D66A2C'; (e.currentTarget as HTMLButtonElement).style.transform = '' }}
          >Start a line scan</button>
          <button
            type="button"
            onClick={() => document.getElementById('inspection-flow')?.scrollIntoView({ behavior: 'smooth' })}
            style={{ background: 'rgba(255,255,255,0.1)', color: 'white', border: '1.5px solid rgba(255,255,255,0.25)', borderRadius: 999, padding: '14px 32px', fontSize: 15, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'all 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.18)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.1)' }}
          >See the inspection flow ↓</button>
        </div>
      </div>

      {/* Floating hero screenshot — moves faster than background for depth */}
      <div
        ref={cardRef}
        style={{
          position: 'relative', zIndex: 10, marginTop: 64, width: '100%', maxWidth: 980, padding: '0 24px',
          transform: `translateY(${fgOffset}px)`,
          willChange: 'transform',
        }}
      >
        <div style={{ borderRadius: 20, overflow: 'hidden', boxShadow: '0 40px 100px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.08)', background: 'white' }}>
          <DashboardMockup />
        </div>
      </div>

      {/* Scroll cue */}
      <div style={{ position: 'absolute', bottom: 36, left: '50%', transform: 'translateX(-50%)', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, opacity: heroOpacity }}>
        <span style={{ fontSize: 11, fontWeight: 500, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.12em' }}>SCROLL</span>
        <div style={{ width: 1, height: 40, background: 'linear-gradient(to bottom, rgba(255,255,255,0.4), transparent)' }} />
      </div>
    </section>
  )
}

// ─── Inline Dashboard Mockup ───────────────────────────────────────────────────
function DashboardMockup() {
  return (
    <div style={{ background: '#F7F6FB', fontFamily: 'inherit' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 18px', background: 'white', borderBottom: '1px solid rgba(79,70,229,0.07)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 22, height: 22, borderRadius: 6, background: '#0B6873', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 7.5L3.5 3.5L5.5 5.5L7.5 2" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <span style={{ fontWeight: 800, fontSize: 12, color: '#1F2033' }}>DARA</span>
          <span style={{ fontSize: 11, color: 'rgba(31,32,51,0.35)' }}>/ Dashboard Overview</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {['Live', 'Line 04'].map((t, i) => (
            <span key={t} style={{ fontSize: 10, fontWeight: 600, padding: '3px 10px', borderRadius: 999, background: i === 0 ? '#0B6873' : 'rgba(11,104,115,0.1)', color: i === 0 ? 'white' : '#0B6873' }}>{t}</span>
          ))}
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, padding: 14 }}>
        {[
          { label: 'Paste Deposits', value: '48,291', delta: '+3.2%', up: true },
          { label: 'Defect Rate', value: '0.42%', delta: '-0.08%', up: true },
          { label: 'Open NCRs', value: '17', delta: '+2', up: false },
          { label: 'Vision Accuracy', value: '98.7%', delta: '+0.3%', up: true },
        ].map(k => (
          <div key={k.label} style={{ background: 'white', borderRadius: 12, padding: '10px 12px', border: '1px solid rgba(79,70,229,0.07)' }}>
            <div style={{ fontSize: 10, color: 'rgba(31,32,51,0.45)', marginBottom: 4 }}>{k.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#1F2033', letterSpacing: '-0.03em' }}>{k.value}</div>
            <div style={{ fontSize: 10, fontWeight: 600, color: k.up ? '#10B981' : '#EF4444', marginTop: 2 }}>{k.delta}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10, padding: '0 14px 14px' }}>
        <div style={{ background: 'white', borderRadius: 12, padding: 12, border: '1px solid rgba(79,70,229,0.07)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(22,32,42,0.5)', marginBottom: 8 }}>Defect Trend — Last 30 Runs</div>
          <svg viewBox="0 0 320 72" style={{ width: '100%', height: 72 }}>
            <defs>
              <linearGradient id="hg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0B6873" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#0B6873" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d="M0,56 C20,50 40,62 70,44 C100,28 120,40 150,34 C180,28 200,38 230,28 C255,20 280,24 320,14" fill="none" stroke="#0B6873" strokeWidth="2" strokeLinecap="round" />
            <path d="M0,56 C20,50 40,62 70,44 C100,28 120,40 150,34 C180,28 200,38 230,28 C255,20 280,24 320,14 L320,72 L0,72Z" fill="url(#hg)" />
          </svg>
        </div>
        <div style={{ background: 'white', borderRadius: 12, padding: 12, border: '1px solid rgba(79,70,229,0.07)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(31,32,51,0.5)', marginBottom: 8 }}>By Type</div>
          {[['Insufficient Paste', '38', '#0B6873'], ['Bridging', '27', '#D66A2C'], ['Misalignment', '19', '#F2A65A'], ['Other', '16', '#B7C9C6']].map(([l, p, c]) => (
            <div key={l} style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'rgba(31,32,51,0.55)', marginBottom: 2 }}><span>{l}</span><span>{p}%</span></div>
              <div style={{ height: 4, borderRadius: 99, background: '#F7F6FB' }}><div style={{ height: 4, borderRadius: 99, width: `${p}%`, background: c }} /></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Logo Row ──────────────────────────────────────────────────────────────────
function LogoRow() {
  return (
    <section style={{ background: 'white', padding: '56px 40px' }}>
      <p style={{ textAlign: 'center', fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: 'rgba(31,32,51,0.32)', marginBottom: 32, textTransform: 'uppercase' }}>
        Built for electronics manufacturing lines
      </p>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap', gap: '8px 40px', maxWidth: 800, margin: '0 auto' }}>
        {['StencilLine', 'BoardWorks', 'FluxCore', 'Precision SMT', 'CopperPeak', 'Assembly Lab'].map(name => (
          <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{ width: 20, height: 20, borderRadius: 5, background: '#D1D5DB' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#9CA3AF', letterSpacing: '-0.02em' }}>{name}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

// ─── Parallax Feature Section — full-bleed photo bg + floating card ────────────
interface FeatureSectionProps {
  eyebrow: string
  heading: React.ReactNode
  body: string
  bullets: string[]
  imgSrc: string
  imgAlt: string
  bgSpeed?: number
  fgSpeed?: number
  flipped?: boolean
  bgColor?: string
  accentColor?: string
  MockupComponent: React.ComponentType
}

function FeatureSection({
  eyebrow, heading, body, bullets, imgSrc, imgAlt,
  bgSpeed = 0.32, fgSpeed = -0.06,
  flipped = false, bgColor = '#F7F6FB',
  MockupComponent,
}: FeatureSectionProps) {
  const sectionRef = useRef<HTMLElement>(null)
  const [bgY, setBgY] = useState(0)
  const [fgY, setFgY] = useState(0)
  const { ref: textRef, inView } = useInView(0.1)

  useEffect(() => {
    const update = () => {
      if (!sectionRef.current) return
      const rect = sectionRef.current.getBoundingClientRect()
      const relCenter = rect.top + rect.height / 2 - window.innerHeight / 2
      setBgY(relCenter * bgSpeed)
      setFgY(relCenter * fgSpeed)
    }
    window.addEventListener('scroll', update, { passive: true })
    update()
    return () => window.removeEventListener('scroll', update)
  }, [bgSpeed, fgSpeed])

  return (
    <section
      ref={sectionRef}
      style={{ background: bgColor, overflow: 'hidden', padding: '120px 0' }}
    >
      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '0 48px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 72, alignItems: 'center' }}>

        {/* Photo + floating mockup */}
        <div style={{ order: flipped ? 2 : 1, position: 'relative' }}>
          {/* Photo card with parallax bg */}
          <div style={{ borderRadius: 20, overflow: 'hidden', position: 'relative', height: 460, boxShadow: '0 32px 80px rgba(31,32,51,0.18)', transform: `translateY(${bgY}px)`, willChange: 'transform', transition: 'transform 0.05s linear' }}>
            <img
              src={imgSrc}
              alt={imgAlt}
              style={{ width: '100%', height: '130%', objectFit: 'cover', objectPosition: 'center top', position: 'absolute', top: '-15%' }}
            />
            {/* Subtle PCB-teal tint overlay */}
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, rgba(11,104,115,0.16) 0%, rgba(16,42,67,0.28) 100%)' }} />
          </div>

          {/* Floating UI card — moves counter to background */}
          <div
            style={{
              position: 'absolute',
              bottom: -28, right: flipped ? 'auto' : -36, left: flipped ? -36 : 'auto',
              width: 340,
              borderRadius: 16,
              overflow: 'hidden',
              boxShadow: '0 20px 60px rgba(11,104,115,0.18), 0 4px 16px rgba(0,0,0,0.1)',
              border: '1px solid rgba(11,104,115,0.12)',
              background: 'white',
              transform: `translateY(${fgY}px)`,
              willChange: 'transform',
              transition: 'transform 0.05s linear',
              zIndex: 10,
            }}
          >
            <MockupComponent />
          </div>
        </div>

        {/* Text */}
        <div
          ref={textRef}
          style={{
            order: flipped ? 1 : 2,
            opacity: inView ? 1 : 0,
            transform: inView ? 'none' : `translateX(${flipped ? -32 : 32}px)`,
            transition: 'opacity 0.8s ease, transform 0.8s ease',
          }}
        >
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(79,70,229,0.08)', borderRadius: 999, padding: '5px 14px', marginBottom: 20 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#0B6873', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{eyebrow}</span>
          </div>
          <h2 style={{ fontSize: 'clamp(1.8rem, 2.8vw, 2.5rem)', fontWeight: 900, color: '#1F2033', lineHeight: 1.12, letterSpacing: '-0.035em', margin: '0 0 18px' }}>{heading}</h2>
          <p style={{ fontSize: 16, color: 'rgba(31,32,51,0.58)', lineHeight: 1.7, marginBottom: 28 }}>{body}</p>
          <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 36px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {bullets.map((b, i) => (
              <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, fontSize: 14, color: 'rgba(31,32,51,0.7)' }}>
                <span style={{ marginTop: 2, width: 18, height: 18, borderRadius: '50%', background: 'rgba(11,104,115,0.1)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="8" height="8" viewBox="0 0 8 8"><path d="M1.5 4L3 5.5L6.5 2" stroke="#0B6873" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </span>
                {b}
              </li>
            ))}
          </ul>
          <button style={{ background: '#D66A2C', color: 'white', border: 'none', borderRadius: 999, padding: '12px 28px', fontSize: 14, fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#B85320'; (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = '#D66A2C'; (e.currentTarget as HTMLButtonElement).style.transform = '' }}
          >View line details →</button>
        </div>
      </div>
    </section>
  )
}

// ─── Mockup: Dashboard stats card ─────────────────────────────────────────────
function MiniDashboard() {
  return (
    <div style={{ padding: 16, background: '#F7F6FB' }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(31,32,51,0.45)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Live KPI Feed</div>
      {[
        { label: 'Line A Paste Rate', value: '0.38%', ok: true },
        { label: 'Line B Throughput', value: '1,204/hr', ok: true },
        { label: 'Line C Open NCRs', value: '4', ok: false },
        { label: 'Vision Accuracy Today', value: '99.1%', ok: true },
      ].map(row => (
        <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'white', borderRadius: 10, padding: '8px 12px', marginBottom: 6, border: '1px solid rgba(79,70,229,0.07)' }}>
          <span style={{ fontSize: 11, color: 'rgba(31,32,51,0.55)' }}>{row.label}</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: row.ok ? '#1F2033' : '#F59E0B' }}>{row.value}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Mockup: AI Scan queue ─────────────────────────────────────────────────────
function MiniAIScan() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(31,32,51,0.45)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Vision Inspection Queue</div>
      {[
        { id: 'PCB-20948', type: 'Insufficient paste', flag: 'error', conf: 94 },
        { id: 'PCB-20947', type: 'Volume within tolerance', flag: 'pass', conf: 99 },
        { id: 'PCB-20946', type: 'Bridging risk detected', flag: 'warn', conf: 87 },
      ].map(item => (
        <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#F7F6FB', borderRadius: 10, padding: '8px 12px', marginBottom: 6, border: '1px solid rgba(79,70,229,0.07)' }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#0B6873' }}>{item.id}</div>
            <div style={{ fontSize: 10, color: 'rgba(31,32,51,0.45)' }}>{item.type}</div>
          </div>
          <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 999, background: item.flag === 'pass' ? 'rgba(16,185,129,0.1)' : item.flag === 'warn' ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)', color: item.flag === 'pass' ? '#059669' : item.flag === 'warn' ? '#D97706' : '#DC2626' }}>
            {item.flag === 'pass' ? 'Pass' : item.flag === 'warn' ? 'Review' : 'Flag'}
          </span>
        </div>
      ))}
      <div style={{ marginTop: 8, height: 4, borderRadius: 99, background: '#D5E3E0' }}>
        <div style={{ height: 4, borderRadius: 99, width: '73%', background: '#0B6873' }} />
      </div>
      <div style={{ fontSize: 10, color: 'rgba(31,32,51,0.35)', marginTop: 4 }}>73 of 100 scanned</div>
    </div>
  )
}

// ─── Mockup: Report approval ───────────────────────────────────────────────────
function MiniReport() {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(31,32,51,0.45)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>CAPA Report Sep 2026</div>
        <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 999, background: 'rgba(11,104,115,0.1)', color: '#0B6873' }}>PDF</span>
      </div>
      {[
        { name: 'S. Okafor', role: 'Quality Lead', signed: true },
        { name: 'M. Reyes', role: 'Process Engineer', signed: true },
        { name: 'L. Chen', role: 'Production Manager', signed: false },
      ].map(s => (
        <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#F7F6FB', borderRadius: 10, padding: '8px 12px', marginBottom: 6, border: '1px solid rgba(79,70,229,0.07)' }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#1F2033' }}>{s.name}</div>
            <div style={{ fontSize: 10, color: 'rgba(31,32,51,0.4)' }}>{s.role}</div>
          </div>
          <span style={{ fontSize: 11, fontWeight: 700, color: s.signed ? '#10B981' : '#F59E0B' }}>{s.signed ? '✓ Signed' : 'Pending'}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Mockup: History bar chart ─────────────────────────────────────────────────
function MiniHistory() {
  const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
  const vals = [28, 35, 22, 41, 30, 17]
  const max = Math.max(...vals)
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(31,32,51,0.45)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Monthly Case Volume</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 60, marginBottom: 4 }}>
        {months.map((m, i) => (
          <div key={m} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <div style={{ width: '100%', borderRadius: '4px 4px 0 0', height: `${(vals[i] / max) * 52}px`, background: i === months.length - 1 ? '#D66A2C' : '#B7C9C6', transition: 'background 0.2s' }} />
            <span style={{ fontSize: 9, color: 'rgba(31,32,51,0.4)' }}>{m}</span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 8, fontSize: 10, color: 'rgba(31,32,51,0.4)', textAlign: 'right' }}>
        <span style={{ color: '#0B6873', fontWeight: 700 }}>↓ 43%</span> vs Aug peak
      </div>
    </div>
  )
}

// ─── Stats Band ────────────────────────────────────────────────────────────────
function StatsBand() {
  const { ref, inView } = useInView(0.2)
  return (
    <section ref={ref} style={{ background: '#0B6873', padding: '64px 48px' }}>
      <div style={{ maxWidth: 900, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 40, textAlign: 'center' }}>
        {[
          { stat: '98.7%', label: 'AI Detection Accuracy' },
          { stat: '0.42%', label: 'Avg Paste Defect Rate' },
          { stat: '40+', label: 'Production Lines' },
          { stat: '<1s', label: 'Vision Scan Latency' },
        ].map((s, i) => (
          <div key={s.label} style={{ opacity: inView ? 1 : 0, transform: inView ? 'none' : 'translateY(20px)', transition: `opacity 0.6s ${i * 100}ms, transform 0.6s ${i * 100}ms` }}>
            <div style={{ fontSize: 'clamp(2rem, 3vw, 3rem)', fontWeight: 900, color: 'white', letterSpacing: '-0.04em', marginBottom: 6 }}>{s.stat}</div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', fontWeight: 500 }}>{s.label}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ─── CTA ───────────────────────────────────────────────────────────────────────
function CTA({ onStartScan }: { onStartScan: () => void }) {
  const { ref: sectionRef, bgOffset } = useParallaxBg(0.3)
  const { ref: textRef, inView } = useInView(0.2)

  return (
    <section ref={sectionRef as React.RefObject<HTMLElement>} style={{ position: 'relative', overflow: 'hidden', padding: '140px 48px', minHeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {/* Parallax bg */}
      <div style={{ position: 'absolute', inset: '-20%', transform: `translateY(${bgOffset}px)`, willChange: 'transform' }}>
        <img src="https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=1600&h=900&fit=crop&auto=format" alt="Engineer inspecting a production line" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, rgba(11,104,115,0.92) 0%, rgba(16,42,67,0.9) 100%)' }} />
      </div>

      <div
        ref={textRef}
        style={{
          position: 'relative', zIndex: 10, textAlign: 'center', maxWidth: 640,
          opacity: inView ? 1 : 0, transform: inView ? 'none' : 'translateY(30px)',
          transition: 'opacity 0.8s, transform 0.8s',
        }}
      >
        <h2 style={{ fontSize: 'clamp(2rem, 4vw, 3.2rem)', fontWeight: 900, color: 'white', letterSpacing: '-0.04em', marginBottom: 18, lineHeight: 1.1 }}>
          Ready to reduce<br />solder-paste defects?
        </h2>
        <p style={{ fontSize: 17, color: 'rgba(255,255,255,0.65)', marginBottom: 40, lineHeight: 1.65 }}>
          Join production teams using DARA to cut rework, close nonconformances faster, and stabilize every dispense.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={onStartScan}
            style={{ background: 'white', color: '#0B6873', border: 'none', borderRadius: 999, padding: '14px 32px', fontSize: 15, fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 4px 24px rgba(0,0,0,0.2)' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 32px rgba(0,0,0,0.25)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = ''; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 24px rgba(0,0,0,0.2)' }}
          >Start a line review</button>
          <button
            type="button"
            onClick={() => document.getElementById('inspection-flow')?.scrollIntoView({ behavior: 'smooth' })}
            style={{ background: 'rgba(255,255,255,0.12)', color: 'white', border: '1.5px solid rgba(255,255,255,0.3)', borderRadius: 999, padding: '14px 32px', fontSize: 15, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'all 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.2)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.12)' }}
          >Explore the workflow</button>
        </div>
      </div>
    </section>
  )
}

// ─── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{ background: 'white', borderTop: '1px solid rgba(79,70,229,0.08)', padding: '40px 48px' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 26, height: 26, borderRadius: 7, background: '#0B6873', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 9L4.5 4.5L7 7L9.5 3" stroke="white" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </div>
          <span style={{ fontWeight: 800, fontSize: 15, color: '#1F2033' }}>DARA</span>
          <span style={{ fontSize: 12, color: 'rgba(31,32,51,0.3)' }}>Dispensing Analysis &amp; Root-cause Assistant for PCB assembly</span>
        </div>
        <div style={{ display: 'flex', gap: 28 }}>
          {['Privacy', 'Terms', 'Security', 'Contact'].map(item => (
            <a key={item} href="#" style={{ fontSize: 12, color: 'rgba(31,32,51,0.4)', textDecoration: 'none', transition: 'color 0.2s' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D66A2C')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(31,32,51,0.4)')}
            >{item}</a>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'rgba(31,32,51,0.28)' }}>© 2026 DARA. All rights reserved.</p>
      </div>
    </footer>
  )
}

// ─── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [view, setView] = useState<AppView>('home')

  const navigate = (next: AppView) => {
    setView(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div style={{ fontFamily: "'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif" }}>
      <Nav view={view} onNavigate={navigate} forceSolid={view !== 'home'} />

      {view === 'home' && (
        <>
          <Hero onStartScan={() => navigate('scan')} />
          <LogoRow />

          <div id="inspection-flow">
            <FeatureSection
              eyebrow="Dashboard"
              heading={<>Every metric,<br />one command center</>}
              body="Real-time KPI tiles, trend sparklines, and configurable alerts give your team an instant picture of paste-deposition health across every line and shift."
              bullets={[
                'Sub-15-second refresh on paste volume and defect KPIs across every line',
                'Threshold-based alerts for bridging, skips, smears, and under-deposit',
                'Rolling run-history views with anomaly detection overlays',
              ]}
              imgSrc="https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&h=800&fit=crop&auto=format"
              imgAlt="Printed circuit board on a production line"
              bgColor="#F7F6FB"
              MockupComponent={MiniDashboard}
            />

            <FeatureSection
              eyebrow="Solder Paste Vision Scan"
              heading={<>Machine-vision<br />detection at every stage</>}
              body="DARA's vision engine inspects pad coverage, deposit volume, bridging, smearing, and placement alignment — flagging anomalies before boards reach rework."
              bullets={[
                'Sub-second detection latency on live production feeds',
                'Confidence scoring with explainable inspection overlays per flag',
                '98.7% accuracy across 14 solder-paste defect classes',
              ]}
              imgSrc="https://images.unsplash.com/photo-1563770660941-10a04f7d7f08?w=1200&h=800&fit=crop&auto=format"
              imgAlt="Electronics assembly line inspection"
              bgColor="white"
              flipped
              MockupComponent={MiniAIScan}
            />

            <FeatureSection
              eyebrow="Root Cause & Reports"
              heading={<>Audit-ready reports<br />generated in seconds</>}
              body="From line-side quality reviews to customer-ready investigations, DARA turns defect evidence into structured, signable reports with one click."
              bullets={[
                'PDF, XLSX, and CSV exports for quality and production reviews',
                '5-Why and fishbone root-cause visualizations built automatically',
                'Corrective-action ownership and sign-off in one workflow',
              ]}
              imgSrc="https://images.unsplash.com/photo-1579532582937-16c108930bf6?w=1200&h=800&fit=crop&auto=format"
              imgAlt="Quality report with manufacturing data"
              bgColor="#F7F6FB"
              MockupComponent={MiniReport}
            />

            <FeatureSection
              eyebrow="Runs & History"
              heading={<>Full case history —<br />search, filter, learn</>}
              body="Every dispense run, investigation, and corrective action lives in a searchable, timestamped ledger. Spot recurring patterns before they become line stoppages."
              bullets={[
                'Run-over-run defect volume with shift and line comparison',
                'Full-text search across defect evidence and notes',
                'Corrective-action linkage — every fix tied to its root cause',
              ]}
              imgSrc="https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=1200&h=800&fit=crop&auto=format"
              imgAlt="Engineer monitoring an electronics production line"
              bgColor="white"
              flipped
              MockupComponent={MiniHistory}
            />
          </div>

          <StatsBand />
          <CTA onStartScan={() => navigate('scan')} />
          <Footer />
        </>
      )}

      {view === 'scan' && <SolderPasteScan onBack={() => navigate('home')} />}

      {view === 'reports' && <ReportsView onBack={() => navigate('home')} />}

      {view === 'history' && <HistoryView onBack={() => navigate('home')} />}
    </div>
  )
}
