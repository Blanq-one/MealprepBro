"""Single-user sign-in (Phase 2): password, session cookie, Origin checks, rate limiting."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import sessions
from app.auth.passwords import PasswordHashError, hash_password, verify_password
from app.config import Settings, get_settings
from app.db.models import LoginAttempt
from app.db.session import get_session
from app.main import create_app

PASSWORD = "correct horse battery"
SECRET = "test-session-secret-0123456789abcdef"
ORIGIN = {"Origin": "http://testserver"}
FAST_HASH = hash_password(PASSWORD, n=2**10)  # tests use a cheap work factor


def settings(**values) -> Settings:
    base = {
        "auth_password_hash": FAST_HASH,
        "session_secret": SECRET,
        "session_cookie_secure": False,  # TestClient talks plain http
        **values,
    }
    return Settings(_env_file=None, **base)


@pytest.fixture
def make_client(seeded_db):
    def build(**values) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_session] = lambda: seeded_db
        app.dependency_overrides[get_settings] = lambda: settings(**values)
        return TestClient(app)

    return build


@pytest.fixture
def api(make_client) -> Iterator[TestClient]:
    with make_client() as client:
        yield client


def login(client: TestClient, password: str = PASSWORD, **headers: str):
    return client.post("/api/v1/auth/login", json={"password": password}, headers={**ORIGIN, **headers})


# ---------------- passwords and tokens ----------------
def test_passwords_are_scrypt_hashed_without_dollar_signs():
    encoded = hash_password(PASSWORD)
    assert encoded.startswith("scrypt:32768:8:1:") and "$" not in encoded  # compose would expand a `$`
    assert verify_password(PASSWORD, encoded) and not verify_password("wrong password", encoded)
    with pytest.raises(PasswordHashError, match="hash-password"):
        verify_password(PASSWORD, "not-a-hash")
    with pytest.raises(PasswordHashError):
        hash_password("short")


def test_a_token_is_valid_until_it_expires_and_any_change_breaks_it():
    token = sessions.issue(SECRET, now=1_000_000)
    assert sessions.read(token, SECRET, 1_000_100, max_age_s=3600) == sessions.Session(1_000_000)
    assert sessions.read(token, SECRET, 1_000_000 + 3601, max_age_s=3600) is None  # expired
    assert sessions.read(token, "another-secret", 1_000_100, 3600) is None  # rotated secret signs out
    version, issued, nonce, signature = token.split(".")
    forged = f"{version}.{int(issued) + 999}.{nonce}.{signature}"
    assert sessions.read(forged, SECRET, 1_000_100, 3600) is None
    assert sessions.read(token[:-2] + "xx", SECRET, 1_000_100, 3600) is None
    assert sessions.read(None, SECRET, 1_000_100, 3600) is None
    assert (
        sessions.read(sessions.issue(SECRET, 2_000_000), SECRET, 1_000_000, 3600) is None
    )  # from the future


# ---------------- the endpoints ----------------
def test_only_health_and_sign_in_work_without_a_session(api):
    assert api.get("/health").status_code == 200
    reply = api.get("/api/v1/plans")
    assert reply.status_code == 401 and reply.headers["content-type"].startswith("application/problem+json")
    assert reply.json()["title"] == "Not signed in"
    assert api.get("/api/v1/auth/session").status_code == 401
    assert api.get("/api/v1/inventory").status_code == 401


def test_a_wrong_password_is_401_and_the_right_one_signs_in_with_a_long_lived_cookie(api):
    wrong = login(api, "nope nope nope")
    assert wrong.status_code == 401 and wrong.json()["title"] == "Wrong password"
    assert "set-cookie" not in wrong.headers
    ok = login(api)
    assert ok.status_code == 204
    cookie = ok.headers["set-cookie"]
    assert cookie.startswith(f"{sessions.COOKIE_NAME}=") and "HttpOnly" in cookie
    assert "Max-Age=15552000" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert api.get("/api/v1/auth/session").json()["signed_in"] is True
    assert api.get("/api/v1/inventory").status_code == 200


def test_the_cookie_is_secure_when_served_over_https(make_client):
    with make_client(session_cookie_secure=True) as client:
        assert "Secure" in login(client).headers["set-cookie"]


def test_a_tampered_or_expired_cookie_is_401(api):
    api.cookies.set(
        sessions.COOKIE_NAME, sessions.issue("someone-elses-secret", now=int(datetime.now(UTC).timestamp()))
    )
    assert api.get("/api/v1/plans").status_code == 401
    old = int((datetime.now(UTC) - timedelta(days=181)).timestamp())
    api.cookies.set(sessions.COOKIE_NAME, sessions.issue(SECRET, now=old))
    assert api.get("/api/v1/plans").status_code == 401


def test_a_cookie_over_a_day_old_is_renewed_so_the_app_stays_signed_in(api):
    two_days_ago = int((datetime.now(UTC) - timedelta(days=2)).timestamp())
    api.cookies.set(sessions.COOKIE_NAME, sessions.issue(SECRET, now=two_days_ago))
    reply = api.get("/api/v1/auth/session")
    assert reply.status_code == 200 and sessions.COOKIE_NAME in reply.headers.get("set-cookie", "")
    fresh = api.get("/api/v1/auth/session")
    assert "set-cookie" not in fresh.headers  # renewed at most once a day


def test_logout_clears_the_cookie(api):
    login(api)
    out = api.post("/api/v1/auth/logout", headers=ORIGIN)
    assert out.status_code == 204 and "Max-Age=0" in out.headers["set-cookie"]
    assert api.get("/api/v1/plans").status_code == 401


def test_sign_in_that_is_not_set_up_says_so(make_client):
    with make_client(auth_password_hash=None) as client:
        reply = login(client)
        assert reply.status_code == 503 and "AUTH_PASSWORD_HASH" in reply.json()["detail"]
    with make_client(session_secret=None) as client:
        assert client.get("/api/v1/plans").status_code == 503


# ---------------- cross-origin changes ----------------
def test_changes_must_come_from_this_site(api):
    login(api)
    assert (
        api.put("/api/v1/settings/ingredient-preferences/1", json={"preference": "like"}).status_code == 403
    )
    evil = api.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.json()["title"] == "Cross-site request refused"
    # behind a proxy (the Next dev server, Vercel) the forwarded host counts
    proxied = api.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://192.168.1.20:3000", "X-Forwarded-Host": "192.168.1.20:3000"},
    )
    assert proxied.status_code == 204
    assert api.get("/api/v1/auth/session").status_code in (200, 401)  # reads need no Origin


def test_extra_allowed_origins(make_client):
    with make_client(allowed_origins="https://mealbro.example.com") as client:
        reply = login(client, Origin="https://mealbro.example.com")
        assert reply.status_code == 204


# ---------------- rate limiting ----------------
def test_too_many_wrong_passwords_are_refused_for_a_while(api, seeded_db):
    for _ in range(5):
        assert login(api, "wrong wrong").status_code == 401
    blocked = login(api)  # even the right password, until the window passes
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
    assert blocked.json()["title"] == "Too many tries"
    for attempt in seeded_db.query(LoginAttempt):  # 15 minutes later
        attempt.occurred_at = attempt.occurred_at - timedelta(minutes=16)
    seeded_db.flush()
    assert login(api).status_code == 204


def test_a_successful_sign_in_clears_the_count(api):
    for _ in range(4):
        login(api, "wrong wrong")
    assert login(api).status_code == 204
    for _ in range(4):
        assert login(api, "wrong wrong").status_code == 401  # a fresh count after the success
    assert login(api).status_code == 204


def test_failures_from_everywhere_together_are_capped_too(make_client):
    with make_client(vercel="1", login_max_failures_global=6) as client:  # Vercel sets x-real-ip
        for n in range(6):
            assert login(client, "wrong wrong", **{"x-real-ip": f"203.0.113.{n}"}).status_code == 401
        assert login(client, **{"x-real-ip": "198.51.100.7"}).status_code == 429


def test_login_attempts_store_a_keyed_hash_not_the_address(api, seeded_db):
    login(api, "wrong wrong")
    keys = [a.client_key for a in seeded_db.query(LoginAttempt)]
    assert keys and all(len(k) == 32 and "testclient" not in k for k in keys)
