# Maya Affiliate API — Partner Reference (digest)

Source: `Maya Affiliate API — Partner Reference-1.pdf` (v0.2, DRAFT, AI-generated, last updated 2026-06-29).
Reviewed 2026-07-03. Authoritative questions → **jean.m@maya.net** (partnerships contact is Bart, bskrzypek@maya.net).

## Endpoint
- `GET https://assets.maya.net/affiliates/plans.json`
- No auth. JSON. Static CDN, ~92 KB. Regenerated on Maya's schedule; **weekly poll is enough, there is no real-time variant.**
- Root keys: `plans` (8 objects), `supportedCurrencies` (15 ISO 4217), `provider` ({name, logoUrl, supportUrl}).

## Catalog (8 plans, all UNLIMITED + FUP 5GB/day then 3Mbps)
| Plan | Validity | USD |
|------|----------|-----|
| 3 Days Unlimited Global | 3 | 9.99 |
| 7 Days Unlimited Global | 7 | 19.99 |
| 14 Days Unlimited Global (POPULAR) | 14 | 27.99 |
| 30 Days Unlimited Global (BEST VALUE) | 30 | 49.99 |
| 3 Days Global + Cruise | 3 | 49.99 |
| 7 Days Global + Cruise | 7 | 109.99 |
| 14 Days Global + Cruise (POPULAR) | 14 | 160.99 |
| 30 Days Global + Cruise (BEST VALUE) | 30 | 299.99 |

- `regionType`: `global` or `cruise`. Cruise = land+sea (same ~165 countries PLUS `supportedCruises` ships), not sea-only.
- Numeric cap fields removed in v0.2 (all unlimited) — read `fupDescription` free-text for throttling.
- Country codes are ISO 3166-1 **alpha-3** (USA/GBR/DEU). `supportedCountries` denormalized per plan (all 8 share the set — dedupe on import).
- Prices locally set per currency (not FX-derived); `priceDiscounted` == `priceOriginal` unless an affiliate promo is active.
- Display name: use "Maya" / "Maya Mobile" (legal entity `provider.name` = "Mobile Maya Inc").

## Affiliate linking (the one actionable takeaway)
- Each plan's `url` is a **clean maya.net link with NO tracking** — publishing it raw earns NO commission.
- Maya runs **exclusively through Impact**. Correct approach: generate an Impact **TrackingLink per plan** (wrap each plan's `url`), or pull them via the Impact API.

## Our status vs. the doc
- `scrape_maya_global` (scraper.py) already reads this exact feed → 8 rows in `global_plans` (verified 2026-07-03). Fully aligned.
- We publish the Impact-wrapped link (`mayamobile.pxf.io/oNV1xn`) via `affiliateLinks.js` + `config.affiliate.maya`, never a raw maya.net URL → **attribution is safe**.
- **Per-plan deep-links — DONE 2026-07-03.** Generated 8 Impact TrackingLinks (one per plan URL) via the Impact "Create a link" tool, wired into `app.py` (`_MAYA_PLAN_DEEPLINKS` + `_maya_deeplink_url`, keyed by region+days parsed from `plan_name`). `/go/maya?plan=…` now deep-links to the exact plan page (covers the B2C `/esim-deals` page + hotel guest portals; the internal dashboard keeps the generic link, same as Saily). `/go/maya` with no plan still falls back to the generic `oNV1xn`. Verified live: 302 per plan + all 8 short links resolve to their plan page carrying `irpid=7205658`.

### The 8 per-plan TrackingLinks (region · days → code)
| global 3d `VOgJBM` | global 7d `vDW5Qy` | global 14d `4a2zyr` | global 30d `NGX5Rb` |
| cruise 3d `yZWajb` | cruise 7d `MKgP22` | cruise 14d `KBgrOy` | cruise 30d `7XdEnd` |

All under `https://mayamobile.pxf.io/<code>`. Generic (plans page) fallback: `oNV1xn`.
