# באנרים ראשיים — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "באנרים ראשיים" tab that shows daily auto-scraped screenshots of every domestic carrier's homepage in a clickable grid.

**Architecture:** Playwright takes a screenshot of each carrier homepage at 08:00 daily and saves PNGs to `data/banners/`. Flask serves PNGs via a static route and metadata via `/api/banners`. A new React tab renders a 4-column grid of BannerCard components with a modal on click.

**Tech Stack:** Python + Playwright (sync), Flask, APScheduler, React + Tailwind, Lucide icons

---

## File Map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `scraper.py` | Add `scrape_carrier_banners()` at end of file |
| Modify | `app.py` | Add `/banners/<f>` static route, `/api/banners` endpoint, `scrape_banners_job`, scheduler entry |
| Create | `data/banners/.gitkeep` | Ensure directory exists in git |
| Modify | `mass-market-app/src/lib/api.js` | Add `getBanners()` |
| Create | `mass-market-app/src/components/BannerCard.jsx` | Banner card + modal |
| Modify | `mass-market-app/src/pages/DashboardPage.jsx` | New tab, state, loadTab branch, render section |

---

## Task 1: Create `data/banners/` directory

**Files:**
- Create: `data/banners/.gitkeep`

- [ ] **Step 1: Create the directory and a gitkeep file**

```bash
mkdir "D:\השוואת MASS MARKET\data\banners"
type nul > "D:\השוואת MASS MARKET\data\banners\.gitkeep"
```

- [ ] **Step 2: Commit**

```bash
cd "D:\השוואת MASS MARKET"
git add data/banners/.gitkeep
git commit -m "chore: add data/banners directory for screenshot storage"
```

---

## Task 2: Add `scrape_carrier_banners()` to scraper.py

**Files:**
- Modify: `scraper.py` (append at end of file)

The function manages its own Playwright context (runs independently at 08:00, not inside the main scrape loop).

- [ ] **Step 1: Read the end of scraper.py to find insertion point**

Open `scraper.py` and note the last line number. The function goes at the very end.

- [ ] **Step 2: Append the function**

Add to the end of `scraper.py`:

```python
# ── CARRIER HOMEPAGE BANNER SCREENSHOTS ──────────────────────────────────────

CARRIER_HOMEPAGE_URLS = {
    "partner":   "https://www.partner.net.il",
    "pelephone": "https://www.pelephone.co.il",
    "hotmobile": "https://www.hotmobile.co.il",
    "cellcom":   "https://www.cellcom.co.il",
    "mobile019": "https://www.019mobile.co.il",
    "xphone":    "https://www.xphone.co.il",
    "wecom":     "https://www.we.co.il",
    "neptucom":  "https://www.neptucom.co.il",
}

def scrape_carrier_banners(output_dir: str) -> list[dict]:
    """
    Navigate to each domestic carrier homepage and save a 1280x720 PNG screenshot.
    Returns a list of dicts: { carrier, scraped_at, success }.
    output_dir — absolute path to the folder where PNGs will be saved.
    """
    import os
    from datetime import datetime, timezone

    results = []
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for carrier, url in CARRIER_HOMEPAGE_URLS.items():
            out_path = os.path.join(output_dir, f"{carrier}.png")
            scraped_at = datetime.now(timezone.utc).isoformat()
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)  # let hero images render
                page.screenshot(path=out_path, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
                results.append({"carrier": carrier, "scraped_at": scraped_at, "success": True})
                logger.info("Banner screenshot saved: %s", out_path)
            except Exception as exc:
                logger.warning("Banner screenshot failed for %s: %s", carrier, exc)
                results.append({"carrier": carrier, "scraped_at": scraped_at, "success": False})

        browser.close()

    return results
```

- [ ] **Step 3: Smoke-test the function manually**

Open a Python REPL in the project root:

```python
from scraper import scrape_carrier_banners
results = scrape_carrier_banners("data/banners")
print(results)
```

Expected: list of 8 dicts, most with `"success": True`. Check that PNG files appeared in `data/banners/`.

- [ ] **Step 4: Commit**

```bash
git add scraper.py
git commit -m "feat: add scrape_carrier_banners() for homepage screenshots"
```

---

## Task 3: Add `/banners/<f>` static route + `/api/banners` endpoint + scheduler job to app.py

**Files:**
- Modify: `app.py`

### 3a — Static route to serve PNGs

- [ ] **Step 1: Locate the `/sw.js` static route in app.py (around line 354) as a reference pattern**

