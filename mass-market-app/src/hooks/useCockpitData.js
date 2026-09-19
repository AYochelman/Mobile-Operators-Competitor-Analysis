import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { materialDiff } from '../lib/benefitDiff'

/**
 * Data layer for the executive cockpit (/cockpit).
 *
 * Everything here reads EXISTING public endpoints — no backend change:
 *   /api/plans, /api/changes, /api/abroad-plans, /api/abroad-changes,
 *   /api/history/daily
 *
 * The derivations are exported as pure functions so they can be smoke-tested
 * in node the same way useDashboardPlans.js is:
 *   npx esbuild src/hooks/useCockpitData.js --bundle --platform=node
 *
 * v2 (owner feedback): the ₪/GB ratio is gone. The page now speaks in two
 * plain measures — what a package COSTS (₪/month, median list price) and what
 * it GIVES (GB, median volume) — plus a fixed 7-day rubric of competitor moves.
 */

// ── small numeric helpers ────────────────────────────────────────────────

export function median(nums) {
  const a = (nums || []).filter((n) => Number.isFinite(n)).sort((x, y) => x - y)
  if (!a.length) return null
  const mid = a.length >> 1
  return a.length % 2 ? a[mid] : (a[mid - 1] + a[mid]) / 2
}

/**
 * Median that lets +Infinity take part — an unlimited plan is "more than any
 * number", so a carrier whose typical package is unlimited must come out as
 * Infinity, not be dropped. Even count: if either middle value is Infinity the
 * median is Infinity; otherwise the mean of the two.
 */
export function medianWithInf(vals) {
  const a = (vals || []).filter((n) => n === Infinity || Number.isFinite(n)).sort((x, y) => x - y)
  if (!a.length) return null
  const mid = a.length >> 1
  if (a.length % 2) return a[mid]
  const lo = a[mid - 1], hi = a[mid]
  if (lo === Infinity || hi === Infinity) return Infinity
  return (lo + hi) / 2
}

