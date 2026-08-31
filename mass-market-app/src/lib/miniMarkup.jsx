import { Fragment } from 'react'

/**
 * Render a SHORT trusted string that contains only <b>…</b> and <br> markup as
 * real React nodes. This is deliberately NOT a general HTML renderer: any tag
 * other than <b>/<br> stays as literal, React-escaped text.
 *
 * WHY: the public marketing surfaces (EsimComparePage, GuestPortalPage) used
 * dangerouslySetInnerHTML to render their "trust" line. Today those strings are
 * static translation constants, so it's safe — but a future refactor that pipes
 * a hotel name, provider label, or any backend/scraped value into that string
 * would turn it into stored XSS on an unauthenticated page. Routing it through
 * this allowlisted renderer removes that vector permanently, with no CSP or
 * sanitiser dependency.
 */
export function miniMarkup(str) {
  if (str == null) return null
  const lines = String(str).split(/<br\s*\/?>/i)
  return lines.map((line, li) => {
    const parts = []
    const re = /<b>([\s\S]*?)<\/b>/gi
    let last = 0
    let m
    while ((m = re.exec(line)) !== null) {
      if (m.index > last) parts.push(line.slice(last, m.index))
      parts.push(<b key={parts.length}>{m[1]}</b>)
      last = re.lastIndex
    }
    if (last < line.length) parts.push(line.slice(last))
    return (
      <Fragment key={li}>
        {parts}
        {li < lines.length - 1 && <br />}
      </Fragment>
    )
  })
}
