"""Scheduled jobs (social sentiment, executive summary, news, resellers, morning digest, scraper drift) and their refresh / preview endpoints.

Extracted from app.py by scripts/split_monolith.py (2026-09).
Names defined in app.py are referenced as `core.<name>` (late-bound) so
monkeypatching `app.<name>` in tests keeps working; app.py re-exports
everything defined here.
"""
import app as core  # noqa: E402  (the monolith; imported at its bottom)
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request, make_response, send_from_directory, g, abort, redirect, Response
logger = core.logger
from flask import Blueprint
bp = Blueprint("jobs", __name__)


def _price_direction(change):
    """Return 'up', 'down', or None for a price_change record."""
    try:
        old, new = float(change['old_val']), float(change['new_val'])
        if new > old: return 'up'
        if new < old: return 'down'
        return None
    except (ValueError, TypeError):
        return None


# Carrier ID \u2192 display name for price-history endpoints.
# MUST stay in sync with mass-market-app/src/data/carrierLabels.js
# (mirrors _CARRIER_NAMES below; both track the JS GLOBAL_LABELS/DOMESTIC_LABELS).
_HISTORY_CARRIER_NAMES = {
    'partner': '\u05e4\u05e8\u05d8\u05e0\u05e8',
    'pelephone': '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
    'hotmobile': '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
    'cellcom': '\u05e1\u05dc\u05e7\u05d5\u05dd',
    'mobile019': '019',
    'xphone': 'XPhone',
    'wecom': 'We-Com',
    'neptucom': 'Neptucom',
    'tuki': 'Tuki',
    'terminalesim': 'Terminal eSIM',
    'gigsky': 'GigSky',
    'esimgenius': 'eSIM Genius',
    'nisim': 'Nisim eSIM',
    'esimax': 'eSIM Max',
    'venterrasim': 'VenterraSIM',
    'simzol': 'Simzol',
    'airalo': 'Airalo',
    'pelephone_global': 'GlobalSIM',
    'esimo': 'eSIMo',
    'simtlv': 'SimTLV',
    'world8': '8 World',
    'xphone_global': 'XPhone Global',
    'saily': 'Saily',
    'holafly': 'Holafly',
    'esimio': 'eSIM.io',
    'sparks': 'Sparks',
    'voye': 'VOYE',
    'orbit': 'Orbit',
    'travelsim': 'Travel Sim',
    'gomoworld': 'GoMoWorld',
    'tasim': 'Tasim',
    'maya': 'Maya Mobile',
    'esim70': 'eSIM70',
    'jetpack': 'Jetpack',
    'breez': 'Breeze',
    'bytesim': 'ByteSim',
    'besim': 'Besim',
    'seven_g': '7G',
    'bestconnect': 'Best Connect',
    'bnesim': 'BNESIM',
    'esimplus': 'eSIM Plus',
    'bcengi': 'Bcengi',
    'yesim': 'Yesim', 'nomad': 'Nomad', 'ubigi': 'Ubigi', 'alosim': 'aloSIM',
}


_HISTORY_TYPE_NAMES = {
    'domestic': '\u05de\u05e7\u05d5\u05de\u05d9',
    'abroad': '\u05d7\u05d5"\u05dc',
    'global': '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9',
    'content': '\u05ea\u05d5\u05db\u05df',
}


CARRIER_DISPLAY = {
    "partner":   {"name": "פרטנר",      "url": "https://www.partner.net.il",       "color": "#2ed5c4"},
    "pelephone": {"name": "פלאפון",     "url": "https://www.pelephone.co.il",      "color": "#001fff"},
    "hotmobile": {"name": "הוט מובייל", "url": "https://www.hotmobile.co.il",      "color": "#e3001e"},
    "cellcom":   {"name": "סלקום",      "url": "https://www.cellcom.co.il",        "color": "#9530ff"},
    "mobile019": {"name": "019 מובייל", "url": "https://www.019mobile.co.il",      "color": "#e8202a"},
    "xphone":    {"name": "XPhone",     "url": "https://www.xphone.co.il",         "color": "#2b9fd5"},
    "wecom":     {"name": "וי-קום",     "url": "https://we-com.co.il",             "color": "#ff4500"},
    "neptucom":  {"name": "נפטוקום",    "url": "https://www.neptucom.com",         "color": "#29b6d6"},
    "golan":     {"name": "גולן טלקום", "url": "https://www.golantelecom.co.il",   "color": "#cc1717"},
    "rami_levy": {"name": "רמי לוי תקשורת", "url": "https://mobile.rami-levy.co.il",  "color": "#e8178a"},
}


