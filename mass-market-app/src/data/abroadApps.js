/**
 * Free app lists for abroad plans (גלישה חופשית באפליקציות).
 */

export const CELLCOM_APPS = [
  { name: 'WhatsApp',    logo: 'https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg' },
  { name: 'Instagram',   logo: 'https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg' },
  { name: 'Facebook',    logo: 'https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg' },
  { name: 'TikTok',      logo: 'https://upload.wikimedia.org/wikipedia/en/a/a9/TikTok_logo.svg' },
  { name: 'Google Maps', logo: 'https://upload.wikimedia.org/wikipedia/commons/b/bd/Google_Maps_Logo_2020.svg' },
  { name: 'Waze',        logo: '/app-icons/waze.png' },
];

export const PELEPHONE_APPS = [
  { name: 'Facebook',    logo: 'https://upload.wikimedia.org/wikipedia/commons/b/b8/2021_Facebook_icon.svg' },
  { name: 'Waze',        logo: '/app-icons/waze.png' },
  { name: 'Snapchat',    logo: 'https://upload.wikimedia.org/wikipedia/en/c/c4/Snapchat_logo.svg' },
  { name: 'Instagram',   logo: 'https://upload.wikimedia.org/wikipedia/commons/e/e7/Instagram_logo_2016.svg' },
  { name: 'WhatsApp',    logo: 'https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg' },
  { name: 'Google Maps', logo: 'https://upload.wikimedia.org/wikipedia/commons/b/bd/Google_Maps_Logo_2020.svg' },
  { name: 'Tripadvisor', logo: '/app-icons/tripadvisor.png' },
  { name: 'YouTube',     logo: 'https://upload.wikimedia.org/wikipedia/commons/0/09/YouTube_full-color_icon_%282017%29.svg' },
  { name: 'Netflix',     logo: 'https://upload.wikimedia.org/wikipedia/commons/7/75/Netflix_icon.svg' },
  { name: 'TikTok',      logo: 'https://upload.wikimedia.org/wikipedia/en/a/a9/TikTok_logo.svg' },
  { name: 'ChatGPT',     logo: 'https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg' },
  { name: 'Gemini',      logo: 'https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg' },
];

/**
 * Get free apps list for a plan (domestic or abroad).
 * Returns { title, apps } or null. Pelephone and Cellcom both market "גלישה
 * חופשית באפליקציות נבחרות" on their 5G domestic plans, not just abroad.
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
  return null;
}

// Back-compat alias — older imports
export const getAppsForAbroadPlan = getAppsForPlan;
