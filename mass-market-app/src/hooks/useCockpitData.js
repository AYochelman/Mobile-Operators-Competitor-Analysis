import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'

/**
 * Data layer for the executive cockpit (/cockpit).
 *
 * Everything here reads EXISTING public endpoints — no backend change:
 *   /api/plans, /api/changes, /api/abroad-plans, /api/abroad-changes,
 *   /api/global-plans, /api/market-movers, /api/history/daily,
 *   /api/executive-summary
 *
 * The derivations below are exported as pure functions so they can be smoke-
 * tested in node the same way useDashboardPlans.js is:
 *   npx esbuild src/hooks/useCockpitData.js --bundle --platform=node
 */

// ── small numeric helpers ────────────────────────────────────────────────

export function median(nums) {
  const a = (nums || []).filter((n) => Number.isFinite(n)).sort((x, y) => x - y)
  if (!a.length) return null
  const mid = a.length >> 1
  return a.length % 2 ? a[mid] : (a[mid - 1] + a[mid]) / 2
}

function round(n, d = 2) {
  if (!Number.isFinite(n)) return null
  const f = 10 ** d
  return Math.round(n * f) / f
}

function pctDiff(value, base) {
  if (!Number.isFinite(value) || !Number.isFinite(base) || base <= 0) return null
  return round(((value - base) / base) * 100, 1)
}

/**
 * Filter out spurious change events caused by upstream data-quality issues —
 * an XPhone scrape whose price regex returned null records a "29.90 → NULL"
 * price_change. Same guard as useDashboardData.js: a price_change is only
 * meaningful when BOTH sides are positive numbers. Other change types have
 * known-null sides by design and pass through.
 */
export function isValidChange(c) {
  if (!c?.change_type) return false
  if (c.change_type === 'price_change') {
    const o = Number(c.old_val)
    const n = Number(c.new_val)
    return Number.isFinite(o) && o > 0 && Number.isFinite(n) && n > 0
  }
  if (c.change_type === 'new_plan') {
    const n = Number(c.new_val)
    return Number.isFinite(n) && n > 0
  }
  return true
}

// ── 1. competitive ladder: blended ₪/GB per carrier ──────────────────────

/**
 * GB-weighted blended price-per-GB per carrier: SUM(price) / SUM(GB).
 *
 * Mirrors compute_executive_metrics() in db.py deliberately — a naive
 * AVG(price/data_gb) is an average-of-ratios, where one tiny-data plan (019's
 * 100MB "חבילת עשר" at ~102 ₪/GB) dominates the mean and falsely ranks a
 * budget carrier as the market's most expensive. Weighting by GB lets large
 * plans count proportionally, which is the intuitively correct blended rate.
 *
 * data_gb === null means UNLIMITED (see the root CLAUDE.md data_gb contract),
 * so those rows carry no divisor and are excluded — same as the SQL's
 * `WHERE data_gb > 0`.
 */
export function blendedPpgb(plans) {
  const acc = new Map()
  for (const p of plans || []) {
    const price = Number(p?.price)
    const gb = Number(p?.data_gb)
    if (!Number.isFinite(price) || price <= 0) continue
    if (!Number.isFinite(gb) || gb <= 0) continue
    const cur = acc.get(p.carrier) || { sumPrice: 0, sumGb: 0, plans: 0, best: Infinity }
    cur.sumPrice += price
    cur.sumGb += gb
    cur.plans += 1
    cur.best = Math.min(cur.best, price / gb)
    acc.set(p.carrier, cur)
  }
  const out = []
  for (const [carrier, v] of acc) {
    if (v.sumGb <= 0) continue
    out.push({
      carrier,
      ppgb: round(v.sumPrice / v.sumGb, 2),
      best: round(v.best, 2),
      plans: v.plans,
    })
  }
  return out.sort((a, b) => a.ppgb - b.ppgb)
}

/**
 * The positioning ladder + where we sit on it.
 * Rank 1 = cheapest blended ₪/GB.
 */
export function buildLadder(plans, oursCarrier) {
  const ladder = blendedPpgb(plans)
  const marketMedian = median(ladder.map((r) => r.ppgb))
  const cheapest = ladder[0] || null
  const idx = oursCarrier ? ladder.findIndex((r) => r.carrier === oursCarrier) : -1
  const ours = idx >= 0 ? ladder[idx] : null
  return {
    ladder,
    marketMedian: round(marketMedian, 2),
    cheapest,
    ours,
    rank: idx >= 0 ? idx + 1 : null,
    total: ladder.length,
    vsMedianPct: ours ? pctDiff(ours.ppgb, marketMedian) : null,
    vsCheapestPct: ours && cheapest ? pctDiff(ours.ppgb, cheapest.ppgb) : null,
  }
}

