"""Feasibility backtest for a global-eSIM price forecasting model (READ-ONLY).

Question it answers: can anything beat "the price won't change" at predicting
eSIM price DROPS 14 days ahead? If not, a forecast feature would mislead users.

Source: archive_snapshots (one full catalog per provider per day since
2026-04-15). Two tasks, both with a strict time split (train on cutoffs whose
label window closes before SPLIT_DAY, test on later ones):

  A. plan level   - will this (carrier, plan_name) drop >=2% in the next H days?
                    Price basis = original_price (provider currency) so FX moves
                    are not counted as price moves.
  B. destination  - will the destination's trip-sized floor (cheapest plan
                    >=5GB-or-unlimited, >=7 days, in ILS - what the B2C alerts
                    track) drop >=5% AND >=2 ILS in the next H days?

Models: constant base rate, per-carrier (per-destination) base rate, a hazard
lookup table, and an L2 logistic regression (numpy only - no sklearn here).

    python scripts/forecast_backtest.py              # uses the cache if present
    python scripts/forecast_backtest.py --rebuild    # re-extract from the DB (~5 min)
    python scripts/forecast_backtest.py --json out.json
"""
import argparse
import datetime as dt
import gzip
import json
import math
import os
import pickle
import sqlite3
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402

DB_PATH = os.path.join(ROOT, "data", "plans.db")
CACHE = os.path.join(ROOT, "data", "_forecast_backtest_cache.pkl.gz")

H = 14                  # forecast horizon, days
STEP = 7                # days between cutoffs
WARMUP = 45             # days of history before the first cutoff
SPLIT_DAY = "2026-08-25"
MIN_PLAN_PCT = 0.02     # plan move smaller than this = noise
FLOOR_PCT, FLOOR_ILS = 0.05, 2.0   # same threshold as notify_esim_price_drops


def d2i(s):
    return dt.date.fromisoformat(s).toordinal()


def i2d(i):
    return dt.date.fromordinal(i).isoformat()


# ---------------------------------------------------------------- extraction
def extract():
    """One pass over the archive -> per-plan change events + per-destination
    daily trip floor. Keeps only what the features need, so the cache is small."""
    conn = sqlite3.connect(DB_PATH)
    plans = {}                         # (carrier, name) -> meta + events
    floor = defaultdict(dict)          # dest -> {day_i: min ILS trip price}
    floor_n = defaultdict(dict)        # dest -> {day_i: #carriers with a trip plan}
    seen_days = defaultdict(set)       # carrier -> snapshot days
    cur = conn.execute(
        "SELECT carrier, snapshot_date, plans_json FROM archive_snapshots "
        "WHERE plan_type='global' ORDER BY carrier, snapshot_date")
    n = 0
    for carrier, day, blob in cur:
        n += 1
        if n % 500 == 0:
            print(f"  {n} snapshots...", flush=True)
        di = d2i(day)
        seen_days[carrier].add(di)
        try:
            rows = json.loads(db._archive_decode(blob))
        except Exception:
            continue
        dest_min = {}
        # A snapshot can repeat a plan_name (pre-fix ByteSim tiers, Voye before
        # 2026-10-23). The DB keeps the last row per UNIQUE(carrier, plan_name),
        # so do the same - diffing the repeats against each other would invent
        # price "events" that never reached the DB.
        rows = list({p.get("plan_name"): p for p in rows}.values())
        for p in rows:
            name = p.get("plan_name")
            price = p.get("price")
            if not name or not price:
                continue
            extras = p.get("extras") or []
            dest = extras[0] if extras else ""
            gb, days = p.get("data_gb"), p.get("days")
            if dest and (gb is None or gb >= 5) and (days is None or days >= 7):
                if dest not in dest_min or price < dest_min[dest]:
                    dest_min[dest] = price
            basis = p.get("original_price") or price
            curr = p.get("currency") or "ILS"
            key = (carrier, name)
            rec = plans.get(key)
            if rec is None:
                plans[key] = {"dest": dest, "gb": gb, "days": days, "curr": curr,
                              "first": di, "last": di, "basis": basis,
                              "price": price, "events": []}
                continue
            if curr == rec["curr"] and rec["basis"] and basis != rec["basis"]:
                pct = basis / rec["basis"] - 1
                if abs(pct) >= MIN_PLAN_PCT:
                    rec["events"].append((di, pct))
            rec.update(last=di, basis=basis, price=price, curr=curr)
        for dest, v in dest_min.items():
            f = floor[dest]
            f[di] = min(v, f.get(di, v))
            floor_n[dest][di] = floor_n[dest].get(di, 0) + 1
    conn.close()
    return {"plans": plans, "floor": dict(floor), "floor_n": dict(floor_n),
            "seen_days": {k: sorted(v) for k, v in seen_days.items()}}


