"""Reads what the daily banner screenshots SAY.

The scrape saves a 1280x720 PNG of every carrier homepage / e-store (and of the
global eSIM providers). Until now those were pictures only. This module sends a
screenshot to Claude (vision) and stores the offer it shows - headline, offer,
price, campaign type - in `banner_insights`, one row per CAMPAIGN PERIOD: a new
row is written only when the reading changes, otherwise the open row's
`last_seen_at` moves forward. The table is therefore a campaign timeline.

Cost control (every reading is a paid API call):
  * a banner is read only when its image changed since the last reading
    (16x16 average-hash distance >= HASH_THRESHOLD) ...
  * ... and at most once per `banner_vision_min_hours` (20) per banner,
  * at most `banner_vision_max_per_run` (20) readings per run,
  * `banner_vision_scope`: "domestic" (homepages + e-stores, the default),
    "global" or "all".
config.json knobs: banner_vision_enabled (true), banner_vision_model
("claude-opus-5-5"), banner_vision_scope, banner_vision_max_per_run,
banner_vision_min_hours, banner_vision_notify (true = Telegram on a change).

The model is told to transcribe, not to interpret: a field it cannot see stays
empty, and `confidence` says how readable the screenshot was (a cookie wall or
a half-loaded page gives "low", which is stored but never reported as a change).

Calls the Messages API over plain HTTP like the project's other Claude call
sites (api/chat.py, api/jobs.py), so usage lands in `claude_api_usage` through
the caller-supplied `record` hook. Tests: tests/test_banner_vision.py.
"""
import base64
import difflib
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta

import requests

import db

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
API_URL = "https://api.anthropic.com/v1/messages"
FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2")
HASH_THRESHOLD = 18          # same bar the global-banner freshness badge uses
ROTATION_DAYS = 14           # a slide seen within this window is rotation, not a new campaign
SAME_HEADLINE = 0.72        # difflib ratio above which two headlines are one campaign
CAMPAIGN_TYPES = ("price_plan", "device", "roaming", "fiber_tv", "esim", "service", "brand", "other")

SCHEMA = {
    "type": "object",
    "properties": {
        "has_offer": {"type": "boolean"},
        "headline": {"type": "string"},
        "offer": {"type": "string"},
        "price_text": {"type": "string"},
        "campaign_type": {"type": "string", "enum": list(CAMPAIGN_TYPES)},
        "products": {"type": "array", "items": {"type": "string"}},
        "fine_print": {"type": "string"},
        "cta": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "obstruction": {"type": "string"},
    },
    "required": ["has_offer", "headline", "offer", "price_text", "campaign_type", "products",
                 "fine_print", "cta", "confidence", "obstruction"],
    "additionalProperties": False,
}

PROMPT = """This is a screenshot of the top of a telecom company's web page ({name}, {kind}).
Report the main promotional offer it shows. Transcribe what is visible - do not interpret,
complete or guess. Write every text field in the language it appears in on the page.

- headline: the main promotional headline, as written.
- offer: one sentence saying what is being offered (plan, data amount, device, bundle).
- price_text: the price exactly as shown, with its currency and period (for example the
  monthly price and any "for N months" wording). Empty when no price is visible.
- campaign_type: price_plan (a mobile plan or its price), device (a phone or gadget),
  roaming (travel packages), fiber_tv (internet, fibre, TV), esim, service (a value-added
  service), brand (image only, no concrete offer), other.
- products: brand or product names that appear in the offer (may be empty).
- fine_print: conditions visible near the offer (commitment, number of lines, price after
  the promotion). Empty when none is readable.
- cta: the text of the main call-to-action button. Empty when there is none.
- has_offer: false when the screenshot shows no promotional offer at all.
- confidence: high when the offer is clearly readable; medium when part of it is cut off or
  small; low when the page is covered or did not load.
- obstruction: what blocks the view (cookie banner, popup, error page, blank page).
  Empty when nothing does.

A field that is not visible stays an empty string. Never fill one from general knowledge."""


# ── storage ──────────────────────────────────────────────────────────────

