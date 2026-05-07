/**
 * Free app lists for plans that include "גלישה חופשית באפליקציות נבחרות".
 * Used for both abroad bundles (Cellcom, Pelephone) and domestic 5G plans
 * that exempt specific apps from the data quota (Golan 750GB).
 */

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
// Currently only the 750GB 5G plan ships with the "גלישה חופשית באפליקציות נבחרות" benefit.
export const GOLAN_APPS_BY_PLAN = {
  'גולן 750GB 5G': [SPOTIFY, YOUTUBE, WHATSAPP, FACEBOOK, INSTAGRAM, NETFLIX],
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
    const apps = GOLAN_APPS_BY_PLAN[plan.plan_name];
    if (apps) return { title: 'גולן — גלישה חופשית באפליקציות', apps };
  }
  return null;
}

// Back-compat alias — older imports
export const getAppsForAbroadPlan = getAppsForPlan;