def load(rebuild):
    if not rebuild and os.path.exists(CACHE):
        with gzip.open(CACHE, "rb") as f:
            return pickle.load(f)
    print("Extracting from archive_snapshots (one-off, a few minutes)...")
    data = extract()
    with gzip.open(CACHE, "wb") as f:
        pickle.dump(data, f)
    return data


# ---------------------------------------------------------------- metrics
def auc(y, s):
    y = np.asarray(y, bool)
    pos, neg = y.sum(), (~y).sum()
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    ss = np.asarray(s)[order]
    i = 0
    while i < len(ss):          # average ranks for ties
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y].sum() - pos * (pos + 1) / 2) / (pos * neg))


def avg_precision(y, s):
    y = np.asarray(y, bool)
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-np.asarray(s), kind="mergesort")
    hits = y[order]
    prec = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float(prec[hits].mean())


def precision_at(y, s, frac):
    y = np.asarray(y, bool)
    k = max(1, int(len(y) * frac))
    top = np.argsort(-np.asarray(s), kind="mergesort")[:k]
    return float(y[top].mean())


def brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y, float)) ** 2))


def evaluate(name, y, p, base_p):
    y = np.asarray(y, bool)
    prev = float(y.mean())
    b_ref = brier(y, base_p)
    return {
        "model": name,
        "auc": round(auc(y, p), 3),
        "avg_precision": round(avg_precision(y, p), 3),
        "prevalence": round(prev, 3),
        "precision_top5": round(precision_at(y, p, 0.05), 3),
        "lift_top5": round(precision_at(y, p, 0.05) / prev, 2) if prev else None,
        "precision_top10": round(precision_at(y, p, 0.10), 3),
        "brier_skill_vs_base": round(1 - brier(y, p) / b_ref, 3) if b_ref else None,
    }


# ---------------------------------------------------------------- logistic
def fit_logistic(X, y, l2=1.0, iters=60):
    """Newton-IRLS with L2 on everything but the intercept."""
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    reg = np.full(Z.shape[1], l2)
    reg[0] = 0
    y = np.asarray(y, float)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - y) + reg * w
        Hm = (Z * (p * (1 - p))[:, None]).T @ Z + np.diag(reg + 1e-9)
        step = np.linalg.solve(Hm, g)
        w -= step
        if np.abs(step).max() < 1e-6:
            break

    def predict(Xn):
        Zn = np.hstack([np.ones((len(Xn), 1)), (Xn - mu) / sd])
        return 1 / (1 + np.exp(-np.clip(Zn @ w, -30, 30)))
    return predict, w


def smoothed_rate(pos, n, prior, k=20):
    return (pos + k * prior) / (n + k)


