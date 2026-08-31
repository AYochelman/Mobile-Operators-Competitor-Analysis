import { useRef } from 'react'
import bannersWall from '../assets/banners-wall.webp'

/* ─────────────────────────────────────────────────────────────
   LandingHeroShot — the hero "product screenshot" for the public
   landing page. A REAL capture of the MOCA banners wall (the live
   interface) that tilts toward the pointer with a moving sheen.
   The screenshot shows competitors' public marketing banners —
   no sensitive client data. Pure decoration.
   ───────────────────────────────────────────────────────────── */

const REST = 'rotateY(-13deg) rotateX(8deg)'
const MAX = 20 // deg — strengthened a touch per user; still legible

export default function LandingHeroShot({ alt = 'מערכת MOCA - קיר הבאנרים של המתחרים בזמן אמת' }) {
  const stageRef = useRef(null)
  const frameRef = useRef(null)

  function onMove(e) {
    const stage = stageRef.current, frame = frameRef.current
    if (!stage || !frame) return
    const r = stage.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width - 0.5
    const py = (e.clientY - r.top) / r.height - 0.5
    frame.style.transform = `rotateY(${px * 2 * MAX}deg) rotateX(${-py * 2 * MAX}deg)`
    frame.style.setProperty('--gx', (px * 70 + 50) + '%')
    frame.style.setProperty('--gy', (py * 70 + 50) + '%')
  }
  function onLeave() {
    if (frameRef.current) frameRef.current.style.transform = REST
  }

  return (
    <div className="lhs-stage" ref={stageRef} onPointerMove={onMove} onPointerLeave={onLeave}>
      <style>{CSS}</style>
      <div className="lhs-frame" ref={frameRef} style={{ transform: REST }}>
        <div className="lhs-shot">
          <img src={bannersWall} alt={alt}
               width="1100" height="957" loading="eager" decoding="async" />
          <div className="lhs-glare" />
        </div>
      </div>
    </div>
  )
}

const CSS = `
.lhs-stage{ perspective:1600px; display:inline-block; max-width:100%; }
.lhs-frame{ transform-style:preserve-3d; transition:transform .25s ease; will-change:transform; }
.lhs-shot{ position:relative; width:min(490px,86vw); border-radius:14px; overflow:hidden;
  border:1px solid rgba(255,255,255,.12);
  box-shadow:0 34px 64px -28px rgba(0,0,0,.62), 0 14px 26px -18px rgba(0,0,0,.5); }
.lhs-shot img{ display:block; width:100%; height:auto; aspect-ratio:1100/957; }
.lhs-glare{ position:absolute; inset:0; pointer-events:none; border-radius:14px;
  background:radial-gradient(440px 320px at var(--gx,32%) var(--gy,4%),rgba(255,255,255,.34),transparent 58%); }
`
