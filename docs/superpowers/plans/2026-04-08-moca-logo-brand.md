# MOCA Logo & Brand Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the purple lightning bolt favicon and plain-text Navbar with a branded MOCA identity in mocha-latte tones, and ship a complete PWA icon set.

**Architecture:** New `Logo.jsx` component encapsulates the bolt + wordmark. `favicon.svg` gets color-only replacement (same shape). Three PNG icons (180/192/512) are generated via `canvas-design` skill and placed in `public/icons/`. `manifest.json` and `index.html` are updated to wire everything together.

**Tech Stack:** React, SVG, Vite, PWA manifest, `anthropic-skills:canvas-design` for PNG generation

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `mass-market-app/public/favicon.svg` | Mocha-latte color swap |
| Create | `mass-market-app/src/components/Logo.jsx` | Reusable bolt + wordmark |
| Modify | `mass-market-app/src/components/Navbar.jsx` | Use `<Logo size="md" />` |
| Create | `mass-market-app/public/icons/icon-192.png` | PWA icon 192×192 |
| Create | `mass-market-app/public/icons/icon-512.png` | PWA icon 512×512 |
| Create | `mass-market-app/public/icons/icon-180.png` | Apple Touch Icon |
| Modify | `mass-market-app/public/manifest.json` | Name + icon paths |
| Modify | `mass-market-app/index.html` | favicon + apple-touch-icon links |

---

## Task 1: Generate PNG icons via canvas-design

**Files:**
- Create: `mass-market-app/public/icons/icon-192.png`
- Create: `mass-market-app/public/icons/icon-512.png`
- Create: `mass-market-app/public/icons/icon-180.png`

- [ ] **Step 1: Create icons directory**

```bash
mkdir -p "mass-market-app/public/icons"
```

- [ ] **Step 2: Invoke canvas-design skill**

Use `anthropic-skills:canvas-design` with the following brief for each icon:

**Brief (same design, three sizes):**
> Square canvas with rounded corners (border-radius 22% of canvas size).
> Background: linear gradient top-left `#f5ede0` to bottom-right `#e8d5bc`.
> Centered lightning bolt SVG path (viewBox 0 0 48 46), fill `#5c3317`, scaled to 60% of canvas width.
> Lightning bolt path: `M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z`
> Sizes: 192×192, 512×512, 180×180.
> Save as PNG to `mass-market-app/public/icons/icon-192.png`, `icon-512.png`, `icon-180.png`.

- [ ] **Step 3: Verify files exist**

```bash
ls mass-market-app/public/icons/
# Expected: icon-180.png  icon-192.png  icon-512.png
```

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/public/icons/
git commit -m "feat: add MOCA PWA icons (192, 512, 180) in mocha-latte palette"
```

---

## Task 2: Update favicon.svg colors

**Files:**
- Modify: `mass-market-app/public/favicon.svg`

- [ ] **Step 1: Replace bolt fill color**

In `mass-market-app/public/favicon.svg`, replace every occurrence of `#863bff` with `#5c3317` and every occurrence of `#7e14ff` with `#8a5230`.

These appear in both `fill="..."` attributes and inside `style="fill:..."` attributes. Do a global replace-all for each.

- [ ] **Step 2: Replace glow ellipse colors**

Replace every occurrence of `#ede6ff` with `#f5ede0` (cream glow).
Replace every occurrence of `#47bfff` with `#c9a97a` (warm caramel accent).

- [ ] **Step 3: Update display-p3 color() values in style attributes**

The SVG uses `style="fill:#xxx;fill:color(display-p3 ...);fill-opacity:1"`. Strip the `color()` override so only the hex value applies. Replace:

| Find | Replace |
|------|---------|
| `fill:color(display-p3 .5252 .23 1)` | *(delete this segment)* |
| `fill:color(display-p3 .4922 .0767 1)` | *(delete this segment)* |
| `fill:color(display-p3 .9275 .9033 1)` | *(delete this segment)* |
| `fill:color(display-p3 .2799 .748 1)` | *(delete this segment)* |

The style attributes should end up like: `style="fill:#5c3317;fill-opacity:1"` (no color() segment).

- [ ] **Step 4: Visual check**

Open `mass-market-app/public/favicon.svg` in a browser tab directly. The bolt should appear in dark espresso brown (`#5c3317`) with warm cream/caramel glows. No purple should be visible.

- [ ] **Step 5: Commit**

```bash
git add mass-market-app/public/favicon.svg
git commit -m "feat: update favicon.svg to mocha-latte palette"
```

---

## Task 3: Create Logo.jsx component

**Files:**
- Create: `mass-market-app/src/components/Logo.jsx`

- [ ] **Step 1: Create the component**

Create `mass-market-app/src/components/Logo.jsx` with this exact content:

