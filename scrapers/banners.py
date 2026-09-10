"""Homepage / e-store / global-provider banner screenshots, popup dismissal, Google News RSS.

Extracted from scraper.py by scripts/split_monolith.py (2026-09).
Names defined in scraper.py are referenced as `core.<name>` (late-bound) so
monkeypatching `scraper.<name>` in tests keeps working; scraper.py re-exports
everything defined here.
"""
import scraper as core  # noqa: E402  (the monolith; imported at its bottom)
import os
from datetime import datetime, timezone
logger = core.logger


def scrape_carrier_news():
    """Fetch Google News RSS headlines for each domestic carrier.

    Uses the free Google News RSS endpoint (no API key required).
    Returns list of dicts: {carrier, headline, url, source, published_at}
    """
    import requests as _req
    import urllib.parse
    import xml.etree.ElementTree as ET

    CARRIER_KEYWORDS = {
        'partner':   '\u05e4\u05e8\u05d8\u05e0\u05e8 \u05e1\u05dc\u05d5\u05dc\u05e8',
        'pelephone': '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
        'hotmobile': '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'cellcom':   '\u05e1\u05dc\u05e7\u05d5\u05dd',
        'mobile019': '019 \u05e1\u05dc\u05d5\u05dc\u05e8',
        'xphone':    'XPhone \u05e1\u05dc\u05d5\u05dc\u05e8',
        'wecom':     'We-Com \u05e1\u05dc\u05d5\u05dc\u05e8',
        'neptucom':  'Neptucom \u05e1\u05dc\u05d5\u05dc\u05e8',
        'golan':     '\u05d2\u05d5\u05dc\u05df \u05d8\u05dc\u05e7\u05d5\u05dd',
        'rami_levy': '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u05e1\u05dc\u05d5\u05dc\u05e8',
        'breez': 'Breeze eSIM',
    }

    articles = []
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; MOCABot/1.0)'}

    for carrier, keyword in CARRIER_KEYWORDS.items():
        try:
            rss_url = (
                'https://news.google.com/rss/search'
                f'?q={urllib.parse.quote(keyword)}&hl=iw&gl=IL&ceid=IL:iw'
            )
            resp = _req.get(rss_url, headers=headers, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item'):
                title     = item.findtext('title') or ''
                link      = item.findtext('link') or ''
                pub       = item.findtext('pubDate') or ''
                source_el = item.find('source')
                source    = source_el.text if source_el is not None else ''
                # Normalize RFC 2822 pubDate → ISO 8601 for correct text sorting in SQLite
                if pub:
                    try:
                        from email.utils import parsedate_to_datetime as _p2d
                        pub = _p2d(pub).isoformat()
                    except Exception:
                        pass
                if title and link:
                    articles.append({
                        'carrier':      carrier,
                        'headline':     title,
                        'url':          link,
                        'source':       source,
                        'published_at': pub,
                    })
        except Exception as e:
            logger.error(f"scrape_carrier_news: {carrier} failed: {e}")

    logger.info(f"scrape_carrier_news: {len(articles)} articles fetched")
    return articles


# Text fragments that indicate a WAF / bot-challenge / error page rather than
# the real site. Used by _is_error_page() to skip saving useless screenshots
# (the previous good banner stays on disk).
_BANNER_ERROR_INDICATORS = (
    "confirm you are human",
    "http error 503",
    "http error 502",
    "http error 504",
    "service unavailable",
    "access denied",
    "request blocked",
    "you have been blocked",
    "the owner of this website",
    "cloudflare",
    "checking your browser",
    "are you a robot",
    "התחברות נכשלה",
)


def _is_error_page(page, *, min_body_chars: int = 300) -> tuple[bool, str]:
    """
    Detect if the current page is a WAF / bot-challenge / generic error page
    instead of the real carrier site. Returns (is_error, reason).
    """
    try:
        body = (page.evaluate("document.body.innerText") or "").strip()
    except Exception as e:
        return True, f"could not read body: {e}"
    if len(body) < min_body_chars:
        return True, f"body too short ({len(body)} chars)"
    body_lc = body.lower()
    for marker in _BANNER_ERROR_INDICATORS:
        if marker in body_lc:
            return True, f"matched indicator '{marker}'"
    return False, ""


# Minimum acceptable screenshot file size in bytes. Anything smaller is almost
# always a near-blank error/challenge page rather than a real banner.
_MIN_BANNER_FILE_BYTES = 50_000


# CSS selectors for common popup close buttons (cookie banners, promos, etc.)
_POPUP_CLOSE_SELECTORS = [
    # Generic close/dismiss buttons by aria-label
    "[aria-label='Close']", "[aria-label='close']",
    "[aria-label='סגור']", "[aria-label='Close dialog']",
    # Common class/id patterns
    ".modal-close", ".popup-close", ".close-btn", ".btn-close",
    "#close-button", "#popup-close", "#modal-close",
    # Cookie consent accept/close buttons
    ".cookie-accept", ".cookie-close", ".cc-dismiss", ".cc-btn",
    "#cookie-accept", "#cookieAccept", "#acceptCookies",
    "[data-dismiss='modal']", "[data-action='close']",
    # Israeli carrier-specific patterns
    ".dialog-close", ".lightbox-close", ".overlay-close",
    # Adoric marketing popups (Partner store)
    ".closeLightboxButton", ".adoric_element.closeLightboxButton",
]


# Marketing-popup containers to force-hide before a screenshot. These are vendor /
# site-specific wrappers that the click-to-close step can miss when a page stacks
# 2-3 popups (e.g. Partner's homepage shows a native #popup1 promo AND an Adoric
# lightbox; Partner's store stacks several Adoric smartboxes). Removing the wrappers
# is safe — they are dedicated overlay containers, not page content — and far more
# reliable than clicking, which can be intercepted by a full-page Adoric backdrop.
# We deliberately do NOT blind-click every generic close selector: on SPA stores a
# stray force-click can hit a router link and navigate to a blank/loading page.
_POPUP_HIDE_JS = r"""
() => {
  let n = 0;
  const sels = [
    'div[class*="__ADORIC__"]',   // Adoric marketing popups + their full-page backdrop
    '[id^="adoric_smartbox"]',    // individual Adoric smartbox lightboxes
    '#popup1',                    // Partner homepage native promo ("ALL IN +")
  ];
  for (const s of sels) {
    for (const el of document.querySelectorAll(s)) {
      el.style.setProperty('display', 'none', 'important');
      n++;
    }
  }
  // Popups commonly lock body scroll — restore it so the hero renders normally.
  document.documentElement.style.overflow = '';
  document.body.style.overflow = '';
  return n;
}
"""


def _dismiss_popups(page) -> None:
    """Try to close any popups or overlays before taking a screenshot."""
    # 1. Press Escape — closes most modal overlays
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        pass

    # 2. Click known close-button selectors (stop after first success)
    for selector in _POPUP_CLOSE_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=300):
                btn.click(timeout=500)
                page.wait_for_timeout(400)
                logger.info("Dismissed popup via selector: %s", selector)
                break
        except Exception:
            continue

    # 3. Safety net: force-hide any leftover marketing overlay (Adoric / Partner
    #    #popup1) that the single click missed. Guarantees a clean screenshot even
    #    when a page stacks multiple popups or a backdrop intercepts the close click.
    try:
        hidden = page.evaluate(_POPUP_HIDE_JS)
        if hidden:
            logger.info("Force-hid %d leftover popup container(s) before screenshot", hidden)
    except Exception:
        pass

    # 4. Final short wait to let any closing animation finish
    page.wait_for_timeout(500)


