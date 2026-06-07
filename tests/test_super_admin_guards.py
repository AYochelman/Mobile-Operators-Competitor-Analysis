"""Guards that prevent silently destroying the global super_admin role.

`public.user_roles` has UNIQUE(user_id) — one role per user — so any write that
upserts a workspace-scoped role for a user OVERWRITES their global super_admin.
Because the UI can only grant admin/viewer, that demotion can't be undone
without a direct DB edit (it can leave the system with zero super_admins).

Three endpoints could trigger it; each now refuses with HTTP 409:
  - POST /api/workspaces/<id>/users           (assign user to workspace)
  - POST /api/users/<id>/role                 (change a user's role)
  - POST /api/invite/<token>/accept           (accept a workspace invite)

This module also covers TENANT ISOLATION on the bare /api/users* endpoints — a
separate concern from super_admin-demotion (a workspace `admin` reaching across
workspaces):
  - GET  /api/users          — a workspace admin sees only their own workspace's
                               users; super_admin gets the full list   (Guard D)
  - POST /api/users,
    DELETE /api/users/<id>,
    POST /api/users/<id>/role — create/delete/re-role are super_admin-only; a
                               workspace admin is denied 401            (Guard E)

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


# ── Guard D: GET /api/users is workspace-scoped (cross-tenant read leak) ──────
# Different guard family: not super_admin-demotion but tenant isolation. The
# endpoint is @require_admin, so a workspace `admin` (e.g. a Partner admin)
# reaches it via the Settings page. It must return only THEIR workspace's users;
# only super_admin (or the trusted server-admin key) gets the cross-workspace
# list. These drive the JWT path (no X-Server-Admin-Key) and mock
# _get_user_context (its query shares the "WHERE LOWER(u.email)" substring with
# require_admin's inline role check, so substring routing can't tell them apart).
def _jwt_user(monkeypatch, role, workspace_id):
    monkeypatch.setattr(appmod, "_verify_supabase_jwt", lambda tok: {"email": "u@example.com"})
    monkeypatch.setattr(appmod, "_get_user_context",
                        lambda email: {"role": role, "workspace_id": workspace_id, "workspace": None})


def test_get_users_scoped_for_workspace_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "admin", WS)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("admin",)),  # require_admin's inline role check
        ("last_sign_in_at", [(UID, "peer@partner.com", "2026-01-01", "admin", None)]),
    ])
    resp = client.get("/api/users", headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    main = [(s, p) for (s, p) in cur.executed if "last_sign_in_at" in s]
    assert main, "user-listing query did not run"
    sql, params = main[-1]
    assert "WHERE r.workspace_id = %s" in sql   # scoped to the caller's workspace
    assert params == (WS,)


def test_get_users_full_list_for_super_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "super_admin", None)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("super_admin",)),
        ("last_sign_in_at", [(UID, "boss@example.com", "2026-01-01", "super_admin", None)]),
    ])
    resp = client.get("/api/users", headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    main = [(s, p) for (s, p) in cur.executed if "last_sign_in_at" in s]
    assert main, "user-listing query did not run"
    sql, params = main[-1]
    assert "WHERE r.workspace_id" not in sql    # cross-workspace list, unscoped
    assert params is None


def test_get_users_admin_without_workspace_returns_empty(client, monkeypatch):
    # An admin with no workspace assigned must get nothing — never the global list.
    _jwt_user(monkeypatch, "admin", None)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("admin",)),
    ])
    resp = client.get("/api/users", headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert json.loads(resp.data) == []
    assert not [s for (s, p) in cur.executed if "last_sign_in_at" in s]  # no query leaked


# ── Guard E: bare /api/users* WRITES are super_admin-only (cross-tenant write) ─
# Sibling of Guard D. POST /api/users (create), DELETE /api/users/<id> (delete),
# and POST /api/users/<id>/role (re-role) all operate on an arbitrary target
# with NO workspace-ownership check, so they were tightened from @require_admin
# to @require_super_admin: a workspace `admin` (e.g. a Partner admin) must not be
# able to create/delete/re-role users belonging to other tenants. Workspace-
# scoped management lives at /api/workspaces/<id>/users (Guard via
# _can_manage_workspace_users). @require_role denies a non-super_admin JWT with
# 401 BEFORE the body runs; super_admin — and the trusted X-Server-Admin-Key
# (covered by Guard B's role tests) — still pass.
def test_create_user_forbidden_for_workspace_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "admin", WS)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("admin",)),  # @require_role's inline role check
    ])
    resp = client.post("/api/users", headers={"Authorization": "Bearer faketoken"},
                       json={"email": "x@partner.com", "password": "secret123", "role": "admin"})
    assert resp.status_code == 401
    # body never ran — no auth account / role row was created
    assert not [s for (s, p) in cur.executed if "INSERT INTO public.user_roles" in s]


def test_delete_user_forbidden_for_workspace_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "admin", WS)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("admin",)),
    ])
    resp = client.delete(f"/api/users/{UID}", headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 401
    assert not [s for (s, p) in cur.executed if "DELETE FROM auth.users" in s]  # no deletion leaked


def test_update_role_forbidden_for_workspace_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "admin", WS)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("admin",)),
    ])
    resp = client.post(f"/api/users/{UID}/role", headers={"Authorization": "Bearer faketoken"},
                       json={"role": "admin"})
    assert resp.status_code == 401
    assert not [s for (s, p) in cur.executed if "INSERT INTO public.user_roles" in s]  # no role write leaked


# Not over-restricted: super_admin (via JWT) still passes the decorator and the
# body runs. (The X-Server-Admin-Key operator path is exercised by Guard B.)
def test_delete_user_allowed_for_super_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "super_admin", None)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("super_admin",)),  # decorator: caller is super_admin
    ])
    resp = client.delete(f"/api/users/{UID}", headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200
    assert json.loads(resp.data)["status"] == "deleted"
    assert [s for (s, p) in cur.executed if "DELETE FROM auth.users" in s]  # body ran


def test_update_role_allowed_for_super_admin(client, monkeypatch):
    _jwt_user(monkeypatch, "super_admin", None)
    cur = fake_db(monkeypatch, [
        ("WHERE LOWER(u.email)", ("super_admin",)),                    # decorator: super_admin
        ("SELECT role FROM public.user_roles WHERE user_id", ("viewer",)),  # target is a viewer
    ])
    resp = client.post(f"/api/users/{UID}/role", headers={"Authorization": "Bearer faketoken"},
                       json={"role": "admin"})
    assert resp.status_code == 200
    assert json.loads(resp.data)["role"] == "admin"
