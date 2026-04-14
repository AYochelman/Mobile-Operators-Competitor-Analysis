import sqlite3
import json
import os
from datetime import datetime

# Canonical Hebrew country/destination names — applied before every global plan save
_DEST_NORM = {
    '\u05e0\u05d5\u05e8\u05d5\u05d5\u05d2\u05d9\u05d4': '\u05e0\u05d5\u05e8\u05d1\u05d2\u05d9\u05d4',                   # נורווגיה → נורבגיה
    '\u05e9\u05d5\u05d5\u05d3\u05d9\u05d4': '\u05e9\u05d1\u05d3\u05d9\u05d4',                                             # שוודיה → שבדיה
    '\u05e4\u05e8\u05d2\u05d5\u05d5\u05d0\u05d9': '\u05e4\u05e8\u05d0\u05d2\u05d5\u05d5\u05d0\u05d9',                   # פרגוואי → פראגוואי
    '\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d0\u05d5\u05df': '\u05e1\u05d9\u05d9\u05e8\u05d4 \u05dc\u05d9\u05d0\u05d5\u05e0\u05d4',  # סיירה לאון → סיירה ליאונה
    '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',    # איי טורק וקייקוס
    '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',  # איי טורקס וקייקוס
    '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',  # איי טוקס וקייקוס
    '\u05d0\u05d9\u05d9 \u05d8\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d9\u05d9\u05e7\u05d5\u05e1': '\u05d0\u05d9\u05d9 \u05d8\u05d5\u05e8\u05e7\u05e1 \u05d5\u05e7\u05d0\u05d9\u05e7\u05d5\u05e1',  # איי טרקס וקייקוס
    # ── 10 canonical renames ────────────────────────────────────────────────
    '\u05d0\u05e8\u05d4"\u05d1': '\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea',                            # ארה"ב → ארצות הברית
    '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05d9\u05dd': '\u05d0\u05e0\u05d8\u05d9\u05dc\u05d9\u05dd \u05d4\u05d4\u05d5\u05dc\u05e0\u05d3\u05d9\u05dd',  # אנטילים ההולנדיים → אנטילים ההולנדים
    '\u05d1\u05d5\u05e6\u05d5\u05d0\u05e0\u05d4': '\u05d1\u05d5\u05d8\u05e1\u05d5\u05d0\u05e0\u05d4',                       # בוצוואנה → בוטסואנה
    '\u05d2\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4': '\u05d2\u05d5\u05d5\u05d0\u05d3\u05dc\u05d5\u05e4',                       # גואדלופ → גוואדלופ
    '\u05d2\u05d9\u05e0\u05d0\u05d4-\u05d1\u05d9\u05e1\u05d0\u05d5': '\u05d2\u05d9\u05e0\u05d0\u05d4 \u05d1\u05d9\u05e1\u05d0\u05d5',  # גינאה-ביסאו → גינאה ביסאו
    '\u05db\u05d5\u05d5\u05d9\u05ea': '\u05db\u05d5\u05d5\u05d9\u05d9\u05ea',                                                # כווית → כוויית
    '\u05dc\u05d8\u05d5\u05d5\u05d9\u05d4': '\u05dc\u05d8\u05d1\u05d9\u05d4',                                                # לטוויה → לטביה
    '\u05e0\u05d9\u05d6\'\u05e8': '\u05e0\u05d9\u05d2\'\u05e8',                                                              # ניז'ר → ניג'ר
    '\u05e0\u05d9\u05e7\u05e8\u05d2\u05d5\u05d0\u05d4': '\u05e0\u05d9\u05e7\u05e8\u05d0\u05d2\u05d5\u05d0\u05d4',          # ניקרגואה → ניקראגואה
    '\u05e1\u05d9\u05d9\u05e9\u05dc': '\u05d0\u05d9\u05d9 \u05e1\u05d9\u05d9\u05e9\u05dc',                                   # סיישל → איי סיישל
    '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05e0\u05d3\u05d9\u05e0\u05d9\u05dd': '\u05e1\u05e0\u05d8 \u05d5\u05d9\u05e0\u05e1\u05e0\u05d8 \u05d5\u05d4\u05d2\u05e8\u05d3\u05d9\u05e0\u05d9\u05dd',  # סנט וינסנט והגרנדינים → סנט וינסנט והגרדינים
    '\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d1\u05d9\u05e1': '\u05e1\u05e0\u05d8 \u05e7\u05d9\u05d8\u05e1 \u05d5\u05e0\u05d5\u05d5\u05d9\u05e1',  # סנט קיטס ונביס → סנט קיטס ונוויס
}