# International eSIM provider sites stack a GDPR cookie-consent banner (OneTrust /
# Cookiebot / Osano / CookieYes / Iubenda / Usercentrics / Quantcast …) AND often a
# marketing / newsletter modal — neither of which _dismiss_popups (tuned for Israeli
# carriers, clicks only ONE button on purpose) reliably clears. Accepting the cookie
# banner is the cleanest dismissal (it's what a real visitor does) and leaves the
# hero — the "main banner" — fully visible. Kept SEPARATE from _dismiss_popups so the
# domestic scrapers' careful single-click behavior is untouched.
_GLOBAL_POPUP_DISMISS_JS = r"""
() => {
  let clicked = 0, hidden = 0;

  // 1) Click well-known consent "accept all" / modal-close controls by id/class.
  const clickSels = [
    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    '.osano-cm-accept-all', '.osano-cm-accept',
    '.cky-btn-accept', '[data-cky-tag="accept-button"]',
    '.iubenda-cs-accept-btn',
    '#uc-btn-accept-banner', '[data-testid="uc-accept-all-button"]',
    '.cc-allow', '.cc-dismiss',
    '.cookie-accept', '#acceptCookies', '#cookie-accept', '#cookieAccept',
    '.termly-styles-buttonPrimary',
    '#hs-eu-confirmation-button',
    '.qc-cmp2-summary-buttons button[mode="primary"]',
    'button[aria-label="Accept all"]', 'button[aria-label="Accept"]',
    '[aria-label="Close"]', '[aria-label="close"]', '[aria-label="Dismiss"]',
    '.modal-close', '.popup-close', '.close-btn', '.btn-close', '[data-dismiss="modal"]',
  ];
  for (const s of clickSels) {
    document.querySelectorAll(s).forEach(el => {
      try { const r = el.getBoundingClientRect(); if (r.width && r.height) { el.click(); clicked++; } } catch (e) {}
    });
  }

  // 2) Click buttons/links by their TEXT (frameworks without stable ids). Kept
  //    consent-specific + short so we never hit a hero CTA (e.g. "Buy", "Continue").
  const wantText = ['accept all','accept cookies','accept','allow all','allow cookies',
    'i agree','agree','got it','אני מסכים','מאשר','אישור','קבל','סגור'];
  document.querySelectorAll('button, a, [role="button"]').forEach(el => {
    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
    if (!t || t.length > 20) return;
    if (wantText.includes(t)) { try { el.click(); clicked++; } catch (e) {} }
  });

  // 3) Force-hide known consent-SDK / overlay containers that survive clicking,
  //    plus the Israeli Adoric marketing wrappers (some .co.il global providers).
  const hideSels = [
    '#onetrust-consent-sdk', '#onetrust-banner-sdk',
    '#CybotCookiebotDialog', '.CybotCookiebotDialog', '#CybotCookiebotDialogBodyUnderlay',
    '.osano-cm-window', '.osano-cm-dialog',
    '.cky-consent-container', '.cky-overlay', '.cky-modal',
    '.iubenda-cs-container', '#iubenda-cs-banner',
    '#usercentrics-root', '#uc-center-container', '#usercentrics-cmp-ui',
    '[id*="usercentrics"]', 'usercentrics-root', 'usercentrics-cmp-ui',
    '#axeptio_overlay', '.axeptio_mount', '[class*="axeptio"]', '#axeptio_main_button',
    '.termly-consent-banner', '#hs-eu-cookie-confirmation',
    '.qc-cmp2-container', '#qc-cmp2-container',
    '.cc-window', '#gdpr-cookie-message', '#gdpr-cookie-notice',
    '[class*="cookie-consent"]', '[id*="cookie-consent"]', '[class*="CookieConsent"]',
    'div[class*="__ADORIC__"]', '[id^="adoric_smartbox"]',
  ];
  for (const s of hideSels) {
    document.querySelectorAll(s).forEach(el => { el.style.setProperty('display','none','important'); hidden++; });
  }

  // 4) Hide common backdrop/overlay wrappers by class so the dimming layer behind a
  //    modal doesn't leave the screenshot darkened. NB: match SPECIFIC backdrop
  //    classes — a bare [class*="backdrop"] wrongly hits Tailwind's `backdrop-blur`
  //    utility (used on sticky headers), which nuked real nav bars.
  const overlaySels = ['.modal-backdrop', '.modal-overlay', '[class*="modal-backdrop"]',
    '[class*="ModalBackdrop"]', '.cdk-overlay-backdrop', '.MuiBackdrop-root',
    '.ReactModal__Overlay', '.fancybox-container', '.fancybox__backdrop',
    '[class*="overlay"][class*="open"]', '[class*="Overlay"][class*="open"]'];
  for (const s of overlaySels) {
    document.querySelectorAll(s).forEach(el => { el.style.setProperty('display','none','important'); hidden++; });
  }

  // 5) General overlay/modal killer: any fixed/sticky element with a high z-index
  //    that either covers most of the viewport (backdrop / full-screen modal) or sits
  //    as a large centered box (cookie / language / newsletter dialog). Hero content
  //    is never position:fixed, and sticky top nav / slim footers are excluded, so
  //    this removes the popup without touching the banner.
  const vw = innerWidth, vh = innerHeight;
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') return;
    if ((parseInt(cs.zIndex, 10) || 0) < 100) return;
    const r = el.getBoundingClientRect();
    if (r.width < 60 || r.height < 60) return;
    if (r.top <= 2 && r.height <= vh * 0.2) return;            // sticky top nav — keep
    if (r.bottom >= vh - 2 && r.height <= vh * 0.15) return;   // slim sticky footer — keep
    const coversMost  = r.width >= vw * 0.85 && r.height >= vh * 0.85;
    const centeredBox = r.width >= vw * 0.3 && r.height >= vh * 0.25 &&
                        r.top > vh * 0.02 && r.top < vh * 0.6;
    const cls = ((el.className && el.className.toString ? el.className.toString() : '') + ' ' + (el.id || '')).toLowerCase();
    const looksOverlay = /(overlay|backdrop|modal|popup|lightbox|dialog|drawer|cookie|consent|lang|newsletter|subscribe)/.test(cls)
      || /rgba\(0,\s*0,\s*0/.test(cs.backgroundColor)
      || !!el.querySelector('[role="dialog"], [class*="modal"], [class*="popup"], [class*="lightbox"]');
    if ((coversMost && looksOverlay) || centeredBox) {
      el.style.setProperty('display','none','important'); hidden++;
    }
  });

  // 5b) Shadow-DOM consent (Usercentrics v2 et al. render the banner inside a
  //     custom-element shadow root, so the light-DOM button/text passes miss it).
  document.querySelectorAll('*').forEach(el => {
    const sr = el.shadowRoot;
    if (!sr) return;
    sr.querySelectorAll('button, [role="button"]').forEach(b => {
      const t = (b.innerText || b.textContent || '').trim().toLowerCase();
      if (b.getAttribute && b.getAttribute('data-testid') === 'uc-accept-all-button') { try { b.click(); clicked++; } catch (e) {} return; }
      if (['accept all','accept cookies','accept','allow all','agree','i agree','ok','got it','אני מסכים','מאשר','אישור','קבל'].includes(t)) {
        try { b.click(); clicked++; } catch (e) {}
      }
    });
    const hostId = ((el.id || '') + ' ' + (el.tagName || '')).toLowerCase();
    if (/usercentrics|consent|cookie|cmp|gdpr/.test(hostId)) { el.style.setProperty('display','none','important'); hidden++; }
  });

  // 6) Consent-text pass: cookie banners are often bottom-anchored (top > 60%, so
  //    the geometry rules above miss them). Hide any fixed/sticky/absolute strip whose
  //    text (or class/id) is clearly a cookie/consent notice — EN or HE (Israeli
  //    providers like GlobalSIM show a Hebrew "שימוש ב-Cookies … מדיניות הפרטיות" bar).
  //    The nav/header guard means a sticky menu that merely links to a cookie policy
  //    is never nuked.
  document.querySelectorAll('div,section,aside,footer').forEach(el => {
    if (el.tagName === 'HEADER' || el.querySelector('nav, header')) return;
    const cs = getComputedStyle(el);
    if (!['fixed','sticky','absolute'].includes(cs.position)) return;
    const r = el.getBoundingClientRect();
    if (r.height > vh * 0.7 || r.width < vw * 0.3 || r.width < 200) return;  // strip, not whole page
    const low = (el.innerText || '').slice(0, 600).toLowerCase();
    const clsid = ((el.className && el.className.toString ? el.className.toString() : '') + ' ' + (el.id || '')).toLowerCase();
    const cookieTok = low.includes('cookie') || low.includes('עוגיות') || low.includes('קוקיז')
      || /(cookie|consent|gdpr)/.test(clsid);
    const consentWord = /(accept|consent|agree|continue|got it|confirm|understood|\bok\b|manage|policy|settings|allow|preferences)/.test(low)
      || /(מדיניות|פרטיות|מסכים|אישור|לאשר|הסכמה|שימוש ב)/.test(low);
    const isConsent = low.includes('we use cookies') || low.includes('uses cookies') ||
      low.includes('gdpr') || (cookieTok && consentWord);
    if (isConsent) { el.style.setProperty('display','none','important'); hidden++; }
  });

  // 7) Restore scroll that popups commonly lock so the hero renders normally.
  document.documentElement.style.overflow = '';
  document.body.style.overflow = '';
  document.body.style.position = '';
  return { clicked, hidden };
}
"""