def ensure_table(db_path=None):
    conn = db._connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS banner_insights (
                id            INTEGER PRIMARY KEY,
                banner_key    TEXT NOT NULL,       -- cellcom | cellcom_store | airalo_global
                carrier       TEXT NOT NULL,
                kind          TEXT NOT NULL,       -- home | store | global
                first_seen_at TEXT NOT NULL,
                last_seen_at  TEXT NOT NULL,
                analyzed_at   TEXT NOT NULL,
                image_hash    TEXT,
                has_offer     INTEGER NOT NULL DEFAULT 0,
                headline      TEXT, offer TEXT, price_text TEXT, price REAL,
                campaign_type TEXT, products TEXT, fine_print TEXT, cta TEXT,
                confidence    TEXT, obstruction TEXT,
                prev_headline TEXT, prev_price_text TEXT,
                model         TEXT
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_banner_insights_key "
                     "ON banner_insights (banner_key, id)")
        conn.commit()
    finally:
        conn.close()


_COLS = ("id, banner_key, carrier, kind, first_seen_at, last_seen_at, analyzed_at, image_hash, "
         "has_offer, headline, offer, price_text, price, campaign_type, products, fine_print, cta, "
         "confidence, obstruction, prev_headline, prev_price_text, model")


def _row(r):
    d = dict(zip([c.strip() for c in _COLS.split(",")], r))
    d["has_offer"] = bool(d["has_offer"])
    try:
        d["products"] = json.loads(d["products"] or "[]")
    except ValueError:
        d["products"] = []
    return d


def latest_rows(db_path=None):
    """{banner_key: newest row}."""
    ensure_table(db_path)
    conn = db._connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_COLS} FROM banner_insights WHERE id IN "
            "(SELECT MAX(id) FROM banner_insights GROUP BY banner_key)").fetchall()
    finally:
        conn.close()
    return {r[1]: _row(r) for r in rows}


def recent_changes(days=30, db_path=None):
    """Campaign switches (rows that replaced an earlier reading), newest first."""
    ensure_table(db_path)
    since = (datetime.now() - timedelta(days=days)).isoformat()
    conn = db._connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_COLS} FROM banner_insights WHERE first_seen_at >= ? "
            "AND prev_headline IS NOT NULL ORDER BY id DESC LIMIT 200", (since,)).fetchall()
    finally:
        conn.close()
    return [_row(r) for r in rows]


# ── pure helpers ─────────────────────────────────────────────────────────

