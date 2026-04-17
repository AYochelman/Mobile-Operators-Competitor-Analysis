# Spec: PWA — Progressive Web App for MOCA

**תאריך:** 2026-04-17  
**טכנולוגיה:** `vite-plugin-pwa` + Workbox  
**מטרה:** הפוך את MOCA לאפליקציה installable עם תמיכה ב-offline (cache-first עם banner)

---

## מטרה

לאפשר למשתמשים להוסיף את MOCA למסך הבית של הטלפון (Android + iOS) ולקבל חוויה של אפליקציה native — כולל טעינה מהירה ותמיכה ב-offline שמציגה את המחירים האחרונים שנטענו עם הודעה מתאימה.

---

## מה קיים כבר

- `public/manifest.json` — בסיסי (name, short_name, start_url, display, icons 192/512)
- `public/icons/icon-180.png`, `icon-192.png`, `icon-512.png`
- `index.html` — `<link rel="manifest">`, `<meta name="theme-color">`, apple-mobile-web-app tags

**מה חסר:** Service Worker (הרכיב הקריטי ל-installability + offline).

---

## ארכיטקטורה

```
Build time:
  vite-plugin-pwa → מייצר sw.js אוטומטית דרך Workbox
  Workbox precaches את כל ה-app shell (HTML/JS/CSS)

Runtime:
  App Shell   → CacheFirst (תמיד מהיר)
  API calls   → NetworkFirst + cache fallback (24h expiry)
  Static assets → CacheFirst (7 ימים)

Offline flow:
  navigator.onLine === false
    → API calls נכשלות → Workbox מחזיר מ-cache
    → useOnlineStatus hook → isOnline = false
    → OfflineBanner מוצג: "⚡ אין חיבור — מציג נתונים אחרונים"
  navigator.onLine === true (חזרה לרשת)
    → isOnline = true → Banner נעלם אוטומטית
```

---

## קבצים

### חדשים
| קובץ | תוכן |
|------|-------|
| `src/hooks/useOnlineStatus.js` | `navigator.onLine` + event listeners ל-`online`/`offline` |
| `src/components/OfflineBanner.jsx` | רצועה עם הודעת offline |

### משתנים
| קובץ | שינוי |
|------|-------|
| `vite.config.js` | הוספת `VitePWA()` plugin עם Workbox config |
| `package.json` | `npm install vite-plugin-pwa` |
| `public/manifest.json` | הוספת `description`, `categories`, `orientation` |
| `index.html` | שינוי `apple-mobile-web-app-title` ל-"MOCA" |
| `src/App.jsx` | הוספת `<OfflineBanner />` בראש ה-layout |

---

## Service Worker — Workbox config

```js
VitePWA({
  registerType: 'autoUpdate',
  includeAssets: ['favicon.svg', 'icons/*.png', 'logos/*.png'],
  manifest: false, // קובץ manifest.json כבר קיים ב-public/
  workbox: {
    globPatterns: ['**/*.{js,css,html,svg,png}'],
    runtimeCaching: [
      {
        // API — NetworkFirst עם 24h cache
        urlPattern: /\/api\/(plans|abroad-plans|global-plans|content-plans|changes|abroad-changes)/,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'api-data-cache',
          networkTimeoutSeconds: 5,
          expiration: { maxEntries: 20, maxAgeSeconds: 86400 },
          cacheableResponse: { statuses: [0, 200] }
        }
      },
      {
        // Banners + logos — CacheFirst 7 ימים
        urlPattern: /\/(banners|logos|icons)\//,
        handler: 'CacheFirst',
        options: {
          cacheName: 'static-assets-cache',
          expiration: { maxEntries: 100, maxAgeSeconds: 604800 },
          cacheableResponse: { statuses: [0, 200] }
        }
      }
    ]
  }
})
```

**לא נכנסים ל-cache:** `/api/scrape-*`, `/api/chat`, `/api/affiliate/stats`, `/go/*`

---

## useOnlineStatus hook

```js
// src/hooks/useOnlineStatus.js
import { useState, useEffect } from 'react'

export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  useEffect(() => {
    const up   = () => setIsOnline(true)
    const down = () => setIsOnline(false)
    window.addEventListener('online',  up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online',  up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return isOnline
}
```

---

## OfflineBanner component

```jsx
// src/components/OfflineBanner.jsx
import { useOnlineStatus } from '../hooks/useOnlineStatus'

export default function OfflineBanner() {
  const isOnline = useOnlineStatus()
  if (isOnline) return null
  return (
    <div className="w-full bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-sm text-amber-800 font-medium">
      ⚡ אין חיבור לאינטרנט — מציג נתונים אחרונים
    </div>
  )
}
```

מיקום: `src/App.jsx`, מעל ל-`<Router>` / `<Layout>` — מוצג בכל עמוד.

---

## manifest.json — שדות להוספה

```json
{
  "description": "השוואת מחירי חבילות סלולר ו-eSIM גלובלי לישראלים",
  "categories": ["utilities", "finance"],
  "orientation": "portrait-primary"
}
```

---

## Edge Cases

| מצב | התנהגות |
|-----|---------|
| אין cache עדיין (פתיחה ראשונה offline) | App shell נטען (precached), API calls נכשלות — רשימות ריקות עם state ריק רגיל |
| חזרה לרשת | Banner נעלם, הנתונים יתרעננו בטעינה הבאה |
| SW גרסה חדשה זמינה | `registerType: 'autoUpdate'` — מתעדכן ב-background, יחיל בפתיחה הבאה |
| iOS Safari | install דרך "Add to Home Screen" ידני — אין `beforeinstallprompt`. Banner לא רלוונטי כאן |
| ngrok redirect (302) | Workbox מטפל ב-`cacheableResponse: { statuses: [0, 200] }` — opaque responses נשמרות |

---

## מה לא בסקופ

- Push notifications (כבר קיים דרך Web Push נפרד)
- Background sync
- Install prompt UI ("`beforeinstallprompt`") — הדפדפן מציג prompt ילידי
- App Store (Google Play דרך Capacitor) — שלב ב׳ אם יש ביקוש
