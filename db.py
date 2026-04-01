import sqlite3
import json
import os
from datetime import datetime

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
