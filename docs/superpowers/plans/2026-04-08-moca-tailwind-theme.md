# MOCA Tailwind Theme Token Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all arbitrary moca hex color values in JSX/CSS with semantic Tailwind v4 token utilities (`bg-moca-bolt`, `text-moca-sub`, etc.) defined via a single `@theme` block.

**Architecture:** Tailwind v4 exposes CSS custom properties defined in `@theme` as utility classes automatically — no `tailwind.config.js` needed. All 11 moca tokens are declared once in `index.css`; every file just uses the named utility. Logo.jsx uses inline styles so it gets CSS var references instead.

**Tech Stack:** React, Tailwind CSS v4 (`@theme` directive), Vite

---

## File Map

| Action | Path | Change |
|--------|------|--------|
| Modify | `mass-market-app/src/index.css` | Add `@theme` block + migrate 2 arbitrary values |
| Modify | `mass-market-app/src/components/ui/Button.jsx` | 8 arbitrary values → tokens |
| Modify | `mass-market-app/src/components/ui/FilterTag.jsx` | 5 arbitrary values → tokens |
| Modify | `mass-market-app/src/components/ui/Badge.jsx` | 2 arbitrary values → tokens |
| Modify | `mass-market-app/src/components/Logo.jsx` | 3 inline hex values → CSS vars |
| Modify | `mass-market-app/src/pages/DashboardPage.jsx` | 7 arbitrary values → tokens |
| Modify | `mass-market-app/src/pages/ComparePage.jsx` | 9 arbitrary values → tokens |

---

## Task 1: Add `@theme` block to index.css (Stage A)

**Files:**
- Modify: `mass-market-app/src/index.css`

This task is additive only. It defines all 11 moca tokens as Tailwind v4 theme variables, then migrates the 2 existing arbitrary values already in `index.css`. After this task, utilities like `bg-moca-bolt` are valid Tailwind classes, but no component uses them yet.

- [ ] **Step 1: Add `@theme` block immediately after the `@import` line**

Open `mass-market-app/src/index.css`. The file currently starts with:
```css
@import "tailwindcss";

@layer base {
```

Replace that with:
```css
@import "tailwindcss";

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

@layer base {
```

- [ ] **Step 2: Migrate body background in `@layer base`**

Find (line ~11 after edit):
```css
    @apply bg-[#f2e8d8] text-gray-900 min-h-screen;
```

Replace with:
```css
    @apply bg-moca-bg text-gray-900 min-h-screen;
```

- [ ] **Step 3: Migrate scrollbar thumb color**

Find (line ~17):
```css
  ::-webkit-scrollbar-thumb { background: #c4a882; border-radius: 3px; }
```

Replace with:
```css
  ::-webkit-scrollbar-thumb { background: var(--color-moca-scroll); border-radius: 3px; }
```

Note: `::selection { background-color: rgba(92, 51, 23, 0.12) }` stays as-is — rgba is not a Tailwind utility and is correct here.

- [ ] **Step 4: Verify the final index.css looks like this**

```css
@import "tailwindcss";

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

@layer base {
  html {
    direction: rtl;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  body {
    @apply bg-moca-bg text-gray-900 min-h-screen;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--color-moca-scroll); border-radius: 3px; }
  ...
```

No other changes in the file.

- [ ] **Step 5: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/index.css
git commit -m "feat: add @theme moca token palette to index.css (Stage A)"
```

---

## Task 2: Migrate Button.jsx (Stage B)

**Files:**
- Modify: `mass-market-app/src/components/ui/Button.jsx` (lines 4–7)

Only the `variants` object changes. `base`, `sizes`, and the JSX return are unchanged.

- [ ] **Step 1: Replace the variants object**

Find (exact current content, lines 3–8):
```js
  const variants = {
    primary:   'bg-[#5c3317] text-white hover:bg-[#4a2a13] focus:ring-[#5c3317]',
    secondary: 'bg-[#f5ede0] text-[#3b1f0d] hover:bg-[#e8d5bc] focus:ring-[#5c3317] border border-[#e0cdb5]',
    danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    ghost:     'text-[#5c3317] hover:bg-[#f5ede0] focus:ring-[#5c3317]',
  }
```

Replace with:
```js
  const variants = {
    primary:   'bg-moca-bolt text-white hover:bg-moca-dark focus:ring-moca-bolt',
    secondary: 'bg-moca-cream text-moca-text hover:bg-moca-sand focus:ring-moca-bolt border border-moca-border',
    danger:    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    ghost:     'text-moca-bolt hover:bg-moca-cream focus:ring-moca-bolt',
  }
```

- [ ] **Step 2: Verify no other changes**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/ui/Button.jsx
```

Expected: only 3 lines changed inside the `variants` object. Everything else identical.

- [ ] **Step 3: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/ui/Button.jsx
git commit -m "feat: migrate Button.jsx variants to moca theme tokens"
```

---

## Task 3: Migrate FilterTag.jsx (Stage B)

**Files:**
- Modify: `mass-market-app/src/components/ui/FilterTag.jsx` (lines 6–8)

- [ ] **Step 1: Replace the conditional className**

Find (exact current content, lines 6–8):
```jsx
        ${active
          ? 'bg-[#5c3317] text-[#f5ede0]'
          : 'text-[#8a6a4a] hover:text-[#3b1f0d] hover:bg-[#f5ede0]'
        }