def _dismiss_global_popups(page) -> None:
    """Aggressively clear cookie-consent + marketing popups on international
    provider sites so the screenshot shows only the hero banner."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        pass
    # Two main-document passes — a 2nd modal often appears only after the consent
    # banner is accepted/closed.
    for _ in range(2):
        try:
            res = page.evaluate(_GLOBAL_POPUP_DISMISS_JS)
            if res and (res.get("clicked") or res.get("hidden")):
                logger.info("Global popup dismiss: clicked=%s hidden=%s",
                            res.get("clicked"), res.get("hidden"))
        except Exception:
            pass
        page.wait_for_timeout(500)
    # Iframe-based consent (Quantcast / TrustArc / some Cookiebot render in an iframe).
    for fr in page.frames:
        for sel in ("#onetrust-accept-btn-handler",
                    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                    "button[aria-label='Accept all']",
                    ".qc-cmp2-summary-buttons button[mode='primary']"):
            try:
                loc = fr.locator(sel).first
                if loc.is_visible(timeout=200):
                    loc.click(timeout=500)
                    page.wait_for_timeout(300)
            except Exception:
                continue
    # Final late pass — some banners (Axeptio, a few Hebrew bars) inject a second or
    # two after load, after the passes above already ran.
    page.wait_for_timeout(1300)
    try:
        page.evaluate(_GLOBAL_POPUP_DISMISS_JS)
    except Exception:
        pass
    page.wait_for_timeout(400)


# Persistent consent-hider — installed as an init script so it runs on every page
# load and keeps HIDING (not clicking) known consent containers + fixed cookie-text
# strips on a 500ms interval for ~15s. Timing-independent: a banner injected 8-12s
# after load (e.g. TravelSim's Hebrew bar, which isn't in the DOM even at 9s) is
# removed within half a second of appearing, regardless of when the one-shot
# dismissal passes ran. Only hides consent-shaped elements, never navs/heroes.
_PERSISTENT_CONSENT_HIDER_JS = r"""
(() => {
  const SELS = [
    '#onetrust-consent-sdk','#onetrust-banner-sdk','#CybotCookiebotDialog','.CybotCookiebotDialog',
    '#CybotCookiebotDialogBodyUnderlay','.osano-cm-window','.osano-cm-dialog','.cky-consent-container',
    '.cky-overlay','.cky-modal','.iubenda-cs-container','#iubenda-cs-banner','#usercentrics-root',
    '#usercentrics-cmp-ui','[id*="usercentrics"]','usercentrics-root','usercentrics-cmp-ui',
    '#axeptio_overlay','.axeptio_mount','[class*="axeptio"]','#axeptio_main_button','.termly-consent-banner',
    '#hs-eu-cookie-confirmation','.qc-cmp2-container','#qc-cmp2-container','.cc-window','#gdpr-cookie-message',
    '#gdpr-cookie-notice','[class*="cookie-consent"]','[id*="cookie-consent"]','[class*="CookieConsent"]',
    'div[class*="__ADORIC__"]','[id^="adoric_smartbox"]'
  ];
  const hide = () => {
    for (const s of SELS) { try { document.querySelectorAll(s).forEach(el => el.style.setProperty('display','none','important')); } catch (e) {} }
    if (!document.body) return;
    const vw = innerWidth, vh = innerHeight;
    document.querySelectorAll('div,section,aside,footer').forEach(el => {
      if (el.tagName === 'HEADER' || el.querySelector('nav, header')) return;
      const cs = getComputedStyle(el);
      if (!['fixed','sticky','absolute'].includes(cs.position)) return;
      const r = el.getBoundingClientRect();
      if (r.height > vh * 0.7 || r.width < vw * 0.3 || r.width < 200) return;
      const low = (el.innerText || '').slice(0, 600).toLowerCase();
      const clsid = ((el.className && el.className.toString ? el.className.toString() : '') + ' ' + (el.id || '')).toLowerCase();
      const cookieTok = low.includes('cookie') || low.includes('עוגיות') || low.includes('קוקיז') || /(cookie|consent|gdpr)/.test(clsid);
      const consentWord = /(accept|consent|agree|continue|got it|confirm|understood|\bok\b|manage|policy|settings|allow|preferences)/.test(low)
        || /(מדיניות|פרטיות|מסכים|אישור|לאשר|הסכמה|שימוש ב)/.test(low);
      if (low.includes('we use cookies') || low.includes('uses cookies') || low.includes('gdpr') || (cookieTok && consentWord)) {
        el.style.setProperty('display','none','important');
      }
    });
    document.documentElement.style.overflow = ''; document.body.style.overflow = '';
  };
  let n = 0;
  const iv = setInterval(() => { try { hide(); } catch (e) {} if (++n > 30) clearInterval(iv); }, 500);
  try { hide(); } catch (e) {}
})();
"""


CARRIER_HOMEPAGE_URLS = {
    "partner":   "https://www.partner.net.il",
    "pelephone": "https://www.pelephone.co.il",
    "hotmobile": "https://www.hotmobile.co.il",
    "cellcom":   "https://www.cellcom.co.il",
    "mobile019": "https://www.019mobile.co.il",
    "xphone":    "https://www.xphone.co.il",
    "wecom":     "https://we-com.co.il",
    "neptucom":  "https://www.neptucom.com",
    "golan":     "https://www.golantelecom.co.il",
    "rami_levy": "https://mobile.rami-levy.co.il",
}


_STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _banner_019_stealth(url: str, out_path: str, scraped_at: str) -> dict:
    """
    Take a banner screenshot of 019mobile using playwright-stealth to bypass
    Imperva/Incapsula WAF.  Returns the same result dict as the main loop.
    """
    try:
        from playwright_stealth import Stealth
        with Stealth().use_sync(core.sync_playwright()) as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.set_viewport_size({"width": 1280, "height": 720})
                page.goto(url, timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                # If page is too small it's still a challenge page — bail out
                if len(page.content()) < 8000:
                    logger.warning("_banner_019_stealth: WAF challenge still active, skipping screenshot.")
                    return {"carrier": "mobile019", "scraped_at": scraped_at, "success": False}
                _dismiss_popups(page)
                page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                file_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
                if file_size < 5000:
                    logger.warning("_banner_019_stealth: screenshot too small (%d bytes), removing.", file_size)
                    os.remove(out_path)
                    return {"carrier": "mobile019", "scraped_at": scraped_at, "success": False}
                logger.info("Banner screenshot saved (stealth): %s", out_path)
                return {"carrier": "mobile019", "scraped_at": scraped_at, "success": True}
            finally:
                browser.close()
    except Exception as exc:
        logger.warning("_banner_019_stealth failed: %s", exc)
        return {"carrier": "mobile019", "scraped_at": scraped_at, "success": False}


def _banner_xphone_stealth(url: str, out_path: str, scraped_at: str) -> dict:
    """
    Take a banner screenshot of XPhone using a fresh session + Chrome 124 UA to bypass
    AWS WAF (same workaround used by scrape_xphone for plan data).
    """
    try:
        from playwright.sync_api import sync_playwright as _sp
        with _sp() as pw:
            # AWS WAF serves a JS challenge that headless Chromium fails.
            # headed=False fails (202 + empty body); headed=True passes the challenge.
            browser = pw.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=core._XPHONE_UA,
                viewport={"width": 1280, "height": 720},
                locale="he-IL",
                extra_http_headers={
                    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            page = context.new_page()
            try:
                try:
                    resp = page.goto(url, timeout=40000, wait_until="domcontentloaded")
                except Exception:
                    resp = None
                page.wait_for_timeout(12000)  # extra time for JS challenge to complete
                body = page.evaluate("document.body.innerText") or ""
                if len(body) < 300 or "confirm you are human" in body.lower() or "http error 503" in body.lower():
                    logger.warning("_banner_xphone_stealth: site unavailable or WAF block (body=%d chars), skipping.", len(body))
                    return {"carrier": "xphone", "scraped_at": scraped_at, "success": False}
                _dismiss_popups(page)
                page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                import os as _os
                file_size = _os.path.getsize(out_path) if _os.path.exists(out_path) else 0
                if file_size < 5000:
                    logger.warning("_banner_xphone_stealth: screenshot too small (%d bytes), likely blank.", file_size)
                    _os.remove(out_path)  # remove bad file so previous good screenshot stays on disk
                    return {"carrier": "xphone", "scraped_at": scraped_at, "success": False}
                logger.info("Banner screenshot saved (xphone stealth): %s (%d bytes)", out_path, file_size)
                return {"carrier": "xphone", "scraped_at": scraped_at, "success": True}
            finally:
                browser.close()
    except Exception as exc:
        logger.warning("_banner_xphone_stealth failed: %s", exc)
        return {"carrier": "xphone", "scraped_at": scraped_at, "success": False}


def scrape_carrier_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each domestic carrier homepage and save a 1280x720 PNG screenshot.
    Returns a list of dicts: { carrier, scraped_at, success }.
    output_dir — absolute path to the folder where PNGs will be saved.
    """
    core._ensure_event_loop()
    results = []
    os.makedirs(output_dir, exist_ok=True)

    # Phase 1: WAF-protected carriers — each stealth helper opens its own
    # sync_playwright() session, so they MUST run outside the shared session
    # below (Playwright forbids nested sync contexts in the same thread).
    stealth_carriers = {
        "mobile019": _banner_019_stealth,
        "xphone":    _banner_xphone_stealth,
    }
    for carrier, fn in stealth_carriers.items():
        if carrier not in CARRIER_HOMEPAGE_URLS:
            continue
        out_path = os.path.join(output_dir, f"{carrier}.png")
        scraped_at = datetime.now(timezone.utc).isoformat()
        results.append(fn(CARRIER_HOMEPAGE_URLS[carrier], out_path, scraped_at))

    # Phase 2: regular carriers — share a single Playwright session.
    with core.sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,  # some carriers have cert mismatches
            )

            for carrier, url in CARRIER_HOMEPAGE_URLS.items():
                if carrier in stealth_carriers:
                    continue  # handled in Phase 1
                out_path = os.path.join(output_dir, f"{carrier}.png")
                scraped_at = datetime.now(timezone.utc).isoformat()
                page = context.new_page()  # fresh page per carrier — avoids cross-navigation pollution
                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)  # let hero images render
                    _dismiss_popups(page)
                    page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                    results.append({"carrier": carrier, "scraped_at": scraped_at, "success": True})
                    logger.info("Banner screenshot saved: %s", out_path)
                except Exception as exc:
                    logger.warning("Banner screenshot failed for %s: %s", carrier, exc)
                    results.append({"carrier": carrier, "scraped_at": scraped_at, "success": False})
                finally:
                    page.close()
        finally:
            browser.close()

    return results


