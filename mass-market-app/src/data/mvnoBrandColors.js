// MVNO brand colors — mirrors CARRIER_DISPLAY in app.py.
// `secondary` is a ~20% darker shade of primary for hover/active states.
export const MVNO_BRAND_COLORS = {
  partner:   { primary: '#2ed5c4', secondary: '#1fa396' },
  pelephone: { primary: '#ff6600', secondary: '#cc5200' },
  hotmobile: { primary: '#e3001e', secondary: '#b50018' },
  cellcom:   { primary: '#003b7a', secondary: '#002e5e' },
  mobile019: { primary: '#555555', secondary: '#333333' },
  xphone:    { primary: '#6a0dad', secondary: '#4d0980' },
  wecom:     { primary: '#006633', secondary: '#004d26' },
  neptucom:  { primary: '#004488', secondary: '#003366' },
  golan:     { primary: '#009688', secondary: '#00695f' },
  rami_levy: { primary: '#e32032', secondary: '#b51a28' },
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
