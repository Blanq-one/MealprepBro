"""The login rate limit's client address (PD1, step 2b.13): a forwarding header counts only from a proxy we
trust (Vercel's edge, or TRUSTED_PROXIES), so two clients behind the proxy get separate counters and a client
can't pick its own key by sending the header. Docker compose trusts no proxy: the Next dev server relays a
client's own header."""

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.client_address import TrustedProxies, TrustedProxiesError, client_address, parse_trusted
from app.auth.tests.test_auth import ORIGIN, PASSWORD, settings
from app.config import BACKEND_DIR, get_settings
from app.db.session import get_session
from app.main import create_app

PROXY = "172.20.0.5"  # a reverse proxy that appends the address it saw (nginx's $proxy_add_x_forwarded_for)
COMPOSE = BACKEND_DIR.parent / "docker-compose.yml"


def trusted(text: str = PROXY) -> TrustedProxies:
    return parse_trusted(text, resolver=lambda host: [PROXY] if host == "proxy" else [])


def test_off_vercel_a_client_s_own_header_is_ignored() -> None:
    spoofed = {
        "x-forwarded-for": "203.0.113.9",
        "x-real-ip": "203.0.113.9",
        "x-vercel-forwarded-for": "1.2.3.4",
    }
    # no trusted proxy, or a peer that isn't one: the socket's address, whatever the headers say
    assert client_address(spoofed, "198.51.100.20", on_vercel=False) == "198.51.100.20"
    assert client_address(spoofed, "198.51.100.20", on_vercel=False, trusted=trusted()) == "198.51.100.20"


def test_behind_a_trusted_proxy_the_nearest_untrusted_hop_is_the_client() -> None:
    proxies = trusted()
    assert client_address({"x-forwarded-for": "192.168.1.30"}, PROXY, on_vercel=False, trusted=proxies) == (
        "192.168.1.30"
    )
    # a client that sends its own header through the proxy: the proxy appends the real address, which wins
    spoof = {"x-forwarded-for": "6.6.6.6, 192.168.1.30"}
    assert client_address(spoof, PROXY, on_vercel=False, trusted=proxies) == "192.168.1.30"
    # trusted hops are skipped; no header at all is the proxy itself
    chain = {"x-forwarded-for": f"192.168.1.30, {PROXY}"}
    assert client_address(chain, PROXY, on_vercel=False, trusted=proxies) == "192.168.1.30"
    assert client_address({}, PROXY, on_vercel=False, trusted=proxies) == PROXY


def test_a_trusted_proxy_by_host_name_and_bad_entries() -> None:
    by_name = trusted("proxy")
    assert client_address({"x-forwarded-for": "192.168.1.31"}, PROXY, on_vercel=False, trusted=by_name) == (
        "192.168.1.31"
    )
    assert client_address(
        {"x-forwarded-for": "192.168.1.31"}, "172.20.0.9", on_vercel=False, trusted=by_name
    ) == ("172.20.0.9")
    nothing = parse_trusted("proxy", resolver=lambda _: [])  # doesn't resolve: trusts nothing
    assert client_address({"x-forwarded-for": "1.1.1.1"}, PROXY, on_vercel=False, trusted=nothing) == PROXY
    assert bool(parse_trusted("10.0.0.0/8, 127.0.0.1")) and not parse_trusted("")
    with pytest.raises(TrustedProxiesError):
        parse_trusted("not a host!")


@pytest.mark.skipif(not COMPOSE.exists(), reason="no docker-compose.yml here (the fresh-clone image)")
def test_docker_compose_trusts_no_proxy_by_default() -> None:
    """The Next dev server's rewrites pass a client's own X-Forwarded-For along unchanged (checked on the dev
    stack, 2026-10-13): trusting it would let any device on the Wi-Fi pick its own sign-in counter."""
    text = COMPOSE.read_text(encoding="utf-8")
    lines = re.findall(r"^\s*TRUSTED_PROXIES:\s*(.*)$", text, flags=re.MULTILINE)
    assert lines == ["${TRUSTED_PROXIES:-}"]


def test_on_vercel_the_platforms_header_names_the_client() -> None:
    # Vercel's edge overwrites these (it doesn't forward external IPs): the first entry is the client
    assert (
        client_address({"x-vercel-forwarded-for": "203.0.113.4"}, "10.0.0.1", on_vercel=True) == "203.0.113.4"
    )
    assert client_address({"x-real-ip": "203.0.113.5"}, "10.0.0.1", on_vercel=True) == "203.0.113.5"
    assert client_address({}, "10.0.0.1", on_vercel=True) == "10.0.0.1"


@pytest.fixture
def through(seeded_db: Session) -> Callable[..., TestClient]:
    """A TestClient whose socket peer is `peer`, with sign-in set up and TRUSTED_PROXIES as given."""

    def build(peer: str, **values: object) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_session] = lambda: seeded_db
        app.dependency_overrides[get_settings] = lambda: settings(**values)
        return TestClient(app, client=(peer, 50000))

    return build


def wrong(client: TestClient, forwarded: str | None = None) -> int:
    headers = {**ORIGIN, **({"x-forwarded-for": forwarded} if forwarded else {})}
    reply = client.post("/api/v1/auth/login", json={"password": "wrong wrong"}, headers=headers)
    return int(reply.status_code)


def test_two_phones_behind_the_proxy_get_separate_counters(through: Callable[..., TestClient]) -> None:
    with through(PROXY, trusted_proxies=PROXY) as proxy:
        for _ in range(5):
            assert wrong(proxy, "192.168.1.30") == 401
        assert wrong(proxy, "192.168.1.30") == 429  # this phone is locked out
        assert wrong(proxy, "192.168.1.31") == 401  # the other one isn't
        right = proxy.post(
            "/api/v1/auth/login",
            json={"password": PASSWORD},
            headers={**ORIGIN, "x-forwarded-for": "192.168.1.31"},
        )
        assert right.status_code == 204


def test_a_spoofed_header_from_an_untrusted_client_is_ignored(through: Callable[..., TestClient]) -> None:
    """A client that isn't the trusted proxy can't pick a fresh key by changing its X-Forwarded-For."""
    with through("198.51.100.20", trusted_proxies=PROXY) as client:
        for n in range(5):
            assert wrong(client, f"203.0.113.{n}") == 401
        assert wrong(client, "203.0.113.99") == 429  # still the same client: locked out