def ahash(path):
    """16x16 grayscale average-hash as a 256-char bit string (None on failure)."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            px = list(im.convert("L").resize((16, 16)).tobytes())
        avg = sum(px) / len(px)
        return "".join("1" if p >= avg else "0" for p in px)
    except Exception as exc:  # unreadable / truncated PNG
        logger.warning("banner vision: hash failed for %s: %s", path, exc)
        return None


def hash_distance(a, b):
    if not a or not b or len(a) != len(b):
        return 999
    return sum(1 for x, y in zip(a, b) if x != y)


def parse_price(text):
    """First price-looking number in the price text ("₪39.90 לחודש" -> 39.9), else None."""
    m = re.search(r"(\d{1,4}(?:[.,]\d{1,2})?)", str(text or "").replace("‏", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _norm(s):
    return re.sub(r"[\W_]+", " ", str(s or "").lower()).strip()


def is_same_campaign(prev, cur):
    """Two readings describe the same campaign: same price and a similar headline.
    The model never words a headline identically twice, so an exact compare
    would report a "new campaign" on every reading."""
    if not prev:
        return False
    if bool(prev.get("has_offer")) != bool(cur.get("has_offer")):
        return False
    if parse_price(prev.get("price_text")) != parse_price(cur.get("price_text")):
        return False
    a, b = _norm(prev.get("headline")), _norm(cur.get("headline"))
    if not a and not b:
        return _norm(prev.get("offer")) == _norm(cur.get("offer")) or \
            difflib.SequenceMatcher(None, _norm(prev.get("offer")), _norm(cur.get("offer"))).ratio() >= SAME_HEADLINE
    return difflib.SequenceMatcher(None, a, b).ratio() >= SAME_HEADLINE


def should_analyze(path, last, now=None, min_hours=20):
    """(bool, reason, hash). Read a banner only when its image really changed
    and it was not read recently."""
    if not os.path.exists(path):
        return False, "no file", None
    h = ahash(path)
    if h is None:
        return False, "unreadable", None
    if not last:
        return True, "first reading", h
    now = now or datetime.now()
    try:
        age_h = (now - datetime.fromisoformat(last["analyzed_at"])).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        age_h = 1e9
    if age_h < min_hours:
        return False, "read %.0fh ago" % age_h, h
    if hash_distance(h, last.get("image_hash")) < HASH_THRESHOLD:
        return False, "image unchanged", h
    return True, "image changed", h


# ── the API call ─────────────────────────────────────────────────────────

def _image_b64(path):
    """JPEG payload (a 1280x720 PNG screenshot is ~4x larger for the same pixels)."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        if max(im.size) > 1568:
            im.thumbnail((1568, 1568))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def read_banner(path, name, kind, api_key, model=DEFAULT_MODEL, record=None, timeout=90):
    """One vision call. Returns the parsed reading dict, or None when the call
    failed or was declined. `record(model, response_json)` logs usage."""
    kind_label = {"home": "homepage", "store": "online store", "global": "eSIM provider homepage"}.get(kind, kind)
    body = {
        "model": model,
        "max_tokens": 4000,
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _image_b64(path)}},
            {"type": "text", "text": PROMPT.format(name=name, kind=kind_label)},
        ]}],
    }
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if model in FALLBACK_MODELS:
        # Should the model ever decline a screenshot, the API re-runs the request
        # on its default fallback inside the same call instead of returning nothing.
        body["fallbacks"] = "default"
        headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
    resp = requests.post(API_URL, timeout=timeout, json=body, headers=headers)
    if resp.status_code != 200:
        logger.warning("banner vision: HTTP %s for %s: %s", resp.status_code, name, resp.text[:300])
        return None
    data = resp.json()
    if record:
        try:
            record(model, data)
        except Exception as exc:  # usage logging must never fail a reading
            logger.warning("banner vision: usage log failed: %s", exc)
    if data.get("stop_reason") != "end_turn":
        logger.warning("banner vision: %s stopped with %s", name, data.get("stop_reason"))
        return None
    text = next((b.get("text") for b in data.get("content", []) if b.get("type") == "text"), None)
    try:
        out = json.loads(text)
    except (TypeError, ValueError):
        logger.warning("banner vision: unparseable answer for %s", name)
        return None
    return out if isinstance(out, dict) else None


# ── the run ──────────────────────────────────────────────────────────────

def store_reading(src, reading, image_hash, model, prev, now=None, db_path=None):
    """Extend the open campaign row or open a new one. Returns
    'same' | 'first' | 'changed' | 'rotation' | 'unreadable'."""
    now_iso = (now or datetime.now()).isoformat()
    conn = db._connect(db_path)
    try:
        # A low-confidence reading (cookie wall, half-loaded page) says nothing
        # about the campaign: remember that we looked, keep the timeline as is.
        if reading.get("confidence") == "low" and prev:
            conn.execute("UPDATE banner_insights SET analyzed_at = ?, image_hash = ? WHERE id = ?",
                         (now_iso, image_hash, prev["id"]))
            conn.commit()
            return "unreadable"
        if is_same_campaign(prev, reading):
            conn.execute("UPDATE banner_insights SET last_seen_at = ?, analyzed_at = ?, image_hash = ? WHERE id = ?",
                         (now_iso, now_iso, image_hash, prev["id"]))
            conn.commit()
            return "same"
        # Homepages rotate several slides, so the screenshot may simply have
        # caught another one. A reading that matches something this banner
        # showed in the last ROTATION_DAYS is a slide coming round again: it is
        # stored (the timeline shows what was on screen) but not as a switch.
        since = ((now or datetime.now()) - timedelta(days=ROTATION_DAYS)).isoformat()
        seen = [_row(r) for r in conn.execute(
            f"SELECT {_COLS} FROM banner_insights WHERE banner_key = ? AND last_seen_at >= ?",
            (src["key"], since)).fetchall()]
        rotation = bool(prev) and any(is_same_campaign(r, reading) for r in seen)
        conn.execute(
            "INSERT INTO banner_insights (banner_key, carrier, kind, first_seen_at, last_seen_at, analyzed_at, "
            "image_hash, has_offer, headline, offer, price_text, price, campaign_type, products, fine_print, cta, "
            "confidence, obstruction, prev_headline, prev_price_text, model) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (src["key"], src["carrier"], src["kind"], now_iso, now_iso, now_iso, image_hash,
             1 if reading.get("has_offer") else 0, reading.get("headline") or "", reading.get("offer") or "",
             reading.get("price_text") or "", parse_price(reading.get("price_text")),
             reading.get("campaign_type") or "other",
             json.dumps(reading.get("products") or [], ensure_ascii=False),
             reading.get("fine_print") or "", reading.get("cta") or "", reading.get("confidence") or "",
             reading.get("obstruction") or "",
             (prev.get("headline") or prev.get("offer") or "") if prev and not rotation else None,
             (prev.get("price_text") or "") if prev and not rotation else None, model))
        conn.commit()
        return "first" if not prev else "rotation" if rotation else "changed"
    finally:
        conn.close()


