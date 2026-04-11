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
        """)
        conn.commit()
    finally:
        conn.close()


def save_plans(plans, db_path=None):
    conn = _connect(db_path)
    try:
        now = datetime.now().isoformat()
        for plan in plans:
            conn.execute("""
                INSERT INTO plans (carrier, plan_name, price, data_gb, minutes, extras, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(carrier, plan_name) DO UPDATE SET
                    price      = excluded.price,
                    data_gb    = excluded.data_gb,
                    minutes    = excluded.minutes,
                    extras     = excluded.extras,
                    scraped_at = excluded.scraped_at
            """, (
                plan["carrier"], plan["plan_name"], plan.get("price"),
                plan.get("data_gb"), plan.get("minutes"),
                json.dumps(plan.get("extras", []), ensure_ascii=False),
                now
            ))
        conn.commit()
    finally:
        conn.close()


def get_plans(carrier=None, db_path=None):
    conn = _connect(db_path)
    try:
        if carrier:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at "
                "FROM plans WHERE carrier=? ORDER BY price",
                (carrier,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT carrier, plan_name, price, data_gb, minutes, extras, scraped_at "
                "FROM plans ORDER BY carrier, price"
            ).fetchall()
        return [
            {
                "carrier": r[0], "plan_name": r[1], "price": r[2],
                "data_gb": r[3], "minutes": r[4],
                "extras": json.loads(r[5]) if r[5] else [],
                "scraped_at": r[6]
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