CARRIER_STORE_DISPLAY = {
    "pelephone": {"name": "פלאפון",     "url": "https://www.pelephone.co.il/ds/heb/eshop/lobby/", "color": "#001fff"},
    "cellcom":   {"name": "סלקום",      "url": "https://shop.cellcom.co.il/",                      "color": "#9530ff"},
    "partner":   {"name": "פרטנר",      "url": "https://store.partner.co.il/home",                 "color": "#2ed5c4"},
    "hotmobile": {"name": "הוט מובייל", "url": "https://hotstore.hotmobile.co.il/smartphones.html","color": "#e3001e"},
}


CARRIER_SEARCH_TERMS = {
    'partner': {
        'he':   '\u05e4\u05e8\u05d8\u05e0\u05e8',
        'en':   'Partner Communications',
        'tags': ['\u05e4\u05e8\u05d8\u05e0\u05e8', 'partner_il', 'partnertv'],
    },
    'pelephone': {
        'he':   '\u05e4\u05dc\u05d0\u05e4\u05d5\u05df',
        'en':   'Pelephone',
        'tags': ['\u05e4\u05dc\u05d0\u05e4\u05d5\u05df', 'pelephone'],
    },
    'cellcom': {
        'he':   '\u05e1\u05dc\u05e7\u05d5\u05dd',
        'en':   'Cellcom Israel',
        'tags': ['\u05e1\u05dc\u05e7\u05d5\u05dd', 'cellcom'],
    },
    'hotmobile': {
        'he':   '\u05d4\u05d5\u05d8 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'en':   'Hot Mobile Israel',
        'tags': ['\u05d4\u05d5\u05d8\u05de\u05d5\u05d1\u05d9\u05d9\u05dc', 'hotmobile'],
    },
    'mobile019': {
        'he':   '019 \u05de\u05d5\u05d1\u05d9\u05d9\u05dc',
        'en':   '019 Mobile',
        'tags': ['019mobile', '019\u05de\u05d5\u05d1\u05d9\u05d9\u05dc'],
    },
    'xphone': {
        'he':   '\u05d0\u05e7\u05e1 \u05e4\u05d5\u05df',
        'en':   'XPhone Israel',
        'tags': ['xphone'],
    },
    'wecom': {
        'he':   '\u05d5\u05d9 \u05e7\u05d5\u05dd',
        'en':   'WeCom Israel',
        'tags': ['wecom', '\u05d5\u05d9\u05e7\u05d5\u05dd'],
    },
    'neptucom': {
        'he':   'Neptucom',
        'en':   'Neptucom Israel',
        'tags': ['neptucom'],
    },
    'golan': {
        'he':   '\u05d2\u05d5\u05dc\u05df \u05d8\u05dc\u05e7\u05d5\u05dd',
        'en':   'Golan Telecom',
        'tags': ['golantelecom', '\u05d2\u05d5\u05dc\u05df\u05d8\u05dc\u05e7\u05d5\u05dd'],
    },
    'rami_levy': {
        'he':   '\u05e8\u05de\u05d9 \u05dc\u05d5\u05d9 \u05ea\u05e7\u05e9\u05d5\u05e8\u05ea',
        'en':   'Rami Levy Communications',
        'tags': ['ramilevy', '\u05e8\u05de\u05d9\u05dc\u05d5\u05d9\u05ea\u05e7\u05e9\u05d5\u05e8\u05ea'],
    },
}


