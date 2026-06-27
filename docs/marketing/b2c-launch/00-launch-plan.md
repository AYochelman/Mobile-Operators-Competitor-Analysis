# B2C Launch Plan - MOCA eSIM Compare

## 1. The product, in plain language
A free web page. You pick the country you're flying to. It instantly shows you the cheapest eSIM data plans for that country, compared across 30+ global providers, with the real price in shekels. No app to download, no account, no email. It updates twice a day so the prices are never stale.

The whole reason it exists: roaming from an Israeli carrier abroad is brutally expensive, buying a local SIM means a queue and a passport, and there are 30+ eSIM brands selling wildly different prices for the same country. Nobody compares them. We do, in 10 seconds, for free.

## 2. Positioning (the wedge)
**Category we own:** "the price-comparison engine for travel data."
Not an eSIM seller (we're neutral, we compare everyone). Not a travel blog (we're live data). We are the *Booking.com / Google Flights of eSIM*.

**Positioning statement:**
> For travelers who don't want to overpay for data abroad, MOCA is the free comparison engine that shows the cheapest eSIM for your exact destination in 10 seconds, because we track 30+ providers twice a day so you don't have to.

**Why this wins:** every competitor is a single eSIM brand spending money to convince you *their* plan is good. We're the referee. Referees get trusted, and trust is the only durable moat in affiliate.

## 3. Target audiences (in priority order)
1. **Backpackers / post-army trips** - גאורגיה, תאילנד, דרום אמריקה, הודו. Price-obsessed, phone-native, share everything. Highest viral coefficient. **Start here.**
2. **Family vacationers** - Europe (Italy, Greece, Spain), USA, Dubai. Decision-maker is the parent who organizes the trip. Hate surprises on the bill.
3. **Business / frequent flyers** - USA, Europe, UAE. Time-poor, will pay a little more for the best fit. High repeat usage.
4. **Digital nomads / long-stay** - want unlimited / 30-day plans. Small but loyal and influential.

**Beachhead = audience #1.** Win the backpacker forums and travel Reels first; the rest follow the social proof.

## 4. The core message hierarchy
- **Level 1 (hook / awareness):** "Stop overpaying for internet abroad."
- **Level 2 (value):** "We compare 30+ eSIM providers and show you the cheapest for your trip. Free."
- **Level 3 (proof):** "Updated twice a day. No sign-up. Same eSIM, sometimes 4x cheaper depending who you buy from."
- **Level 4 (action):** "Check before your next flight: esim.mocaintel.com"

## 5. The funnel
```
Short-form video / Reels / TikTok (top of funnel, organic)
        │  hook: roaming-bill shock + price-gap reveal
        ▼
Carousel + bio link / story (consideration)
        │  proof: how it works, destination price reveals
        ▼
esim.mocaintel.com  (pick destination → see deals)   ← the product IS the landing page
        │
        ▼
"Get this deal ↗"  → affiliate redirect /go  → provider checkout
        │  (+ MOCA promo codes: Voye 15%, Saily 10%)
        ▼
Commission + repeat visitor + word of mouth
```
The product needs no separate landing page - it *is* a landing page. Every piece of content drives to a destination-specific deep link (`esim.mocaintel.com/?dest=יוון`), so the user lands already on results for the country in the video.

## 6. Channel strategy
**Organic-first.** Attention is cheapest on short-form video right now; that is where launch budget = zero buys reach. Paid comes only after we know which creative converts.

| Channel | Role | Cadence |
|---------|------|---------|
| Instagram Reels | Primary reach + carousels | 1 Reel/day + 3 carousels/week |
| TikTok | Primary reach (younger, backpackers) | 1-2/day, repurpose Reels natively |
| YouTube Shorts | Reach + SEO long-tail | daily repurpose |
| Facebook groups | Distribution into travel communities (טיolים, backpacking groups) | value comments, not spam |
| Threads / X | Real-time, screenshots of price gaps | 1-3/day |
| WhatsApp / Telegram | The Israeli super-channel: shareable deep links | every video ends with "share this" |
| Reddit (r/travel, r/esim, r/solotravel) | High-intent English audience | helpful answers, link when relevant |
| Email/SMS capture (light) | Retention (optional v2) | n/a at launch |

**Deliberately NOT at launch:** paid search, billboards, influencer cash deals. Earn the organic signal first.