```

Replace with:
```jsx
        ${active
          ? 'bg-moca-bolt text-moca-cream'
          : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
        }
```

- [ ] **Step 2: Verify no other changes**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/ui/FilterTag.jsx
```

Expected: exactly 2 lines changed (the active and inactive color strings). Everything else identical.

- [ ] **Step 3: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/ui/FilterTag.jsx
git commit -m "feat: migrate FilterTag.jsx to moca theme tokens"
```

---

## Task 4: Migrate Badge.jsx (Stage B)

**Files:**
- Modify: `mass-market-app/src/components/ui/Badge.jsx` (line 3)

- [ ] **Step 1: Replace the gray entry only**

Find (exact current content, line 3):
```js
    gray:   'bg-[#f5ede0] text-[#5c3317]',
```

Replace with:
```js
    gray:   'bg-moca-cream text-moca-bolt',
```

All other color entries (blue, green, orange, red, purple, pink, teal, amber) stay exactly as-is.

- [ ] **Step 2: Verify only one line changed**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/ui/Badge.jsx
```

Expected: exactly 1 line changed — the `gray` entry. All 8 other colors identical.

- [ ] **Step 3: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/ui/Badge.jsx
git commit -m "feat: migrate Badge.jsx gray color to moca theme token"
```

---

## Task 5: Migrate Logo.jsx (Stage B)

**Files:**
- Modify: `mass-market-app/src/components/Logo.jsx` (lines 15, 23, 33)

Logo uses JSX inline styles, not Tailwind classes. Use CSS custom properties that reference the tokens defined in `@theme`. These vars are available globally since `index.css` is loaded at app root.

- [ ] **Step 1: Replace the bolt fill color (line 15)**

Find:
```jsx
        <path fill="#5c3317" d={BOLT_PATH} />
```

Replace with:
```jsx
        <path fill="var(--color-moca-bolt)" d={BOLT_PATH} />
```

- [ ] **Step 2: Replace the wordmark color (line ~23)**

Find:
```jsx
            color: '#3b1f0d',
```

Replace with:
```jsx
            color: 'var(--color-moca-text)',
```

- [ ] **Step 3: Replace the subtext color (line ~33)**

Find:
```jsx
              color: '#8a6a4a',
```

Replace with:
```jsx
              color: 'var(--color-moca-sub)',
```

- [ ] **Step 4: Verify no other changes**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/components/Logo.jsx
```

Expected: exactly 3 lines changed. The `BOLT_PATH` constant, `CONFIG` object, structure — all identical.

- [ ] **Step 5: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/components/Logo.jsx
git commit -m "feat: migrate Logo.jsx inline colors to CSS var references"
```

---

## Task 6: Migrate DashboardPage.jsx (Stage C)

**Files:**
- Modify: `mass-market-app/src/pages/DashboardPage.jsx` (lines 312–313, 342)

There are 2 locations in this file. Make each edit separately and carefully — this file is large (~400+ lines).

- [ ] **Step 1: Migrate the tab active/inactive className (lines 312–313)**

Find (exact content):
```jsx
                ? 'text-[#3b1f0d] after:absolute after:bottom-0 after:inset-x-2 after:h-[2px] after:bg-[#5c3317] after:rounded-full'
                : 'text-[#a08468] hover:text-[#5c3317]'
```

Replace with:
```jsx
                ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-2 after:h-[2px] after:bg-moca-bolt after:rounded-full'
                : 'text-moca-muted hover:text-moca-bolt'