# ---------------------------------------------------------------- task A
def task_plans(data):
    plans = data["plans"]
    seen = {c: set(v) for c, v in data["seen_days"].items()}
    all_days = sorted({d for v in seen.values() for d in v})
    d0, d1 = all_days[0], all_days[-1]
    split = d2i(SPLIT_DAY)
    cutoffs = list(range(d0 + WARMUP, d1 - H + 1, STEP))

    # carrier-level drop activity per day (repricing waves) + dest-level drops
    carr_drops = defaultdict(lambda: defaultdict(int))
    dest_drops = defaultdict(lambda: defaultdict(int))
    carr_size = defaultdict(int)
    for (c, _), r in plans.items():
        carr_size[c] += 1
        for di, pct in r["events"]:
            if pct < 0:
                carr_drops[c][di] += 1
                dest_drops[r["dest"]][di] += 1

    # cumulative daily counts -> O(1) window sums
    span = d1 - d0 + 2

    def cumulate(dd):
        arr = np.zeros(span)
        for d, v in dd.items():
            arr[d - d0 + 1] += v
        return np.cumsum(arr)
    carr_cum = {c: cumulate(v) for c, v in carr_drops.items()}
    dest_cum = {k: cumulate(v) for k, v in dest_drops.items()}
    zero = np.zeros(span)

    def window_sum(cum, a, b):     # events with a < day <= b
        return float(cum[b - d0 + 1] - cum[a - d0 + 1])

    rows = []
    for t in cutoffs:
        for (c, name), r in plans.items():
            # alive before the cutoff and still listed after the label window
            if not (r["first"] <= t - 7 and r["last"] >= t + H):
                continue
            if not any(d in seen[c] for d in (t, t - 1, t - 2, t - 3)):
                continue
            ev = r["events"]
            past = [(d, p) for d, p in ev if d <= t]
            fut = [(d, p) for d, p in ev if t < d <= t + H]
            y_drop = any(p < 0 for _, p in fut)
            y_any = bool(fut)
            last_d = past[-1][0] if past else r["first"]
            rows.append({
                "t": t, "carrier": c, "dest": r["dest"],
                "y_drop": y_drop, "y_any": y_any,
                "dsl": t - last_d,
                "n30": sum(1 for d, _ in past if d > t - 30),
                "n90": sum(1 for d, _ in past if d > t - 90),
                "drops90": sum(1 for d, p in past if d > t - 90 and p < 0),
                "last_dir": (1 if past[-1][1] > 0 else -1) if past else 0,
                "age": t - r["first"],
                "carr_wave7": window_sum(carr_cum.get(c, zero), t - 7, t) / max(carr_size[c], 1),
                "carr_wave30": window_sum(carr_cum.get(c, zero), t - 30, t) / max(carr_size[c], 1),
                "dest_drops14": window_sum(dest_cum.get(r["dest"], zero), t - 14, t),
                "foreign": 0 if r["curr"] == "ILS" else 1,
                "days": r["days"] or 0,
                "unl": 1 if r["gb"] is None else 0,
                "train": t + H <= split,
            })
    print(f"  task A: {len(rows):,} plan-cutoff rows, {len(cutoffs)} cutoffs, "
          f"{sum(r['train'] for r in rows):,} train / {sum(not r['train'] for r in rows):,} test")
    return rows


