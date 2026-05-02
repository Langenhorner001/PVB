"""Helpers for parsing user-supplied proxy strings and converting them into
the dict shape Playwright's ``chromium.launch(proxy=...)`` expects.

Accepted input forms (case-insensitive scheme):

* ``scheme://[user:pass@]host:port``  — full URL form
* ``host:port``                       — bare; defaults to ``http``
* ``host:port:user:pass``             — common proxy-list shorthand
* ``user:pass@host:port``             — auth without scheme
* ``socks5://...`` / ``socks4://...`` — SOCKS proxies (auth via SOCKS not
  supported by Chromium; HTTP/HTTPS auth works via Proxy-Authorization)

Output of :func:`normalize_proxy` is always a canonical
``scheme://[user:pass@]host:port`` URL string with one of the schemes:
``http``, ``https``, ``socks4``, ``socks5``.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit, quote

_ALLOWED_SCHEMES = {"http", "https", "socks4", "socks5"}
_SOCKS_SCHEMES = {"socks4", "socks5"}
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]{1,255}$")

_BLOCKED_HOSTNAMES = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
    "metadata",
    "metadata.google.internal",
}


class ProxyParseError(ValueError):
    """Raised when a proxy string cannot be normalized."""


def _is_blocked_host(host: str) -> bool:
    """Reject loopback, link-local, private, and metadata-service addresses.

    SSRF guard: when the bot dials a user-supplied proxy, the proxy host
    becomes an outbound destination from the bot's network. We refuse to
    forward to private ranges so users cannot probe internal services.
    """
    h = host.lower()
    if h in _BLOCKED_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False  # hostname; let DNS handle it (still bound by network egress)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _hostname_resolves_to_blocked_ip(host: str) -> bool:
    """Return True when a hostname resolves to a private/reserved address."""
    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False

    for info in addr_infos:
        if _is_blocked_host(info[4][0]):
            return True
    return False


def _is_valid_port(p: str) -> bool:
    return p.isdigit() and 1 <= int(p) <= 65535


def _is_valid_host(h: str) -> bool:
    return bool(_HOST_RE.match(h))


def normalize_proxy(raw: str) -> str:
    """Validate and normalize a user-supplied proxy string.

    Raises :class:`ProxyParseError` for invalid input.
    """
    if not raw or not isinstance(raw, str):
        raise ProxyParseError("Empty proxy string.")
    raw = raw.strip()
    if len(raw) > 256:
        raise ProxyParseError("Proxy string too long.")
    if any(ch in raw for ch in ("\n", "\r", " ", "\t")):
        raise ProxyParseError("Proxy string contains whitespace.")

    # Form: scheme://...
    if "://" in raw:
        scheme, rest = raw.split("://", 1)
        scheme = scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise ProxyParseError(
                f"Unsupported scheme '{scheme}'. Use one of: "
                + ", ".join(sorted(_ALLOWED_SCHEMES))
            )
        return _from_authority(scheme, rest)

    # Form without scheme: detect SOCKS hint, otherwise default to http.
    scheme = "http"
    return _from_authority(scheme, raw)


def _from_authority(scheme: str, authority: str) -> str:
    """Parse the part after ``scheme://`` (or the bare authority) into a URL."""
    if "@" in authority:
        userinfo, hostport = authority.rsplit("@", 1)
        if ":" not in userinfo:
            raise ProxyParseError("Auth must be 'user:pass'.")
        user, pwd = userinfo.split(":", 1)
        if not user:
            raise ProxyParseError("Username cannot be empty.")
        if scheme in _SOCKS_SCHEMES:
            # Chromium does not support SOCKS auth; reject upfront so users
            # don't pay for failed orders after a successful /proxycheck.
            raise ProxyParseError(
                "SOCKS auth is not supported by Chromium. "
                "Use an unauthenticated SOCKS proxy or an HTTP/HTTPS proxy."
            )
        host, port = _split_hostport(hostport)
        return f"{scheme}://{quote(user, safe='')}:{quote(pwd, safe='')}@{host}:{port}"

    parts = authority.split(":")
    if len(parts) == 2:
        host, port = parts
        host, port = _split_hostport(f"{host}:{port}")
        return f"{scheme}://{host}:{port}"
    if len(parts) == 4:
        # Common format: host:port:user:pass
        host, port, user, pwd = parts
        host, port = _split_hostport(f"{host}:{port}")
        if not user:
            raise ProxyParseError("Username cannot be empty.")
        if scheme in _SOCKS_SCHEMES:
            raise ProxyParseError(
                "SOCKS auth is not supported by Chromium. "
                "Use an unauthenticated SOCKS proxy or an HTTP/HTTPS proxy."
            )
        return f"{scheme}://{quote(user, safe='')}:{quote(pwd, safe='')}@{host}:{port}"
    raise ProxyParseError(
        "Format not recognized. Use host:port, host:port:user:pass, or scheme://user:pass@host:port."
    )


def _split_hostport(s: str) -> tuple[str, str]:
    if ":" not in s:
        raise ProxyParseError("Missing port (host:port required).")
    host, port = s.rsplit(":", 1)
    if not _is_valid_host(host):
        raise ProxyParseError(f"Invalid host: {host}")
    if not _is_valid_port(port):
        raise ProxyParseError(f"Invalid port: {port}")
    if _is_blocked_host(host) or _hostname_resolves_to_blocked_ip(host):
        raise ProxyParseError(
            "Host is in a private/loopback/reserved range and is not allowed as a proxy."
        )
    return host, port


def to_playwright_proxy(proxy_url: str) -> dict:
    """Convert a normalized proxy URL into the dict Playwright expects:

    ``{"server": "scheme://host:port", "username": ..., "password": ...}``.

    Username/password keys are omitted when no auth is present.
    """
    parts = urlsplit(proxy_url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise ProxyParseError(f"Unsupported scheme: {parts.scheme}")
    if not parts.hostname or not parts.port:
        raise ProxyParseError("Proxy URL missing host or port.")
    server = f"{parts.scheme}://{parts.hostname}:{parts.port}"
    out: dict = {"server": server}
    if parts.username:
        out["username"] = parts.username
    if parts.password is not None:
        out["password"] = parts.password
    return out


def to_requests_proxies(proxy_url: str) -> dict:
    """Convert a normalized proxy URL into the dict ``requests`` expects."""
    return {"http": proxy_url, "https": proxy_url}