function round(n, d = 2) {
  if (!Number.isFinite(n)) return n === Infinity ? Infinity : null
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

// ── 1. plan classification (mirrors api/mobile.py) ───────────────────────

// /api/plans is the RAW table; the consumer endpoint normalises these quirks
// server-side (api/mobile.py) and this mirrors its rules exactly:
//   · data_gb >= 9999 → unlimited (wecom encodes "גלישה חופשית" as 10000GB)
//   · data_gb NULL    → unlimited by the dashboard convention, EXCEPT the
//     voice-only kosher plans, which are the only live NULL rows in practice
//   · 0 < data_gb < 1 → a sub-GB voice-first plan (019's 100MB "חבילת עשר")
export const UNLIMITED_SENTINEL_GB = 9999
const RE_KOSHER = /כשר|נטפרי|ועד הרבנים|KOSHER/i
const RE_NO_DATA = /ללא גלישה/

export function classifyPlan(p) {
  const price = Number(p?.price)
  if (!Number.isFinite(price) || price <= 0) return { kind: 'invalid', price: null, gb: null }
  const raw = p?.data_gb
  const gb = raw == null ? null : Number(raw)
  if (gb != null && Number.isFinite(gb) && gb >= UNLIMITED_SENTINEL_GB) return { kind: 'unlimited', price, gb: null }
  if (gb == null || !Number.isFinite(gb)) {
    const extras = Array.isArray(p?.extras) ? p.extras : []
    const hay = [p?.plan_name || '', ...extras.filter((e) => typeof e === 'string' && !e.startsWith('__info__|'))].join(' ')
    if (RE_KOSHER.test(hay) || RE_NO_DATA.test(hay)) return { kind: 'voice', price, gb: null }
    return { kind: 'unlimited', price, gb: null }
  }
  if (gb <= 0) return { kind: 'invalid', price, gb: null }
  if (gb < 1) return { kind: 'subgb', price, gb }
  return { kind: 'limited', price, gb }
}

// ── 2. cost & volume ladder ──────────────────────────────────────────────

/**
 * Per carrier: the MEDIAN list price of its packages (₪/month) and the MEDIAN
 * data volume (GB) — two plain measures, never a ratio.
 *
 *  · cost   = median(price) over limited + unlimited plans. Promo prices are
 *             ignored (list price only). Voice-only and sub-GB rows are not
 *             "packages" in the sense a VP means, so they are excluded from
 *             BOTH measures and their count is disclosed on screen.
 *  · volume = medianWithInf(GB) where every unlimited plan counts as
 *             +Infinity, so a carrier whose typical package is unlimited
 *             reads "ללא הגבלה" instead of being silently under-reported.
 *
 * Rank 1 on cost = cheapest typical package; rank 1 on volume = most data
 * (Infinity first; ties share the rank).
 */
export function buildCostVolume(plans, oursCarrier) {
  const acc = new Map()
  for (const p of plans || []) {
    if (!p?.carrier) continue
    const c = classifyPlan(p)
    if (c.kind === 'invalid') continue
    let r = acc.get(p.carrier)
    if (!r) { r = { carrier: p.carrier, prices: [], vols: [], unlimitedCount: 0, excluded: 0, plans: 0, promo: 0 }; acc.set(p.carrier, r) }
    r.plans++
    if (Number(p.promo_price) > 0) r.promo++
    if (c.kind === 'voice' || c.kind === 'subgb') { r.excluded++; continue }
    r.prices.push(c.price)
    if (c.kind === 'unlimited') { r.unlimitedCount++; r.vols.push(Infinity) } else r.vols.push(c.gb)
  }

  const rows = []
  for (const r of acc.values()) {
    if (!r.prices.length) continue // sells only voice / sub-GB rows — no package to rank
    const vol = medianWithInf(r.vols)
    rows.push({
      carrier: r.carrier,
      cost: round(median(r.prices), 1),
      volume: vol === Infinity ? Infinity : round(vol, 0),
      unlimitedCount: r.unlimitedCount,
      packages: r.prices.length,
      excluded: r.excluded,
      plans: r.plans,
      promoCount: r.promo,
    })
  }
  rows.sort((a, b) => a.cost - b.cost || a.carrier.localeCompare(b.carrier))

  const n = rows.length
  const marketCost = round(median(rows.map((r) => r.cost)), 1)
  const marketVolumeRaw = medianWithInf(rows.map((r) => r.volume).filter((v) => v != null))
  const marketVolume = marketVolumeRaw === Infinity ? Infinity : round(marketVolumeRaw, 0)
  const unlimitedCarriers = rows.filter((r) => r.volume === Infinity).length

  const volGreater = (a, b) => (a === Infinity ? b !== Infinity : Number.isFinite(a) && Number.isFinite(b) && a > b)
  const rankVolOf = (row) => 1 + rows.filter((o) => o !== row && o.volume != null && volGreater(o.volume, row.volume)).length

  const ours = oursCarrier ? rows.find((r) => r.carrier === oursCarrier) || null : null
  // A rank among 1-2 carriers is not a positioning — the workspace hidden-carrier
  // filter can shrink the set that far. Suppress rather than print 'מקום 1 מתוך 2'.
  const rankable = n >= 3
  const rankCost = ours && rankable ? rows.indexOf(ours) + 1 : null
  const rankVol = ours && rankable && ours.volume != null ? rankVolOf(ours) : null

  const cheapest = rows[0] || null
  const mostGenerous = rows.slice().sort((a, b) => {
    if (a.volume === b.volume) return a.cost - b.cost
    if (a.volume == null) return 1
    if (b.volume == null) return -1
    return volGreater(a.volume, b.volume) ? -1 : 1
  })[0] || null

  // Segment defence: the competitor that gives MORE data at a typical price at
  // or below ours — the row a pricing VP has to answer. null when nobody does.
  let defender = null
  if (ours) {
    for (const r of rows) {
      if (r === ours || r.cost > ours.cost || r.volume == null) continue
      if (ours.volume != null && !volGreater(r.volume, ours.volume)) continue
      if (!defender || volGreater(r.volume, defender.volume) || (r.volume === defender.volume && r.cost < defender.cost)) defender = r
    }
  }

  return {
    rows, total: n, marketCost, marketVolume, unlimitedCarriers, rankable,
    ours, rankCost, rankVol,
    costGapPct: ours ? pctDiff(ours.cost, marketCost) : null,
    volumeGapPct: ours && Number.isFinite(ours.volume) && Number.isFinite(marketVolume) ? pctDiff(ours.volume, marketVolume) : null,
    cheapest, mostGenerous, defender,
    excludedTotal: rows.reduce((s, r) => s + r.excluded, 0),
  }
}

// ── 3. price trend (history has price aggregates only) ───────────────────

/**
 * price_history_daily → two lines: our carrier's mean list price vs the
 * market median of every carrier's mean, per day. History stores no GB
 * aggregate, so this is a COST trend only (the page says so in words).
 *
 * Guards:
 *  · `carrier === '*'` rows are maintenance.py's market-wide aggregate;
 *    including them would double-count, so the median is recomputed from
 *    the per-carrier rows only.
 *  · A day with fewer than 3 reporting carriers is a partially-built
 *    aggregate, not a market — dropping it stops a half-finished
 *    maintenance run from spiking the line.
 *  · A carrier-day whose plan_count is under half that carrier's maximum in
 *    the window is a partial scrape (its mean shifts with whichever plans
 *    happened to load), so it is skipped as well.
 */
export function buildPriceTrend(rows, oursCarrier) {
  const maxCount = new Map()
  for (const r of rows || []) {
    if (!r?.day || r.carrier === '*' || r.destination) continue
    const pc = Number(r.plan_count)
    if (Number.isFinite(pc) && pc > (maxCount.get(r.carrier) || 0)) maxCount.set(r.carrier, pc)
  }
  const byDay = new Map()
  for (const r of rows || []) {
    if (!r?.day || r.carrier === '*' || r.destination) continue
    const avg = Number(r.avg_price)
    if (!Number.isFinite(avg) || avg <= 0) continue
    const pc = Number(r.plan_count)
    const mx = maxCount.get(r.carrier) || 0
    if (Number.isFinite(pc) && mx > 0 && pc < mx * 0.5) continue
    let slot = byDay.get(r.day)
    if (!slot) { slot = { day: r.day, vals: [], ours: null, floor: null, floorCarrier: null }; byDay.set(r.day, slot) }
    slot.vals.push(avg)
    if (oursCarrier && r.carrier === oursCarrier) slot.ours = avg
    const mn = Number(r.min_price)
    if (Number.isFinite(mn) && mn > 0 && (slot.floor == null || mn < slot.floor)) { slot.floor = mn; slot.floorCarrier = r.carrier }
  }
  return [...byDay.values()]
    .filter((d) => d.vals.length >= 3)
    .sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0))
    .map((d) => ({
      day: d.day,
      market: round(median(d.vals), 1),
      ours: d.ours == null ? null : round(d.ours, 1),
      floor: d.floor == null ? null : round(d.floor, 1),
      floorCarrier: d.floorCarrier,
      carriers: d.vals.length,
    }))
}

