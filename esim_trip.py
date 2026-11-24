"""Multi-destination trip planner for the public /esim-deals page.

A traveller going to several countries can buy one eSIM per country, one
regional / global bundle for the whole trip, or a mix. The answer needs two
things that live in different places: prices (here, in `global_plans`) and
which countries a bundle covers (the per-provider coverage lists of the React
app, data/globalCountries.js). So the work is split:

  server (this module): for every CONTIGUOUS stretch of the itinerary, the
      cheapest plans that are long enough and big enough - from the stretch's
      own country when it is a single leg, and from every bundle destination
      the client named;
  client (lib/tripPlanner.js): drops the bundles that do not cover every
      country of their stretch, then picks the cheapest way to cut the
      itinerary into stretches.

A stretch has to be contiguous because a bundle's validity runs from its first
day of use: covering legs 1 and 3 with one plan means paying for leg 2's days
as well, which is the stretch 1-3.

Used by POST /api/esim/trip (api/esim.py). Tests: tests/test_esim_trip.py.
"""
import math

import db

MAX_LEGS = 5
MAX_DAYS = 90
MAX_BUNDLE_DESTS = 90
OWN_KEEP = 12         # per single-leg stretch: plans from the leg's own country
BUNDLE_KEEP = 6       # per stretch and bundle destination
UNLIMITED_MIN_GB = 50  # "unlimited" also accepts 50GB+, like the page's trip wizard


def clean_request(payload):
    """Validate the POST body. Returns (legs, gb, bundle_dests) or raises ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("body must be an object")
    raw_legs = payload.get("legs")
    if not isinstance(raw_legs, list) or not 2 <= len(raw_legs) <= MAX_LEGS:
        raise ValueError("legs must list 2-%d destinations" % MAX_LEGS)
    legs = []
    for leg in raw_legs:
        dest = str((leg or {}).get("destination") or "").strip()
        try:
            days = int((leg or {}).get("days"))
        except (TypeError, ValueError):
            raise ValueError("every leg needs a number of days")
        if not dest or len(dest) > 60 or not 1 <= days <= MAX_DAYS:
            raise ValueError("every leg needs a destination and 1-%d days" % MAX_DAYS)
        legs.append({"destination": dest, "days": days})
    if sum(l["days"] for l in legs) > MAX_DAYS:
        raise ValueError("the trip can be at most %d days" % MAX_DAYS)
    gb = payload.get("gb")
    if gb in ("unl", None):
        gb = None
    else:
        try:
            gb = float(gb)
        except (TypeError, ValueError):
            raise ValueError("gb must be a number or 'unl'")
        if not 0 < gb <= 1000:
            raise ValueError("gb out of range")
    bundles = payload.get("bundles") or []
    if not isinstance(bundles, list):
        raise ValueError("bundles must be a list")
    own = {l["destination"] for l in legs}
    bundles = [str(b).strip() for b in bundles if isinstance(b, str) and 0 < len(b.strip()) <= 60]
    bundles = [b for b in dict.fromkeys(bundles) if b not in own][:MAX_BUNDLE_DESTS]
    return legs, gb, bundles


def segments_of(legs, gb):
    """Every contiguous stretch (from, to) with the days and data it has to cover.
    The trip's data allowance is split by days, rounded up to a whole GB."""
    total_days = sum(l["days"] for l in legs)
    out = []
    for i in range(len(legs)):
        for j in range(i, len(legs)):
            days = sum(l["days"] for l in legs[i:j + 1])
            need = None if gb is None else max(1, math.ceil(gb * days / total_days - 1e-9))
            out.append({"from": i, "to": j, "days": days, "gb": need})
    return out


def fits(row, days, gb):
    """Long enough for the stretch and with enough data. A plan with no day
    count is never used: the planner cannot tell whether it lasts the trip."""
    if not row.get("days") or row["days"] < days or row.get("ils") is None:
        return False
    if row.get("data_gb") is None:
        return True
    return row["data_gb"] >= (UNLIMITED_MIN_GB if gb is None else gb)


def cheapest_per_provider(rows, keep):
    best = {}
    for r in rows:
        cur = best.get(r["carrier"])
        if cur is None or r["ils"] < cur["ils"]:
            best[r["carrier"]] = r
    return sorted(best.values(), key=lambda r: r["ils"])[:keep]


def _ils(price, original_price, currency, fx):
    """The page's own conversion: native price x live FX (the stored ILS price
    uses a scrape-time rate), stored price for ILS-native plans."""
    rate = {"USD": fx.get("usd"), "EUR": fx.get("eur"), "GBP": fx.get("gbp")}.get(currency or "USD")
    if currency == "ILS" or not original_price or not rate:
        return price
    return original_price * rate


def _deal(r, dest):
    return {
        "provider": r["carrier"], "kind": "global", "form": "esim" if r["esim"] else "sim",
        "gb": r["data_gb"], "days": r["days"],
        "price": round(r["price"], 2) if r["price"] is not None else None,
        "original_price": r["original_price"], "currency": r["currency"] or "USD",
        "plan_name": r["plan_name"], "dest": dest, "ils": round(r["ils"], 2),
    }


def load_rows(destinations, fx, db_path=None):
    """{destination: [plan rows]} for the given extras[0] values, in one query."""
    out = {d: [] for d in destinations}
    if not destinations:
        return out, None
    conn = db._connect(db_path)
    try:
        marks = ",".join("?" * len(destinations))
        rows = conn.execute(
            "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, esim, "
            "json_extract(extras, '$[0]'), scraped_at FROM global_plans "
            f"WHERE json_extract(extras, '$[0]') IN ({marks}) AND price IS NOT NULL",
            list(destinations)).fetchall()
    finally:
        conn.close()
    newest = None
    for r in rows:
        row = {"carrier": r[0], "plan_name": r[1], "price": r[2], "currency": r[3],
               "original_price": r[4], "days": r[5], "data_gb": r[6], "esim": bool(r[7])}
        row["ils"] = _ils(row["price"], row["original_price"], row["currency"], fx)
        out[r[8]].append(row)
        if r[9] and (newest is None or r[9] > newest):
            newest = r[9]
    return out, newest


def trip_candidates(legs, gb, bundle_dests, fx, db_path=None):
    """The payload's `segments`: per contiguous stretch, `own` (plans sold for the
    leg's own country - single-leg stretches only) and `bundles` (plans of the
    named bundle destinations), each already filtered to what fits the stretch."""
    own_dests = list(dict.fromkeys(l["destination"] for l in legs))
    rows, newest = load_rows(own_dests + list(bundle_dests), fx, db_path)
    out = []
    for seg in segments_of(legs, gb):
        ok = lambda r: fits(r, seg["days"], seg["gb"])
        own = []
        if seg["from"] == seg["to"]:
            dest = legs[seg["from"]]["destination"]
            own = [_deal(r, dest) for r in cheapest_per_provider(filter(ok, rows[dest]), OWN_KEEP)]
        bundles = []
        for dest in bundle_dests:
            bundles.extend(_deal(r, dest) for r in cheapest_per_provider(filter(ok, rows[dest]), BUNDLE_KEEP))
        out.append(dict(seg, own=own, bundles=bundles))
    return out, newest