def _normalize_post(platform, raw):
    """Normalize a raw Apify post dict to a consistent schema.

    Handles field-name differences across actors:
      Facebook  (scrapeforge~facebook-search-posts):   message, post_text, content
      Instagram (apify~instagram-hashtag-scraper):     caption, alt
      Twitter   (api-ninja~x-twitter-advanced-search): text, full_text, tweet_text
      TikTok    (clockworks~tiktok-scraper):           text, description
    """
    text = (
        raw.get('message') or raw.get('post_text') or raw.get('content') or
        raw.get('caption') or raw.get('alt') or
        raw.get('text') or raw.get('full_text') or raw.get('tweet_text') or
        raw.get('description') or raw.get('title') or ''
    )
    likes = (
        raw.get('likesCount') or raw.get('diggCount') or raw.get('likes') or
        raw.get('likeCount') or raw.get('favoriteCount') or
        raw.get('like_count') or raw.get('retweet_count') or 0
    )
    date = (
        raw.get('time') or raw.get('timestamp') or raw.get('date') or
        raw.get('createdAt') or raw.get('created_at') or raw.get('publishedAt') or
        raw.get('post_date') or ''
    )
    url = (
        raw.get('url') or raw.get('postUrl') or raw.get('post_url') or
        raw.get('webVideoUrl') or raw.get('link') or raw.get('tweet_url') or ''
    )
    likes_val = likes
    if not isinstance(likes_val, int):
        try:
            likes_val = int(likes_val)
        except (TypeError, ValueError):
            likes_val = 0
    return {
        'platform': platform,
        'text':     str(text)[:400],
        'likes':    likes_val,
        'date':     str(date),
        'url':      str(url),
    }


