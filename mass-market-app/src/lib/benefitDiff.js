/**
 * Benefit-list diffing shared by the home dashboard's change feed and the
 * executive cockpit's weekly section. Pure functions, no React.
 */

/**
 * Parse a Python list-repr string into a JS string array.
 * `extras_change` events store old_val/new_val as `str(list)` (db.py), so the
 * API hands us something like `['דקות ללא הגבלה', '6GB גלישה בחו"ל']`. Python
 * uses single quotes by default, double quotes when an item contains an
 * apostrophe; Hebrew/Unicode is emitted verbatim. Falls back to a single-item
 * array for any non-list string.
 */
export function parsePyList(raw) {
  if (Array.isArray(raw)) return raw.map((x) => String(x))
  if (typeof raw !== 'string') return []
  const s = raw.trim()
  if (!s.startsWith('[') || !s.endsWith(']')) return s ? [s] : []
  const body = s.slice(1, -1)
  const items = []
  let i = 0
  while (i < body.length) {
    while (i < body.length && (body[i] === ' ' || body[i] === ',' || body[i] === '\t')) i++
    if (i >= body.length) break
    const q = body[i]
    if (q !== "'" && q !== '"') { items.push(body.slice(i).trim()); break }
    i++
    let buf = ''
    while (i < body.length) {
      const ch = body[i]
      if (ch === '\\' && i + 1 < body.length) {
        const next = body[i + 1]
        // Python repr() escapes non-printable chars — crucially NBSP (\xa0)
        // and bidi marks (‎/‏) — which appear verbatim in scraped
        // benefit strings. Decode \xHH / \uHHHH / \UHHHHHHHH back to the real
        // character; otherwise the literal "xa0" text leaks into the UI.
        if (next === 'x' && /^[0-9a-fA-F]{2}$/.test(body.slice(i + 2, i + 4))) {
          buf += String.fromCharCode(parseInt(body.slice(i + 2, i + 4), 16)); i += 4; continue
        }
        if (next === 'u' && /^[0-9a-fA-F]{4}$/.test(body.slice(i + 2, i + 6))) {
          buf += String.fromCharCode(parseInt(body.slice(i + 2, i + 6), 16)); i += 6; continue
        }
        if (next === 'U' && /^[0-9a-fA-F]{8}$/.test(body.slice(i + 2, i + 10))) {
          buf += String.fromCodePoint(parseInt(body.slice(i + 2, i + 10), 16)); i += 10; continue
        }
        buf += next === 'n' ? '\n' : next === 't' ? '\t' : next === 'r' ? '\r' : next
        i += 2
        continue
      }
      if (ch === q) { i++; break }
      buf += ch
      i++
    }
    items.push(buf)
  }
  return items
}

/**
 * Filler tokens that carry no essence — connectors and the "at no extra cost"
 * family. Dropping them lets "X ללא עלות" and "X ללא תוספת תשלום" (and a comma
 * vs "ו-" separator, and a reordered app list) collapse to the same signature,
 * so a pure rewording isn't reported as a benefit change.
 */
const BENEFIT_FILLERS = new Set([
  'ללא', 'תוספת', 'תשלום', 'עלות', 'נוספת', 'נוסף', 'חינם',
  'כלול', 'כלולה', 'כלולים', 'כולל', 'כוללת',
  'שירות', 'שירותים', 'בתכנית', 'בתוכנית', 'בחבילה', 'במסלול',
  'של', 'את', 'עם', 'גם', 'ה', 'ו', 'ב', 'ל',
])

/**
 * Canonical signature of one benefit string. Splits on list separators (comma,
 * bullet, slash, "ו-"…) into independent items, normalizes each (lower-case,
 * strip 6,000→6000 grouping + punctuation, drop filler words) keeping word
 * order *within* an item, then sorts the items. So an app list reordered or a
 * separator/filler reworded collapses to the same signature — but a number
 * swapped against its noun ("100 דקות ל-50 יעדים" vs "50…ל-100…") does NOT,
 * because each item's internal order is preserved. Guards against hiding a
 * real change as if it were cosmetic.
 */
export function benefitSignature(s) {
  const segments = String(s)
    .toLowerCase()
    .replace(/(?<=\d),(?=\d)/g, '')               // 6,000 → 6000 before splitting on comma
    .split(/\s*(?:[,;/|•·]|ו-)\s*/)         // independent list items
    .map((seg) => seg
      .replace(/[:."'()[\]\-–—]/g, ' ')           // strip remaining punctuation
      .split(/\s+/)
      .filter(Boolean)
      .filter((t) => !BENEFIT_FILLERS.has(t))
      .join(' ')                                  // keep word order within an item
      .trim())
    .filter(Boolean)
  return segments.sort().join('|')                // order-insensitive across items
}

/**
 * Diff two extras lists, suppressing text-only churn. An old item and a new
 * item with the same {@link benefitSignature} cancel out (reordered/reworded —
 * no essence change). What survives is genuinely added / removed.
 * Returns { added, removed } as the original (display) strings.
 */
export function materialDiff(oldVal, newVal) {
  const oldArr = parsePyList(oldVal)
  const newArr = parsePyList(newVal)
  const oldSigs = oldArr.map(benefitSignature)
  const newSigs = newArr.map(benefitSignature)

  const tally = (sigs) => sigs.reduce((m, sig) => m.set(sig, (m.get(sig) || 0) + 1), new Map())
  const newAvail = tally(newSigs)
  const oldAvail = tally(oldSigs)

  const removed = oldArr.filter((item, i) => {
    const sig = oldSigs[i]
    if ((newAvail.get(sig) || 0) > 0) { newAvail.set(sig, newAvail.get(sig) - 1); return false }
    return true
  })
  const added = newArr.filter((item, i) => {
    const sig = newSigs[i]
    if ((oldAvail.get(sig) || 0) > 0) { oldAvail.set(sig, oldAvail.get(sig) - 1); return false }
    return true
  })
  return { added, removed }
}