def run_task_plans(rows, target):
    tr = [r for r in rows if r["train"]]
    te = [r for r in rows if not r["train"]]
    y_tr = np.array([r[target] for r in tr])
    y_te = np.array([r[target] for r in te])
    prior = float(y_tr.mean())

    # per-carrier base rate (train)
    cstat = defaultdict(lambda: [0, 0])
    for r in tr:
        cstat[r["carrier"]][0] += r[target]
        cstat[r["carrier"]][1] += 1
    crate = {c: smoothed_rate(p, n, prior) for c, (p, n) in cstat.items()}
    p_carr = np.array([crate.get(r["carrier"], prior) for r in te])

    # hazard lookup: carrier x days-since-last-change bucket x wave flag
    def bucket(r):
        dsl = r["dsl"]
        b = 0 if dsl <= 7 else 1 if dsl <= 30 else 2 if dsl <= 90 else 3
        return (r["carrier"], b, r["carr_wave7"] > 0.05)
    hstat = defaultdict(lambda: [0, 0])
    for r in tr:
        hstat[bucket(r)][0] += r[target]
        hstat[bucket(r)][1] += 1
    p_haz = np.array([
        smoothed_rate(*hstat[bucket(r)], crate.get(r["carrier"], prior))
        if bucket(r) in hstat else crate.get(r["carrier"], prior) for r in te])

    # logistic regression on engineered features + carrier target encoding
    feats = ["dsl", "n30", "n90", "drops90", "last_dir", "age", "carr_wave7",
             "carr_wave30", "dest_drops14", "foreign", "days", "unl"]

    def X(rs):
        out = []
        for r in rs:
            v = [math.log1p(r["dsl"]), r["n30"], r["n90"], r["drops90"], r["last_dir"],
                 math.log1p(r["age"]), r["carr_wave7"], r["carr_wave30"],
                 math.log1p(r["dest_drops14"]), r["foreign"], math.log1p(r["days"]), r["unl"]]
            cr = crate.get(r["carrier"], prior)
            v.append(math.log(cr / (1 - cr)))
            out.append(v)
        return np.array(out, float)
    predict, w = fit_logistic(X(tr), y_tr)
    p_log = predict(X(te))

    base = np.full(len(te), prior)
    res = [evaluate("constant base rate", y_te, base, base),
           evaluate("per-carrier rate", y_te, p_carr, base),
           evaluate("hazard table", y_te, p_haz, base),
           evaluate("logistic", y_te, p_log, base)]
    coefs = dict(zip(["intercept"] + feats + ["carrier_logit"], [round(float(x), 3) for x in w]))

    # how concentrated are the positives? (repricing waves)
    pos_by_carrier = defaultdict(int)
    for r in te:
        if r[target]:
            pos_by_carrier[r["carrier"]] += 1
    tot = sum(pos_by_carrier.values()) or 1
    top = sorted(pos_by_carrier.items(), key=lambda kv: -kv[1])[:5]
    conc = [(c, round(n / tot, 3)) for c, n in top]
    return res, coefs, conc, len(tr), len(te)


# ---------------------------------------------------------------- task B
def task_floor(data):
    floor, floor_n = data["floor"], data["floor_n"]
    all_days = sorted({d for f in floor.values() for d in f})
    d0, d1 = all_days[0], all_days[-1]
    split = d2i(SPLIT_DAY)
    cutoffs = list(range(d0 + WARMUP, d1 - H + 1, STEP))
    rows = []
    for dest, f in floor.items():
        days = sorted(f)
        if len(days) < 60:
            continue
        for t in cutoffs:
            past = [f[d] for d in days if t - 30 < d <= t]
            fut = [f[d] for d in days if t < d <= t + H]
            if len(past) < 10 or len(fut) < H // 2 or t not in f:
                continue
            now = f[t]
            low = min(fut)
            y = (now - low) >= max(FLOOR_PCT * now, FLOOR_ILS)
            hist = [f[d] for d in days if d <= t]
            chg = [hist[i] - hist[i - 1] for i in range(1, len(hist))]
            last_change = max((d for d, a, b in zip(days[1:], hist[:-1], hist[1:]) if a != b and d <= t),
                              default=days[0])
            rows.append({
                "t": t, "dest": dest, "y": y, "now": now,
                "rel30": now / (min(past) or now),
                "vol30": float(np.std(past) / (np.mean(past) or 1)),
                "drops30": sum(1 for c_ in chg[-30:] if c_ < 0),
                "dsl": t - last_change,
                "ncar": floor_n[dest].get(t, 0),
                "logp": math.log(now),
                "train": t + H <= split,
                "saving": (now - low) if y else 0.0,
            })
    print(f"  task B: {len(rows):,} destination-cutoff rows, {len({r['dest'] for r in rows})} destinations")
    return rows