def generate_social_sentiment():
    """Scrape social media for each carrier and generate Hebrew sentiment analysis.

    Runs every 3 days at 08:00 via APScheduler and on-demand via POST /api/social-sentiment/refresh.
    Requires 'apify_api_key' and 'anthropic_api_key' in config.json.
    """
    logger.info("Generating social sentiment...")
    config = core.load_config()
    anthropic_key = config.get("anthropic_api_key", "")
    apify_key     = config.get("apify_api_key", "")
    if not anthropic_key:
        logger.warning("social sentiment: anthropic_api_key missing, skipping")
        return
    if not apify_key:
        logger.warning("social sentiment: apify_api_key missing — add 'apify_api_key' to config.json")
        return

    import requests as _req
    import re as _re

    def _scrape_apify(platform, actor_slug, actor_input):
        """Call Apify run-sync and return normalized post list (max 10).

        actor_slug must use ~ separator (e.g. 'apify~facebook-posts-scraper').
        Apify run-sync returns 200 or 201; both indicate dataset items.
        """
        try:
            url = (
                f"https://api.apify.com/v2/acts/{actor_slug}/run-sync-get-dataset-items"
                f"?token={apify_key}&timeout=60&memory=256"
            )
            resp = _req.post(url, json=actor_input, timeout=75)
            if resp.status_code not in (200, 201):
                logger.warning(f"social sentiment: Apify {platform} HTTP {resp.status_code} — {resp.text[:150]}")
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            # Filter out error/empty sentinel items
            valid = [
                item for item in data
                if isinstance(item, dict)
                and not item.get('error')
                and not item.get('noResults')
                and (item.get('message') or item.get('caption') or item.get('text')
                     or item.get('full_text') or item.get('description') or item.get('title'))
            ]
            return [_normalize_post(platform, item) for item in valid[:10]]
        except Exception as exc:
            logger.warning(f"social sentiment: {platform} failed: {exc}")
            return []

    # Social LISTENING: search public mentions of carriers, not their own pages.
    system_prompt = (
        "אתה אנליסט מדיה חברתית במחלקת השיווק של Pelephone. "
        "תפקידך לנטר את שיח הציבור על ספקי הסלולר ולהסיק משמעויות עבור מנהל השיווק של Pelephone. "
        "אתה מקבל פוסטים של לקוחות ומשתמשים רגילים ברשתות החברתיות שמאזכרים ספק סלולר מסוים. "
        "כאשר הספק הוא Pelephone — נתח מה אומר הציבור עלינו ומה משמעות הדבר לפעילות השיווקית. "
        "כאשר הספק הוא מתחרה — נתח מה חולשותיו וחוזקותיו בעיני הציבור ומה Pelephone יכולה ללמוד מכך. "
        "כתוב אך ורק בעברית תקנית, נכונה ורהוטה. "
        "השתמש במילים עבריות קיימות ונפוצות בלבד — אל תמציא מילים. "
        "שמות ספקים וחברות תמיד באנגלית (Partner, Pelephone, Cellcom, Hot Mobile, 019, XPhone, WeCom). "
        "אסור לתרגם שמות ספקים לעברית. "
        "אסור להשתמש ב-Markdown, כותרות, כוכביות, או תבליטים. "
        "כתוב פרוזה רגילה בלבד. "
        "בסוף התגובה, הוסף שורה חדשה: SENTIMENT: ולאחריה אחת מ: positive / negative / neutral / mixed"
    )

    platform_labels = {
        'facebook':  '\u05e4\u05d9\u05d9\u05e1\u05d1\u05d5\u05e7',
        'instagram': '\u05d0\u05d9\u05e0\u05e1\u05d8\u05d2\u05e8\u05dd',
        'twitter':   'Twitter / X',
        'tiktok':    'TikTok',
    }
    since_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')

    from urllib.parse import quote as _url_quote

    for carrier, terms in CARRIER_SEARCH_TERMS.items():
        try:
            platform_data = {}
            he_term = terms['he']
            en_term = terms['en']
            tags     = terms.get('tags', [he_term])

            # ── Facebook: search public posts mentioning the carrier ──────────
            # scrapeforge~facebook-search-posts: keyword search across public posts
            fb_query = f"{he_term} OR {en_term}"
            posts = _scrape_apify('facebook', 'scrapeforge~facebook-search-posts', {
                'query':        fb_query,
                'search_type':  'posts',
                'max_results':  15,
                'recent_posts': True,
            })
            if posts:
                platform_data['facebook'] = posts

            # ── Instagram: search by Hebrew hashtag ───────────────────────────
            # apify~instagram-hashtag-scraper: official hashtag search actor
            posts = _scrape_apify('instagram', 'apify~instagram-hashtag-scraper', {
                'hashtags':     [t.lstrip('#') for t in tags[:2]],
                'resultsType':  'posts',
                'resultsLimit': 10,
            })
            if posts:
                platform_data['instagram'] = posts

            # ── Twitter/X: search for public mentions in Hebrew ───────────────
            # api-ninja~x-twitter-advanced-search: keyword + language filter
            twitter_query = f'{he_term} OR {en_term}'
            posts = _scrape_apify('twitter', 'api-ninja~x-twitter-advanced-search', {
                'query':           twitter_query,
                'search_type':     'Latest',
                'numberOfTweets':  15,
                'contentLanguage': 'he',
                'timeWithinTime':  '7d',
                'tweetTypes':      ['original', 'quotes', 'replies'],
            })
            if posts:
                platform_data['twitter'] = posts

            # ── TikTok: search by hashtags ────────────────────────────────────
            posts = _scrape_apify('tiktok', 'clockworks~tiktok-scraper', {
                'hashtags':              [t.lstrip('#') for t in tags[:2]],
                'resultsPerPage':        10,
                'oldestPostDateUnified': since_date,
            })
            if posts:
                platform_data['tiktok'] = posts

            if not platform_data:
                logger.info(f"social sentiment: no mentions found for {carrier}, skipping")
                continue

            carrier_english = en_term
            total_posts = sum(len(v) for v in platform_data.values())
            posts_text = ''
            for platform, posts in platform_data.items():
                label = platform_labels.get(platform, platform)
                posts_text += f"\n{label} ({len(posts)} \u05e4\u05d5\u05e1\u05d8\u05d9\u05dd):\n"
                for p in posts:
                    if p['text']:
                        posts_text += f"  - {p['text'][:250]}\n"

            is_pelephone = (carrier == 'pelephone')
            perspective_line = (
                "סכם מה הציבור אומר עלינו (Pelephone), מה הנושאים החוזרים, ומה המשמעות לפעילות השיווקית שלנו."
                if is_pelephone else
                f"סכם מה הציבור אומר על {carrier_english}, והסק מה Pelephone יכולה ללמוד מכך — חולשות שניתן לנצל, או חוזקות שכדאי לקחת בחשבון."
            )
            prompt = (
                f"להלן {total_posts} פוסטים של משתמשים ברשתות החברתיות שמאזכרים את {carrier_english} ב-7 הימים האחרונים:\n"
                f"{posts_text}\n"
                f"כתוב פסקה אחת קצרה ורהוטה בעברית תקינה (3-4 משפטים, עד 80 מילה).\n"
                f"{perspective_line}\n"
                f"לאחר הפסקה, הוסף שתי שורות:\n"
                f"SENTIMENT: ואחריה אחת מ: positive / negative / neutral / mixed\n"
                f"COUNTS: positive:N negative:N neutral:N (כאשר N הוא מספר הפוסטים בכל קטגוריה)"
            )

            resp = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 400,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            _ss_body = resp.json()
            core._record_claude_call('social_sentiment', 'claude-sonnet-4-6', _ss_body)
            raw = _ss_body["content"][0]["text"].strip()

            sentiment = 'neutral'
            counts = {'positive': 0, 'negative': 0, 'neutral': 0}

            if 'SENTIMENT:' in raw:
                parts = raw.split('SENTIMENT:', 1)
                raw_narrative = parts[0].strip()
                after_sentiment = parts[1]
                for s in ['positive', 'negative', 'mixed', 'neutral']:
                    if s in after_sentiment.lower():
                        sentiment = s
                        break
                if 'COUNTS:' in after_sentiment:
                    counts_str = after_sentiment.split('COUNTS:', 1)[1]
                    for key in ['positive', 'negative', 'neutral']:
                        m = _re.search(rf'{key}:(\d+)', counts_str, _re.IGNORECASE)
                        if m:
                            counts[key] = int(m.group(1))
            else:
                raw_narrative = raw

            narrative = _re.sub(r'^#+\s*', '', raw_narrative, flags=_re.MULTILINE)
            narrative = _re.sub(r'\*+', '', narrative)
            narrative = _re.sub(r'\n{2,}', ' ', narrative).strip()

            platform_data['_counts'] = counts
            core.save_social_sentiment(carrier, platform_data, narrative, sentiment, db_path=core._db_path())
            logger.info(f"social sentiment: saved {carrier} ({sentiment})")

        except Exception as exc:
            logger.error(f"social sentiment: failed for {carrier}: {exc}", exc_info=True)

    logger.info("Social sentiment generation complete.")