/** First→last % move of a trend series key, ignoring gaps. */
export function trendDelta(trend, key) {
  const pts = (trend || []).map((d) => d[key]).filter((n) => Number.isFinite(n))
  if (pts.length < 2) return null
  return pctDiff(pts[pts.length - 1], pts[0])
}

// ── 4. weekly competitor changes (fixed 7-day rubric) ────────────────────

export const WEEK_MS = 7 * 24 * 60 * 60 * 1000
const KIND_ORDER = { drop: 0, new: 1, rise: 2, removed: 3, extras: 4 }

/**
 * What competitors did to their packages in the last 7 days — domestic +
 * roaming, our carrier excluded, grouped by carrier, ranked by impact.
 *
 *  · Window is FIXED at 7 days regardless of the page's chart picker.
 *  · Net-dedup per (scope, carrier, plan, type): a price that moved twice
 *    shows once as week-start → latest (net 0 = dropped), with `updates`.
 *  · A plan that was both launched and removed inside the week is a scraper
 *    flap, not a market event — both rows are dropped.
 *  · extras_change goes through materialDiff (lib/benefitDiff.js): reworded
 *    or reordered benefits with no change in essence are dropped, so
 *    "הטבות עודכנו" only appears when a benefit was really added/removed.
 *  · details_change is noise at this altitude and is skipped.
 *  · `truncated` flags a feed that hit its row cap inside the window, so the
 *    page can say the week may be incomplete instead of pretending.
 */
