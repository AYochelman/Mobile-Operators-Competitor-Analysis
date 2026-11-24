import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'
import { CarrierChip } from './moca'

/**
 * "Who moves after whom" - the reaction card of the situation room.
 *
 * Reads GET /api/history/reactions (reactions.py). Two honest halves:
 *   1. Activity: how many move-days each carrier had and in which category.
 *   2. Patterns: ordered pairs where the follower moved after the leader MORE
 *      often than chance predicts. A pair is called a pattern only when the
 *      server marks it `reliable` (p < 0.01); the closest candidates are listed
 *      under an explicit "not beyond chance" label, with their case counts.
 * The busy market makes "B moved within a week of A" common by chance, so the
 * empty state ("no pattern yet") is the expected reading, not an error.
 */

const CAT = {
  domestic:  { he: 'סלולר', en: 'Mobile' },
  abroad:    { he: 'חו״ל', en: 'Roaming' },
  resellers: { he: 'מתחת לקו', en: 'Below the line' },
  content:   { he: 'תוכן', en: 'Content' },
}

function Num({ children }) {
  return <span className="tnum" style={{ direction: 'ltr', unicodeBidi: 'isolate', display: 'inline-block' }}>{children}</span>
}

const pct = (x) => `${Math.round(x * 100)}%`

function PairRow({ p, tt, strong }) {
  return (
    <li className="rx-pair">
      <span className="rx-who">
        <CarrierChip id={p.leader} size={22} showName />
        <span aria-hidden="true" className="rx-arrow">{tt('←', '→')}</span>
        <span className="sr-only">{tt('ואחריה', 'followed by')}</span>
        <CarrierChip id={p.follower} size={22} showName />
      </span>
      <span className="rx-facts">
        {tt('אחרי', 'After')} <Num>{p.followed}</Num> {tt('מתוך', 'of')} <Num>{p.leader_moves}</Num> {tt('מהלכים', 'moves')}
        {' · '}<Num>{pct(p.rate)}</Num> {tt('לעומת', 'vs')} <Num>{pct(p.expected)}</Num> {tt('במקרה', 'by chance')}
        {' · '}{tt('חציון', 'median')} <Num>{p.median_lag}</Num> {tt('ימים', 'days')}
      </span>
      {strong && <span className="rx-badge">{tt('דפוס מובהק', 'Significant')}</span>}
    </li>
  )
}

