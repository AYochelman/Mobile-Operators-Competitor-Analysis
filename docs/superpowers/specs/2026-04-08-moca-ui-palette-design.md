# MOCA UI Palette — Design Spec
**Date:** 2026-04-08
**Approach:** Approach 2 — Neutral components only (no carrier badge colors touched)

---

## Overview

Apply the mocha-latte color palette to neutral UI components only: body background, scrollbar, text selection, Button variants, FilterTag states, and the `gray` Badge color. All carrier/provider badge colors (blue, green, orange, purple, etc.) remain unchanged.

This approach is a stepping stone toward Approach 3 (Tailwind theme extension) — all changes here are a strict subset of what Approach 3 would do.

---

## Color Reference

| Token | Hex | Usage |
|-------|-----|-------|
| `--moca-cream` | `#f9f4ee` | Body background |
| `--moca-cream-light` | `#f5ede0` | Button/tag hover bg, badge bg |
| `--moca-border` | `#e0cdb5` | Secondary button border |
| `--moca-bolt` | `#5c3317` | Primary button, active FilterTag, gray badge text |
| `--moca-bolt-dark` | `#4a2a13` | Primary button hover |
| `--moca-text` | `#3b1f0d` | Secondary button text |
| `--moca-sub` | `#8a6a4a` | FilterTag inactive text |
| `--moca-scrollbar` | `#c4a882` | Scrollbar thumb |
| `--moca-selection` | `rgba(92,51,23,0.12)` | Text selection highlight |

---

## Files Changed

### 1. `mass-market-app/src/index.css` — Updated

Three targeted changes inside `@layer base`:

**body:**
```css
body {
  @apply bg-[#f9f4ee] text-gray-900 min-h-screen;
}
```
(was `bg-[#fafafa]`)

**scrollbar thumb:**
```css
::-webkit-scrollbar-thumb { background: #c4a882; border-radius: 3px; }
```
(was `#d1d5db`)

**selection:**
```css
::selection {
  background-color: rgba(92, 51, 23, 0.12);
  color: inherit;
}
```
(was `rgba(59, 130, 246, 0.15)`)

No other changes to index.css.

---

### 2. `mass-market-app/src/components/ui/Button.jsx` — Updated

Only the `variants` object changes. Everything else (base classes, sizes, structure) stays identical.

```js
const variants = {
  primary:   'bg-[#5c3317] text-white hover:bg-[#4a2a13] focus:ring-[#5c3317]',
  secondary: 'bg-[#f5ede0] text-[#3b1f0d] hover:bg-[#e8d5bc] focus:ring-[#5c3317] border border-[#e0cdb5]',
  danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
  ghost:     'text-[#5c3317] hover:bg-[#f5ede0] focus:ring-[#5c3317]',
}
```

`danger` is unchanged (red stays red — it conveys meaning).

---

### 3. `mass-market-app/src/components/ui/FilterTag.jsx` — Updated

Only the conditional className string changes:

```jsx
className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
  ${active
    ? 'bg-[#5c3317] text-[#f5ede0]'
    : 'text-[#8a6a4a] hover:text-[#3b1f0d] hover:bg-[#f5ede0]'
  }`}
```

---

### 4. `mass-market-app/src/components/ui/Badge.jsx` — Updated

Only the `gray` entry in the `colors` object changes. All other colors (blue, green, orange, purple, red, pink, teal, amber) are untouched.

```js
const colors = {
  gray:   'bg-[#f5ede0] text-[#5c3317]',   // ← changed
  blue:   'bg-blue-50 text-blue-600',        // unchanged
  green:  'bg-emerald-50 text-emerald-600',  // unchanged
  orange: 'bg-amber-50 text-amber-600',      // unchanged
  red:    'bg-red-50 text-red-600',          // unchanged
  purple: 'bg-violet-50 text-violet-600',    // unchanged
  pink:   'bg-pink-50 text-pink-600',        // unchanged
  teal:   'bg-teal-50 text-teal-600',        // unchanged
  amber:  'bg-amber-50 text-amber-600',      // unchanged
}
```

---

## Out of Scope

- PlanCard.jsx — not touched
- Navbar.jsx — already updated in previous brand work
- DashboardPage.jsx, ComparePage.jsx, etc. — not touched
- Any carrier/provider badge colors
- Tailwind config — deferred to Approach 3

---

## Implementation Order

1. Update `index.css` (body bg, scrollbar, selection)
2. Update `Button.jsx` (variants object)
3. Update `FilterTag.jsx` (active/inactive classes)
4. Update `Badge.jsx` (gray color only)
5. Visual verification in dev server
