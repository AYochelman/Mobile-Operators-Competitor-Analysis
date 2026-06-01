"""Guards that prevent silently destroying the global super_admin role.

`public.user_roles` has UNIQUE(user_id) — one role per user — so any write that
upserts a workspace-scoped role for a user OVERWRITES their global super_admin.
Because the UI can only grant admin/viewer, that demotion can't be undone
without a direct DB edit (it can leave the system with zero super_admins).

Three endpoints could trigger it; each now refuses with HTTP 409:
  - POST /api/workspaces/<id>/users           (assign user to workspace)
  - POST /api/users/<id>/role                 (change a user's role)
  - POST /api/invite/<token>/accept           (accept a workspace invite)

These tests fake the Supabase connection (a substring-routed cursor) and the
api-key / server-admin-key helpers, so they run without a live DB or JWT.
"""
import json
import pytest

import app as appmod
from app import app as flask_app
from db import init_db


# ── Fakes ───────────────────────────────────────────────────────────────────
class FakeCursor:
    """psycopg2-cursor stand-in. Each execute() picks a canned result by the
    first matching SQL substring; fetchone()/fetchall() return it. Unmatched
    statements (e.g. INSERT/UPDATE) yield no rows."""
    def __init__(self, routes):
        self.routes = routes          # list of (sql_substring, result)
        self._result = None
        self.executed = []            # (sql, params) — available for assertions

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._result = None
        for sub, res in self.routes:
            if sub in sql:
                self._result = res
                break

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result if isinstance(self._result, list) else []

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = False

    def cursor(self):
        return self._cursor

    def close(self):
        pass


WS = "11111111-1111-1111-1111-111111111111"
UID = "22222222-2222-2222-2222-222222222222"


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def client(tmp_path):
    # A throwaway SQLite DB so log_audit() writes never touch the real data/plans.db
    db = str(tmp_path / "test.db")
    flask_app.config["TEST_DB_PATH"] = db
    flask_app.config["TESTING"] = True
    init_db(db_path=db)
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def auth(monkeypatch):
    """Deterministic keys so the test client can satisfy @require_auth,
    @require_admin, and _can_manage_workspace_users without a real JWT."""
    monkeypatch.setattr(appmod, "_get_api_key", lambda: "testkey")
    monkeypatch.setattr(appmod, "_get_server_admin_key", lambda: "testsakey")
    return {"X-API-Key": "testkey", "X-Server-Admin-Key": "testsakey"}


def fake_db(monkeypatch, routes):
    cur = FakeCursor(routes)
    monkeypatch.setattr(appmod, "_supabase_conn", lambda: FakeConn(cur))
    return cur


# ── Guard A: assigning a super_admin to a workspace is blocked ───────────────
def test_assign_super_admin_to_workspace_is_blocked(client, auth, monkeypatch):
    fake_db(monkeypatch, [
        ("FROM auth.users WHERE LOWER(email)", (UID,)),
        ("SELECT role FROM public.user_roles WHERE user_id", ("super_admin",)),
    ])
    resp = client.post(f"/api/workspaces/{WS}/users", headers=auth,
                       json={"email": "boss@example.com", "role": "admin"})
    assert resp.status_code == 409
    assert "super_admin" in json.loads(resp.data)["error"]


def test_assign_regular_user_to_workspace_is_allowed(client, auth, monkeypatch):
    # Guard must NOT over-block: a non-super_admin assignment still succeeds.
    import notifier
    monkeypatch.setattr(notifier, "send_welcome_email", lambda *a, **k: True, raising=False)
    fake_db(monkeypatch, [
        ("FROM auth.users WHERE LOWER(email)", (UID,)),
        ("SELECT role FROM public.user_roles WHERE user_id", ("viewer",)),
        ("SELECT 1 FROM public.workspaces WHERE id", (1,)),
        ("SELECT name FROM public.workspaces WHERE id", ("Acme",)),
    ])
    resp = client.post(f"/api/workspaces/{WS}/users", headers=auth,
                       json={"email": "new@example.com", "role": "viewer"})
    assert resp.status_code == 201
    assert json.loads(resp.data)["status"] == "assigned"


# ── Guard B: demoting the LAST super_admin via the role manager is blocked ───
def test_demote_last_super_admin_is_blocked(client, auth, monkeypatch):
    fake_db(monkeypatch, [
        ("SELECT role FROM public.user_roles WHERE user_id", ("super_admin",)),
        ("COUNT(*) FROM public.user_roles", (1,)),  # only one super_admin exists
    ])
    resp = client.post(f"/api/users/{UID}/role", headers=auth,
                       json={"role": "admin"})
    assert resp.status_code == 409
    assert "super_admin" in json.loads(resp.data)["error"]


def test_demote_super_admin_when_others_exist_is_allowed(client, auth, monkeypatch):
    # With a second super_admin present, demoting one is permitted.
    fake_db(monkeypatch, [
        ("SELECT role FROM public.user_roles WHERE user_id", ("super_admin",)),
        ("COUNT(*) FROM public.user_roles", (2,)),
    ])
    resp = client.post(f"/api/users/{UID}/role", headers=auth,
                       json={"role": "admin"})
    assert resp.status_code == 200
    assert json.loads(resp.data)["role"] == "admin"


def test_change_non_super_admin_role_is_allowed(client, auth, monkeypatch):
    # A normal user's role change never touches the super_admin guard.
    fake_db(monkeypatch, [
        ("SELECT role FROM public.user_roles WHERE user_id", ("viewer",)),
    ])
    resp = client.post(f"/api/users/{UID}/role", headers=auth,
                       json={"role": "admin"})
    assert resp.status_code == 200


# ── Guard C: a super_admin accepting a workspace invite is not demoted ───────
def test_super_admin_accepting_invite_is_blocked(client, auth, monkeypatch):
    monkeypatch.setattr(appmod, "_current_user_email", lambda: "boss@example.com")
    monkeypatch.setattr(appmod, "get_workspace_invite", lambda token, db_path=None: {
        "used_at": None,
        "expires_at": "2999-01-01T00:00:00+00:00",
        "workspace_id": WS,
        "role": "admin",
    })
    fake_db(monkeypatch, [
        ("FROM auth.users WHERE LOWER(email)", (UID,)),
        ("SELECT role FROM public.user_roles WHERE user_id", ("super_admin",)),
    ])
    resp = client.post("/api/invite/sometoken/accept", headers=auth)
    assert resp.status_code == 409
    assert "super_admin" in json.loads(resp.data)["error"]