CARRIER_STORE_URLS = {
    "pelephone": "https://www.pelephone.co.il/ds/heb/eshop/lobby/",
    "cellcom":   "https://shop.cellcom.co.il/",
    "partner":   "https://store.partner.co.il/home",
    "hotmobile": "https://hotstore.hotmobile.co.il/smartphones.html",
}


def scrape_carrier_store_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each carrier e-store page and save a 1280x720 PNG screenshot.
    Files are saved as {carrier}_store.png in output_dir.
    Returns a list of dicts: { carrier, scraped_at, success }.
    """
    core._ensure_event_loop()
    results = []
    os.makedirs(output_dir, exist_ok=True)

    with core.sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )

            for carrier, url in CARRIER_STORE_URLS.items():
                out_path = os.path.join(output_dir, f"{carrier}_store.png")
                scraped_at = datetime.now(timezone.utc).isoformat()
                # Try up to 2 times — WAF 503 / bot-challenge pages are often
                # transient on retry with a fresh page/context.
                success = False
                last_reason = ""
                for attempt in (1, 2):
                    page = context.new_page()
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        # Store pages load marketing popups with a delay — wait longer than homepage scraper
                        page.wait_for_timeout(4000)
                        is_err, reason = _is_error_page(page)
                        if is_err:
                            last_reason = f"attempt {attempt}: {reason}"
                            logger.warning("Store banner %s: skipping bad page (%s)", carrier, last_reason)
                            if attempt == 1:
                                page.wait_for_timeout(3000)  # brief backoff before retry
                            continue
                        _dismiss_popups(page)
                        tmp_path = out_path + ".new.png"
                        page.screenshot(path=tmp_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                        file_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                        if file_size < _MIN_BANNER_FILE_BYTES:
                            last_reason = f"attempt {attempt}: screenshot too small ({file_size} bytes)"
                            logger.warning("Store banner %s: %s", carrier, last_reason)
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                            continue
                        # Valid — atomically replace the existing banner.
                        os.replace(tmp_path, out_path)
                        success = True
                        logger.info("Store banner screenshot saved: %s (%d bytes)", out_path, file_size)
                        break
                    except Exception as exc:
                        last_reason = f"attempt {attempt}: {exc}"
                        logger.warning("Store banner attempt %d failed for %s: %s", attempt, carrier, exc)
                    finally:
                        page.close()
                if not success:
                    logger.warning("Store banner FAILED for %s after retries; previous banner preserved (%s)",
                                   carrier, last_reason)
                results.append({"carrier": carrier, "scraped_at": scraped_at, "success": success})
        finally:
            browser.close()

    return results


# Screenshot the MAIN (homepage) banner of every global eSIM provider once per
# capture, exactly like the domestic carrier banners. Files are saved as
# {provider}_global.png in the same data/banners/ folder. URLs are the provider's
# clean homepage root (the "main banner"), NOT an Israel deep-link — mirror of
# app.py's GLOBAL_PROVIDERS_REGISTRY / _GUEST_PROVIDER_META ids.
GLOBAL_BANNER_URLS = {
    "seven_g":          "https://7g.app",
    "world8":           "https://world8.co.il",
    "airalo":           "https://www.airalo.com",
    "bcengi":           "https://www.bcengi.com",
    "besim":            "https://besim.co.il",
    "bestconnect":      "https://bestconnect.online",
    "bnesim":           "https://www.bnesim.com",
    "breez":            "https://breezesim.com",
    "bytesim":          "https://bytesim.com",
    "esimplus":         "https://esimplus.me",
    "esimio":           "https://esim.io",
    "esim70":           "https://esim70.com",
    "esimgenius":       "https://esimgenius.ai",
    "esimax":           "https://esimax.io",
    "esimo":            "https://esimo.io",
    "terminalesim":     "https://terminalesim.com",
    "gigsky":           "https://www.gigsky.com",
    "pelephone_global": "https://www.pelephone.co.il/digitalsite/heb/abroad/global-sim/",
    "gomoworld":        "https://www.gomoworld.com",
    "holafly":          "https://esim.holafly.com",
    "jetpack":          "https://www.jetpacglobal.com",
    "maya":             "https://maya.net",
    "nisim":            "https://www.nisim-esim.co.il",
    "orbit":            "https://orbitmobile.com",
    "saily":            "https://saily.com",
    "simtlv":           "https://simtlv.co.il",
    "sparks":           "https://www.sparks.travel",
    "tasim":            "https://tasim.us",
    "travelsim":        "https://travelsimobile.co.il",
    "tuki":             "https://tuki-esim.co.il",
    "venterrasim":      "https://venterrasim.com",
    "simzol":           "https://www.simzol.co.il",
    "voye":             "https://voyeglobal.com",
    "xphone_global":    "https://www.xphone.co.il",
    "yesim":            "https://yesim.app",
    "nomad":            "https://www.nomadesim.com",
    "ubigi":            "https://www.ubigi.com",
    "alosim":           "https://alosim.com",
}


# "Banner changed" (freshness) tracking. We store a small perceptual average-hash
# (aHash) per provider in a JSON sidecar; when a fresh capture's aHash drifts past a
# threshold from the stored one, the provider changed its homepage campaign and we
# stamp changed_at=now. A perceptual hash (not sha256) is used so minor rendering
# noise — antialiasing, a blinking cursor — doesn't trigger a false "changed".
_GLOBAL_BANNER_STATE_FILE = "_global_banner_state.json"


_BANNER_CHANGE_THRESHOLD = 18   # aHash bits (out of 256) that must differ = a real change


def _banner_ahash(path: str):
    """16x16 grayscale average-hash → 256-char bit string (None on failure)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("L").resize((16, 16))
        px = list(img.getdata())
        avg = sum(px) / len(px)
        return "".join("1" if p >= avg else "0" for p in px)
    except Exception as exc:
        logger.warning("aHash failed for %s: %s", path, exc)
        return None


