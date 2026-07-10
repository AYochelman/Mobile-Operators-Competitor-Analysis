# MOCA Landing Page - Build Spec

**Decision (2026-06-05):** Public marketing landing page at `mocaintel.com/` built INTO the React app (`mass-market-app/`). Logged-in users hitting `/` → redirect to dashboard. Anonymous users → see the landing. Primary CTA → pilot request (→ `/login` or a contact action). App stays behind login.

**Source of verbatim Hebrew copy:** `pitch/index.html` (the existing polished standalone landing - adapt its content into a React component using the MOCA design system / Tailwind tokens in `index.css`).

## ✅ Verified numbers - USE THESE (others in old docs are stale)
| Fact | USE | NOT |
|---|---|---|
| Domestic operators | **10** | 8 |
| Global eSIM providers | **20+** | 14 / 27 |
| Scrapes/day | **2×** (07:30 + 17:00) | 10:00/16:00 |
| Pricing /mo (pre-VAT) | **₪5,000 / ₪8,500 / ₪12,000** | ₪490/990/2,490 |
| Pilot | **14 days, 3 competitors, free** | - |
| Cancellation | **30-day notice** | - |
| Live URL | **mocaintel.com** | ngrok/render |

## Pricing tiers (authoritative - build_saas_agreement.py + deck slide 9)
- **בסיס / Starter - ₪5,000/mo:** עד 3 מתחרים · מעקב מחירים יומי · התראות וואטסאפ
- **מקצועי / Pro - ₪8,500/mo:** כל 10 המפעילים · + ניטור באנרים · מכונת זמן · ניתוחי AI · התראות בזמן אמת
- **Enterprise - ₪12,000/mo:** שוק מלא כולל נדידה/eSIM · + API · סביבת עבודה ממותגת · תמיכה מוגברת
- כל המדרגות: פיילוט חינם שבועיים על 3 מתחרים.

## Section order (from pitch/index.html)
1. **Hero** - headline + lede + stats strip (10 מפעילים · 20+ eSIM · 2× ביום · דקות מאירוע להתראה) + CTA button.
2. **Pain points** - 4 ✕ cards (זמן תגובה / כיסוי חלקי / אין היסטוריה / עלות מחקר).
3. **"What MOCA does instead"** - 4-beat (סורקת / מזהה / מתריאה / מציגה).
4. **Features grid** - 6 (מעקב מחירים · ניטור קמפיינים · הגנת נדידה ו-eSIM · התראות בזמן אמת · מכונת זמן · ניתוח AI).
5. **eSIM/roaming spotlight** - "הכנסות הנדידה שלך נשחקות…" (strongest differentiator).
6. **Differentiation table** - תדירות / היקף / מהירות / היסטוריה / תובנות (today vs MOCA).
7. **Pricing** - 3 tiers above.
8. **Pilot CTA** - eyebrow "הצעת פיילוט" · "שבועיים. שלושה מתחרים. אפס סיכון." · button "בוא נתחיל פיילוט →" · note "המערכת כבר רצה בפרודקשן…".

## Headlines / slogans (verbatim, pick for hero)
- Primary: **"כל מהלך תחרותי בשוק הסלולר - על המסך שלך, לפני שהוא משפיע עליך."**
- Slogan / kicker: **"תפסיק לגלוש. תתחיל לדעת."**
- Lede: "מערכת מודיעין תחרותי שעוקבת אוטומטית אחרי כל השוק - פעמיים ביום - ושולחת התראה ברגע שמתחרה מזיז מחיר, מחליף קמפיין או משיק חבילה."

## Notes
- Audience: Israeli carrier marketing execs (VP Marketing / CMO). Hebrew, RTL.
- No customer logos/testimonials exist - do NOT fabricate. Use "כבר רץ בפרודקשן" + scale stats as proof.
- Legality reassurance block optional: "מידע גלוי לציבור… לא חדירה."
- Design: MOCA mocha-latte tokens (`--color-moca-*`), `--font-display` (Frank Ruhl Libre) for headings, `--font-body` (Assistant). Reuse `Logo.jsx`.
- Full brief lived in the research-agent output this session; this spec is the distilled build target.
