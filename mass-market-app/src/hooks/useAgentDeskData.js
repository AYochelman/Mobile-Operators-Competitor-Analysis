import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { classifyPlan, buildWeeklyChanges } from './useCockpitData'
import { classifyPriority } from '../data/networkPriority'

/**
 * Data layer for /agent-desk — the first-line support rep's screen.
 *
 * The rep is on a call with a customer who says "at X they give me N GB for
 * ₪P". The page has to answer, in seconds:
 *   1. Is that true?             → the competitor's actual plans, nearest first
 *   2. What do I offer instead?  → our counter-offers, ranked
 *   3. What do I SAY?            → factual talking points (no invented claims)
 *
 * Everything below the hook is PURE (smoke-testable in node with
 * `npx esbuild src/hooks/useAgentDeskData.js --bundle --platform=node`).
 * Comparisons are on the FIRST-YEAR cost, not the sticker price, because the
 * most common customer claim is a promo price ("₪39" that becomes ₪49 after
 * three months) - the single most useful thing a rep can point out.
 */

// ── normalisation ────────────────────────────────────────────────────────

const RE_ABROAD = /חו"ל|חו״ל|בחו|roaming/i
const RE_GB_IN = /(\d+(?:\.\d+)?)\s*GB/i

function visibleExtras(p) {
  return (Array.isArray(p?.extras) ? p.extras : [])
    .filter((e) => typeof e === 'string' && e.trim() && !e.startsWith('__info__|'))
}

/** First-year cost in ₪ - promo months at the promo price, the rest at list. */
export function firstYearCost(price, promoPrice, promoMonths) {
  const m = Number(promoMonths)
  const pp = Number(promoPrice)
  if (pp > 0 && m > 0) {
    const n = Math.min(12, m)
    return pp * n + price * (12 - n)
  }
  return price * 12
}

/** Minutes as a number; "ללא הגבלה"/huge values → Infinity; unknown → null. */
function parseMinutes(v) {
  if (v == null || v === '') return null
  const n = Number(String(v).replace(/[,\s]/g, ''))
  if (Number.isFinite(n) && n > 0) return n >= 9999 ? Infinity : n
  if (/ללא הגבלה|unlimited/i.test(String(v))) return Infinity
  return null
}

/** GB of roaming data the plan bundles, from its extras ("10GB גלישה בחו"ל"). */
function abroadGb(extras) {
  for (const e of extras) {
    if (!RE_ABROAD.test(e)) continue
    const m = e.match(RE_GB_IN)
    if (m) return Number(m[1])
  }
  return 0
}

/**
 * One shape for every offer the desk shows - our plans, competitor plans and
 * below-the-line reseller offers alike.
 *   gb: Infinity = unlimited, number = GB, null = voice-only / unknown.
 */
export function normalizePlan(p, source = 'rate_card') {
  const cls = classifyPlan(p)
  if (cls.kind === 'invalid') return null
  const extras = visibleExtras(p)
  const promoPrice = Number(p.promo_price) > 0 ? Number(p.promo_price) : null
  const promoMonths = Number(p.promo_months) > 0 ? Number(p.promo_months) : null
  const gb = cls.kind === 'unlimited' ? Infinity : cls.kind === 'voice' ? null : cls.gb
  return {
    key: `${source}|${p.reseller_id || ''}|${p.carrier}|${p.plan_name}`,
    source,
    carrier: p.carrier,
    plan_name: p.plan_name,
    price: cls.price,
    promoPrice,
    promoMonths,
    yearCost: firstYearCost(cls.price, promoPrice, promoMonths),
    gb,
    kind: cls.kind,
    minutes: parseMinutes(p.minutes),
    abroadGb: abroadGb(extras),
    network: classifyPriority(p), // 'max' | 'basic' | 'none'
    extras,
    termsUrl: p.url || p.terms_url || null,
    sourceUrl: p.source_url || null,
    resellerId: p.reseller_id || null,
  }
}

// ── matching ─────────────────────────────────────────────────────────────

/** Comparable GB for sorting: unlimited sorts as very large, voice as 0. */
const gbKey = (gb) => (gb === Infinity ? 1e6 : gb == null ? 0 : gb)

/**
 * The competitor plans that best match what the customer said.
 * No price and no GB given → the carrier's whole list, cheapest first.
 */
export function matchCompetitorPlans(plans, { carrier, price, gb }) {
  let list = plans.filter((p) => !carrier || p.carrier === carrier)
  const hasPrice = Number(price) > 0
  const hasGb = gb === Infinity || Number(gb) > 0
  if (!hasPrice && !hasGb) return list.slice().sort((a, b) => a.price - b.price)

  const score = (p) => {
    let s = 0
    // The customer may be quoting the promo price - match whichever is closer.
    if (hasPrice) {
      const dList = Math.abs(p.price - price) / price
      s += p.promoPrice ? Math.min(dList, Math.abs(p.promoPrice - price) / price) : dList
    }
    if (hasGb) {
      if (gb === Infinity) s += p.gb === Infinity ? 0 : 1
      else if (p.gb === Infinity) s += 0.6
      else if (p.gb == null) s += 2
      else s += Math.min(2, Math.abs(Math.log((p.gb || 0.1) / gb)))
    }
    return s
  }
  list = list.map((p) => ({ p, s: score(p) })).sort((a, b) => a.s - b.s || a.p.price - b.p.price).map((x) => x.p)
  return list
}