def run(config, banners_dir, sources, db_path=None, record=None, dry_run=False, limit=None, force=False):
    """Read the banners that changed. `sources`: [{key, carrier, kind, name, file}].
    Returns {analyzed, skipped, changed: [...], errors, plan: [...]}."""
    out = {"analyzed": 0, "skipped": 0, "errors": 0, "changed": [], "plan": []}
    if not config.get("banner_vision_enabled", True) and not force:
        out["disabled"] = True
        return out
    api_key = config.get("anthropic_api_key", "")
    if not api_key and not dry_run:
        logger.warning("banner vision: anthropic_api_key missing, skipping")
        out["disabled"] = True
        return out
    model = config.get("banner_vision_model") or DEFAULT_MODEL
    cap = int(limit or config.get("banner_vision_max_per_run") or 20)
    min_hours = 0 if force else float(config.get("banner_vision_min_hours") or 20)
    ensure_table(db_path)
    last = latest_rows(db_path)
    for src in sources:
        path = os.path.join(banners_dir, src["file"])
        go, reason, h = should_analyze(path, None if force else last.get(src["key"]), min_hours=min_hours)
        out["plan"].append({"key": src["key"], "analyze": go, "reason": reason})
        if not go or out["analyzed"] >= cap:
            out["skipped"] += 1
            continue
        if dry_run:
            out["analyzed"] += 1
            continue
        try:
            reading = read_banner(path, src["name"], src["kind"], api_key, model=model, record=record)
        except Exception as exc:
            logger.warning("banner vision: %s failed: %s", src["key"], exc)
            reading = None
        if reading is None:
            out["errors"] += 1
            continue
        out["analyzed"] += 1
        prev = last.get(src["key"])
        status = store_reading(src, reading, h, model, prev, db_path=db_path)
        if status == "changed":
            out["changed"].append({"key": src["key"], "name": src["name"], "kind": src["kind"],
                                   "headline": reading.get("headline") or reading.get("offer") or "",
                                   "price_text": reading.get("price_text") or "",
                                   "prev_headline": (prev.get("headline") or prev.get("offer") or ""),
                                   "prev_price_text": prev.get("price_text") or ""})
    logger.info("banner vision: %d read, %d skipped, %d errors, %d campaign changes",
                out["analyzed"], out["skipped"], out["errors"], len(out["changed"]))
    return out


def changes_message(changed):
    """Telegram text for a run's campaign switches (Hebrew)."""
    lines = ["\U0001f5bc️ שינויי קמפיין בבאנרים"]
    for c in changed:
        where = c["name"] + (" (חנות)" if c["kind"] == "store" else "")
        now_txt = c["headline"] + (" - " + c["price_text"] if c["price_text"] else "")
        before = c["prev_headline"] + (" - " + c["prev_price_text"] if c["prev_price_text"] else "")
        lines.append("")
        lines.append("• " + where + ": " + (now_txt or "-"))
        if before:
            lines.append("  קודם: " + before)
    return "\n".join(lines)