def run_task_floor(rows):
    tr = [r for r in rows if r["train"]]
    te = [r for r in rows if not r["train"]]
    y_tr = np.array([r["y"] for r in tr])
    y_te = np.array([r["y"] for r in te])
    prior = float(y_tr.mean())
    dstat = defaultdict(lambda: [0, 0])
    for r in tr:
        dstat[r["dest"]][0] += r["y"]
        dstat[r["dest"]][1] += 1
    drate = {d: smoothed_rate(p, n, prior, k=5) for d, (p, n) in dstat.items()}
    p_dest = np.array([drate.get(r["dest"], prior) for r in te])

    def X(rs):
        out = []
        for r in rs:
            dr = drate.get(r["dest"], prior)
            out.append([r["rel30"], r["vol30"], r["drops30"], math.log1p(r["dsl"]),
                        r["ncar"], r["logp"], math.log(dr / (1 - dr))])
        return np.array(out, float)
    predict, w = fit_logistic(X(tr), y_tr, l2=3.0)
    p_log = predict(X(te))
    base = np.full(len(te), prior)
    res = [evaluate("constant base rate", y_te, base, base),
           evaluate("per-destination rate", y_te, p_dest, base),
           evaluate("logistic", y_te, p_log, base)]
    pos = [r["saving"] for r in te if r["y"]]
    savings = {"median_ils": round(float(np.median(pos)), 1) if pos else None,
               "mean_ils": round(float(np.mean(pos)), 1) if pos else None,
               "mean_pct": round(float(np.mean([r["saving"] / r["now"] for r in te if r["y"]])) * 100, 1) if pos else None}
    coefs = dict(zip(["intercept", "rel30", "vol30", "drops30", "log_dsl", "ncar", "logp", "dest_logit"],
                     [round(float(x), 3) for x in w]))
    return res, coefs, savings, len(tr), len(te)


# ---------------------------------------------------------------- main
def print_table(title, res):
    print(f"\n{title}")
    cols = ["model", "auc", "avg_precision", "prevalence", "precision_top5", "lift_top5",
            "precision_top10", "brier_skill_vs_base"]
    print("  " + " | ".join(f"{c:>19}" if i else f"{c:<20}" for i, c in enumerate(cols)))
    for r in res:
        print("  " + " | ".join(f"{str(r[c]):>19}" if i else f"{r[c]:<20}" for i, c in enumerate(cols)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    data = load(args.rebuild)
    n_ev = sum(len(r["events"]) for r in data["plans"].values())
    print(f"plans tracked: {len(data['plans']):,}, real price events (>= {MIN_PLAN_PCT:.0%}, FX-free): {n_ev:,}")
    print(f"horizon {H}d, split {SPLIT_DAY} (test = cutoffs after it)")

    out = {}
    rows_a = task_plans(data)
    for target in ("y_drop", "y_any"):
        res, coefs, conc, ntr, nte = run_task_plans(rows_a, target)
        label = "drop >= 2%" if target == "y_drop" else "any move >= 2%"
        print_table(f"TASK A - plan {label} within {H}d (train {ntr:,} / test {nte:,})", res)
        print(f"  logistic coefs (standardized): {coefs}")
        print(f"  test positives by carrier (top 5 share): {conc}")
        out[f"plans_{target}"] = {"results": res, "coefs": coefs, "concentration": conc}

    rows_b = task_floor(data)
    res, coefs, savings, ntr, nte = run_task_floor(rows_b)
    print_table(f"TASK B - destination trip floor drops >= {FLOOR_PCT:.0%} & >= {FLOOR_ILS} ILS "
                f"within {H}d (train {ntr:,} / test {nte:,})", res)
    print(f"  logistic coefs (standardized): {coefs}")
    print(f"  size of the drops that happened (test): {savings}")
    out["floor"] = {"results": res, "coefs": coefs, "savings": savings}
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
