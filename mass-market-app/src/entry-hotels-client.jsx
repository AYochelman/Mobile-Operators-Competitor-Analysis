import { hydrateRoot } from 'react-dom/client'
import HotelsLandingPage from './pages/HotelsLandingPage'

/* Client hydration entry for the prerendered /hotels page.

   Vite builds this as a standalone module chunk (see vite.config.js
   build.rollupOptions.input → dist/assets/hotels-client-*.js). scripts/
   prerender-hotels.mjs injects a <script type="module"> pointing at the hashed
   output. It attaches React to the server-rendered #hotels-root markup, making
   the live demo, ROI calculator and lead form interactive WITHOUT re-painting
   (the static HTML already shows on first frame). */
hydrateRoot(document.getElementById('hotels-root'), <HotelsLandingPage />)