- [ ] **Step 2: Add the static route for banner PNGs directly below the `/sw.js` route**

```python
@app.route("/banners/<path:filename>")
def serve_banner(filename):
    """Serve carrier homepage screenshot PNGs."""
    import os
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    return send_from_directory(banners_dir, filename)
```

### 3b — `/api/banners` metadata endpoint

- [ ] **Step 3: Add the API endpoint after the content-plans route (around line 576)**

```python
CARRIER_DISPLAY = {
    "partner":   {"name": "פרטנר",     "url": "https://www.partner.net.il",    "color": "#e8003d"},
    "pelephone": {"name": "פלאפון",    "url": "https://www.pelephone.co.il",   "color": "#ff6600"},
    "hotmobile": {"name": "הוט מובייל","url": "https://www.hotmobile.co.il",   "color": "#e3001e"},
    "cellcom":   {"name": "סלקום",     "url": "https://www.cellcom.co.il",     "color": "#003b7a"},
    "mobile019": {"name": "019 מובייל","url": "https://www.019mobile.co.il",   "color": "#555555"},
    "xphone":    {"name": "XPhone",    "url": "https://www.xphone.co.il",      "color": "#6a0dad"},
    "wecom":     {"name": "וי-קום",    "url": "https://www.we.co.il",          "color": "#006633"},
    "neptucom":  {"name": "נפטוקום",   "url": "https://www.neptucom.co.il",    "color": "#004488"},
}

@app.route("/api/banners")
@limiter.limit("60 per minute")
def api_banners():
    """Return metadata for all carrier homepage banner screenshots."""
    import os, glob
    from datetime import datetime, timezone

    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    result = []
    for carrier, meta in CARRIER_DISPLAY.items():
        png_path = os.path.join(banners_dir, f"{carrier}.png")
        scraped_at = None
        if os.path.exists(png_path):
            mtime = os.path.getmtime(png_path)
            scraped_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        result.append({
            "carrier":    carrier,
            "name":       meta["name"],
            "url":        meta["url"],
            "color":      meta["color"],
            "image_url":  f"/banners/{carrier}.png" if os.path.exists(png_path) else None,
            "scraped_at": scraped_at,
        })
    return jsonify(result)
```

### 3c — Scheduler job

- [ ] **Step 4: Add the job function near the other scheduler job functions (before the `scheduler = BackgroundScheduler()` line)**

```python
def scrape_banners_job():
    """Daily 08:00 job — screenshot each carrier homepage."""
    import os
    from scraper import scrape_carrier_banners
    banners_dir = os.path.join(os.path.dirname(__file__), "data", "banners")
    logger.info("Starting daily banner screenshot job")
    results = scrape_carrier_banners(banners_dir)
    ok = sum(1 for r in results if r["success"])
    logger.info("Banner screenshots: %d/%d succeeded", ok, len(results))
```

- [ ] **Step 5: Register the job in the scheduler block (right after the existing `scheduler.add_job` calls for the main scrape, around line 1138)**

```python
scheduler.add_job(scrape_banners_job, "cron", hour=8, minute=0)
```

- [ ] **Step 6: Test the endpoint manually**

Restart Flask (`taskkill /F /IM python.exe && python app.py`), then:

```
GET http://localhost:5000/api/banners
```

Expected: JSON array of 8 objects. `image_url` will be `null` until screenshots exist; run `scrape_carrier_banners("data/banners")` from a REPL first if you want to test with real images.

- [ ] **Step 7: Test static file route**

If PNGs exist in `data/banners/`:
```
GET http://localhost:5000/banners/partner.png
```
Expected: PNG image served with 200.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat: /api/banners endpoint + /banners/ static route + daily 08:00 scheduler job"
```

---

## Task 4: Add `getBanners()` to api.js

**Files:**
- Modify: `mass-market-app/src/lib/api.js`

- [ ] **Step 1: Open api.js and find the `getContentPlans` line as anchor**

It looks like:
```js
getContentPlans: () => fetchApi('/api/content-plans'),
```

- [ ] **Step 2: Add `getBanners` immediately after `getContentPlans`**

```js
getBanners: () => fetchApi('/api/banners'),
```

- [ ] **Step 3: Verify the change**

The relevant section of api.js should now read:

```js
getContentPlans: () => fetchApi('/api/content-plans'),
getBanners: () => fetchApi('/api/banners'),
```

- [ ] **Step 4: Commit**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
git add src/lib/api.js
git commit -m "feat: add getBanners() API call"
```