// ── 2. period activity: what actually moved ──────────────────────────────

/**
 * Counts of material events inside the window, across every tracked category.
 * `drops` / `rises` are competitor-inclusive; `oursDrops` isolates our own
 * moves so the exec can tell market pressure from our own pricing actions.
 */
export function buildActivity(changeSets, days, oursCarrier) {
  const since = Date.now() - days * 24 * 60 * 60 * 1000
  const out = {
    drops: 0, rises: 0, newPlans: 0, removed: 0,
    oursDrops: 0, oursRises: 0, total: 0,
    byCarrier: new Map(),
  }
  for (const [scope, changes] of Object.entries(changeSets || {})) {
    for (const c of changes || []) {
      if (!isValidChange(c)) continue
      const ts = c?.changed_at ? new Date(c.changed_at).getTime() : 0
      if (!ts || ts < since) continue
      const isOurs = oursCarrier && c.carrier === oursCarrier
      let kind = null
      if (c.change_type === 'price_change') {
        kind = Number(c.new_val) < Number(c.old_val) ? 'drop' : 'rise'
        if (kind === 'drop') { out.drops++; if (isOurs) out.oursDrops++ } else { out.rises++; if (isOurs) out.oursRises++ }
      } else if (c.change_type === 'new_plan') {
        kind = 'new'; out.newPlans++
      } else if (c.change_type === 'removed_plan') {
        kind = 'removed'; out.removed++
      } else {
        continue // extras/details changes are noise at exec altitude
      }
      out.total++
      const row = out.byCarrier.get(c.carrier) || { carrier: c.carrier, drops: 0, rises: 0, newPlans: 0, removed: 0, scopes: new Set() }
      if (kind === 'drop') row.drops++
      else if (kind === 'rise') row.rises++
      else if (kind === 'new') row.newPlans++
      else if (kind === 'removed') row.removed++
      row.scopes.add(scope)
      out.byCarrier.set(c.carrier, row)
    }
  }
  return out
}

// ── 3. trend: the market ₪/GB index over time ────────────────────────────

/**
 * Turn price_history_daily rows into a two-line series: our carrier's best
 * ₪/GB vs the market median of every carrier's best ₪/GB, per day.
 *
 * Guards:
 *  - `carrier === '*'` rows are the market-wide aggregate maintenance.py also
 *    writes; including them would double-count, so the median is recomputed
 *    from the per-carrier rows only.
 *  - A day where fewer than 3 carriers reported is a partially-built
 *    aggregate, not a market — dropping it stops a half-finished
 *    maintenance run from spiking the line.
 */
export function buildTrend(rows, oursCarrier) {
  const byDay = new Map()
  for (const r of rows || []) {
    if (!r?.day || r.carrier === '*') continue
    const ppgb = Number(r.min_ppgb)
    if (!Number.isFinite(ppgb) || ppgb <= 0) continue
    let slot = byDay.get(r.day)
    if (!slot) { slot = { day: r.day, vals: [], ours: null }; byDay.set(r.day, slot) }
    slot.vals.push(ppgb)
    if (oursCarrier && r.carrier === oursCarrier) slot.ours = ppgb
  }
  return [...byDay.values()]
    .filter((d) => d.vals.length >= 3)
    .sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0))
    .map((d) => ({
      day: d.day,
      market: round(median(d.vals), 2),
      ours: d.ours == null ? null : round(d.ours, 2),
      carriers: d.vals.length,
    }))
}

/** First→last % move of a trend series key, ignoring gaps. */
export function trendDelta(trend, key) {
  const pts = (trend || []).map((d) => d[key]).filter((n) => Number.isFinite(n))
  if (pts.length < 2) return null
  return pctDiff(pts[pts.length - 1], pts[0])
}

// ── 4. signals: threat / opportunity / attention ─────────────────────────

/**
 * The three things an exec should read before anything else. Each returns
 * null rather than a filler value when the data doesn't support a claim —
 * an empty slot is honest, an invented "threat" is not.
 */
export function buildSignals({ activity, ladderInfo, freshness, oursCarrier, days }) {
  const signals = {}

  // Threat — the competitor that cut the most prices in the window.
  let threat = null
  for (const row of activity.byCarrier.values()) {
    if (oursCarrier && row.carrier === oursCarrier) continue
    if (row.drops < 2) continue // one cut is not a campaign
    if (!threat || row.drops > threat.drops) threat = row
  }
  signals.threat = threat
    ? { carrier: threat.carrier, drops: threat.drops, newPlans: threat.newPlans, days }
    : null

  // Opportunity — the cheapest blended rate on the market and the gap to it.
  const { cheapest, ours, vsCheapestPct } = ladderInfo
  signals.opportunity = cheapest
    ? {
        carrier: cheapest.carrier,
        ppgb: cheapest.ppgb,
        gapPct: vsCheapestPct,
        weLead: !!(ours && cheapest.carrier === oursCarrier),
      }
    : null

  // Attention — data we cannot stand behind. 36h mirrors the backend's
  // morning_check_stale_hours; global gets 72h (morning_check_global_stale_hours)
  // because per-country providers scrape partially on every run.
  const stale = (freshness || []).filter((f) => f.hours != null && f.hours > f.limit)
  signals.attention = stale.length ? { stale } : null

  return signals
}