/**
 * Our answer to a target offer, ranked:
 *   'beats'   - at least the same data for no more money over the first year
 *   'more'    - at least the same data, but it costs more (gap shown)
 *   'cheaper' - cheaper than the target, with less data (a downsell option)
 * Voice-only targets compare only on price.
 */
export function counterOffers(ourPlans, target, max = 3) {
  if (!target) return []
  const tGb = gbKey(target.gb)
  const pool = ourPlans.filter((p) => target.kind === 'voice' ? p.kind === 'voice' : p.gb != null && p.kind !== 'voice')
  const withData = pool.filter((p) => target.kind === 'voice' || gbKey(p.gb) >= tGb)
  const beats = withData.filter((p) => p.yearCost <= target.yearCost + 0.01)
    .sort((a, b) => a.yearCost - b.yearCost || gbKey(b.gb) - gbKey(a.gb))
  const more = withData.filter((p) => p.yearCost > target.yearCost + 0.01)
    .sort((a, b) => a.yearCost - b.yearCost)
  const cheaper = pool.filter((p) => gbKey(p.gb) < tGb && p.yearCost <= target.yearCost)
    .sort((a, b) => gbKey(b.gb) - gbKey(a.gb) || a.yearCost - b.yearCost)

  const out = []
  const seen = new Set()
  const push = (p, tag) => { if (p && !seen.has(p.key) && out.length < max) { seen.add(p.key); out.push({ plan: p, tag }) } }
  push(beats[0], 'beats')
  push(beats.find((p) => gbKey(p.gb) > gbKey(beats[0]?.gb)), 'beats') // an upsell that still beats
  push(more[0], 'more')
  push(cheaper[0], 'cheaper')
  push(beats[1], 'beats')
  return out
}

/**
 * Factual talking points for "our plan vs theirs". Every line is derived from
 * the scraped fields - nothing promotional is invented. Each point carries a
 * tone: 'win' (an argument for us), 'warn' (a caveat about their offer the
 * customer may not know) or 'loss' (where they genuinely win - the rep must
 * not be surprised by it).
 */