_CATEGORY_LABELS = {
    'domestic': '\u05d7\u05d1\u05d9\u05dc\u05d5\u05ea \u05e1\u05dc\u05d5\u05dc\u05e8',
    'abroad':   '\u05d7\u05d5"\u05dc',
    'global':   '\u05d2\u05dc\u05d5\u05d1\u05dc\u05d9 (eSIM)',
    'content':  '\u05ea\u05d5\u05db\u05df',
}


def generate_executive_summary():
    """Generate AI-powered executive summary for all 4 categories and store in DB.

    Runs at 08:05 via APScheduler and on-demand via POST /api/executive-summary/refresh.
    """
    logger.info("Generating executive summary...")
    config = core.load_config()
    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        logger.warning("executive summary: anthropic_api_key missing, skipping")
        return

    import requests as _req
    try:
        from scraper import _get_usd_to_ils, _get_eur_to_ils
        usd_rate = _get_usd_to_ils()
        eur_rate = _get_eur_to_ils()
    except Exception as e:
        logger.warning(f"executive summary: could not get exchange rates: {e}, using defaults")
        usd_rate, eur_rate = 3.7, 4.0

    for category in ['domestic', 'abroad', 'global', 'content']:
        try:
            metrics = core.compute_executive_metrics(
                category, usd_rate=usd_rate, eur_rate=eur_rate, db_path=core._db_path()
            )
            if not metrics['chart_data']:
                logger.info(f"executive summary: no data for {category}, skipping")
                continue

            cat_label = _CATEGORY_LABELS.get(category, category)
            cheapest = metrics['cheapest']
            aggressive = metrics['most_aggressive']
            wc = metrics['weekly_changes']
            top_plans_str = '\n'.join(f"  - {p}" for p in metrics['top_plans'])

            cheapest_name = CARRIER_DISPLAY.get(cheapest['carrier'], {}).get('name', cheapest['carrier'])
            aggressive_name = CARRIER_DISPLAY.get(aggressive['carrier'], {}).get('name', aggressive['carrier'])

            prompt = (
                f"נתוני שוק עדכניים לקטגוריית {cat_label}:\n\n"
                f"הספק הזול ביותר: {cheapest_name} — {cheapest['value']} {cheapest['unit']}\n"
                f"הספק האגרסיבי ביותר (הכי הרבה הורדות מחיר ב-7 ימים): {aggressive_name} — {aggressive['changes']} שינויים\n"
                f"שינויים השבוע: סך הכל {wc['total']} ({wc['drops']} ירידות מחיר, {wc['rises']} עליות מחיר)\n\n"
                f"חבילות מובילות בשוק:\n{top_plans_str}\n\n"
                f"כתוב פסקה אחת קצרה ורהוטה בעברית תקינה ונכונה (3 עד 4 משפטים, עד 80 מילה).\n"
                f"הפסקה תנותח מנקודת מבטו של מנהל השיווק של Pelephone: מה מצב Pelephone ביחס למתחרים, אילו איומים או הזדמנויות עולים מהנתונים, ומה המשמעות השיווקית המיידית עבור Pelephone.\n"
                f"כתוב פרוזה רגילה בלבד — ללא כותרות, ללא מספרים, ללא תבליטים, ללא סימני Markdown."
            )

            resp = _req.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 400,
                    "system": (
                        "אתה אנליסט שוק בכיר במחלקת השיווק של Pelephone. "
                        "תפקידך לנתח את תמונת השוק ולהסיק משמעויות אסטרטגיות עבור מנהל השיווק של Pelephone. "
                        "כתוב אך ורק בעברית תקנית, נכונה ורהוטה. "
                        "השתמש במילים עבריות קיימות ונפוצות בלבד — אל תמציא מילים. "
                        "שמות ספקים וחברות יש לכתוב תמיד באנגלית בלבד (לדוגמה: Orbit, SimTLV, eSIMio, Airalo, Holafly, Voye, Partner, Pelephone, Cellcom, Hot Mobile, 019). "
                        "אסור לתעתק שמות ספקים לעברית. "
                        "השתמש במונחים מדויקים ובמשפטים קצרים וברורים. "
                        "אסור להשתמש ב-Markdown, כותרות, כוכביות, מספרים ממוספרים, או תבליטים. "
                        "כתוב פרוזה רגילה בלבד."
                    ),
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            _exec_body = resp.json()
            core._record_claude_call('executive_summary', 'claude-sonnet-4-6', _exec_body)
            raw_narrative = _exec_body["content"][0]["text"].strip()
            # Strip any markdown artifacts Claude might still produce
            import re as _re
            narrative = _re.sub(r'^#+\s*', '', raw_narrative, flags=_re.MULTILINE)
            narrative = _re.sub(r'\*+', '', narrative)
            narrative = _re.sub(r'\n{2,}', ' ', narrative).strip()

            core.save_executive_summary(category, metrics, narrative, db_path=core._db_path())
            logger.info(f"executive summary: saved {category}")

        except Exception as e:
            logger.error(f"executive summary: failed for {category}: {e}", exc_info=True)

    logger.info("Executive summary generation complete.")


