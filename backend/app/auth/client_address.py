"""The client address the login rate limit is keyed on (BUILD_PLAN §12.4, PD1; step 2b.13).

A forwarding header is believed only from a proxy we trust; a client can never pick its own key by sending
one:

  on Vercel        the platform's edge sets x-vercel-forwarded-for (and x-real-ip, x-forwarded-for) and
                   overwrites whatever a client sent: Vercel doesn't forward external IPs, to prevent spoofing
                   (vercel.com/docs/headers/request-headers). A function is only reached through that edge.
  behind your own  TRUSTED_PROXIES (addresses, networks or host names, comma-separated): when the socket's
  proxy            peer is one of them, its X-Forwarded-For is read from the right, skipping trusted proxies,
                   and the first address that isn't one is the client (entries to its left are whatever the
                   client sent: never used). Only for a proxy that appends the address it saw (nginx's
                   $proxy_add_x_forwarded_for). Not the Next dev server: its rewrites pass a client's own
                   header along unchanged and never add one, so docker compose trusts no proxy and every
                   device on the Wi-Fi shares the dev server's counter.
  otherwise        the socket's peer address; any forwarding header is ignored

A host name is resolved when it's needed (cached for a minute), so a proxy that restarts with a new address
is followed; one that doesn't resolve trusts nothing.
"""

import re
import socket
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network

Network = IPv4Network | IPv6Network
Address = IPv4Address | IPv6Address
Resolver = Callable[[str], list[str]]
VERCEL_HEADERS = ("x-vercel-forwarded-for", "x-real-ip", "x-forwarded-for")
RESOLVE_EVERY_S = 60.0
HOST_NAME = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*$")


class TrustedProxiesError(ValueError):
    """TRUSTED_PROXIES has an entry that is neither an address, a network nor a host name."""


def resolve(host: str) -> list[str]:
    try:
        return sorted({str(info[4][0]) for info in socket.getaddrinfo(host, None)})
    except OSError:
        return []


@dataclass
class TrustedProxies:
    networks: tuple[Network, ...] = ()
    hosts: tuple[str, ...] = ()
    resolver: Resolver = resolve
    _resolved: tuple[float, frozenset[Address]] | None = field(default=None, repr=False)

    def __bool__(self) -> bool:
        return bool(self.networks or self.hosts)

    def _host_addresses(self) -> frozenset[Address]:
        now = time.monotonic()
        if self._resolved is None or now - self._resolved[0] > RESOLVE_EVERY_S:
            found = {_ip(a) for host in self.hosts for a in self.resolver(host)}
            self._resolved = (now, frozenset(a for a in found if a is not None))
        return self._resolved[1]

    def contains(self, address: str) -> bool:
        ip = _ip(address)
        if ip is None:
            return False  # junk is never a trusted proxy
        return any(ip in n for n in self.networks) or (bool(self.hosts) and ip in self._host_addresses())


def _ip(text: str) -> Address | None:
    try:
        return ip_address(text.strip())
    except ValueError:
        return None


def parse_trusted(text: str, resolver: Resolver = resolve) -> TrustedProxies:
    networks: list[Network] = []
    hosts: list[str] = []
    for entry in (e.strip() for e in text.split(",")):
        if not entry:
            continue
        try:
            networks.append(ip_network(entry, strict=False))
            continue
        except ValueError:
            pass
        if not HOST_NAME.match(entry):
            raise TrustedProxiesError(
                f"TRUSTED_PROXIES: {entry!r} isn't an address, a network or a host name"
            )
        hosts.append(entry)
    return TrustedProxies(tuple(networks), tuple(hosts), resolver)


@lru_cache(maxsize=8)
def trusted_proxies(text: str) -> TrustedProxies:
    """TRUSTED_PROXIES, parsed once per value (its host names' addresses cached for a minute)."""
    return parse_trusted(text)


def client_address(
    headers: Mapping[str, str], peer: str | None, *, on_vercel: bool, trusted: TrustedProxies | None = None
) -> str:
    """The address to key on: the platform's on Vercel, the nearest untrusted hop behind a trusted proxy,
    else the socket's peer."""
    peer = peer or "unknown"
    if on_vercel:
        for name in VERCEL_HEADERS:
            if first := headers.get(name, "").split(",")[0].strip():
                return first
        return peer
    if not trusted or not trusted.contains(peer):
        return peer
    hops = [h.strip() for h in headers.get("x-forwarded-for", "").split(",") if h.strip()]
    for hop in reversed(hops):
        if not trusted.contains(hop):
            return hop
    return hops[0] if hops else peer