def _norm_extras(extras):
    """Normalize extras[0] (destination) to canonical name before DB save."""
    if not extras:
        return extras
    dest = extras[0]
    if dest and dest in _DEST_NORM:
        return [_DEST_NORM[dest]] + list(extras[1:])
    return extras

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "plans.db")


def _connect(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return sqlite3.connect(path)


def init_db(db_path=None):
    conn = _connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id         INTEGER PRIMARY KEY,
                carrier    TEXT NOT NULL,
                plan_name  TEXT NOT NULL,
                price      REAL,
                data_gb    INTEGER,
                minutes    TEXT,
                extras     TEXT,
                scraped_at TEXT,
                url        TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE TABLE IF NOT EXISTS changes (
                id          INTEGER PRIMARY KEY,
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id         INTEGER PRIMARY KEY,
                endpoint   TEXT NOT NULL UNIQUE,
                p256dh     TEXT NOT NULL,
                auth       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS abroad_changes (
                id          INTEGER PRIMARY KEY,
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS global_plans (
                id             INTEGER PRIMARY KEY,
                carrier        TEXT NOT NULL,
                plan_name      TEXT NOT NULL,
                price          REAL,
                currency       TEXT,
                original_price REAL,
                days           INTEGER,
                data_gb        REAL,
                minutes        INTEGER,
                sms            INTEGER,
                esim           INTEGER DEFAULT 1,
                extras         TEXT,
                scraped_at     TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE TABLE IF NOT EXISTS global_changes (
                id          INTEGER PRIMARY KEY,
                carrier     TEXT NOT NULL,
                plan_name   TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS abroad_plans (
                id         INTEGER PRIMARY KEY,
                carrier    TEXT NOT NULL,
                plan_name  TEXT NOT NULL,
                price      REAL,
                days       INTEGER,
                data_gb    REAL,
                minutes    INTEGER,
                sms        INTEGER,
                extras     TEXT,
                scraped_at TEXT,
                UNIQUE(carrier, plan_name)
            );
            CREATE TABLE IF NOT EXISTS content_plans (
                id         INTEGER PRIMARY KEY,
                service    TEXT NOT NULL,
                carrier    TEXT NOT NULL,
                price      TEXT,
                free_trial TEXT,
                note       TEXT,
                status     TEXT,
                scraped_at TEXT,
                UNIQUE(service, carrier)
            );
            CREATE TABLE IF NOT EXISTS content_changes (
                id          INTEGER PRIMARY KEY,
                service     TEXT NOT NULL,
                carrier     TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_val     TEXT,
                new_val     TEXT,
                changed_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS price_alerts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email     TEXT NOT NULL,
                tab            TEXT NOT NULL DEFAULT 'domestic',
                carrier        TEXT,
                plan_pattern   TEXT,
                threshold      REAL NOT NULL,
                active         INTEGER NOT NULL DEFAULT 1,
                last_triggered TEXT,
                created_at     TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS executive_summary (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category     TEXT NOT NULL UNIQUE,
                metrics_json TEXT NOT NULL,
                narrative    TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );
        """)
        conn.commit()
        # Migration: add url column if DB was created before this column existed
        try:
            conn.execute("ALTER TABLE plans ADD COLUMN url TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists
    finally:
        conn.close()


def save_executive_summary(category, metrics, narrative, db_path=None):
    """Upsert one category's executive summary row."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO executive_summary (category, metrics_json, narrative, generated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(category) DO UPDATE SET
                   metrics_json = excluded.metrics_json,
                   narrative    = excluded.narrative,
                   generated_at = excluded.generated_at""",
            (category, json.dumps(metrics, ensure_ascii=False),
             narrative, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_executive_summary(db_path=None):
    """Return list of all category summaries, or [] if table is empty."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT category, metrics_json, narrative, generated_at "
            "FROM executive_summary ORDER BY category"
        ).fetchall()
        return [
            {
                "category":     r[0],
                "metrics":      json.loads(r[1]),
                "narrative":    r[2],
                "generated_at": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()


def compute_executive_metrics(category, usd_rate=3.7, eur_rate=4.0, db_path=None):
    """Compute algorithmic market metrics for one category.

    Returns dict: { cheapest, most_aggressive, weekly_changes, chart_data, top_plans }
    """
    _VALID_CATEGORIES = {'domestic', 'abroad', 'global', 'content'}
    if category not in _VALID_CATEGORIES:
        raise ValueError(f"Unknown category: {category!r}")

    conn = _connect(db_path)
    try:
        if category == 'domestic':
            rows = conn.execute("""
                SELECT carrier, AVG(price * 1.0 / data_gb) AS v
                FROM plans
                WHERE data_gb > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/GB'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, data_gb FROM plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]} | " + (f"{r[3]}GB" if r[3] else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                for r in top_rows
            ]
            changes_table = 'changes'
            changes_carrier_col = 'carrier'

        elif category == 'abroad':
            rows = conn.execute("""
                SELECT carrier, AVG(price * 1.0 / NULLIF(days, 0)) AS v
                FROM abroad_plans
                WHERE days > 0 AND price IS NOT NULL
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa/\u05d9\u05d5\u05dd'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, days, data_gb FROM abroad_plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]} | {r[3]} \u05d9\u05de\u05d9\u05dd | " + (f"{r[4]}GB" if r[4] else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                for r in top_rows
            ]
            changes_table = 'abroad_changes'
            changes_carrier_col = 'carrier'

        elif category == 'global':
            all_global = conn.execute(
                "SELECT carrier, plan_name, price, currency, data_gb FROM global_plans "
                "WHERE price IS NOT NULL ORDER BY carrier"
            ).fetchall()
            by_carrier = {}
            for r in all_global:
                carrier, name, price, currency, data_gb = r
                if currency == 'USD':
                    ils = price * usd_rate
                elif currency == 'EUR':
                    ils = price * eur_rate
                else:
                    ils = price if price else 0
                if data_gb and data_gb > 0:
                    ppgb = ils / data_gb
                    by_carrier.setdefault(carrier, []).append(ppgb)
            rows_raw = [(c, sum(v) / len(v)) for c, v in by_carrier.items()]
            rows_raw.sort(key=lambda x: x[1])
            rows = rows_raw
            unit = '\u20aa/GB (\u05d1\u05e9\u05e7\u05dc\u05d9\u05dd)'
            top_rows = conn.execute("""
                SELECT carrier, plan_name, price, currency, data_gb FROM global_plans
                WHERE price IS NOT NULL ORDER BY price ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | {r[2]}{r[3]} | " + (f"{r[4]}GB" if r[4] else "\u05dc\u05dc\u05d0 \u05d4\u05d2\u05d1\u05dc\u05d4")
                for r in top_rows
            ]
            changes_table = 'global_changes'
            changes_carrier_col = 'carrier'

        elif category == 'content':
            rows = conn.execute("""
                SELECT carrier, AVG(CAST(price AS REAL)) AS v
                FROM content_plans
                WHERE price GLOB '[0-9]*'
                GROUP BY carrier ORDER BY v ASC
            """).fetchall()
            unit = '\u20aa (\u05de\u05d7\u05d9\u05e8 \u05e2\u05e8\u05d5\u05e5 \u05de\u05d5\u05e6\u05dc\u05d1)'
            top_rows = conn.execute("""
                SELECT carrier, service, price, free_trial FROM content_plans
                WHERE price GLOB '[0-9]*' ORDER BY CAST(price AS REAL) ASC LIMIT 10
            """).fetchall()
            top_plans = [
                f"{r[0]} | {r[1]} | \u20aa{r[2]}"
                + (f" | \u05e0\u05d9\u05e1\u05d9\u05d5\u05df: {r[3]}" if r[3] else "")
                for r in top_rows
            ]
            changes_table = 'content_changes'
            changes_carrier_col = 'carrier'

        chart_data = [
            {'carrier': r[0], 'value': round(float(r[1]), 2)}
            for r in rows if r[1] is not None
        ]
        cheapest = chart_data[0] if chart_data else {'carrier': '-', 'value': 0}

        if category == 'content':
            drop_rows = conn.execute(f"""
                SELECT {changes_carrier_col}, COUNT(*) AS cnt
                FROM {changes_table}
                WHERE change_type = 'price_change'
                  AND changed_at >= datetime('now', '-7 days')
                GROUP BY {changes_carrier_col} ORDER BY cnt DESC
            """).fetchall()
        else:
            drop_rows = conn.execute(f"""
                SELECT {changes_carrier_col}, COUNT(*) AS cnt
                FROM {changes_table}
                WHERE change_type = 'price_change'
                  AND changed_at >= datetime('now', '-7 days')
                  AND CAST(new_val AS REAL) < CAST(old_val AS REAL)
                GROUP BY {changes_carrier_col} ORDER BY cnt DESC
            """).fetchall()

        rise_rows = conn.execute(f"""
            SELECT {changes_carrier_col}, COUNT(*) AS cnt
            FROM {changes_table}
            WHERE change_type = 'price_change'
              AND changed_at >= datetime('now', '-7 days')
              AND CAST(new_val AS REAL) > CAST(old_val AS REAL)
            GROUP BY {changes_carrier_col} ORDER BY cnt DESC
        """).fetchall()

        total_drops = sum(r[1] for r in drop_rows)
        total_rises = sum(r[1] for r in rise_rows)
        most_aggressive_carrier = drop_rows[0][0] if drop_rows else (
            chart_data[-1]['carrier'] if chart_data else '-'
        )
        most_aggressive_count = drop_rows[0][1] if drop_rows else 0

        return {
            'cheapest':        {'carrier': cheapest['carrier'], 'value': cheapest['value'], 'unit': unit},
            'most_aggressive': {'carrier': most_aggressive_carrier, 'changes': most_aggressive_count},
            'weekly_changes':  {'total': total_drops + total_rises, 'drops': total_drops, 'rises': total_rises},
            'chart_data':      chart_data,
            'top_plans':       top_plans,
        }
    finally:
        conn.close()


def save_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO plans (carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    extras     = excluded.extras,
                    scraped_at = excluded.scraped_at,
                    url        = excluded.url
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("data_gb"), plan.get("minutes"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                now, plan.get("url")
            ))
        conn.commit()
    finally:
        conn.close()


def get_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url "
                "FROM plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at, url "
                "FROM plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "data_gb": r[3], "minutes": r[4],
                "extras": json.loads(r[5]) if r[5] else [],
                "scraped_at": r[6], "url": r[7]
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_global_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO global_plans
                  (carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price          = excluded.price,
                    currency       = excluded.currency,
                    original_price = excluded.original_price,
                    days           = excluded.days,
                    data_gb        = excluded.data_gb,
                    minutes        = excluded.minutes,
                    sms            = excluded.sms,
                    esim           = excluded.esim,
                    extras         = excluded.extras,
                    scraped_at     = excluded.scraped_at
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("currency"), plan.get("original_price"),
                plan.get("days"), plan.get("data_gb"), plan.get("minutes"),
                plan.get("sms"), 1 if plan.get("esim", True) else 0,
                json.dumps(_norm_extras(plan.get("extras", [])), ensure_ascii=False), now
            ))
        conn.commit()
    finally:
        conn.close()


def get_global_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at "
                "FROM global_plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, currency, original_price, days, data_gb, minutes, sms, esim, extras, scraped_at "
                "FROM global_plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "price": r[2], "currency": r[3],
             "original_price": r[4], "days": r[5], "data_gb": r[6], "minutes": r[7],
             "sms": r[8], "esim": bool(r[9]),
             "extras": json.loads(r[10]) if r[10] else [], "scraped_at": r[11]}
            for r in rows
        ]
    finally:
        conn.close()


def save_global_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO global_changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["carrier"], ch["plan_name"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def get_global_changes(limit=50, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM global_changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def save_abroad_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO abroad_plans (carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    days       = excluded.days,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    sms        = excluded.sms,
                    extras     = excluded.extras,
                    scraped_at = excluded.scraped_at
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("days"), plan.get("data_gb"), plan.get("minutes"),
                plan.get("sms"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                now
            ))
        conn.commit()
    finally:
        conn.close()


def get_abroad_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at "
                "FROM abroad_plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, days, data_gb, minutes, sms, extras, scraped_at "
                "FROM abroad_plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "days": r[3], "data_gb": r[4], "minutes": r[5], "sms": r[6],
                "extras": json.loads(r[7]) if r[7] else [],
                "scraped_at": r[8]
            }
            for r in rows
        ]
    finally:
        conn.close()


def save_abroad_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO abroad_changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["carrier"], ch["plan_name"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def get_abroad_changes(limit=50, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM abroad_changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def save_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO changes (carrier, plan_name, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["carrier"], ch["plan_name"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def save_push_subscription(endpoint, p256dh, auth, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth, created_at) "
            "VALUES (?, ?, ?, ?)",
            (endpoint, p256dh, auth, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def delete_push_subscription(endpoint, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))
        conn.commit()
    finally:
        conn.close()


def get_push_subscriptions(db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions"
        ).fetchall()
        return [
            {"endpoint": r[0], "keys": {"p256dh": r[1], "auth": r[2]}}
            for r in rows
        ]
    finally:
        conn.close()


def save_content_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO content_plans (service, carrier, price, free_trial, note, status, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(service, carrier) DO UPDATE SET
                    price      = excluded.price,
                    free_trial = excluded.free_trial,
                    note       = excluded.note,
                    status     = excluded.status,
                    scraped_at = excluded.scraped_at
            """, (
                plan["service"], plan["carrier"], plan.get("price"),
                plan.get("free_trial"), plan.get("note", ""),
                plan.get("status"), now
            ))
        conn.commit()
    finally:
        conn.close()


def get_content_plans(service=None, carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if service and carrier:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans WHERE service=? AND carrier=? ORDER BY service, carrier",
                (service, carrier)
            ).fetchall()
        elif service:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans WHERE service=? ORDER BY carrier",
                (service,)
            ).fetchall()
        elif carrier:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans WHERE carrier=? ORDER BY service",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT service, carrier, price, free_trial, note, status, scraped_at "
                "FROM content_plans ORDER BY service, carrier"
            ).fetchall()
        return [
            {"service": r[0], "carrier": r[1], "price": r[2], "free_trial": r[3],
             "note": r[4], "status": r[5], "scraped_at": r[6]}
            for r in rows
        ]
    finally:
        conn.close()


def save_content_changes(changes, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for ch in changes:
            conn.execute(
                "INSERT INTO content_changes (service, carrier, change_type, old_val, new_val, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ch["service"], ch["carrier"], ch["change_type"],
                 str(ch["old_val"]) if ch.get("old_val") is not None else None,
                 str(ch["new_val"]) if ch.get("new_val") is not None else None,
                 now)
            )
        conn.commit()
    finally:
        conn.close()


def get_content_changes(limit=50, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT service, carrier, change_type, old_val, new_val, changed_at "
            "FROM content_changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"service": r[0], "carrier": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def get_changes(limit=20, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT carrier, plan_name, change_type, old_val, new_val, changed_at "
            "FROM changes ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {"carrier": r[0], "plan_name": r[1], "change_type": r[2],
             "old_val": r[3], "new_val": r[4], "changed_at": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


# ── Price Alerts CRUD ─────────────────────────────────────────────────────

def save_price_alert(user_email, tab, carrier, plan_pattern, threshold, db_path=None):
    """Create a new price alert."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO price_alerts (user_email, tab, carrier, plan_pattern, threshold, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_email, tab, carrier or None, plan_pattern or None,
             threshold, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_price_alerts(user_email=None, active_only=True, db_path=None):
    """Get alerts, optionally filtered by user."""
    conn = _connect(db_path)
    try:
        conditions = []
        params = []
        if user_email:
            conditions.append("user_email = ?")
            params.append(user_email)
        if active_only:
            conditions.append("active = 1")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT id, user_email, tab, carrier, plan_pattern, threshold, active, last_triggered, created_at "
            f"FROM price_alerts {where} ORDER BY created_at DESC",
            params
        ).fetchall()
        return [
            {"id": r[0], "user_email": r[1], "tab": r[2], "carrier": r[3],
             "plan_pattern": r[4], "threshold": r[5], "active": bool(r[6]),
             "last_triggered": r[7], "created_at": r[8]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_price_alert(alert_id, db_path=None):
    """Delete an alert by ID."""
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
        conn.commit()
    finally:
        conn.close()


def update_alert_triggered(alert_id, db_path=None):
    """Mark alert as triggered (set last_triggered to now)."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE price_alerts SET last_triggered = ? WHERE id = ?",
            (datetime.now().isoformat(), alert_id)
        )
        conn.commit()
    finally:
        conn.close()