export function talkingPoints(ours, theirs, tt) {
  if (!ours || !theirs) return []
  const pts = []
  const ils = (n) => `₪${Math.round(n).toLocaleString('en-US')}`

  if (theirs.promoPrice && theirs.promoMonths) {
    pts.push({
      tone: 'warn',
      text: tt(
        `המחיר ${ils(theirs.promoPrice)} אצל המתחרה הוא רק ל-${theirs.promoMonths} חודשים, אחר כך ${ils(theirs.price)} לחודש`,
        `Their ${ils(theirs.promoPrice)} is only for ${theirs.promoMonths} months, then ${ils(theirs.price)}/month`,
      ),
    })
  }

  const yearDiff = theirs.yearCost - ours.yearCost
  if (Math.abs(yearDiff) >= 6) {
    pts.push(yearDiff > 0
      ? { tone: 'win', text: tt(`בשנה הראשונה הלקוח חוסך ${ils(yearDiff)} אצלנו`, `The customer saves ${ils(yearDiff)} with us in year one`) }
      : { tone: 'loss', text: tt(`המתחרה זול ב-${ils(-yearDiff)} בשנה הראשונה`, `They are ${ils(-yearDiff)} cheaper in year one`) })
  } else {
    pts.push({ tone: 'win', text: tt('המחיר השנתי כמעט זהה', 'Practically the same yearly cost') })
  }

  const a = gbKey(ours.gb), b = gbKey(theirs.gb)
  if (ours.gb === Infinity && theirs.gb !== Infinity && theirs.gb != null) {
    pts.push({ tone: 'win', text: tt('אצלנו גלישה ללא הגבלה', 'Unlimited data with us') })
  } else if (theirs.gb === Infinity && ours.gb !== Infinity) {
    pts.push({ tone: 'loss', text: tt('אצל המתחרה גלישה ללא הגבלה', 'They offer unlimited data') })
  } else if (ours.gb != null && theirs.gb != null && a !== b) {
    const d = Math.abs(a - b)
    pts.push(a > b
      ? { tone: 'win', text: tt(`${Math.round(d)}GB יותר גלישה אצלנו`, `${Math.round(d)}GB more data with us`) }
      : { tone: 'loss', text: tt(`למתחרה ${Math.round(d)}GB יותר`, `They give ${Math.round(d)}GB more`) })
  }

  if (ours.abroadGb > theirs.abroadGb) {
    pts.push({
      tone: 'win',
      text: theirs.abroadGb
        ? tt(`${ours.abroadGb}GB גלישה בחו"ל כלולה (אצלם ${theirs.abroadGb}GB)`, `${ours.abroadGb}GB roaming included (they give ${theirs.abroadGb}GB)`)
        : tt(`כולל ${ours.abroadGb}GB גלישה בחו"ל - אצלם אין`, `Includes ${ours.abroadGb}GB roaming - they include none`),
    })
  } else if (theirs.abroadGb > ours.abroadGb) {
    pts.push({ tone: 'loss', text: tt(`המתחרה כולל ${theirs.abroadGb}GB בחו"ל`, `They include ${theirs.abroadGb}GB roaming`) })
  }

  const rank = { none: 0, basic: 1, max: 2 }
  if (rank[ours.network] > rank[theirs.network]) {
    pts.push({ tone: 'win', text: ours.network === 'max' ? tt('5G עם תעדוף ברשת בעומסים', '5G with network priority under load') : tt('כולל 5G - אצלם לא מצוין', 'Includes 5G - not listed on theirs') })
  } else if (rank[theirs.network] > rank[ours.network]) {
    pts.push({ tone: 'loss', text: theirs.network === 'max' ? tt('אצל המתחרה 5G עם תעדוף', 'They offer 5G with priority') : tt('אצל המתחרה 5G', 'They offer 5G') })
  }

  if (ours.minutes != null && theirs.minutes != null && ours.minutes !== theirs.minutes) {
    if (ours.minutes === Infinity) pts.push({ tone: 'win', text: tt('דקות ללא הגבלה', 'Unlimited minutes') })
    else if (theirs.minutes !== Infinity && ours.minutes > theirs.minutes * 1.5) pts.push({ tone: 'win', text: tt(`${ours.minutes.toLocaleString('en-US')} דקות (אצלם ${theirs.minutes.toLocaleString('en-US')})`, `${ours.minutes.toLocaleString('en-US')} minutes (they give ${theirs.minutes.toLocaleString('en-US')})`) })
  }

  if (theirs.source === 'reseller') {
    pts.push({ tone: 'warn', text: tt('זו הצעת משווק/דף נחיתה, לא המחירון הרשמי של המתחרה - כדאי לבדוק את התנאים בקישור', 'This is a reseller / landing-page offer, not their official rate card - check its terms') })
  }

  const order = { warn: 0, win: 1, loss: 2 }
  return pts.sort((x, y) => order[x.tone] - order[y.tone])
}

// ── the hook ─────────────────────────────────────────────────────────────

function newestTs(list) {
  let n = 0
  for (const p of list || []) {
    const t = p?.scraped_at ? new Date(p.scraped_at).getTime() : 0
    if (t > n) n = t
  }
  return n || null
}

export function useAgentDeskData(oursCarrier) {
  const [raw, setRaw] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const reload = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const soft = (p) => p.catch(() => null)
    Promise.all([
      soft(api.getPlans()),
      soft(api.getAbroadPlans()),
      soft(api.getContentPlans()),
      soft(api.getResellerPlans()),
      soft(api.getChanges(500)),
      soft(api.getAbroadChanges(500)),
    ]).then(([plans, abroad, content, resellers, changes, abroadChanges]) => {
      if (cancelled) return
      if (plans === null) { setError('primary feed failed'); setLoading(false); return }
      const arr = (x) => (Array.isArray(x) ? x : [])
      setRaw({
        plans: arr(plans), abroad: arr(abroad), content: arr(content), resellers: arr(resellers),
        changes: arr(changes), abroadChanges: arr(abroadChanges), fetchedAt: Date.now(),
      })
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [reloadKey])

  const data = useMemo(() => {
    if (!raw) return null
    const domestic = raw.plans.map((p) => normalizePlan(p)).filter(Boolean)
    const resellers = raw.resellers.map((p) => normalizePlan(p, 'reseller')).filter(Boolean)
    const ours = oursCarrier ? domestic.filter((p) => p.carrier === oursCarrier) : []
    const competitors = domestic.filter((p) => p.carrier !== oursCarrier)
    const competitorResellers = resellers.filter((p) => p.carrier !== oursCarrier)
    const carriers = [...new Set(domestic.map((p) => p.carrier))]
    const weekly = buildWeeklyChanges({ domestic: raw.changes, abroad: raw.abroadChanges }, oursCarrier, raw.fetchedAt)
    const newest = newestTs(raw.plans)
    return {
      domestic, ours, competitors, resellers: competitorResellers, carriers,
      abroad: raw.abroad, content: raw.content, weekly,
      updatedHours: newest ? Math.max(0, Math.round((raw.fetchedAt - newest) / 3_600_000)) : null,
    }
  }, [raw, oursCarrier])

  return { loading, error, data, reload }
}

export default useAgentDeskData