export function buildWeeklyChanges({ domestic, abroad }, oursCarrier, now = Date.now(), feedLimit = 500) {
  const since = now - WEEK_MS
  const byKey = new Map()
  let truncated = false

  for (const [scope, list] of [['domestic', domestic], ['abroad', abroad]]) {
    const arr = Array.isArray(list) ? list : []
    if (arr.length >= feedLimit) {
      let oldest = Infinity
      for (const c of arr) { const ts = c?.changed_at ? new Date(c.changed_at).getTime() : 0; if (ts && ts < oldest) oldest = ts }
      if (oldest > since) truncated = true
    }
    for (const c of arr) {
      if (!isValidChange(c) || c.change_type === 'details_change') continue
      if (oursCarrier && c.carrier === oursCarrier) continue
      const ts = c.changed_at ? new Date(c.changed_at).getTime() : 0
      if (!ts || ts < since) continue
      const key = `${scope}|${c.carrier}|${c.plan_name}|${c.change_type}`
      const cur = byKey.get(key)
      if (!cur) byKey.set(key, { scope, carrier: c.carrier, plan_name: c.plan_name, type: c.change_type, first: c, firstTs: ts, last: c, lastTs: ts, n: 1 })
      else {
        cur.n++
        if (ts < cur.firstTs) { cur.first = c; cur.firstTs = ts }
        if (ts > cur.lastTs) { cur.last = c; cur.lastTs = ts }
      }
    }
  }

  const flapKey = (e) => `${e.scope}|${e.carrier}|${e.plan_name}`
  const launched = new Set(), removed = new Set()
  for (const e of byKey.values()) {
    if (e.type === 'new_plan') launched.add(flapKey(e))
    if (e.type === 'removed_plan') removed.add(flapKey(e))
  }

  const rows = []
  for (const e of byKey.values()) {
    const fk = flapKey(e)
    if ((e.type === 'new_plan' || e.type === 'removed_plan') && launched.has(fk) && removed.has(fk)) continue
    const row = { scope: e.scope, carrier: e.carrier, plan_name: e.plan_name, ts: e.lastTs, updates: e.n }
    if (e.type === 'price_change') {
      const oldP = Number(e.first.old_val), newP = Number(e.last.new_val)
      if (!(oldP > 0 && newP > 0) || oldP === newP) continue
      row.kind = newP < oldP ? 'drop' : 'rise'
      row.oldPrice = oldP; row.newPrice = newP; row.pct = round(((newP - oldP) / oldP) * 100, 1)
    } else if (e.type === 'new_plan') {
      row.kind = 'new'; row.newPrice = Number(e.last.new_val)
    } else if (e.type === 'removed_plan') {
      const o = Number(e.last.old_val); row.kind = 'removed'; row.oldPrice = Number.isFinite(o) && o > 0 ? o : null
    } else if (e.type === 'extras_change') {
      const diff = materialDiff(e.first.old_val, e.last.new_val)
      if (!diff.added.length && !diff.removed.length) continue
      row.kind = 'extras'; row.diff = diff
    } else continue
    rows.push(row)
  }

  const groups = new Map()
  for (const r of rows) {
    let g = groups.get(r.carrier)
    if (!g) { g = { carrier: r.carrier, rows: [], drops: 0, rises: 0, newPlans: 0, removed: 0, extras: 0, latest: 0 }; groups.set(r.carrier, g) }
    g.rows.push(r)
    if (r.kind === 'drop') g.drops++
    else if (r.kind === 'rise') g.rises++
    else if (r.kind === 'new') g.newPlans++
    else if (r.kind === 'removed') g.removed++
    else g.extras++
    if (r.ts > g.latest) g.latest = r.ts
  }
  const score = (g) => 3 * g.drops + 2 * g.newPlans + g.rises + g.removed + 0.5 * g.extras
  const ordered = [...groups.values()].sort((a, b) => score(b) - score(a) || b.latest - a.latest || a.carrier.localeCompare(b.carrier))
  for (const g of ordered) g.rows.sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || b.ts - a.ts)

  const totals = { changes: rows.length, drops: 0, rises: 0, newPlans: 0, removed: 0, extras: 0 }
  for (const g of ordered) { totals.drops += g.drops; totals.rises += g.rises; totals.newPlans += g.newPlans; totals.removed += g.removed; totals.extras += g.extras }

  return {
    groups: ordered,
    totals,
    mostActive: ordered[0] && ordered[0].rows.length >= 2 ? ordered[0] : null,
    truncated,
    since,
  }
}

