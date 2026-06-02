/**
 * Free app lists for plans that include "גלישה חופשית באפליקציות נבחרות".
 * Used for both abroad bundles (Cellcom, Pelephone) and domestic 5G plans
 * that exempt specific apps from the data quota (Golan 750GB).
 */

import { carrierLabel } from './carrierLabels'

const WHATSAPP   = { name: 'WhatsApp',    logo: 'https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg' };
const INSTAGRAM  = { name: 'Instagram',   logo: 'https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg' };
const FACEBOOK   = { name: 'Facebook',    logo: 'https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg' };
const TIKTOK     = { name: 'TikTok',      logo: 'https://upload.wikimedia.org/wikipedia/en/a/a9/TikTok_logo.svg' };
const GMAPS      = { name: 'Google Maps', logo: 'https://upload.wikimedia.org/wikipedia/commons/b/bd/Google_Maps_Logo_2020.svg' };
const WAZE       = { name: 'Waze',        logo: '/app-icons/waze.png' };
const SNAPCHAT   = { name: 'Snapchat',    logo: 'https://upload.wikimedia.org/wikipedia/en/c/c4/Snapchat_logo.svg' };
const TRIPADV    = { name: 'Tripadvisor', logo: '/app-icons/tripadvisor.png' };
const YOUTUBE    = { name: 'YouTube',     logo: 'https://upload.wikimedia.org/wikipedia/commons/0/09/YouTube_full-color_icon_%282017%29.svg' };
const NETFLIX    = { name: 'Netflix',     logo: 'https://upload.wikimedia.org/wikipedia/commons/7/75/Netflix_icon.svg' };
const CHATGPT    = { name: 'ChatGPT',     logo: 'https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg' };
const GEMINI     = { name: 'Gemini',      logo: 'https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg' };
const SPOTIFY    = { name: 'Spotify',     logo: 'https://upload.wikimedia.org/wikipedia/commons/1/19/Spotify_logo_without_text.svg' };

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
    return { title: 'סלקום — גלישה חופשית באפליקציות', apps: CELLCOM_APPS };
  }
  if (carrier === 'pelephone' && hasApps) {
    return { title: 'פלאפון — גלישה חופשית באפליקציות', apps: PELEPHONE_APPS };
  }
  if (carrier === 'golan') {
    // 1) name-keyed list (domestic 750GB — card only says "אפליקציות נבחרות")
    const byName = GOLAN_APPS_BY_PLAN[plan.plan_name];
    if (byName) return { title: 'גולן — גלישה חופשית באפליקציות', apps: byName };
    // 2) roaming bundles name the apps in extras → parse + map to icons
    const line = extras.find(e => /גלישה חופשית באפליקציות\s*[:：]/.test(e));
    if (line) {
      const apps = line.split(/[:：]/)[1].split(/[·,]/)
        .map(s => APP_BY_NAME[s.trim().toLowerCase()] || APP_BY_NAME[s.trim()])
        .filter(Boolean);
      if (apps.length) return { title: 'גולן — גלישה חופשית באפליקציות', apps };
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
      if (apps.length) return { title: `${carrierLabel(carrier)} — גלישה חופשית באפליקציות`, apps };
    }
  }
  return null;
}

// Back-compat alias — older imports
export const getAppsForAbroadPlan = getAppsForPlan;
