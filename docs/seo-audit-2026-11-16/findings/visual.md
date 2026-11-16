# Visual audit - lucent-kulfi-f037ad.netlify.app (2026-11-16)
Screens: C:\Users\Alon\AppData\Local\Temp\claude\8d71af8ee6869051\354486a8-2e64-4940-8054-3a2fcbe420e1\scratchpad\moca-audit\screenshots\ (<page>-<desktop|mobile>.png final, -t0.png = ~0.7s). Metrics: ..\metrics.json

1. HIGH - /esim/ is not a hub: 301 -> /esim -> SPA login form (esimhub-mobile.png). Hub pages promised in CLAUDE.md are not served; the hub is an indexed-URL dead end, only a login form with the title H1 "login".
2. HIGH - /esim-deals mobile CLS 0.246 (poor, >0.25 is bad threshold edge; desktop 0.043). Popular-destination chips are absent at first paint (esimdeals-mobile-t0.png) and pop in later, pushing the "first time with eSIM" card down ~540px (esimdeals-mobile.png). Fix: reserve chip-block height (skeleton / min-height) or render chips in the prerender.
3. MEDIUM - /esim-deals shows no deals above the fold: hero + destination search + chips only; no price/plan content until a destination is chosen. Not a loading state, but the page's value (prices) is invisible to users and to the first-paint snapshot. Fix: show a "cheapest right now" strip or top deal cards above the steps.
4. MEDIUM - Tap targets under 44px on /esim-deals (mobile chips 38px high, language button 46x34, 14 of 15 visible targets undersized), /esim/thailand/ (breadcrumb links 17px high, "to interactive comparison" link 23px, MOCA 32x17), /hotels (EN 64x37, header CTA 37px high), home (EN 67x38, login 111x36). Fix: min-height 44-48px / padding on chips, breadcrumbs, EN toggle.
5. LOW - Home has an off-canvas decorative blob (DIV.absolute -right-32, right edge 503px at 375 vw) but scrollWidth == viewport (375/1440) so no horizontal scroll on any page. OK.
6. LOW - Home has two H1s (he + en both in DOM, en hidden); fine visually, but crawlers see duplicate H1. Home mobile: H1, value prop, stats and hero image visible; primary CTA is only the small header "כניסה למערכת" (111x36); no CTA in the hero body (home-mobile.png). Fix: add hero CTA (e.g. demo/contact).
7. OK - Interstitials: NO cookie banner, PWA install card, or any fixed/sticky overlay appeared on any of the 5 pages at mobile or desktop after ~5s (only sticky topbar 65px on /hotels = 8% of viewport). Banner/install card are not an intrusive-interstitial risk at first load (the install card is engagement-gated; not triggered in a fresh session, not tested after interaction).
8. OK - RTL: html dir=rtl lang=he everywhere; text, logo, chips, breadcrumbs, price/CTA alignment correct. Mixed-script (eSIM, MOCA, 102MB, 2026) renders correctly. Thailand hero line "154 חבילות מ-29 ספקים · החל מ-1.19 ₪ · עודכן 16 בנובמבר 2026" reads fine.
9. OK - Legibility: base text 13-17px on esim pages, 14px mobile body on home, 30-36px H1. Smallest text 10-11px (login footer, esim-deals meta) - borderline. 
10. Per page above-the-fold (mobile):
 - /: H1 present (36px), value prop, 4 stats, hero collage; CTA only in header.
 - /esim-deals: H1 "כמה תשלמו על אינטרנט בטיול הבא?", search box (primary CTA, 56px) visible; chips below; real content but no prices. Orphan "?" wraps to its own line in H1 (minor RTL punctuation wrap).
 - /hotels: H1, value prop, two big CTAs (צפו בהדגמה החיה 84px high, תיאום שיחת הכרות) visible; header CTA "פיילוט 60 יום חינם" wraps to 2 lines. Good.
 - /esim/: login form (see 1).
 - /esim/thailand/: hero image + H1 "eSIM לתאילנד - השוואת מחירים", price cards with "לרכישה" CTA (~100x43) visible above the fold; no layout shift (CLS 0). Best page.
Note: capture_screenshot.py was not used (custom viewports/metrics needed; the claude-seo runner only accepts bundled scripts) - plain Playwright/Chromium used, sandbox default.