/** Hours since the newest scraped_at in a plan list. */
function hoursSince(plans, now = Date.now()) {
  let newest = 0
  for (const p of plans || []) {
    const ts = p?.scraped_at ? new Date(p.scraped_at).getTime() : 0
    if (ts > newest) newest = ts
  }
  if (!newest) return null
  return Math.max(0, Math.round((now - newest) / 3_600_000))
}

// ── the hook ─────────────────────────────────────────────────────────────

const DAY_MS = 24 * 60 * 60 * 1000

function isoDay(offsetDays) {
  return new Date(Date.now() - offsetDays * DAY_MS).toISOString().slice(0, 10)
}

/**
 * @param {string|null} oursCarrier  workspace.mvno_carrier — null renders the
 *                                   whole page at market level (no "us" lines).
 * @param {number} days              lookback window for the price trend (7/30/90)
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
      soft(api.getAbroadChanges(500)),
      soft(api.getHistoryDaily('domestic', { from: isoDay(days) })),
    ])
      .then(([plans, changes, abroadPlans, abroadChanges, daily]) => {
        if (cancelled) return
        setRaw({
          plans: Array.isArray(plans) ? plans : [],
          changes: Array.isArray(changes) ? changes : [],
          abroadPlans: Array.isArray(abroadPlans) ? abroadPlans : [],
          abroadChanges: Array.isArray(abroadChanges) ? abroadChanges : [],
          daily: daily?.rows || [],
          fetchedAt: Date.now(),
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
    const now = raw.fetchedAt

    const costVolume = buildCostVolume(raw.plans, oursCarrier)
    const trend = buildPriceTrend(raw.daily, oursCarrier)
    const weekly = buildWeeklyChanges({ domestic: raw.changes, abroad: raw.abroadChanges }, oursCarrier, now)

    // 36h mirrors the backend's morning_check_stale_hours. Global eSIM is not
    // on this page (competitors' packages = domestic + roaming), so it is not
    // in the footer either.
    const freshness = [
      { id: 'domestic', label: 'סלולר', labelEn: 'Domestic', hours: hoursSince(raw.plans, now), limit: 36 },
      { id: 'abroad', label: 'חו״ל', labelEn: 'Roaming', hours: hoursSince(raw.abroadPlans, now), limit: 36 },
    ]
    const stale = freshness.filter((f) => f.hours != null && f.hours > f.limit)

    return {
      costVolume,
      trend,
      marketTrendPct: trendDelta(trend, 'market'),
      oursTrendPct: trendDelta(trend, 'ours'),
      weekly,
      freshness,
      stale,
      counts: {
        domestic: raw.plans.length,
        abroad: raw.abroadPlans.length,
        carriers: costVolume.total,
      },
    }
  }, [raw, oursCarrier])

  return { loading, error, data: derived, reload }
}

export default useCockpitData
