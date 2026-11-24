// Campaign types banner_vision.py assigns to a banner reading (mirror of
// CAMPAIGN_TYPES in banner_vision.py) and their display labels.
export const CAMPAIGN_TYPE = {
  price_plan: { he: 'חבילת סלולר', en: 'Mobile plan' },
  device:     { he: 'מכשיר', en: 'Device' },
  roaming:    { he: 'חו״ל', en: 'Roaming' },
  fiber_tv:   { he: 'אינטרנט וטלוויזיה', en: 'Internet and TV' },
  esim:       { he: 'eSIM', en: 'eSIM' },
  service:    { he: 'שירות', en: 'Service' },
  brand:      { he: 'תדמית', en: 'Brand' },
  other:      { he: 'אחר', en: 'Other' },
}

export function campaignTypeLabel(type, tt) {
  const t = CAMPAIGN_TYPE[type] || CAMPAIGN_TYPE.other
  return tt(t.he, t.en)
}