def scrape_news_job():
    """Fetch Google News RSS for all domestic carriers and store in DB.

    Runs daily at 08:10 via APScheduler.
    """
    from scraper import scrape_carrier_news
    logger.info("Scraping carrier news from Google News RSS...")
    try:
        articles = scrape_carrier_news()
        core.upsert_news_articles(articles, db_path=core._db_path())
        logger.info(f"News scrape complete: {len(articles)} articles saved")
    except Exception as e:
        logger.error(f"News scrape job failed: {e}", exc_info=True)


# pelephon4u_scraper SILENCED 2026-07-26: pelephon4u.co.il returns 403 since
# ~2026-07-12 (Cloudways domain unmapped). Re-add if the site comes back.
RESELLER_SCRAPER_MODULES = ("pelephone_join_scraper", "btl_scrapers")


def scrape_resellers_job():
    """Scrape known reseller / below-the-line sources for promotional plans not
    on the carrier rate cards.

    Runs daily at 08:15 via APScheduler — 5 minutes before the morning digest,
    whose "מתחת לקו" section reads the reseller_changes this job writes. Each
    module is called in isolation so a failure in one doesn't block the others;
    btl_scrapers additionally isolates each SOURCE internally.

    Returns {module: {plans, changes}} for the manual-trigger endpoint.
    """
    logger.info("Scraping reseller websites...")
    from db import sync_reseller_plans
    result = {}
    for module_name in RESELLER_SCRAPER_MODULES:
        try:
            mod = __import__(module_name)
            plans = mod.scrape()
            if plans:
                changes = sync_reseller_plans(plans, db_path=core._db_path())
                logger.info(f"{module_name}: {len(plans)} plans synced, {len(changes)} changes")
                result[module_name] = {"plans": len(plans), "changes": len(changes)}
            else:
                logger.warning(f"{module_name}: 0 plans matched — site layout may have changed")
                result[module_name] = {"plans": 0, "changes": 0}
        except Exception as e:
            logger.error(f"{module_name} scrape failed: {e}", exc_info=True)
            result[module_name] = {"error": str(e)}
    return result


