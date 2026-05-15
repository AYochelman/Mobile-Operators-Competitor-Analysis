// MVNO brand colors — mirrors CARRIER_DISPLAY in app.py.
// `secondary` is a ~20% darker shade of primary for hover/active states.
export const MVNO_BRAND_COLORS = {
  partner:   { primary: '#2ed5c4', secondary: '#1fa396' },
  pelephone: { primary: '#001fff', secondary: '#0018cc' },
  hotmobile: { primary: '#e3001e', secondary: '#b50018' },
  cellcom:   { primary: '#9530ff', secondary: '#7120cc' },
  mobile019: { primary: '#e8202a', secondary: '#b81818' },
  xphone:    { primary: '#2b9fd5', secondary: '#1f75a0' },
  wecom:     { primary: '#ff4500', secondary: '#cc3600' },
  neptucom:  { primary: '#29b6d6', secondary: '#1d8ca3' },
  golan:     { primary: '#cc1717', secondary: '#a01212' },
  rami_levy: { primary: '#e8178a', secondary: '#b51069' },
}

export function getMvnoColors(mvno) {
  return mvno ? MVNO_BRAND_COLORS[mvno] || null : null
}

// true if `color` matches ANY MVNO's primary brand color — i.e. the user
// hasn't set a custom override, they're using one of our known defaults.
export function isKnownMvnoPrimary(color) {
  if (!color) return false
  const lower = color.toLowerCase()
  return Object.values(MVNO_BRAND_COLORS).some(c => c.primary.toLowerCase() === lower)
}
