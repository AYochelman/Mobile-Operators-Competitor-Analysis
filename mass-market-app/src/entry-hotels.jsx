import { renderToString } from 'react-dom/server'
import HotelsLandingPage from './pages/HotelsLandingPage'

/* Build-time SSR entry for the hotels marketing page (route: /hotels).

   Unlike the main landing (entry-landing.jsx uses renderToStaticMarkup — that
   page is purely presentational), THIS page is interactive: the live demo
   iframe picker, the ROI calculator sliders and the lead form all need React.
   So it is rendered with renderToString (hydration-compatible) and re-hydrated
   on the client by entry-hotels-client.jsx.

   Consumed by scripts/prerender-hotels.mjs, which wraps this markup in a static
   <head> + the hydration <script> and writes dist/hotels.html (Netlify serves
   it at /hotels for instant paint).

   HotelsLandingPage's initial language is deterministically Hebrew, so this
   server markup matches the client's FIRST render — hydration is clean; the
   visitor's real language (?lang= / stored pref) is applied right after mount. */
export function render() {
  return renderToString(<HotelsLandingPage />)
}
