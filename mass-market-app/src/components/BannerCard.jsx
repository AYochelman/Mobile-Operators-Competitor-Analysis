// mass-market-app/src/components/BannerCard.jsx
import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, X } from 'lucide-react'

// Fallback gradient per carrier when screenshot isn't available yet
const CARRIER_GRADIENT = {
  partner:   'linear-gradient(135deg,#e8003d,#ff6b8a)',
  pelephone: 'linear-gradient(135deg,#ff6600,#ffaa44)',
  hotmobile: 'linear-gradient(135deg,#e3001e,#ff5555)',
  cellcom:   'linear-gradient(135deg,#003b7a,#0077cc)',
  mobile019: 'linear-gradient(135deg,#1a1a1a,#555)',
  xphone:    'linear-gradient(135deg,#6a0dad,#b44fec)',
  wecom:     'linear-gradient(135deg,#006633,#22bb66)',
  neptucom:  'linear-gradient(135deg,#004488,#2277cc)',
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('he-IL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function BannerCard({ banner }) {
  const { carrier, name, url, color, image_url, scraped_at } = banner
  const [modalOpen, setModalOpen] = useState(false)
  const [imgError, setImgError] = useState(false)

  // Close modal on Escape + lock body scroll
  useEffect(() => {
    if (!modalOpen) return
    document.body.style.overflow = 'hidden'
    const handler = (e) => { if (e.key === 'Escape') setModalOpen(false) }
    window.addEventListener('keydown', handler)
    return () => {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', handler)
    }
  }, [modalOpen])

  const hasImage = image_url && !imgError

  function renderMedia(className, style) {
    return hasImage ? (
      <img
        src={image_url}
        alt={`באנר ${name}`}
        className={className}
        style={{ objectFit: 'cover', ...style }}
        onError={() => setImgError(true)}
      />
    ) : (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{ background: CARRIER_GRADIENT[carrier] || '#ccc', ...style }}
      >
        <span className="text-white/80 text-lg font-bold">{name}</span>
      </div>
    )
  }

  return (
    <>
      {/* Card */}
      <div
        className="bg-white rounded-xl border border-moca-border/40 overflow-hidden cursor-pointer
                   transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:scale-[1.01]"
        onClick={() => setModalOpen(true)}
      >
        {renderMedia('w-full', { aspectRatio: '16/7' })}
        <div className="px-3 py-2 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
          <span className="text-sm font-bold text-[#3b1f0d] truncate">{name}</span>
          <span className="mr-auto text-[11px] text-moca-muted">{formatDate(scraped_at)}</span>
        </div>
      </div>

      {/* Modal */}
      {modalOpen && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setModalOpen(false) }}
          role="dialog"
          aria-modal="true"
          aria-label={`באנר ${name}`}
        >
          <div className="bg-white rounded-2xl overflow-hidden w-[90vw] max-w-4xl shadow-2xl relative">
            {renderMedia('w-full', { aspectRatio: '16/7' })}

            <button
              className="absolute top-3 left-3 w-8 h-8 rounded-full bg-black/50 text-white
                         flex items-center justify-center hover:bg-black/70 transition-colors"
              onClick={() => setModalOpen(false)}
            >
              <X size={15} />
            </button>

            <div className="px-5 py-4 flex items-center gap-3">
              <div>
                <div className="text-base font-bold text-[#3b1f0d]">{name}</div>
                <div className="text-xs text-moca-muted">עודכן: {formatDate(scraped_at)}</div>
              </div>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="mr-auto flex items-center gap-2 bg-[#5c3317] hover:bg-[#7a4422]
                           text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink size={14} />
                פתח באתר הספק
              </a>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  )
}