export default function ReactionsCard({ oursCarrier }) {
  const { tt } = useLang()
  const [win, setWin] = useState(7)
  const [state, setState] = useState({ loading: true, error: false, data: null })

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: false }))
    api.getReactions(win)
      .then((data) => { if (!cancelled) setState({ loading: false, error: false, data }) })
      .catch(() => { if (!cancelled) setState({ loading: false, error: true, data: null }) })
    return () => { cancelled = true }
  }, [win])

  const { loading, error, data } = state
  const reliable = (data?.pairs || []).filter((p) => p.reliable)
  const candidates = (data?.pairs || []).filter((p) => p.enough && !p.reliable).slice(0, 4)
  const carriers = data?.carriers || []
  const maxMoves = Math.max(1, ...carriers.map((c) => c.moves))

  return (
    <section className="rx-card">
      <header className="rx-head">
        <h2>{tt('מי מגיב למי', 'Who moves after whom')}</h2>
        <span className="rx-hint">
          {data ? tt(`${data.total_moves} ימי מהלך ב-${data.days} הימים האחרונים`, `${data.total_moves} move-days in the last ${data.days} days`) : ''}
        </span>
        <span role="group" aria-label={tt('חלון תגובה', 'Reaction window')} className="rx-seg">
          {[5, 7, 14].map((w) => (
            <button key={w} type="button" aria-pressed={win === w} className={win === w ? 'on' : ''} onClick={() => setWin(w)}>
              {tt(`${w} ימים`, `${w} days`)}
            </button>
          ))}
        </span>
      </header>

      {loading && <p className="rx-empty" role="status">{tt('טוען…', 'Loading…')}</p>}
      {!loading && error && <p className="rx-empty">{tt('לא ניתן לטעון את ניתוח התגובות כרגע.', 'The reaction analysis could not be loaded right now.')}</p>}
      {!loading && !error && data && (
        <div className="rx-grid">
          <div>
            <h3>{tt('פעילות לפי מפעיל', 'Activity by carrier')}</h3>
            {carriers.length === 0
              ? <p className="rx-empty">{tt('אין מהלכים מתועדים בתקופה.', 'No recorded moves in the period.')}</p>
              : (
                <ul className="rx-act">
                  {carriers.map((c) => (
                    <li key={c.carrier} className={c.carrier === oursCarrier ? 'ours' : ''}>
                      <CarrierChip id={c.carrier} size={22} showName />
                      <span className="rx-bar" aria-hidden="true"><i style={{ width: `${Math.round((c.moves / maxMoves) * 100)}%` }} /></span>
                      <b><Num>{c.moves}</Num></b>
                      <small>
                        {Object.entries(c.by_category).sort((a, b) => b[1] - a[1])
                          .map(([k, n]) => `${tt(CAT[k]?.he || k, CAT[k]?.en || k)} ${n}`).join(' · ')}
                      </small>
                    </li>
                  ))}
                </ul>
              )}
          </div>
          <div>
            <h3>{tt('דפוסי תגובה', 'Reaction patterns')}</h3>
            {reliable.length > 0
              ? <ul className="rx-pairs">{reliable.map((p) => <PairRow key={p.leader + p.follower} p={p} tt={tt} strong />)}</ul>
              : (
                <p className="rx-verdict">
                  {tt(
                    `עדיין אין דפוס מובהק. נבדקו ${data.tested_pairs} זוגות מפעילים, ובאף אחד מהם התזמון לא חורג ממה שצפוי במקרה.`,
                    `No significant pattern yet. ${data.tested_pairs} carrier pairs were tested and in none does the timing exceed what chance predicts.`,
                  )}
                </p>
              )}
            {candidates.length > 0 && (
              <>
                <h4>{tt('הקרובים ביותר לרף (לא מובהק)', 'Closest to the bar (not significant)')}</h4>
                <ul className="rx-pairs dim">{candidates.map((p) => <PairRow key={p.leader + p.follower} p={p} tt={tt} />)}</ul>
              </>
            )}
            <p className="rx-foot">
              {tt(
                `מהלך = יום שבו מפעיל שינה מחיר, השיק או הסיר חבילה (סלולר, חו״ל, מתחת לקו, תוכן). "תגובה" = מהלך של המפעיל השני בתוך ${data.window} ימים. זהו מתאם בזמן ולא הוכחה לסיבתיות, ולכן זוג מסומן כדפוס רק כשהסיכוי לקבל אותו במקרה קטן מ-1%.`,
                `A move = a day on which a carrier changed a price, launched or removed a plan (mobile, roaming, below the line, content). A "reaction" = a move by the other carrier within ${data.window} days. This is correlation in time, not proof of cause, so a pair is marked a pattern only when chance would produce it less than 1% of the time.`,
              )}
            </p>
          </div>
        </div>
      )}

      <style>{`
        .rx-card { background: #fff; border: 1px solid var(--color-moca-border); border-radius: 16px; box-shadow: var(--sh-card); padding: 18px; min-width: 0; }
        .rx-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
        .rx-head h2 { margin: 0; font-size: 13.5px; font-weight: 800; color: var(--color-moca-dark); }
        .rx-hint { font-size: 11px; color: var(--color-moca-muted); }
        .rx-seg { margin-inline-start: auto; display: inline-flex; border: 1px solid var(--color-moca-border); border-radius: 9px; overflow: hidden; }
        .rx-seg button { border: 0; background: #fff; padding: 5px 10px; font: inherit; font-size: 11.5px; font-weight: 700; color: var(--color-moca-sub); cursor: pointer; }
        .rx-seg button.on { background: var(--color-moca-bolt); color: #fff; }
        .rx-grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
        @media (min-width: 1000px) { .rx-grid { grid-template-columns: 1fr 1.25fr; } }
        .rx-grid h3 { margin: 0 0 10px; font-size: 11px; font-weight: 800; letter-spacing: .4px; color: var(--color-moca-muted); }
        .rx-grid h4 { margin: 14px 0 8px; font-size: 11px; font-weight: 700; color: var(--color-moca-muted); }
        .rx-act, .rx-pairs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 7px; }
        .rx-act li { display: grid; grid-template-columns: 118px 1fr 28px; align-items: center; gap: 8px; font-size: 12.5px; }
        .rx-act li small { grid-column: 2 / -1; font-size: 11px; color: var(--color-moca-sub); margin-top: -4px; }
        .rx-act li.ours .rx-bar i { background: #c9622f; }
        .rx-bar { height: 8px; background: var(--color-moca-cream); border-radius: 99px; overflow: hidden; }
        .rx-bar i { display: block; height: 100%; background: #cdb69b; border-radius: 99px; }
        .rx-act b { text-align: end; color: var(--color-moca-dark); }
        .rx-pair { border: 1px solid var(--color-moca-border); border-radius: 10px; padding: 8px 10px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; }
        .rx-pairs.dim .rx-pair { background: var(--color-moca-mist); border-style: dashed; }
        .rx-who { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 700; color: var(--color-moca-dark); }
        .rx-arrow { color: var(--color-moca-muted); }
        .rx-facts { font-size: 12px; color: var(--color-moca-sub); }
        .rx-badge { margin-inline-start: auto; font-size: 11px; font-weight: 700; background: #e5efe0; color: #3d6a33; border-radius: 999px; padding: 2px 8px; }
        .rx-verdict { font-size: 13px; line-height: 1.6; color: var(--color-moca-text); margin: 0; background: var(--color-moca-mist); border-radius: 10px; padding: 10px 12px; }
        .rx-empty { font-size: 12.5px; color: var(--color-moca-muted); margin: 6px 0; }
        .rx-foot { font-size: 11px; line-height: 1.6; color: var(--color-moca-muted); margin: 12px 0 0; }
      `}</style>
    </section>
  )
}
