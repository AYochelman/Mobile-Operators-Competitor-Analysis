import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import LandingPage from './pages/LandingPage'

/* Build-time prerender entry — renders the public marketing landing page to a
   static HTML string (no hydration; the landing is purely presentational).
   Consumed by scripts/prerender-landing.mjs to emit dist/landing.html, which
   Netlify serves at "/" so the marketing page paints instantly (no SPA boot).

   `lang` ('he' | 'en') is passed as `forceLang` so each language renders a
   single, statically-correct direction. prerender-landing.mjs calls render()
   twice (he + en) and a vanilla script toggles between them on the live page. */
export function render(lang = 'he') {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={['/']}>
      <LandingPage forceLang={lang} />
    </MemoryRouter>
  )
}
