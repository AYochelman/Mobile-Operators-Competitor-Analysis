"""DELETE /api/workspaces/<id> - guarded, transactional workspace deletion.
Supabase is replaced by a tiny in-memory fake that honours commit / rollback."""
import copy

import pytest

import db


class FakeSupabase:
    def __init__(self):
        self.workspaces = {"ws-int": {"slug": "moca-internal", "name": "MOCA Internal"},
                           "ws-a": {"slug": "acme", "name": "Acme Mobile"}}
        self.users = {"u1": "one@acme.test", "u2": "two@acme.test", "u9": "boss@moca.test"}
        self.roles = {"u1": ("admin", "ws-a"), "u2": ("viewer", "ws-a"), "u9": ("super_admin", "ws-int")}
        self.fail_on = None            # substring of an SQL statement that should raise

    def connect(self):
        return _Conn(self)


class _Conn:
    def __init__(self, store):
        self.store = store
        self.autocommit = False
        self._snapshot = self._take()

    def _take(self):
        s = self.store
        return copy.deepcopy((s.workspaces, s.users, s.roles))

    def cursor(self):
        return _Cur(self.store)

    def commit(self):
        self._snapshot = self._take()

    def rollback(self):
        s = self.store
        s.workspaces, s.users, s.roles = copy.deepcopy(self._snapshot)

    def close(self):
        self.rollback()                # anything uncommitted is discarded, like psycopg2


class _Cur:
    def __init__(self, store):
        self.s = store
        self._rows = []

    def execute(self, sql, params=None):
        s, p = self.s, params or ()
        q = " ".join(sql.split())
        if s.fail_on and s.fail_on in q:
            raise RuntimeError("supabase down")
        if q.startswith("SELECT slug, name FROM public.workspaces"):
            w = s.workspaces.get(p[0])
            self._rows = [(w["slug"], w["name"])] if w else []
        elif q.startswith("SELECT r.user_id, LOWER(u.email), r.role"):
            self._rows = [(uid, s.users.get(uid), role) for uid, (role, ws) in s.roles.items() if ws == p[0]]
        elif q.startswith("SELECT id FROM public.workspaces WHERE slug"):
            self._rows = [(wid,) for wid, w in s.workspaces.items() if w["slug"] == p[0]]
        elif q.startswith("UPDATE public.user_roles SET workspace_id"):
            for uid, (role, ws) in list(s.roles.items()):
                if ws == p[1]:
                    s.roles[uid] = ("viewer", p[0])
        elif q.startswith("DELETE FROM public.user_roles WHERE workspace_id"):
            for uid in [u for u, (_r, ws) in s.roles.items() if ws == p[0]]:
                del s.roles[uid]
        elif q.startswith("DELETE FROM auth.users WHERE id"):
            s.users.pop(p[0], None)
        elif q.startswith("DELETE FROM public.workspaces WHERE id"):
            s.workspaces.pop(p[0], None)
        else:
            raise AssertionError(f"unexpected SQL: {q}")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app as core
    path = str(tmp_path / "t.db")
    db.init_db(path)
    core.app.config["TEST_DB_PATH"] = path
    store = FakeSupabase()
    monkeypatch.setattr(core, "_supabase_conn", store.connect)
    monkeypatch.setattr(core, "_current_user_email", lambda: "boss@moca.test")
    headers = {"X-Server-Admin-Key": core._get_server_admin_key()}
    # The endpoint allows 5 calls a minute; these tests make more than that.
    was_enabled = core.limiter.enabled
    core.limiter.enabled = False
    yield core.app.test_client(), store, headers, path
    core.limiter.enabled = was_enabled
    core.app.config.pop("TEST_DB_PATH", None)


def _seed_local(path):
    db.save_dashboard_setup("workspace", "ws-a", {"sections": {"/news": "hidden"}}, db_path=path)
    db.save_dashboard_setup("user", "one@acme.test", {"channels": {}}, db_path=path)
    db.set_alert_cursor("one@acme.test", "email", "2026-11-15T07:00:00", db_path=path)
    db.create_workspace_invite("ws-a", role="viewer", created_by="boss@moca.test", db_path=path)
    db.create_workspace_invite("ws-int", role="viewer", created_by="boss@moca.test", db_path=path)
    conn = db._connect(path)
    conn.execute("INSERT INTO price_alerts (user_email, tab, threshold, created_at) VALUES (?,?,?,?)",
                 ("one@acme.test", "domestic", 30, "2026-11-01"))
    conn.execute("INSERT INTO price_alerts (user_email, tab, threshold, created_at) VALUES (?,?,?,?)",
                 ("boss@moca.test", "domestic", 30, "2026-11-01"))
    conn.execute("INSERT INTO plan_annotations (workspace_id, user_email, carrier, plan_name, plan_type, note, "
                 "created_at) VALUES (?,?,?,?,?,?,?)", ("ws-a", "one@acme.test", "partner", "P", "domestic", "n", "x"))
    conn.commit()
    conn.close()


