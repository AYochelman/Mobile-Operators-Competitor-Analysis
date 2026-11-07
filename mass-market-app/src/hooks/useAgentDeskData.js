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

// ── call script ──────────────────────────────────────────────────────────

/** The customer pushbacks the script has an answer for (labels = customer's words). */
export const OBJECTIONS = [
  { id: 'price', he: 'עדיין יקר לי', en: 'Still too expensive' },
  { id: 'data', he: 'אצלם יותר גלישה', en: 'They give more data' },
  { id: 'perks', he: 'אצלם יש חו"ל / 5G', en: 'They have roaming / 5G' },
  { id: 'think', he: 'רוצה לחשוב על זה', en: 'Wants to think about it' },
  { id: 'leave', he: 'רוצה לעזוב בכל מקרה', en: 'Leaving anyway' },
]

const ilsR = (n) => `₪${Math.round(n).toLocaleString('en-US')}`
const ilsP = (n) => `₪${Number.isInteger(n) ? n : n.toFixed(1)}`

function gbText(gb, tt) {
  if (gb === Infinity) return tt('גלישה ללא הגבלה', 'unlimited data')
  if (gb == null) return tt('שיחות בלבד', 'calls only')
  return `${Math.round(gb)}GB`
}

/** Short spoken phrases for what our plan has that theirs lacks. */
export function perksOf(ours, theirs, tt) {
  if (!ours || !theirs) return []
  const out = []
  if (ours.gb === Infinity && theirs.gb !== Infinity) out.push(tt('גלישה ללא הגבלה', 'unlimited data'))
  else if (ours.gb != null && theirs.gb != null && ours.gb !== Infinity && gbKey(ours.gb) > gbKey(theirs.gb)) out.push(tt(`${Math.round(ours.gb - theirs.gb)}GB יותר גלישה`, `${Math.round(ours.gb - theirs.gb)}GB more data`))
  if (ours.abroadGb > theirs.abroadGb) out.push(tt(`${ours.abroadGb}GB גלישה בחו"ל כלולה`, `${ours.abroadGb}GB roaming included`))
  const rank = { none: 0, basic: 1, max: 2 }
  if (rank[ours.network] > rank[theirs.network]) out.push(ours.network === 'max' ? tt('5G עם תעדוף ברשת בשעות עומס', '5G with priority at peak times') : tt('רשת 5G', '5G network'))
  if (ours.minutes === Infinity && theirs.minutes != null && theirs.minutes !== Infinity) out.push(tt('דקות ללא הגבלה', 'unlimited minutes'))
  return out
}

/**
 * A staged call script for the current comparison. Lines are either 'say'
 * (read to the customer, gender-neutral Hebrew) or 'note' (an instruction to
 * the rep). Like talkingPoints, every number comes from the scraped plans -
 * the script never promises discounts or terms the data doesn't show.
 *
 * opts: { tag, offers, theirName, claimPrice, objection }
 * Returns [{ id, title, lines: [{ kind, text }] }].
 */
