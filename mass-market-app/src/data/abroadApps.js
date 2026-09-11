/**
 * Free app lists for plans that include "גלישה חופשית באפליקציות נבחרות".
 * Used for both abroad bundles (Cellcom, Pelephone) and domestic 5G plans
 * that exempt specific apps from the data quota (Golan 750GB).
 */

import { carrierLabel } from './carrierLabels'

// Logo URLs were removed 2026-09-11 (Wikimedia hot-links of third-party marks);
// AppsModal renders the names as text chips.
const WHATSAPP   = { name: 'WhatsApp' };
const INSTAGRAM  = { name: 'Instagram' };
const FACEBOOK   = { name: 'Facebook' };
const TIKTOK     = { name: 'TikTok' };
const GMAPS      = { name: 'Google Maps' };
const WAZE       = { name: 'Waze' };
const SNAPCHAT   = { name: 'Snapchat' };
const TRIPADV    = { name: 'Tripadvisor' };
const YOUTUBE    = { name: 'YouTube' };
const NETFLIX    = { name: 'Netflix' };
const CHATGPT    = { name: 'ChatGPT' };
const GEMINI     = { name: 'Gemini' };
const SPOTIFY    = { name: 'Spotify' };

export const CELLCOM_APPS   = [WHATSAPP, INSTAGRAM, FACEBOOK, TIKTOK, GMAPS, WAZE];
export const PELEPHONE_APPS = [FACEBOOK, WAZE, SNAPCHAT, INSTAGRAM, WHATSAPP, GMAPS, TRIPADV, YOUTUBE, NETFLIX, TIKTOK, CHATGPT, GEMINI];

// Golan: per-plan apps list (sourced from each plan's PDF terms — see scraper.py PDF URLs).
// The domestic 750GB plan ships "גלישה חופשית באפליקציות נבחרות" but doesn't name the apps
// on the card, so it's keyed here. Roaming bundles DO name them, parsed via APP_BY_NAME below.
export const GOLAN_APPS_BY_PLAN = {
  'גולן 750GB': [SPOTIFY, YOUTUBE, WHATSAPP, FACEBOOK, INSTAGRAM, NETFLIX],
};

// Name → icon map (English + Hebrew aliases) for plans that list their free apps by name
// in extras, e.g. Golan roaming "גלישה חופשית באפליקציות: Waze · WhatsApp · ...".
const APP_BY_NAME = {
  waze: WAZE, ווייז: WAZE,
  whatsapp: WHATSAPP, וואטסאפ: WHATSAPP, ווטסאפ: WHATSAPP,
  facebook: FACEBOOK, פייסבוק: FACEBOOK,
  instagram: INSTAGRAM, אינסטגרם: INSTAGRAM,
  tiktok: TIKTOK, טיקטוק: TIKTOK,
  youtube: YOUTUBE, יוטיוב: YOUTUBE,
  spotify: SPOTIFY, ספוטיפיי: SPOTIFY,
  netflix: NETFLIX, נטפליקס: NETFLIX,
  snapchat: SNAPCHAT, 'סנאפצ\'אט': SNAPCHAT, סנאפצאט: SNAPCHAT,
  'google maps': GMAPS, gmaps: GMAPS, 'מפות גוגל': GMAPS,
  tripadvisor: TRIPADV, 'טריפאדוייזר': TRIPADV,
};

/**
 * Get free apps list for a plan (domestic or abroad).
 * Returns { title, apps } or null. Pelephone and Cellcom market this on their 5G
 * domestic plans (detected by an "אפליקציות" hint in extras). Golan 750GB markets
 * the same benefit but doesn't surface it in card extras, so we key by plan_name.
 */
export function getAppsForPlan(plan) {
  const carrier = plan.carrier;
  const extras = plan.extras || [];
  const hasApps = extras.some(e => /אפליקציות/.test(e));

  if (carrier === 'cellcom' && hasApps) {
    return { title: 'סלקום - גלישה חופשית באפליקציות', apps: CELLCOM_APPS };
  }
  if (carrier === 'pelephone' && hasApps) {
    return { title: 'פלאפון - גלישה חופשית באפליקציות', apps: PELEPHONE_APPS };
  }
  if (carrier === 'golan') {
    // 1) name-keyed list (domestic 750GB — card only says "אפליקציות נבחרות")
    const byName = GOLAN_APPS_BY_PLAN[plan.plan_name];
    if (byName) return { title: 'גולן - גלישה חופשית באפליקציות', apps: byName };
    // 2) roaming bundles name the apps in extras → parse + map to icons
    const line = extras.find(e => /גלישה חופשית באפליקציות\s*[:：]/.test(e));
    if (line) {
      const apps = line.split(/[:：]/)[1].split(/[·,]/)
        .map(s => APP_BY_NAME[s.trim().toLowerCase()] || APP_BY_NAME[s.trim()])
        .filter(Boolean);
      if (apps.length) return { title: 'גולן - גלישה חופשית באפליקציות', apps };
    }
  }

  // Generic: any plan that NAMES its free apps anywhere in extras — including inside the
  // "__info__|" plan-terms blob — e.g. Rami Levy roaming "גלישה חופשית באפליקציות
  // Facebook, Waze, Snapchat, Whatsapp, Google Maps, Tripadvisor." Map each named app →
  // icon and show the link only when at least one name resolves (so an unnamed
  // "אפליקציות נבחרות" stays hidden). Carriers handled above return before reaching here.
  if (hasApps) {
    const m = extras.join('\n').match(/גלישה חופשית באפליקציות\s*[:：]?\s*([^\n.]+)/);
    if (m) {
      const apps = m[1].split(/[·,]/)
        .map(s => APP_BY_NAME[s.trim().toLowerCase()] || APP_BY_NAME[s.trim()])
        .filter(Boolean);
      if (apps.length) return { title: `${carrierLabel(carrier)} - גלישה חופשית באפליקציות`, apps };
    }
  }
  return null;
}

// Back-compat alias — older imports
export const getAppsForAbroadPlan = getAppsForPlan;
