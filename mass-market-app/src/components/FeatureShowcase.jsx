import featPlaceholder from '../assets/banners-wall.webp'
import { useLang } from '../hooks/useLanguage'

/* ─────────────────────────────────────────────────────────────
   FeatureShowcase — alternating "zigzag" feature rows for the
   landing page: text on one side, a real-UI screenshot on the
   other, sides alternating per row. Screenshots get a STATIC 3D
   tilt (no pointer motion) that "opens" toward the text; flattened
   on mobile. An optional `overlay` image floats in the screenshot's
   bottom-left corner, popped forward in 3D (used for the AI row:
   the chat panel over the heat-map). Items without `img` fall back
   to a placeholder so the layout can be previewed.
   ───────────────────────────────────────────────────────────── */

function FeatureRow({ ic, h, p, img, overlay, flip, w, h2, ow, oh }) {
  const { tt } = useLang()
  const src = img || featPlaceholder
  return (
    <div className={`flex flex-col gap-7 lg:gap-14 items-center ${flip ? 'lg:flex-row-reverse' : 'lg:flex-row'}`}>
      <div className="lg:w-[44%] text-start">
        <div className="w-12 h-12 rounded-[14px] grid place-items-center text-2xl bg-moca-cream mb-4"
             style={{ boxShadow: 'var(--sh-card)' }}>{ic}</div>
        <h3 className="font-display text-2xl md:text-[26px] text-moca-dark mb-2.5">{h}</h3>
        <p className="text-moca-sub text-[15px] md:text-base leading-relaxed max-w-[440px]">{p}</p>
      </div>
      <div className="lg:w-[56%] w-full fs-persp flex justify-center">
        <div className="fs-stack" data-tilt={flip ? 'r' : 'l'}>
          <div className="fs-shot">
            <img src={src} alt={h} loading="lazy" decoding="async" width={w} height={h2} />
            {!img && <span className="fs-ph">{tt('תמונה זמנית — כאן ייכנס צילום המסך שלך', 'Placeholder image — your screenshot goes here')}</span>}
          </div>
          {overlay && (
            <div className="fs-overlay">
              <img src={overlay} alt="" loading="lazy" decoding="async" width={ow} height={oh} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function FeatureShowcase({ items }) {
  return (
    <div className="mt-14 flex flex-col gap-16 lg:gap-24">
      <style>{CSS}</style>
      {items.map((f, i) => <FeatureRow key={f.h} {...f} flip={i % 2 === 1} />)}
    </div>
  )
}

const CSS = `
.fs-persp{ perspective:1500px; }
.fs-stack{ position:relative; display:inline-block; max-width:100%; transform-style:preserve-3d; }
.fs-stack[data-tilt="l"]{ transform:rotateY(-9deg) rotateX(5deg); }
.fs-stack[data-tilt="r"]{ transform:rotateY(9deg) rotateX(5deg); }

.fs-shot{ position:relative; border-radius:16px; overflow:hidden;
  border:1px solid var(--color-moca-border);
  box-shadow:0 2px 5px rgba(60,40,20,.07), 0 36px 64px -30px rgba(60,40,20,.5); }
.fs-shot img{ display:block; width:auto; height:auto; max-width:min(580px,86vw); max-height:440px; }

/* floating overlay card — bottom-left, popped forward in 3D */
.fs-overlay{ position:absolute; left:-22px; bottom:-26px; width:clamp(148px,46%,206px);
  transform:translateZ(55px); border-radius:13px; overflow:hidden;
  border:1px solid var(--color-moca-border);
  box-shadow:0 26px 46px -16px rgba(40,25,10,.55); }
.fs-overlay img{ display:block; width:100%; height:auto; }

.fs-ph{ position:absolute; inset:auto 0 0 0; text-align:center; font-size:12px; font-weight:700;
  color:#fff; background:rgba(92,51,23,.78); padding:6px 8px; }

@media (max-width:1023px){
  .fs-stack{ transform:none !important; }
  .fs-overlay{ transform:none; left:-12px; bottom:-16px; }
}
`