```jsx
const BOLT_PATH = 'M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z'

const CONFIG = {
  xs: { boltW: 16, boltH: 15, wordmarkSize: null, subtextSize: null },
  sm: { boltW: 20, boltH: 19, wordmarkSize: 14,   subtextSize: null },
  md: { boltW: 28, boltH: 27, wordmarkSize: 18,   subtextSize: 9   },
}

export default function Logo({ size = 'md' }) {
  const { boltW, boltH, wordmarkSize, subtextSize } = CONFIG[size]

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width={boltW} height={boltH} viewBox="0 0 48 46" fill="none" aria-hidden="true">
        <path fill="#5c3317" d={BOLT_PATH} />
      </svg>

      {wordmarkSize && (
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
          <span style={{
            fontSize: wordmarkSize,
            fontWeight: 900,
            color: '#3b1f0d',
            letterSpacing: '-0.02em',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}>
            MOCA
          </span>
          {subtextSize && (
            <span style={{
              fontSize: subtextSize,
              fontWeight: 400,
              color: '#8a6a4a',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              letterSpacing: '0.01em',
            }}>
              by Alon Yochelman
            </span>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add mass-market-app/src/components/Logo.jsx
git commit -m "feat: add Logo.jsx component (MOCA, mocha-latte, 3 sizes)"
```

---

## Task 4: Update Navbar.jsx to use Logo

**Files:**
- Modify: `mass-market-app/src/components/Navbar.jsx`

- [ ] **Step 1: Add import**

At the top of `mass-market-app/src/components/Navbar.jsx`, add after the existing imports:

```jsx
import Logo from './Logo'
```

- [ ] **Step 2: Replace text elements with Logo**

Find this block inside the `<NavLink to="/" ...>` element (lines 20-23):

```jsx
<NavLink to="/" className="flex flex-col">
  <span className="text-sm font-semibold text-gray-900 tracking-tight">Mobile Operators Competitor Analysis</span>
  <span className="text-[10px] text-gray-400">Made By Alon Yochelman</span>
</NavLink>
```

Replace with:

```jsx
<NavLink to="/" className="flex items-center">
  <Logo size="md" />
</NavLink>
```

- [ ] **Step 3: Start dev server and visually verify**

```bash
cd mass-market-app && npm run dev
```

Open http://localhost:5173. Check:
- Navbar left side shows the bolt + "MOCA" + "by Alon Yochelman"
- Clicking the logo navigates to `/`
- No layout shift or overflow on desktop and mobile

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/src/components/Navbar.jsx
git commit -m "feat: replace Navbar text header with Logo component"
```

---

## Task 5: Update manifest.json and index.html

**Files:**
- Modify: `mass-market-app/public/manifest.json`
- Modify: `mass-market-app/index.html`

- [ ] **Step 1: Update manifest.json**

Replace the entire contents of `mass-market-app/public/manifest.json` with:

```json
{
  "name": "MOCA — Mobile Operators Competitor Analysis",
  "short_name": "MOCA",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f5ede0",
  "theme_color": "#5c3317",
  "lang": "he",
  "dir": "rtl",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```

Note: `background_color` and `theme_color` updated to mocha-latte. Icon paths moved to `/icons/` subfolder.

- [ ] **Step 2: Update index.html head links**

In `mass-market-app/index.html`, replace:

```html
<meta name="theme-color" content="#2563eb" />
```

with:

```html
<meta name="theme-color" content="#5c3317" />
```

Replace:

```html
<link rel="icon" type="image/png" href="/icon-192.png" />
<link rel="apple-touch-icon" href="/icon-192.png" />
```

with:

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="apple-touch-icon" href="/icons/icon-180.png" />
```

- [ ] **Step 3: Verify in browser**

In Chrome/Edge: open DevTools → Application → Manifest. Confirm:
- Name: "MOCA — Mobile Operators Competitor Analysis"
- Short name: "MOCA"
- Icons show the mocha rounded-square at 192 and 512

Check the browser tab — favicon should show the mocha bolt.

- [ ] **Step 4: Commit**

```bash
git add mass-market-app/public/manifest.json mass-market-app/index.html
git commit -m "feat: update manifest and index.html for MOCA brand (mocha theme)"
```

---

## Task 6: Final integration check + wrap-up commit

- [ ] **Step 1: Hard refresh and full visual check**

```bash
# Kill any running dev server, restart clean
cd mass-market-app && npm run dev
```

Open http://localhost:5173, do Ctrl+Shift+R (hard refresh). Verify:
1. Tab favicon = mocha bolt (not purple, not blue)
2. Navbar = bolt icon + "MOCA" bold + "by Alon Yochelman" small
3. No console errors
4. Mobile bottom bar unaffected (Navbar.jsx mobile section unchanged)

- [ ] **Step 2: Check git log is clean**

```bash
git log --oneline -6
# Expected recent commits:
# feat: update manifest and index.html for MOCA brand (mocha theme)
# feat: replace Navbar text header with Logo component
# feat: add Logo.jsx component (MOCA, mocha-latte, 3 sizes)
# feat: update favicon.svg to mocha-latte palette
# feat: add MOCA PWA icons (192, 512, 180) in mocha-latte palette
```

- [ ] **Step 3: Tag checkpoint**

```bash
git tag v-moca-brand-launch
```
