# MOCA Tailwind Theme Extension — Design Spec
**Date:** 2026-04-08
**Approach:** Approach 3 — Tailwind v4 `@theme` extension (semantic token migration)

---

## Overview

Replace all arbitrary moca color values (`bg-[#5c3317]`, `text-[#8a6a4a]`, etc.) with semantic Tailwind utilities (`bg-moca-bolt`, `text-moca-sub`). The entire palette is defined once in a `@theme` block in `index.css`; every consumer just uses named tokens.

This is a purely mechanical token-replacement — zero structural changes to any component.

**Tailwind version:** v4.2.x — theme extension uses `@theme` CSS directive, NOT `tailwind.config.js`.

---

## Color Token Map

| Token | CSS var | Hex | Semantic usage |
|-------|---------|-----|----------------|
| `moca-bolt` | `--color-moca-bolt` | `#5c3317` | Primary actions, active states |
| `moca-dark` | `--color-moca-dark` | `#4a2a13` | Hover on primary |
| `moca-text` | `--color-moca-text` | `#3b1f0d` | Body/secondary text |
| `moca-sub` | `--color-moca-sub` | `#8a6a4a` | Subdued/tertiary text |
| `moca-muted` | `--color-moca-muted` | `#a08468` | Very muted text (tab inactive) |
| `moca-cream` | `--color-moca-cream` | `#f5ede0` | Light fill, hover bg |
| `moca-bg` | `--color-moca-bg` | `#f2e8d8` | Page background |
| `moca-border` | `--color-moca-border` | `#e0cdb5` | Borders |
| `moca-sand` | `--color-moca-sand` | `#e8d5bc` | Secondary hover bg |
| `moca-scroll` | `--color-moca-scroll` | `#c4a882` | Scrollbar thumb |
| `moca-mist` | `--color-moca-mist` | `#faf5ee` | Active select/dropdown bg |

---

## Implementation Strategy

4 stages to minimize blast radius and allow incremental verification:

### Stage A — `@theme` block in `index.css`
Add the 11-token `@theme` block. Also migrate the 3 existing arbitrary values in `index.css` itself (`bg-[#f2e8d8]` → `bg-moca-bg`, etc.). Nothing else changes yet — this stage is additive only.

### Stage B — UI Components (4 files)
Migrate all arbitrary moca values in:
- `components/ui/Button.jsx` — 8 occurrences
- `components/ui/FilterTag.jsx` — 5 occurrences
- `components/ui/Badge.jsx` — 2 occurrences
- `components/Logo.jsx` — 3 occurrences (inline styles, uses CSS vars not Tailwind utilities)

### Stage C — Pages (2 files)
Migrate all arbitrary moca values in:
- `pages/DashboardPage.jsx` — 6 occurrences
- `pages/ComparePage.jsx` — 9 occurrences

### Stage D — Verification & tag
Visual check + git tag `v-moca-theme-tokens`.

---

## Files Changed

### 1. `mass-market-app/src/index.css` — Modified (Stage A)

Add `@theme` block immediately after `@import "tailwindcss"`:

```css
@theme {
  --color-moca-bolt:   #5c3317;
  --color-moca-dark:   #4a2a13;
  --color-moca-text:   #3b1f0d;
  --color-moca-sub:    #8a6a4a;
  --color-moca-muted:  #a08468;
  --color-moca-cream:  #f5ede0;
  --color-moca-bg:     #f2e8d8;
  --color-moca-border: #e0cdb5;
  --color-moca-sand:   #e8d5bc;
  --color-moca-scroll: #c4a882;
  --color-moca-mist:   #faf5ee;
}
```

Then migrate the 3 remaining arbitrary values in `index.css`:
- `bg-[#f2e8d8]` → `bg-moca-bg`
- `background: #c4a882` → `background: var(--color-moca-scroll)`