---

## Task 5: Create BannerCard component

**Files:**
- Create: `mass-market-app/src/components/BannerCard.jsx`

This component renders a single carrier banner card and owns the modal state.

- [ ] **Step 1: Create the file**

```jsx
// mass-market-app/src/components/BannerCard.jsx
import { useState, useEffect } from 'react'
import { ExternalLink, X } from 'lucide-react'

// Fallback gradient per carrier when screenshot isn't available yet
const CARRIER_GRADIENT = {
  partner:   'linear-gradient(135deg,#e8003d,#ff6b8a)',
  pelephone: 'linear-gradient(135deg,#ff6600,#ffaa44)',
  hotmobile: 'linear-gradient(135deg,#e3001e,#ff5555)',
  cellcom:   'linear-gradient(135deg,#003b7a,#0077cc)',
  mobile019: 'linear-gradient(135deg,#1a1a1a,#555)',
  xphone:    'linear-gradient(135deg,#6a0dad,#b44fec)',
  wecom:     'linear-gradient(135deg,#006633,#22bb66)',
  neptucom:  'linear-gradient(135deg,#004488,#2277cc)',
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('he-IL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function BannerCard({ banner }) {
  const { carrier, name, url, color, image_url, scraped_at } = banner
  const [modalOpen, setModalOpen] = useState(false)
  const [imgError, setImgError] = useState(false)

  // Close modal on Escape
  useEffect(() => {
    if (!modalOpen) return
    const handler = (e) => { if (e.key === 'Escape') setModalOpen(false) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [modalOpen])

  const hasImage = image_url && !imgError

  const BannerMedia = ({ className = '', style = {} }) =>
    hasImage ? (
      <img
        src={image_url}
        alt={`באנר ${name}`}
        className={className}
        style={{ objectFit: 'cover', ...style }}
        onError={() => setImgError(true)}
      />
    ) : (
      <div
        className={`flex items-center justify-center ${className}`}
        style={{ background: CARRIER_GRADIENT[carrier] || '#ccc', ...style }}
      >
        <span className="text-white/80 text-lg font-bold">{name}</span>
      </div>
    )

  return (
    <>
      {/* Card */}
      <div
        className="bg-white rounded-xl border border-moca-border/40 overflow-hidden cursor-pointer
                   transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:scale-[1.01]"
        onClick={() => setModalOpen(true)}
      >
        <BannerMedia className="w-full" style={{ aspectRatio: '16/7' }} />
        <div className="px-3 py-2 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
          <span className="text-sm font-bold text-[#3b1f0d] truncate">{name}</span>
          <span className="mr-auto text-[11px] text-moca-muted">{formatDate(scraped_at)}</span>
        </div>
      </div>

      {/* Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setModalOpen(false) }}
        >
          <div className="bg-white rounded-2xl overflow-hidden w-[90vw] max-w-4xl shadow-2xl relative">
            <BannerMedia className="w-full" style={{ aspectRatio: '16/7' }} />

            <button
              className="absolute top-3 left-3 w-8 h-8 rounded-full bg-black/50 text-white
                         flex items-center justify-center hover:bg-black/70 transition-colors"
              onClick={() => setModalOpen(false)}
            >
              <X size={15} />
            </button>

            <div className="px-5 py-4 flex items-center gap-3">
              <div>
                <div className="text-base font-bold text-[#3b1f0d]">{name}</div>
                <div className="text-xs text-moca-muted">עודכן: {formatDate(scraped_at)}</div>
              </div>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="mr-auto flex items-center gap-2 bg-[#5c3317] hover:bg-[#7a4422]
                           text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink size={14} />
                פתח באתר הספק
              </a>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 2: Verify the component renders without errors**

We'll validate this in the next task when wiring it into DashboardPage.

- [ ] **Step 3: Commit**

```bash
git add src/components/BannerCard.jsx
git commit -m "feat: BannerCard component with modal and fallback gradient"
```

---

## Task 6: Add "באנרים ראשיים" tab to DashboardPage.jsx

**Files:**
- Modify: `mass-market-app/src/pages/DashboardPage.jsx`

### 6a — Add Camera icon import

- [ ] **Step 1: Find the Lucide icons import in DashboardPage.jsx**

It should look like:
```js
import { Globe, Smartphone, ... } from 'lucide-react'
```

- [ ] **Step 2: Add `Camera` to the import**

```js
import { Globe, Smartphone, ..., Camera } from 'lucide-react'
```

### 6b — Add tab definition

- [ ] **Step 3: Add the new tab to the TABS array (lines ~86-91)**

```js
const TABS = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad',   label: 'חו"ל' },
  { id: 'global',   label: 'גלובלי' },
  { id: 'content',  label: 'תוכן' },
  { id: 'banners',  label: 'באנרים ראשיים' },   // ← add this line
]
```

- [ ] **Step 4: Add icon to TAB_ICONS**

Find the `TAB_ICONS` object and add:
```js
banners: <Camera size={16} />,
```

### 6c — Add state

- [ ] **Step 5: Add banners state near the other `useState` declarations (around line 127)**

```js
const [banners, setBanners] = useState([])
const [bannersLoaded, setBannersLoaded] = useState(false)
```

### 6d — Add import for BannerCard

- [ ] **Step 6: Add import at the top of the file with the other component imports**

```js
import BannerCard from '../components/BannerCard'
```

### 6e — Wire data loading

- [ ] **Step 7: Add a new `else if` branch inside the `loadTab` function (after the content branch, around line 233)**

```js
} else if (t === 'banners' && !bannersLoaded) {
  const data = await api.getBanners()
  setBanners(data)
  setBannersLoaded(true)
}
```

### 6f — Add render section

- [ ] **Step 8: Add the banners render section after the content tab render block (after line ~848)**

```jsx
{!loading && tab === 'banners' && (
  <div>
    {/* info strip */}
    <div className="mb-4 px-1 flex items-center gap-2 text-xs text-moca-muted">
      <Camera size={13} />
      <span>צילומי מסך אוטומטיים של עמוד הבית של כל ספק — מתעדכנים כל יום בשעה 08:00</span>
    </div>

    {bannersLoaded && banners.length === 0 && (
      <div className="text-center text-moca-muted py-16 text-sm">
        אין באנרים זמינים עדיין — הם יצולמו בשעה 08:00
      </div>
    )}

    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {banners.map(banner => (
        <BannerCard key={banner.carrier} banner={banner} />
      ))}
    </div>
  </div>
)}
```

### 6g — Build and verify

- [ ] **Step 9: Run the build**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build
```

