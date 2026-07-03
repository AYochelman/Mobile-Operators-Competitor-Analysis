// TikTok Pixel for the public B2C eSIM page (/esim-deals).
//
// The pixel id comes from VITE_TIKTOK_PIXEL_ID. Find it in TikTok Ads Manager →
// Assets → Events → Web Events → (create/open your pixel) → "Pixel ID".
// Empty id = disabled: every function below is a safe no-op, so the page ships
// fine before the pixel exists. Set the id in .env.production + rebuild to turn
// it on. Pixel ids are NOT secret — they live in client JS by design.
//
// Wired into EsimComparePage: initTikTokPixel() fires PageView on mount (for the
// "Landing page view" optimization + a retargeting audience), and trackTikTok()
// fires a ClickButton event on every affiliate deal tap (the money event, so the
// campaign can later be optimized toward provider clicks).

const PIXEL_ID = import.meta.env.VITE_TIKTOK_PIXEL_ID || ''
let started = false

// Inject TikTok's official base snippet once, load the pixel, fire PageView.
export function initTikTokPixel() {
  if (started || !PIXEL_ID || typeof window === 'undefined') return
  started = true
  /* eslint-disable */
  !function (w, d, t) {
    w.TiktokAnalyticsObject = t
    var ttq = w[t] = w[t] || []
    ttq.methods = ['page', 'track', 'identify', 'instances', 'debug', 'on', 'off', 'once', 'ready', 'alias', 'group', 'enableCookie', 'disableCookie', 'holdConsent', 'revokeConsent', 'grantConsent']
    ttq.setAndDefer = function (t, e) { t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))) } }
    for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i])
    ttq.instance = function (t) { for (var e = ttq._i[t] || [], n = 0; n < ttq.methods.length; n++) ttq.setAndDefer(e, ttq.methods[n]); return e }
    ttq.load = function (e, n) {
      var r = 'https://analytics.tiktok.com/i18n/pixel/events.js', o = n && n.partner
      ttq._i = ttq._i || {}, ttq._i[e] = [], ttq._i[e]._u = r, ttq._t = ttq._t || {}, ttq._t[e] = +new Date, ttq._o = ttq._o || {}, ttq._o[e] = n || {}
      n = document.createElement('script'), n.type = 'text/javascript', n.async = !0, n.src = r + '?sdkid=' + e + '&lib=' + t
      var a = document.getElementsByTagName('script')[0]; a.parentNode.insertBefore(n, a)
    }
    ttq.load(PIXEL_ID)
    ttq.page()
  }(window, document, 'ttq')
  /* eslint-enable */
}

// Fire a standard TikTok event (e.g. 'ClickButton', 'ViewContent', 'Search').
// No-op until the pixel is configured and the base snippet has loaded.
export function trackTikTok(event, params) {
  if (!PIXEL_ID || typeof window === 'undefined' || !window.ttq || typeof window.ttq.track !== 'function') return
  try { window.ttq.track(event, params || {}) } catch { /* ignore */ }
}

// True when a pixel id is configured (useful for conditional UI / consent).
export const tiktokPixelEnabled = () => !!PIXEL_ID
