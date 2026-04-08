# MOCA UI Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the mocha-latte color palette to neutral UI components (body, scrollbar, selection, Button, FilterTag, Badge gray) without touching carrier/provider badge colors.

**Architecture:** Four targeted file edits — `index.css` for global base styles, then three UI component files. Each change is a color-only swap; no structural changes to any component.

**Tech Stack:** React, Tailwind CSS (arbitrary value syntax `bg-[#hex]`), Vite dev server

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `mass-market-app/src/index.css` | Body bg, scrollbar, selection colors |
| Modify | `mass-market-app/src/components/ui/Button.jsx` | primary/secondary/ghost variant colors |
| Modify | `mass-market-app/src/components/ui/FilterTag.jsx` | active/inactive state colors |
| Modify | `mass-market-app/src/components/ui/Badge.jsx` | gray color only |

---

## Task 1: Update index.css — body, scrollbar, selection

**Files:**
- Modify: `mass-market-app/src/index.css`

- [ ] **Step 1: Update body background**

Find:
```css
body {
  @apply bg-[#fafafa] text-gray-900 min-h-screen;
}
```

Replace with:
```css
body {
  @apply bg-[#f9f4ee] text-gray-900 min-h-screen;
}
```

- [ ] **Step 2: Update scrollbar thumb color**

Find:
```css
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
```

Replace with:
```css
::-webkit-scrollbar-thumb { background: #c4a882; border-radius: 3px; }
```

- [ ] **Step 3: Update text selection color**

Find:
```css
::selection {
  background-color: rgba(59, 130, 246, 0.15);
  color: inherit;
}
```

Replace with:
```css
::selection {
  background-color: rgba(92, 51, 23, 0.12);
  color: inherit;
}
```

- [ ] **Step 4: Verify no other changes were made**

Run:
```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/index.css
```

Expected: exactly 3 color value changes (bg-[#fafafa]→bg-[#f9f4ee], #d1d5db→#c4a882, rgba(59,130,246,0.15)→rgba(92,51,23,0.12)). No structural changes.

- [ ] **Step 5: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/index.css
git commit -m "feat: update index.css to mocha-latte base colors (body, scrollbar, selection)"
```

---

## Task 2: Update Button.jsx variant colors

**Files:**
- Modify: `mass-market-app/src/components/ui/Button.jsx`

- [ ] **Step 1: Replace the variants object**

Find this exact block:
```js
const variants = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
  secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200 focus:ring-gray-400 border border-gray-300',
  danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
  ghost: 'text-gray-600 hover:bg-gray-100 focus:ring-gray-400',
}
```

Replace with:
```js
const variants = {
  primary:   'bg-[#5c3317] text-white hover:bg-[#4a2a13] focus:ring-[#5c3317]',
  secondary: 'bg-[#f5ede0] text-[#3b1f0d] hover:bg-[#e8d5bc] focus:ring-[#5c3317] border border-[#e0cdb5]',
  danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
  ghost:     'text-[#5c3317] hover:bg-[#f5ede0] focus:ring-[#5c3317]',
}
```

Note: `danger` is intentionally unchanged — red conveys destructive meaning.

- [ ] **Step 2: Verify no structural changes**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/ui/Button.jsx
```

Expected: only the `variants` object changed. `base`, `sizes`, JSX return — all identical.

- [ ] **Step 3: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/ui/Button.jsx
git commit -m "feat: update Button.jsx variants to mocha-latte palette"
```

---

## Task 3: Update FilterTag.jsx active/inactive colors

**Files:**
- Modify: `mass-market-app/src/components/ui/FilterTag.jsx`

- [ ] **Step 1: Replace the conditional className**

Find this exact block:
```jsx
className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
  ${active
    ? 'bg-gray-900 text-white'
    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
  }`}
```

Replace with:
```jsx
className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all duration-150
  ${active
    ? 'bg-[#5c3317] text-[#f5ede0]'
    : 'text-[#8a6a4a] hover:text-[#3b1f0d] hover:bg-[#f5ede0]'
  }`}
```

- [ ] **Step 2: Verify no structural changes**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/ui/FilterTag.jsx
```

Expected: only the 4 color values inside the conditional changed. `onClick`, `label`, `count` props and everything else identical.

- [ ] **Step 3: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/ui/FilterTag.jsx
git commit -m "feat: update FilterTag.jsx to mocha-latte active/inactive colors"
```

---

## Task 4: Update Badge.jsx gray color

**Files:**
- Modify: `mass-market-app/src/components/ui/Badge.jsx`

- [ ] **Step 1: Replace only the gray entry**

Find this exact block:
```js
const colors = {
  gray: 'bg-gray-50 text-gray-600',
  blue: 'bg-blue-50 text-blue-600',
  green: 'bg-emerald-50 text-emerald-600',
  orange: 'bg-amber-50 text-amber-600',
  red: 'bg-red-50 text-red-600',
  purple: 'bg-violet-50 text-violet-600',
  pink: 'bg-pink-50 text-pink-600',
  teal: 'bg-teal-50 text-teal-600',
  amber: 'bg-amber-50 text-amber-600',
}
```

Replace with:
```js
const colors = {
  gray:   'bg-[#f5ede0] text-[#5c3317]',
  blue:   'bg-blue-50 text-blue-600',
  green:  'bg-emerald-50 text-emerald-600',
  orange: 'bg-amber-50 text-amber-600',
  red:    'bg-red-50 text-red-600',
  purple: 'bg-violet-50 text-violet-600',
  pink:   'bg-pink-50 text-pink-600',
  teal:   'bg-teal-50 text-teal-600',
  amber:  'bg-amber-50 text-amber-600',
}
```

- [ ] **Step 2: Verify only gray changed**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/ui/Badge.jsx
```

Expected: exactly 1 line changed — the `gray` entry. All 8 other colors identical.

- [ ] **Step 3: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/ui/Badge.jsx
git commit -m "feat: update Badge.jsx gray color to mocha-latte (other colors unchanged)"
```

---

## Task 5: Visual verification + final tag

- [ ] **Step 1: Start dev server**

```bash
cd "D:/השוואת MASS MARKET/mass-market-app" && npm run dev
```

Open http://localhost:5173, hard refresh (Ctrl+Shift+R).

- [ ] **Step 2: Visual checklist**

Check each of the following:
1. Page background — warm cream (`#f9f4ee`), not white/cold gray
2. Navbar — unchanged (already MOCA-branded)
3. Tab buttons (סלולר / חו״ל / גלובלי / תוכן) — active tab is espresso brown, inactive is muted mocha
4. Sort/filter buttons — active state is espresso brown on cream, not black on white
5. "🔄 עדכן" button (primary) — espresso brown, not blue
6. Carrier badges (הוט מובייל, פרטנר, etc.) — still colored (blue/green/orange etc.), NOT changed to mocha
7. eSIM badge — still colored, NOT changed
8. Scrollbar thumb (if visible) — warm caramel tone

- [ ] **Step 3: Check console for errors**

```bash
# In browser DevTools → Console
# Expected: no errors, no warnings about unknown CSS
```

- [ ] **Step 4: Tag**

```bash
cd "D:/השוואת MASS MARKET"
git tag v-moca-ui-palette
```