Expected: Build completes with no errors.

- [ ] **Step 10: Start the dev server and verify the tab appears**

```bash
npm run dev
```

Navigate to `http://localhost:5173`, click "באנרים ראשיים" tab. Expected:
- Tab appears and is clickable
- Info strip shows with camera icon
- If PNGs exist in `data/banners/`, cards show screenshots
- If not, cards show colored gradient fallbacks
- Clicking a card opens the modal with the carrier's name + "פתח באתר הספק" button

- [ ] **Step 11: Commit**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
git add src/pages/DashboardPage.jsx src/components/BannerCard.jsx src/lib/api.js
git commit -m "feat: באנרים ראשיים tab — daily homepage screenshots grid"
```

---

## Task 7: Final build + manual end-to-end test

- [ ] **Step 1: Run a full screenshot scrape to populate images**

```python
# In Python REPL at project root:
from scraper import scrape_carrier_banners
results = scrape_carrier_banners("data/banners")
for r in results:
    print(r['carrier'], '✓' if r['success'] else '✗')
```

- [ ] **Step 2: Restart Flask**

```bash
taskkill /F /IM python.exe
python app.py
```

- [ ] **Step 3: Verify `/api/banners`**

```
GET http://localhost:5000/api/banners
```

Expected: 8 objects, `image_url` is `/banners/<carrier>.png` for each that succeeded, `scraped_at` is a recent ISO timestamp.

- [ ] **Step 4: Verify static PNG route**

```
GET http://localhost:5000/banners/partner.png
```

Expected: PNG image served (200).

- [ ] **Step 5: Verify React UI end-to-end**

1. Open `http://localhost:5173`
2. Click "באנרים ראשיים" tab
3. Confirm 8 cards appear with real screenshots
4. Click a card → modal opens with full-size image
5. Click "פתח באתר הספק" → carrier website opens in new tab
6. Press Escape → modal closes
7. Click outside modal → modal closes

- [ ] **Step 6: Production build**

```bash
cd "D:\השוואת MASS MARKET\mass-market-app"
npm run build
```

Expected: Clean build, no warnings about missing imports.

- [ ] **Step 7: Final commit**

```bash
cd "D:\השוואת MASS MARKET"
git add -A
git commit -m "feat: באנרים ראשיים — complete implementation"
```
