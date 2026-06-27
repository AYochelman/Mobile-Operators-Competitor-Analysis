# MOCA eSIM Compare - B2C Launch Kit

Everything needed to launch **MOCA eSIM Compare** to consumers and drive viral reach.

**Product:** a free, no-login page where a traveler picks where they're flying and instantly sees the cheapest eSIM deals across 30+ global providers, refreshed twice a day.
**Live URL:** `esim.mocaintel.com` (also `mocaintel.com/esim-deals`)
**Audience:** Israeli outbound travelers first (backpackers, families, business, digital nomads), then global.
**Money:** affiliate redirect on every "get this deal" tap + our own promo codes (Voye 15%, Saily 10%).
**Brand:** mocha-latte (espresso `#5c3317`, hot-orange `#c9622f`, cream `#f9f4ee`). HE default + EN. Mobile-first.

## Files

| File | What it gives you |
|------|-------------------|
| [00-launch-plan.md](00-launch-plan.md) | The strategy: positioning, audience, funnel, channels, 6-week launch calendar, budget, KPIs, tracking setup |
| [01-viral-video-scripts.md](01-viral-video-scripts.md) | 7 short-form video scripts (hook + shot list + on-screen text + VO + CTA) built for Reels / TikTok / Shorts |
| [02-carousel-banners.md](02-carousel-banners.md) | 5 carousel decks, slide-by-slide copy + exact design specs in the MOCA palette (Instagram/LinkedIn) |
| [03-social-posts.md](03-social-posts.md) | Ready-to-paste posts in Hebrew AND English, with 30+ hook variants, per platform |
| [04-higgsfield-storyboards.md](04-higgsfield-storyboards.md) | 4 UGC storyboards with paste-ready Higgsfield image + motion prompts and dialogue |
| [05-garyvee-playbook.md](05-garyvee-playbook.md) | The Gary Vaynerchuk-style distribution playbook: how to actually maximize exposure at launch |

## The one-sentence pitch
> "Before your next flight, check MOCA - it compares 30+ eSIM providers in 10 seconds and shows you the cheapest data for exactly where you're going. Free, no sign-up."

## Three numbers that sell it
- **30+** global eSIM providers compared in one place
- **2x/day** price refresh (it's never stale)
- **0₪** to use, **0** sign-up, **10 sec** to an answer

## Launch-day non-negotiables (detail in 00-launch-plan.md)
1. Flip `ESIM_B2C_LIVE = true`, rebuild, deploy `mass-market-app/dist`, verify the live bundle.
2. Confirm `esim.mocaintel.com` resolves (Netlify domain alias + Cloudflare CNAME).
3. Add click attribution so B2C traffic is measurable (the `src=esim` param is currently dropped - see plan).
4. Stand up the social handles + link-in-bio before posting anything.