Note: `rgba(92, 51, 23, 0.12)` in `::selection` stays as-is (can't be a Tailwind utility; CSS rgba is fine).

---

### 2. `mass-market-app/src/components/ui/Button.jsx` — Modified (Stage B)

```js
const variants = {
  primary:   'bg-moca-bolt text-white hover:bg-moca-dark focus:ring-moca-bolt',
  secondary: 'bg-moca-cream text-moca-text hover:bg-moca-sand focus:ring-moca-bolt border border-moca-border',
  danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
  ghost:     'text-moca-bolt hover:bg-moca-cream focus:ring-moca-bolt',
}
```

---

### 3. `mass-market-app/src/components/ui/FilterTag.jsx` — Modified (Stage B)

```jsx
className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
  ${active
    ? 'bg-moca-bolt text-moca-cream'
    : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
  }`}
```

---

### 4. `mass-market-app/src/components/ui/Badge.jsx` — Modified (Stage B)

```js
const colors = {
  gray:   'bg-moca-cream text-moca-bolt',
  // all other entries unchanged
}
```

---

### 5. `mass-market-app/src/components/Logo.jsx` — Modified (Stage B)

Logo uses inline styles (SVG + JSX style objects), not Tailwind utilities. Use CSS custom properties:

```jsx
// Before:
<path fill="#5c3317" d={BOLT_PATH} />
// After:
<path fill="var(--color-moca-bolt)" d={BOLT_PATH} />

// Before:
color: '#3b1f0d',
// After:
color: 'var(--color-moca-text)',

// Before:
color: '#8a6a4a',
// After:
color: 'var(--color-moca-sub)',
```

---

### 6. `mass-market-app/src/pages/DashboardPage.jsx` — Modified (Stage C)

Replacements (exact occurrences from grep):
- `text-[#3b1f0d]` → `text-moca-text`
- `bg-[#5c3317]` (in tab active pseudo-element) → `bg-moca-bolt`
- `text-[#a08468]` → `text-moca-muted`
- `hover:text-[#5c3317]` → `hover:text-moca-bolt`
- `text-[#8a6a4a]` → `text-moca-sub`
- `hover:text-[#3b1f0d]` → `hover:text-moca-text`
- `hover:bg-[#f5ede0]` → `hover:bg-moca-cream`

---

### 7. `mass-market-app/src/pages/ComparePage.jsx` — Modified (Stage C)

Replacements (exact occurrences from grep):
- `text-[#8a6a4a]` → `text-moca-sub`
- `hover:text-[#5c3317]` → `hover:text-moca-bolt`
- `hover:bg-[#f5ede0]` → `hover:bg-moca-cream`
- `focus:border-[#5c3317]` → `focus:border-moca-bolt`
- `focus:ring-[#5c3317]` → `focus:ring-moca-bolt`
- `border-[#5c3317]` → `border-moca-bolt`
- `bg-[#faf5ee]` → `bg-moca-mist`
- `hover:text-[#3b1f0d]` → `hover:text-moca-text`
- `text-[#8a6a4a]` → `text-moca-sub` (carrier filter button inactive)

---

## Out of Scope

- Carrier/provider badge colors (`blue`, `green`, `orange`, etc.) — unchanged
- `public/favicon.svg` — SVG hardcodes colors (no Tailwind), unchanged
- `public/manifest.json` — JSON, unchanged
- `index.html` — meta theme-color, unchanged
- Any structural, layout, or non-color changes

---

## Verification Checklist

After Stage C, run a final grep to confirm zero moca arbitrary values remain:
```bash
grep -rn '#5c3317\|#4a2a13\|#3b1f0d\|#8a6a4a\|#a08468\|#f5ede0\|#f2e8d8\|#e0cdb5\|#e8d5bc\|#c4a882\|#faf5ee' mass-market-app/src/
```
Expected: zero matches in `.jsx` / `.css` files (Logo.jsx also zero — uses CSS vars).

Visual check: app should look identical to pre-migration state.