export function callScript(ours, theirs, opts, tt) {
  if (!ours || !theirs) return []
  const { tag, offers = [], theirName = '', claimPrice, objection } = opts || {}
  const say = (he, en) => ({ kind: 'say', text: tt(he, en) })
  const note = (he, en) => ({ kind: 'note', text: tt(he, en) })
  const tEff = theirs.promoPrice || theirs.price
  const oEff = ours.promoPrice || ours.price
  const yearDiff = theirs.yearCost - ours.yearCost
  const monthDiff = oEff - tEff
  const perks = perksOf(ours, theirs, tt)
  const perksLine = perks.length ? say(`ובנוסף: ${perks.join(', ')}.`, `Plus: ${perks.join(', ')}.`) : null
  const others = offers.map((o) => o.plan).filter((p) => p.key !== ours.key)
  const cheaperAlt = others.filter((p) => p.yearCost < ours.yearCost).sort((a, b) => a.yearCost - b.yearCost)[0] || null
  const biggerAlt = others.filter((p) => gbKey(p.gb) > gbKey(ours.gb)).sort((a, b) => a.yearCost - b.yearCost)[0] || null
  const stages = []

  stages.push({
    id: 'open',
    title: tt('פתיחה', 'Opening'),
    lines: [
      say('תודה ששיתפת. חשוב לנו שהמחיר יהיה הוגן, אז נבדוק את זה יחד עכשיו.', 'Thanks for telling me. We want your price to be fair, so let\'s check it together right now.'),
      note('הקשיבו עד הסוף לפני שמציגים הצעה. אם לא נאמר - שאלו באיזו חברה ובכמה.', 'Let the customer finish before offering. If not mentioned, ask which carrier and what price.'),
    ],
  })

  const verify = [
    say(
      `בדקתי: ב${theirName} התוכנית "${theirs.plan_name}" עולה ${ilsP(tEff)} לחודש וכוללת ${gbText(theirs.gb, tt)}.`,
      `I checked: at ${theirName}, "${theirs.plan_name}" costs ${ilsP(tEff)}/month with ${gbText(theirs.gb, tt)}.`,
    ),
  ]
  if (theirs.promoPrice && theirs.promoMonths) {
    verify.push(say(
      `חשוב לדעת שהמחיר הזה הוא רק ל-${theirs.promoMonths} חודשים. אחר כך הוא עולה ל-${ilsP(theirs.price)}, כלומר ${ilsR(theirs.yearCost)} בשנה הראשונה.`,
      `Worth knowing: that price is only for ${theirs.promoMonths} months, then ${ilsP(theirs.price)} - ${ilsR(theirs.yearCost)} over the first year.`,
    ))
  }
  if (theirs.source === 'reseller') {
    verify.push(say('זו הצעה של משווק ולא המחירון הרשמי שלהם, כדאי לבדוק את התנאים לפני שמחליטים.', 'That\'s a reseller offer, not their official price list - worth checking its terms before deciding.'))
  }
  if (Number(claimPrice) > 0 && Number(claimPrice) < tEff * 0.9) {
    verify.push(note(
      `המחיר שהלקוח ציין (${ilsP(Number(claimPrice))}) נמוך מכל מה שמפורסם אצלם. ייתכן שזו הצעה אישית - שאלו מאיפה ההצעה.`,
      `The quoted ${ilsP(Number(claimPrice))} is below anything they publish. It may be a personal offer - ask where it came from.`,
    ))
  }
  stages.push({ id: 'verify', title: tt('אימות ההצעה שלהם', 'Check their offer'), lines: verify })

  const offer = []
  if (tag === 'beats') {
    offer.push(say(
      `יש לי בשבילך הצעה טובה יותר: "${ours.plan_name}" עם ${gbText(ours.gb, tt)} ב-${ilsP(oEff)} לחודש.`,
      `I have a better option for you: "${ours.plan_name}" with ${gbText(ours.gb, tt)} for ${ilsP(oEff)}/month.`,
    ))
    offer.push(yearDiff >= 6
      ? say(`זה חיסכון של ${ilsR(yearDiff)} בשנה הראשונה לעומת ההצעה שלהם, ובלי לעבור חברה.`, `That saves ${ilsR(yearDiff)} in the first year compared with their offer, without switching carriers.`)
      : say('במחיר כמעט זהה, ובלי הטרחה של מעבר חברה.', 'For practically the same price, without the hassle of switching.'))
    if (perksLine) offer.push(perksLine)
  } else if (tag === 'more') {
    offer.push(say(
      `כדי לקבל ${gbText(theirs.gb, tt)} ומעלה, התוכנית המתאימה אצלנו היא "${ours.plan_name}" ב-${ilsP(oEff)} לחודש.`,
      `For ${gbText(theirs.gb, tt)} or more, our matching plan is "${ours.plan_name}" at ${ilsP(oEff)}/month.`,
    ))
    if (perks.length) {
      offer.push(say(
        `זה ${ilsP(Math.abs(monthDiff))} יותר בחודש, ובתמורה: ${perks.join(', ')}.`,
        `That's ${ilsP(Math.abs(monthDiff))} more per month, and in return: ${perks.join(', ')}.`,
      ))
    }
    offer.push(offers.some((o) => o.tag === 'beats')
      ? note('זו הצעת שדרוג. אם המחיר חשוב ללקוח - חזרו ללשונית "משתלם יותר".', 'This is an upsell. If price matters to the customer, go back to the "better value" tab.')
      : note('אין לנו תוכנית זולה יותר עם אותה גלישה. הדגישו את היתרונות, אל תתחרו על המחיר.', 'We have nothing cheaper with the same data. Lead with the advantages, don\'t fight on price.'))
  } else {
    offer.push(say('כמה גלישה יוצאת לך בפועל בחודש?', 'How much data do you actually use per month?'))
    offer.push(say(
      `אם זה פחות מ-${gbText(ours.gb, tt)}, יש לנו "${ours.plan_name}" ב-${ilsP(oEff)} לחודש, זול יותר מההצעה שלהם.`,
      `If it's under ${gbText(ours.gb, tt)}, we have "${ours.plan_name}" at ${ilsP(oEff)}/month - cheaper than their offer.`,
    ))
    offer.push(note('הצעה זו מתאימה רק אם הצריכה בפועל נמוכה. אחרת - בחרו את הלשונית "יותר גלישה".', 'Only fits if actual usage is low. Otherwise switch to the "more data" tab.'))
  }
  stages.push({ id: 'offer', title: tt('ההצעה שלנו', 'Our offer'), lines: offer })

  stages.push({
    id: 'close',
    title: tt('סגירה', 'Close'),
    lines: [
      tag === 'more' && perks.length
        ? say(`שווה לך ${ilsP(Math.abs(monthDiff))} בחודש בשביל ${perks[0]}? אפשר לעדכן את התוכנית כבר עכשיו.`, `Is ${perks[0]} worth ${ilsP(Math.abs(monthDiff))} a month to you? I can update the plan right now.`)
        : say('מתאים לך? אפשר לעדכן את התוכנית כבר עכשיו.', 'Does that work for you? I can update the plan right now.'),
      note('הסכמה ← עדכנו את התוכנית ותעדו ("העתקה לתיעוד"). התנגדות ← בחרו אותה למטה.', 'Agreed → update the plan and log it ("Copy for notes"). Pushback → pick it below.'),
    ],
  })

  if (objection) {
    const lines = []
    if (objection === 'price') {
      if (cheaperAlt) lines.push(say(`אם המחיר הוא העיקר, יש גם "${cheaperAlt.plan_name}" ב-${ilsP(cheaperAlt.promoPrice || cheaperAlt.price)} לחודש, עם ${gbText(cheaperAlt.gb, tt)}.`, `If price matters most, there's also "${cheaperAlt.plan_name}" at ${ilsP(cheaperAlt.promoPrice || cheaperAlt.price)}/month with ${gbText(cheaperAlt.gb, tt)}.`))
      if (theirs.promoPrice) lines.push(say(`כדאי להסתכל על כל השנה: אצלם ${ilsR(theirs.yearCost)} בשנה הראשונה, אצלנו ${ilsR(ours.yearCost)}.`, `Look at the whole year: ${ilsR(theirs.yearCost)} with them in year one, ${ilsR(ours.yearCost)} with us.`))
      if (!cheaperAlt && !theirs.promoPrice) lines.push(say('ברור לי. אשמח לבדוק אם יש אפשרות להצעה מותאמת יותר.', 'I understand. Let me check whether a more tailored offer is possible.'))
      lines.push(note('אם הלקוח עדיין מתלבט - העבירו לשימור לבדיקת הצעה אישית. אל תבטיחו הנחה שאינה קיימת.', 'Still hesitant → escalate to retention for a personal offer. Never promise a discount that doesn\'t exist.'))
    } else if (objection === 'data') {
      if (ours.gb === Infinity) lines.push(say('אצלנו הגלישה ללא הגבלה, אין צורך לספור ג\'יגה.', 'Our data is unlimited - no need to count gigabytes.'))
      else if (biggerAlt) lines.push(say(`אם צריך יותר גלישה, "${biggerAlt.plan_name}" כוללת ${gbText(biggerAlt.gb, tt)} ב-${ilsP(biggerAlt.promoPrice || biggerAlt.price)} לחודש.`, `If you need more data, "${biggerAlt.plan_name}" has ${gbText(biggerAlt.gb, tt)} for ${ilsP(biggerAlt.promoPrice || biggerAlt.price)}/month.`))
      lines.push(say('כדאי לבדוק כמה גלישה יוצאת לך בפועל בחודש - ייתכן שהחבילה שלנו מספיקה בהחלט.', 'It\'s worth checking your actual monthly usage - our plan may be plenty.'))
      lines.push(note('בדקו את הצריכה בפועל בתיק הלקוח. אם היא באמת גבוהה ואין תוכנית מתאימה - שימור.', 'Check actual usage on the account. If it really is high and nothing fits → retention.'))
    } else if (objection === 'perks') {
      const rank0 = { none: 0, basic: 1, max: 2 }
      const extra = []
      if (ours.abroadGb > theirs.abroadGb) extra.push(tt(`${ours.abroadGb}GB גלישה בחו"ל`, `${ours.abroadGb}GB roaming`))
      if (rank0[ours.network] > rank0[theirs.network]) extra.push(ours.network === 'max' ? tt('5G עם תעדוף ברשת', '5G with network priority') : tt('רשת 5G', '5G network'))
      if (extra.length) lines.push(say(`אצלנו כלול: ${extra.join(', ')}.`, `With us you get: ${extra.join(', ')}.`))
      if (theirs.abroadGb > ours.abroadGb) lines.push(note(`אצלם ${theirs.abroadGb}GB בחו"ל כלולים. אפשר להציע חבילת חו"ל לפי נסיעה - ראו טבלת חו"ל למטה.`, `They bundle ${theirs.abroadGb}GB roaming. Offer a per-trip roaming pack - see the roaming table below.`))
      const rank = { none: 0, basic: 1, max: 2 }
      if (rank[theirs.network] > rank[ours.network]) lines.push(note('אצלם רשת 5G/תעדוף שאין בתוכנית הזו. בדקו אם תוכנית אחרת שלנו כוללת 5G.', 'They have 5G/priority this plan lacks. Check whether another plan of ours includes 5G.'))
      if (!lines.length) lines.push(note('בתוכנית הזו אין יתרון חו"ל/5G על פני המתחרה. חזרו להשוואת המחיר השנתי.', 'No roaming/5G edge over them on this plan. Go back to the yearly price comparison.'))
    } else if (objection === 'think') {
      lines.push(say(
        `בטח, זו החלטה חשובה. רק לסיכום: "${ours.plan_name}" ב-${ilsP(oEff)} לחודש, ${gbText(ours.gb, tt)}${yearDiff >= 6 ? `, חיסכון של ${ilsR(yearDiff)} בשנה הראשונה` : ''}.`,
        `Of course, it's an important decision. To recap: "${ours.plan_name}" at ${ilsP(oEff)}/month, ${gbText(ours.gb, tt)}${yearDiff >= 6 ? `, saving ${ilsR(yearDiff)} in year one` : ''}.`,
      ))
      lines.push(say('אשמח לרשום את ההצעה בתיק, כך שתהיה זמינה גם בפעם הבאה שנדבר.', 'I\'ll note the offer on your account so it\'s there next time we talk.'))
      lines.push(note('תעדו את ההצעה בתיק ("העתקה לתיעוד").', 'Log the offer on the account ("Copy for notes").'))
    } else if (objection === 'leave') {
      lines.push(say('חבל לשמוע. לפני שמחליטים, אשמח להעביר אותך לצוות שיכול לבדוק הצעה מותאמת אישית.', 'Sorry to hear that. Before you decide, let me transfer you to the team that can look at a personal offer.'))
      lines.push(note('העבירו לשימור עם סיכום ההשוואה ("העתקה לתיעוד").', 'Transfer to retention with the comparison summary ("Copy for notes").'))
    }
    const label = OBJECTIONS.find((o) => o.id === objection)
    stages.push({ id: 'objection', title: tt(`התנגדות: ${label?.he || ''}`, `Pushback: ${label?.en || ''}`), lines })
  }
  return stages
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