def run_morning_check_job(send=True):
    """Morning changes check — runs daily (default 08:20) via APScheduler.

    Why it exists: the 07:30/17:00 scrape jobs notify only on changes that are
    freshly detected at scrape time — if a notification is missed, or a scraper
    silently breaks and stops seeing a carrier's page, nothing tells the
    operator. This job is the daily heartbeat: it summarizes everything in the
    change log over the last N hours (new plans / removed plans / price &
    extras changes across domestic+abroad+global+content), flags carriers whose
    data went stale or empty (a broken scraper can never report a new plan it
    didn't see), and ALWAYS sends — an explicit "אין שינויים" included.

    config.json knobs (all optional):
      morning_check_time          "HH:MM"  — cron time, default "08:20"
      morning_check_window_hours  int      — lookback window, default 26
      morning_check_stale_hours   int      — freshness threshold, default 36
      morning_check_global_stale_hours int — global freshness threshold, default 72
      morning_check_whatsapp      bool     — also send via WhatsApp, default false
    """
    from db import get_recent_changes_summary, get_scrape_freshness
    from notifier import format_morning_digest, send_notification, send_whatsapp

    config = core.load_config()
    within = int(config.get("morning_check_window_hours", 26))
    stale_after = int(config.get("morning_check_stale_hours", 36))
    # Global eSIM providers scrape hundreds of per-country pages; coverage is partial
    # per run by design, so MAX(scraped_at) legitimately lags a domestic carrier's.
    # A blanket 36h threshold here false-positives on normal flakiness and trains the
    # operator to ignore the global section — which is how esimio (frozen since Apr 29)
    # and maya (May 11) rotted unnoticed. A days-scale threshold flags real breakage
    # (weeks of zero rows) while tolerating a missed run or two. Note: a broken global
    # scraper returns [] but save_global_plans never deletes, so its rows AGE rather
    # than vanish — the per-row staleness check below is what catches the breakage.
    global_stale_after = int(config.get("morning_check_global_stale_hours", 72))

    summary = get_recent_changes_summary(within_hours=within, db_path=core._db_path())
    freshness = get_scrape_freshness(db_path=core._db_path())

    warnings = []
    now = datetime.now()
    for category, rows in freshness.items():
        threshold = global_stale_after if category == "global" else stale_after
        for row in rows:
            hours_ago = None
            if row.get("last_scraped"):
                try:
                    hours_ago = (now - datetime.fromisoformat(row["last_scraped"])).total_seconds() / 3600
                except (ValueError, TypeError):
                    pass
            if not row.get("count") or hours_ago is None or hours_ago > threshold:
                warnings.append({"carrier": row["carrier"], "category": category,
                                 "count": row.get("count", 0),
                                 "last_scraped": row.get("last_scraped"),
                                 "hours_ago": round(hours_ago, 1) if hours_ago is not None else None})
    # A carrier whose rows vanished entirely has no GROUP BY row at all —
    # check the known domestic carriers explicitly (skip when the DB is empty,
    # e.g. a fresh install, to avoid 10 false alarms).
    domestic_seen = {r["carrier"] for r in freshness.get("domestic", [])}
    if domestic_seen:
        for cid in CARRIER_DISPLAY:
            if cid not in domestic_seen:
                warnings.append({"carrier": cid, "category": "domestic", "count": 0,
                                 "last_scraped": None, "hours_ago": None})

    message = format_morning_digest(summary, warnings, within_hours=within,
                                    lang=config.get("notify_lang", "he"))
    sent = {"telegram": False, "whatsapp": False}
    if send:
        sent["telegram"] = send_notification(message, config)
        if config.get("morning_check_whatsapp"):
            sent["whatsapp"] = bool(send_whatsapp(message, config))

    total = sum(len(v) for v in summary.values())
    logger.info(f"Morning check: {total} change(s) in last {within}h, "
                f"{len(warnings)} freshness warning(s); telegram={sent['telegram']}")
    return {
        "total_changes": total,
        "by_category": {k: len(v) for k, v in summary.items()},
        "changes": summary,
        "freshness_warnings": warnings,
        "message": message,
        "sent": sent,
    }


