---
name: deploy-live
description: >-
  Build and deploy the MOCA frontend to Netlify (mocaintel.com) and VERIFY the
  deploy actually landed. Use after ANY React/JS/CSS change in mass-market-app,
  whenever the user says "תעלה לאוויר", "תפרוס", "deploy", "גרור ל-Netlify", asks
  why a change isn't showing on the live site, or when a session ends with a built
  dist that was never deployed. Claude can now deploy DIRECTLY via the authenticated
  Netlify CLI - never end a frontend task with "נשאר לך לגרור את dist" again.
---

# Deploy Live (Netlify, mocaintel.com)

Committed ≠ built ≠ live. Historically every frontend change ended with a manual
drag-deploy that was forgotten or done with a stale folder. Since 2026-07-09 the
Netlify CLI is installed, logged in as Alon, and the `mass-market-app/` folder is
linked to the production site - so deploy it yourself and verify, don't hand it off.

**Site**: `lucent-kulfi-f037ad` (id `39164e5d-2df9-4254-82e1-a1e9d825a240`) →
https://mocaintel.com (+ esim.mocaintel.com subdomain, served from the same deploy).

## 1. Build

```bash
cd "D:\השוואת MASS MARKET\mass-market-app" && npm run build
```

The chain (package.json) is: `vite build` → SSR + `prerender-landing.mjs`
(`dist/landing.html`) → SSR + `prerender-hotels.mjs` (`dist/hotels.html`) →
`prerender-esim.mjs` (`dist/esim.html`) → `stamp-sitemap.mjs`. So a change to
LandingPage/HotelsLandingPage/EsimComparePage head only ships via a full rebuild.

## 2. Pre-flight - make sure you're deploying the right thing

- `dist/index.html` mtime is from THIS build (the historical trap: deploying an old
  dist - always check the date).
- `dist/` contains: `_redirects`, `landing.html`, `hotels.html`, `esim.html`, `sw.js`.
- Record the deploy fingerprint - the hashed entry script in `dist/index.html`,
  e.g. `/assets/main-kvTQ4DFw.js`. Vite content-hashes filenames, so this hash is
  unique per build.

```bash
grep -o 'assets/main-[^"]*\.js' dist/index.html
```

## 3. Deploy

```bash
cd "D:\השוואת MASS MARKET\mass-market-app" && netlify deploy --prod --dir=dist
```

- If the folder isn't linked (fresh clone): `netlify link --id 39164e5d-2df9-4254-82e1-a1e9d825a240`.
- If auth expired: `netlify login` (opens Alon's browser to approve).
- CLI deploys also read `mass-market-app/netlify.toml` (headers/redirects), which is
  kept in sync with `public/_redirects`; the `_redirects` inside dist is the file the
  CDN serves. If you change routing, change BOTH.
- Fallback (CLI broken): tell the user to drag `mass-market-app/dist` (today's date!)
  at https://app.netlify.com/projects/lucent-kulfi-f037ad.

## 4. Verify - the deploy isn't done until proven live

```bash
curl -s https://mocaintel.com/home | grep -o 'assets/main-[^"]*\.js'
```

Must equal the fingerprint from step 2. (Fetch `/home` or any SPA route - `/` serves
the static landing.html, which has no main bundle.) Then spot-check what changed:

- Prerendered page changed → curl `/` / `/hotels` / `/esim-deals` and grep for the
  new copy.
- Affiliate button changed → confirm the new provider id appears in the live JS
  bundle, and `/go/<id>` still 302s (it proxies to api.mocaintel.com per `_redirects`).
- Backend sanity: `curl -s https://api.mocaintel.com/api/ping` (deploys don't touch
  Flask, but users report "the site" as one thing).

## 5. PWA cache caveat (when the user says "אני עדיין רואה את הישן")

The service worker (`registerType: 'autoUpdate'`) precaches all JS/CSS/HTML; an
already-open client keeps serving the old precache until the new `sw.js` activates
on the next load. API JSON is StaleWhileRevalidate (up to 12h); logos/icons
CacheFirst (7d). Remedies in order: reload twice, hard refresh (Ctrl+Shift+R),
DevTools → Application → unregister SW, or incognito. A mismatched fingerprint in
step 4 means the deploy didn't land; a matched fingerprint + stale browser means SW
cache - don't redeploy.

## Scope notes

- This skill covers the FRONTEND only. Backend code changes need the elevated Flask
  restart (`schtasks /end /tn CellularComparison` + `schtasks /run /tn CellularComparison`);
  config.json changes are live without restart (mtime-cached).
- Netlify env vars (VITE_*) are set in the dashboard and only matter for CI builds;
  local `npm run build` uses `.env.production` (VITE_DEV_AUTH must stay false).
- After deploying a change the user asked about, state the fingerprint match as the
  proof of delivery.
