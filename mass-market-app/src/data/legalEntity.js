// Single source of truth for the operator's identity on every legal surface:
// the four static pages under public/ (stamped into dist/*.html at build time
// by scripts/stamp-legal.mjs), the React footers, and the accessibility
// statement. The SERVER-side copy for outbound e-mails lives in config.json
// (business_name / business_id / business_address / business_email, read by
// notifier._sender_identity) - keep the two in sync.
//
// null = not published yet. The stamp script simply omits null fields, so the
// pages never show a placeholder; fill these in before the next deploy:
//   legalName        the registered business name (e.g. "MOCA Intel Ltd." or
//                    "<full name> - עוסק מורשה")
//   registrationId   ח.פ. / מספר עוסק
//   address          a postal address for notices (Consumer Protection Law +
//                    Communications Law s.30A sender identification)
export const LEGAL_ENTITY = {
  brand: 'MOCA',
  legalName: null,
  registrationId: null,
  address: null,
  email: 'Helpdesk@mocaintel.com',
  privacyEmail: 'Helpdesk@mocaintel.com',
  accessibilityEmail: 'Helpdesk@mocaintel.com',
  accessibilityCoordinator: null,   // name of the accessibility contact person (optional)
  policiesUpdated: '2026-09-11',    // ISO date shown as "last updated" on all legal pages
}

/** Plain-text operator line, e.g. for footers: "MOCA · Helpdesk@mocaintel.com". */
export function operatorLine(lang = 'he') {
  const e = LEGAL_ENTITY
  const parts = [e.legalName ? `${e.brand} (${e.legalName})` : e.brand]
  if (e.registrationId) parts.push((lang === 'en' ? 'Reg. no. ' : 'מס\' עוסק/ח.פ. ') + e.registrationId)
  if (e.address) parts.push(e.address)
  parts.push(e.email)
  return parts.join(' · ')
}