```

- [ ] **Step 2: Migrate the Excel export button (line 342)**

Find (exact content):
```jsx
              <button onClick={exportToExcel} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-[#8a6a4a] hover:text-[#3b1f0d] hover:bg-[#f5ede0] transition-all duration-150" title="ייצוא ל-Excel">
```

Replace with:
```jsx
              <button onClick={exportToExcel} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-moca-sub hover:text-moca-text hover:bg-moca-cream transition-all duration-150" title="ייצוא ל-Excel">
```

- [ ] **Step 3: Verify exactly 2 locations changed**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/pages/DashboardPage.jsx
```

Expected: 4 changed lines total — 2 in the tab className block, 1 in the export button className.

- [ ] **Step 4: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/pages/DashboardPage.jsx
git commit -m "feat: migrate DashboardPage.jsx moca colors to theme tokens"
```

---

## Task 7: Migrate ComparePage.jsx (Stage C)

**Files:**
- Modify: `mass-market-app/src/pages/ComparePage.jsx` (lines 251, 307, 327, 349, 379, 392)

There are 6 locations in this file. Make each edit separately — this file is large (~500+ lines).

- [ ] **Step 1: Migrate the reset button (line 251)**

Find:
```jsx
          <button onClick={resetFilters} className="text-xs text-[#8a6a4a] hover:text-[#5c3317] hover:bg-[#f5ede0] px-2 py-1 rounded-md transition-colors">
```

Replace with:
```jsx
          <button onClick={resetFilters} className="text-xs text-moca-sub hover:text-moca-bolt hover:bg-moca-cream px-2 py-1 rounded-md transition-colors">
```

- [ ] **Step 2: Migrate the search input (line 307)**

Find:
```jsx
                  className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs focus:border-[#5c3317] focus:ring-1 focus:ring-[#5c3317] outline-none"
```

Replace with:
```jsx
                  className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs focus:border-moca-bolt focus:ring-1 focus:ring-moca-bolt outline-none"
```

- [ ] **Step 3: Migrate the region filter select (line 327)**

Find:
```jsx
                      className={`w-full border rounded-lg px-2 py-1 text-xs ${regionFilter !== 'all' ? 'border-[#5c3317] bg-[#faf5ee]' : 'border-gray-200'}`}
```

Replace with:
```jsx
                      className={`w-full border rounded-lg px-2 py-1 text-xs ${regionFilter !== 'all' ? 'border-moca-bolt bg-moca-mist' : 'border-gray-200'}`}
```

- [ ] **Step 4: Migrate the destination filter select (line 349)**

Find:
```jsx
                      className={`w-full border rounded-lg px-2 py-1 text-xs ${destinationFilter !== 'all' ? 'border-[#5c3317] bg-[#faf5ee]' : 'border-gray-200'}`}
```

Replace with:
```jsx
                      className={`w-full border rounded-lg px-2 py-1 text-xs ${destinationFilter !== 'all' ? 'border-moca-bolt bg-moca-mist' : 'border-gray-200'}`}
```

- [ ] **Step 5: Migrate the "הכל/נקה" carriers button (line 379)**

Find:
```jsx
              className="text-[10px] text-[#8a6a4a] hover:text-[#3b1f0d]"
```

Replace with:
```jsx
              className="text-[10px] text-moca-sub hover:text-moca-text"
```

- [ ] **Step 6: Migrate the individual carrier filter button inactive state (line 392)**

Find:
```jsx
                  selectedCarriers.includes(c.id) ? 'text-white' : 'text-[#8a6a4a] hover:text-[#3b1f0d] hover:bg-[#f5ede0]'
```

Replace with:
```jsx
                  selectedCarriers.includes(c.id) ? 'text-white' : 'text-moca-sub hover:text-moca-text hover:bg-moca-cream'
```

- [ ] **Step 7: Verify exactly 6 locations changed**

```bash
cd "D:/השוואת MASS MARKET" && git diff mass-market-app/src/pages/ComparePage.jsx
```

Expected: 6 changed lines — one per location above. All other content identical.

- [ ] **Step 8: Commit**

```bash
cd "D:/השוואת MASS MARKET"
git add mass-market-app/src/pages/ComparePage.jsx
git commit -m "feat: migrate ComparePage.jsx moca colors to theme tokens"
```

---

## Task 8: Verification & cleanup (Stage D)

**Files:** None — read-only verification + git tag

- [ ] **Step 1: Grep check — confirm zero remaining moca arbitrary values in src/**

```bash
cd "D:/השוואת MASS MARKET" && grep -rn "#5c3317\|#4a2a13\|#3b1f0d\|#8a6a4a\|#a08468\|#f5ede0\|#f2e8d8\|#e0cdb5\|#e8d5bc\|#c4a882\|#faf5ee" mass-market-app/src/
```

Expected: **zero matches**. If any remain, fix them before continuing.

Note: `public/` files (favicon.svg, manifest.json) legitimately retain hex values — they don't use Tailwind. Don't touch them.

- [ ] **Step 2: Start dev server and visually verify**

```bash
cd "D:/השוואת MASS MARKET/mass-market-app" && npm run dev
```

Open http://localhost:5173, hard refresh (Ctrl+Shift+R). Confirm:
1. Page background — same warm cream as before migration
2. Active tab underline — espresso brown
3. FilterTag active state — espresso brown fill
4. Primary button — espresso brown (if visible)
5. Carrier badges — still their original colors (blue/green/orange)
6. Logo bolt — same espresso brown color
7. Scrollbar thumb (if visible) — warm caramel

**App must look visually identical to pre-migration.** This is a pure refactor.

- [ ] **Step 3: Check browser console for Tailwind errors**

If Tailwind generates CSS warnings about unknown utilities, it means a token name was misspelled. Fix the typo in the affected file and re-verify.

- [ ] **Step 4: Tag the migration complete**

```bash
cd "D:/השוואת MASS MARKET"
git tag v-moca-theme-tokens
git log --oneline -8
```

Expected recent commits:
```
feat: migrate ComparePage.jsx moca colors to theme tokens
feat: migrate DashboardPage.jsx moca colors to theme tokens
feat: migrate Logo.jsx inline colors to CSS var references
feat: migrate Badge.jsx gray color to moca theme token
feat: migrate FilterTag.jsx to moca theme tokens
feat: migrate Button.jsx variants to moca theme tokens
feat: add @theme moca token palette to index.css (Stage A)
```