def run_scraper_drift_job(send=True):
    """Weekly live drift probe of the pure-HTTP scrapers (Sunday 06:30).

    For every provider with a recorded fixture (tests/fixtures/http/), re-fetch
    ONLY the fixture's URL set live and compare the parsed plan count with the
    count the fixture reproduces (scraper_fixtures.drift_check). Catches a
    redesigned site DAYS before the morning digest notices aged rows - and does
    it with ~12 requests per provider instead of a full scrape.
    """
    import scraper_fixtures as _sf
    import notifier
    config = core.load_config()
    results = _sf.run_drift_check_all(min_ratio=float(config.get("scraper_drift_min_ratio", 0.5)))
    message = _sf.format_drift_report(results)
    bad = [r["provider"] for r in results if r["status"] in ("drift", "error")]
    if bad:
        logger.warning(f"Scraper drift: {len(bad)} provider(s) off - {bad}")
    else:
        logger.info(f"Scraper drift check: {len(results)} providers OK")
    sent = False
    if send and config.get("telegram_bot_token"):
        try:
            sent = notifier.send_notification(message, config)
        except Exception as e:
            logger.error(f"Scraper drift Telegram failed: {e}")
    return {"checked": len(results), "off": bad, "results": results, "message": message, "sent": sent}


@bp.route("/api/scraper-drift/now", methods=["GET", "POST"])
@core.require_api_key_or_query
def api_scraper_drift_now():
    """Manually run the weekly scraper drift probe. ?send=false = JSON only."""
    send = request.args.get("send", "true").lower() != "false"
    try:
        return jsonify(run_scraper_drift_job(send=send))
    except Exception as e:
        logger.error(f"Scraper drift check failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/morning-check/now", methods=["GET", "POST"])
@core.require_api_key_or_query
def api_morning_check_now():
    """Manually trigger the morning changes digest (same logic as the daily cron).

    ?send=false returns the digest JSON without sending Telegram/WhatsApp —
    useful for previewing what the morning message will look like.
    """
    send = request.args.get("send", "true").lower() != "false"
    try:
        return jsonify(run_morning_check_job(send=send))
    except Exception as e:
        logger.error(f"Morning check failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/executive-summary")
@core.limiter.limit("60 per minute")
def api_executive_summary():
    """Return cached executive summary for all 4 categories."""
    rows = core.get_executive_summary(db_path=core._db_path())
    if not rows:
        return jsonify({"error": "not_generated_yet"}), 404
    return jsonify(rows)


@bp.route("/api/executive-summary/refresh", methods=["POST"])
@core.require_scrape_auth
def api_executive_summary_refresh():
    """Trigger manual regeneration of all 4 executive summaries."""
    ok, used, limit = core._check_refresh_quota()
    if not ok:
        return jsonify({"error": f"מכסת הרענון החודשית הגיעה לסיום ({used}/{limit}). מחכים לחודש הבא.", "quota_used": used, "quota_limit": limit}), 429
    try:
        generate_executive_summary()
        rows = core.get_executive_summary(db_path=core._db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        core._log_refresh('executive_summary')
        return jsonify({"status": "ok", "generated_at": generated_at, "quota_used": used + 1, "quota_limit": limit})
    except Exception as e:
        logger.error(f"executive summary refresh failed: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/api/social-sentiment")
@core.limiter.limit("60 per minute")
def api_social_sentiment():
    """Return cached social-media sentiment for all carriers."""
    rows = core.get_social_sentiment(db_path=core._db_path())
    if not rows:
        return jsonify({"error": "not_generated_yet"}), 404
    return jsonify(rows)


@bp.route("/api/social-sentiment/refresh", methods=["POST"])
@core.require_scrape_auth
def api_social_sentiment_refresh():
    """Trigger manual regeneration of social sentiment for all carriers."""
    ok, used, limit = core._check_refresh_quota()
    if not ok:
        return jsonify({"error": f"מכסת הרענון החודשית הגיעה לסיום ({used}/{limit}). מחכים לחודש הבא.", "quota_used": used, "quota_limit": limit}), 429
    try:
        generate_social_sentiment()
        rows = core.get_social_sentiment(db_path=core._db_path())
        generated_at = rows[0]["generated_at"] if rows else None
        core._log_refresh('social_sentiment')
        return jsonify({"status": "ok", "generated_at": generated_at, "quota_used": used + 1, "quota_limit": limit})
    except Exception as exc:
        logger.error(f"social sentiment refresh failed: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