def _ahash_distance(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 999
    return sum(1 for x, y in zip(a, b) if x != y)


def _load_global_banner_state(output_dir: str) -> dict:
    import json
    try:
        with open(os.path.join(output_dir, _GLOBAL_BANNER_STATE_FILE), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_global_banner_state(output_dir: str, state: dict) -> None:
    import json
    try:
        with open(os.path.join(output_dir, _GLOBAL_BANNER_STATE_FILE), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as exc:
        logger.warning("Could not write global banner state: %s", exc)


def scrape_global_provider_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each global eSIM provider's homepage and save a 1280x720 PNG.
    Files are saved as {provider}_global.png in output_dir.
    Returns a list of dicts: { carrier, scraped_at, success }.

    Mirrors scrape_carrier_store_banners: 2 attempts, error-page detection,
    min-size guard, atomic replace — so a failed capture preserves the previous
    good screenshot instead of overwriting it with a blank/consent page. On each
    successful capture it also updates the perceptual-hash state so the API can
    flag which banners changed their campaign (freshness badge).
    """
    core._ensure_event_loop()
    results = []
    os.makedirs(output_dir, exist_ok=True)
    state = _load_global_banner_state(output_dir)

    with core.sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )
            # Persistent hider catches late-injected consent banners regardless of
            # the one-shot dismissal timing.
            context.add_init_script(_PERSISTENT_CONSENT_HIDER_JS)

            for provider, url in GLOBAL_BANNER_URLS.items():
                out_path = os.path.join(output_dir, f"{provider}_global.png")
                scraped_at = datetime.now(timezone.utc).isoformat()
                success = False
                last_reason = ""
                for attempt in (1, 2):
                    page = context.new_page()
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        # Global SPA sites render hero + consent banners with a delay.
                        page.wait_for_timeout(4000)
                        is_err, reason = _is_error_page(page)
                        if is_err:
                            last_reason = f"attempt {attempt}: {reason}"
                            logger.warning("Global banner %s: skipping bad page (%s)", provider, last_reason)
                            if attempt == 1:
                                page.wait_for_timeout(3000)
                            continue
                        # International cookie-consent + marketing popups need the
                        # aggressive dismissal, not the Israeli-tuned _dismiss_popups.
                        _dismiss_global_popups(page)
                        tmp_path = out_path + ".new.png"
                        page.screenshot(path=tmp_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                        file_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                        if file_size < _MIN_BANNER_FILE_BYTES:
                            last_reason = f"attempt {attempt}: screenshot too small ({file_size} bytes)"
                            logger.warning("Global banner %s: %s", provider, last_reason)
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                            continue
                        os.replace(tmp_path, out_path)
                        success = True
                        logger.info("Global banner screenshot saved: %s (%d bytes)", out_path, file_size)
                        # ── Freshness tracking: mark changed_at when the campaign drifts.
                        new_h = _banner_ahash(out_path)
                        prev = state.get(provider) or {}
                        prev_h = prev.get("hash")
                        if not prev_h or new_h is None:
                            # First-ever baseline (or hash failure) — record, don't flag.
                            changed_at = prev.get("changed_at")
                        elif _ahash_distance(new_h, prev_h) > _BANNER_CHANGE_THRESHOLD:
                            changed_at = datetime.now(timezone.utc).isoformat()
                            logger.info("Global banner CHANGED: %s", provider)
                        else:
                            changed_at = prev.get("changed_at")
                        state[provider] = {"hash": new_h or prev_h, "changed_at": changed_at}
                        break
                    except Exception as exc:
                        last_reason = f"attempt {attempt}: {exc}"
                        logger.warning("Global banner attempt %d failed for %s: %s", attempt, provider, exc)
                    finally:
                        page.close()
                if not success:
                    logger.warning("Global banner FAILED for %s after retries; previous banner preserved (%s)",
                                   provider, last_reason)
                results.append({"carrier": provider, "scraped_at": scraped_at, "success": success})
        finally:
            browser.close()

    _save_global_banner_state(output_dir, state)
    return results