## 7. Six-week launch calendar
**Week 0 - Pre-launch (build the rails)**
- Flip `ESIM_B2C_LIVE = true`, build, deploy, verify live bundle + `esim.mocaintel.com`.
- Fix click attribution so `src=esim` is logged (see §10).
- Create handles: `@moca.esim` (IG/TikTok), claim X/Threads/YouTube. Link-in-bio (Linktree or a tiny page) → destination picker.
- Shoot a batch of 15-20 videos in one session (see 01-viral-video-scripts.md). Bank content.
- Seed 5 carousels (see 02-carousel-banners.md).

**Week 1 - Soft launch / "we exist"**
- Post the founder story video + "the trick" video. 1 video/day.
- Drop the "Stop overpaying" carousel.
- Personally share into 10 travel WhatsApp/Facebook groups with a genuine "I built this, it's free" note.
- Reply to every single comment within the first hour (the $1.80 strategy starts now).

**Week 2 - Destination blitz**
- One video per popular destination using live price reveals (Japan, Greece, Thailand, USA, Georgia, Dubai).
- Deep-link each to its `?dest=` page.
- Start the "$1.80" routine: 2 thoughtful comments on 90 travel posts/day.

**Week 3 - Social proof loop**
- Repost any user that mentions saving money. Screenshot price gaps people send you.
- Launch a UGC ask: "tell us your worst roaming bill" (storyboards in 04).
- First small paid test (₪50-100/day) on the single best-performing organic video.

**Week 4 - Authority + SEO**
- Publish destination posts/Shorts targeting "eSIM for [country] price" searches.
- Threads/X: weekly "biggest price gap this week" data drop (you already compute this - MarketMoversWidget logic).

**Week 5 - Scale winners**
- Kill losers, 3x the budget on the 1-2 winning creatives.
- Pitch 3-5 micro travel-creators a free collab (they get content, you get reach).

**Week 6 - Lock the system**
- Codify the content engine: 1 pillar piece → 20 micro clips/week.
- Review KPIs, decide paid scale.

## 8. Budget (lean launch)
| Item | Cost |
|------|------|
| Content (you + phone) | 0 |
| Handles, link-in-bio | 0 |
| Editing app (CapCut) | 0 |
| Paid test (weeks 3-6) | ₪1,500-3,000 total |
| Optional micro-creator collabs | product/affiliate-share, ~0 cash |
**Total cash to launch: under ₪3,000.** This is an attention play, not a media-buy play.

## 9. KPIs
**North star:** affiliate clicks from B2C (`src=esim`) → conversions.
- **Awareness:** views, reach, follower growth, saves+shares (shares > likes for this).
- **Activation:** sessions on `esim.mocaintel.com`, destination picks, % who reach results.
- **Revenue:** "get this deal" taps → `/go` clicks → confirmed commissions; promo-code redemptions (Voye/Saily).
- **Efficiency:** cost per affiliate click (once paid starts); viral coefficient (shares per 100 views).
Weekly review. Double down on whatever drives *shares* and *deep-link clicks*, not vanity likes.

## 10. Tracking setup (do this before launch - it's currently a gap)
The memory note flags it: the affiliate click currently **drops the `src` param**, so B2C traffic isn't distinguishable in the log.
**Action items:**
1. In `app.py` `log_affiliate_click`, persist the `src` query param (e.g. `src=esim`) on the click row.
2. Have every piece of content link with `?src=esim&utm_source=<channel>` so you can attribute by channel.
3. Add a lightweight analytics tag (Plausible or GA4) to the `esim.mocaintel.com` host - it's a clean microsite, easy to instrument.
4. Build (or reuse) a tiny "B2C dashboard" view: sessions, top destinations, clicks by provider, code redemptions.
Without this you're flying blind on which video actually made money. This is the single highest-leverage pre-launch task.

## 11. Risks & guardrails
- **Affiliate approvals pending** (Airalo/Saily/Voye per memory): make sure the providers featured in launch creative are LIVE-approved so clicks actually pay. Lead with the codes you own (Voye 15%, Saily 10%).
- **Price accuracy:** the page already shows "updated twice a day" + live FX. Keep the disclaimer ("final price on provider page"). Never promise an exact price in a video that could be stale - say "from ₪X" and let the live page be the source of truth.
- **Trust = the asset.** Never fake a price gap. The whole brand is "the honest referee." One caught exaggeration kills it.
- **Don't gate it.** The magic is no sign-up. Resist any urge to add a wall before launch.