/** Hours since the newest scraped_at in a plan list. */
function hoursSince(plans) {
  let newest = 0
  for (const p of plans || []) {
    const ts = p?.scraped_at ? new Date(p.scraped_at).getTime() : 0
    if (ts > newest) newest = ts
  }
  if (!newest) return null
  return Math.max(0, Math.round((Date.now() - newest) / 3_600_000))
}

// ── the hook ─────────────────────────────────────────────────────────────

const DAY_MS = 24 * 60 * 60 * 1000

function isoDay(offsetDays) {
  return new Date(Date.now() - offsetDays * DAY_MS).toISOString().slice(0, 10)
}

/**
 * @param {string|null} oursCarrier  workspace.mvno_carrier — null renders the
 *                                   whole page at market level (no "us" lines).
 * @param {number} days              lookback window (7 / 30 / 90)
 */
export function useCockpitData(oursCarrier, days = 30) {
  const [raw, setRaw] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    // Each source degrades independently — one dead endpoint must not blank
    // the page. The executive summary 404s until the 08:05 job has run once,
    // and /api/history/daily is empty until maintenance.run_daily has.
    const soft = (p) => p.then((v) => v).catch(() => null)

    Promise.all([
      soft(api.getPlans()),
      soft(api.getChanges(500)),
      soft(api.getAbroadPlans()),
      soft(api.getAbroadChanges()),
      soft(api.getGlobalPlans()),
      soft(api.getMarketMovers(days, 8, ['domestic', 'abroad', 'global'])),
      soft(api.getHistoryDaily('domestic', { from: isoDay(days) })),
      soft(api.getExecutiveSummary()),
    ])
      .then(([plans, changes, abroadPlans, abroadChanges, globalPlans, movers, daily, execSummary]) => {
        if (cancelled) return
        setRaw({
          plans: Array.isArray(plans) ? plans : [],
          changes: Array.isArray(changes) ? changes : [],
          abroadPlans: Array.isArray(abroadPlans) ? abroadPlans : [],
          abroadChanges: Array.isArray(abroadChanges) ? abroadChanges : [],
          globalPlans: Array.isArray(globalPlans) ? globalPlans : [],
          movers: movers?.movers || [],
          daily: daily?.rows || [],
          execSummary: Array.isArray(execSummary) ? execSummary : [],
        })
        setLoading(false)
      })
      .catch((e) => {
        if (cancelled) return
        setError(e?.message || 'load failed')
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [days, reloadKey])

  const derived = useMemo(() => {
    if (!raw) return null

    const ladderInfo = buildLadder(raw.plans, oursCarrier)
    const activity = buildActivity(
      { domestic: raw.changes, abroad: raw.abroadChanges },
      days,
      oursCarrier,
    )
    const trend = buildTrend(raw.daily, oursCarrier)

    const freshness = [
      { id: 'domestic', label: 'סלולר', labelEn: 'Domestic', hours: hoursSince(raw.plans), limit: 36 },
      { id: 'abroad', label: 'חו״ל', labelEn: 'Roaming', hours: hoursSince(raw.abroadPlans), limit: 36 },
      { id: 'global', label: 'eSIM גלובלי', labelEn: 'Global eSIM', hours: hoursSince(raw.globalPlans), limit: 72 },
    ]

    const signals = buildSignals({ activity, ladderInfo, freshness, oursCarrier, days })

    // The cached AI read-out for the domestic market (generated 08:05).
    const narrative = (raw.execSummary || []).find((r) => r.category === 'domestic') || null

    return {
      ladderInfo,
      activity,
      trend,
      marketTrendPct: trendDelta(trend, 'market'),
      oursTrendPct: trendDelta(trend, 'ours'),
      movers: raw.movers,
      freshness,
      signals,
      narrative,
      counts: {
        domestic: raw.plans.length,
        abroad: raw.abroadPlans.length,
        global: raw.globalPlans.length,
        carriers: ladderInfo.total,
      },
    }
  }, [raw, oursCarrier, days])

  return { loading, error, data: derived, reload }
}

export default useCockpitData