def _count(path, table, where="1=1", params=()):
    conn = db._connect(path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
    finally:
        conn.close()


def test_refusals_change_nothing(env):
    c, store, h, _path = env
    before = copy.deepcopy((store.workspaces, store.users, store.roles))
    # the regular API key is not enough
    import app as core
    assert c.delete("/api/workspaces/ws-a", headers={"X-API-Key": core._get_api_key()},
                    json={"confirm_slug": "acme", "users": "move"}).status_code in (401, 403)
    assert c.delete("/api/workspaces/ws-a", headers=h, json={"confirm_slug": "acme"}).status_code == 400
    assert c.delete("/api/workspaces/ws-a", headers=h,
                    json={"confirm_slug": "wrong", "users": "delete"}).status_code == 400
    assert c.delete("/api/workspaces/nope", headers=h,
                    json={"confirm_slug": "acme", "users": "move"}).status_code == 404
    # the protected workspace, even with the right slug typed
    assert c.delete("/api/workspaces/ws-int", headers=h,
                    json={"confirm_slug": "moca-internal", "users": "move"}).status_code == 400
    # a super_admin member blocks both modes
    store.roles["u9"] = ("super_admin", "ws-a")
    for mode in ("move", "delete"):
        assert c.delete("/api/workspaces/ws-a", headers=h,
                        json={"confirm_slug": "acme", "users": mode}).status_code == 409
    store.roles["u9"] = ("super_admin", "ws-int")
    assert (store.workspaces, store.users, store.roles) == before


def test_delete_moving_users_keeps_their_accounts_and_data(env):
    c, store, h, path = env
    _seed_local(path)
    r = c.delete("/api/workspaces/ws-a", headers=h, json={"confirm_slug": "ACME", "users": "move"})
    assert r.status_code == 200 and r.get_json() == {"status": "deleted", "users": "move",
                                                     "user_count": 2, "cleanup_ok": True}
    assert "ws-a" not in store.workspaces and "ws-int" in store.workspaces
    assert store.roles["u1"] == ("viewer", "ws-int") and store.roles["u2"] == ("viewer", "ws-int")
    assert set(store.users) == {"u1", "u2", "u9"}
    # workspace rows are gone, the moved users' personal data stays
    assert db.get_dashboard_setup("workspace", "ws-a", db_path=path) is None
    assert _count(path, "workspace_invites", "workspace_id=?", ("ws-a",)) == 0
    assert _count(path, "workspace_invites", "workspace_id=?", ("ws-int",)) == 1
    assert _count(path, "plan_annotations") == 0
    assert db.get_dashboard_setup("user", "one@acme.test", db_path=path) is not None
    assert _count(path, "price_alerts") == 2
    assert _count(path, "audit_log", "action='workspace_deleted'") == 1


def test_delete_with_users_erases_accounts_and_personal_data(env):
    c, store, h, path = env
    _seed_local(path)
    r = c.delete("/api/workspaces/ws-a", headers=h, json={"confirm_slug": "acme", "users": "delete"})
    assert r.status_code == 200 and r.get_json()["user_count"] == 2
    assert "ws-a" not in store.workspaces
    assert set(store.users) == {"u9"} and set(store.roles) == {"u9"}
    assert db.get_dashboard_setup("user", "one@acme.test", db_path=path) is None
    assert db.get_alert_cursors("one@acme.test", db_path=path) == {}
    # only the deleted user's price alert is gone - it would have kept e-mailing them
    assert _count(path, "price_alerts", "user_email=?", ("one@acme.test",)) == 0
    assert _count(path, "price_alerts", "user_email=?", ("boss@moca.test",)) == 1


def test_failure_mid_transaction_rolls_everything_back(env):
    c, store, h, path = env
    _seed_local(path)
    before = copy.deepcopy((store.workspaces, store.users, store.roles))
    store.fail_on = "DELETE FROM public.workspaces"      # after the users were already removed
    r = c.delete("/api/workspaces/ws-a", headers=h, json={"confirm_slug": "acme", "users": "delete"})
    assert r.status_code == 500
    assert (store.workspaces, store.users, store.roles) == before
    # and nothing local was touched either
    assert db.get_dashboard_setup("workspace", "ws-a", db_path=path) is not None
    assert db.get_dashboard_setup("user", "one@acme.test", db_path=path) is not None
    assert _count(path, "price_alerts") == 2
    assert _count(path, "audit_log", "action='workspace_deleted'") == 0
