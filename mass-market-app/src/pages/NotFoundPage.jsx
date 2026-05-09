import { Link } from 'react-router-dom'
import Button from '../components/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-moca-bg px-4">
      <div className="text-center max-w-sm">
        <div
          aria-hidden="true"
          className="w-16 h-16 mx-auto mb-5 rounded-full bg-moca-cream border border-moca-border flex items-center justify-center"
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--color-moca-bolt)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        </div>
        <p className="text-[10px] text-moca-muted font-extrabold tracking-widest uppercase mb-2">404 · Not Found</p>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 800, color: 'var(--color-moca-dark)', letterSpacing: -0.5, margin: '0 0 8px' }}>
          העמוד לא נמצא
        </h1>
        <p className="text-sm text-moca-sub mb-6 leading-relaxed">
          הקישור שגוי או שהעמוד הוסר. אפשר לחזור לדשבורד ולנסות מהתחלה.
        </p>
        <Link to="/"><Button>חזרה לדשבורד</Button></Link>
      </div>
    </div>
  )
}
