"""SSRF protection for outbound HTTP requests initiated by user workflows
(HTTP node, notification webhooks, etc.).

By default blocks requests to private/internal addresses (loopback, RFC1918,
link-local including cloud-metadata 169.254.169.254). For self-host setups where
workflows legitimately reach internal services, this is disabled via
`HTTP_NODE_ALLOW_INTERNAL=true`.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class SSRFValidationError(ValueError):
    """Outbound URL blocked by the SSRF protection policy."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # includes 169.254.0.0/16 (cloud metadata)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_validated_ip(url: str, *, allow_internal: bool = False) -> str | None:
    """Validate a URL for an outbound request and return a vetted IP to connect to.

    Resolves the host, checks EVERY resolved IP against the block-list, and returns
    one validated IP. Callers should connect to this exact IP (not re-resolve the
    hostname) to close the DNS-rebinding TOCTOU: the address that was checked is the
    address that gets used. Returns None when allow_internal is set (self-host opt-out)
    — there is nothing to pin because private targets are permitted.

    Raises SSRFValidationError if the scheme is not http(s), the host is missing,
    the host does not resolve, or any resolved IP falls in a private/internal range.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SSRFValidationError(f"URL scheme '{parsed.scheme}' is not allowed (only http/https)")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL has no host")

    if allow_internal:
        return None

    # Resolve the host to all IPs and check EVERY one — otherwise multi-A-record
    # rebinding (one public + one private) could bypass the check.
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFValidationError(f"Cannot resolve host '{hostname}'") from exc

    # Preserve resolution order so we can pin to a deterministic (the first) address.
    resolved: list[str] = []
    for info in infos:
        addr = str(info[4][0])  # sockaddr host element (str for AF_INET/AF_INET6)
        if addr not in resolved:
            resolved.append(addr)
    if not resolved:
        raise SSRFValidationError(f"Host '{hostname}' did not resolve to any address")

    for addr in resolved:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as e:
            raise SSRFValidationError(f"Host '{hostname}' resolved to invalid address") from e
        if _is_blocked_ip(ip):
            raise SSRFValidationError(
                f"Host '{hostname}' resolves to a blocked address ({ip}). "
                "Set HTTP_NODE_ALLOW_INTERNAL=true to allow internal targets (self-host)."
            )

    # Every resolved IP passed; pin the connection to the first one.
    return resolved[0]


def validate_outbound_url(url: str, *, allow_internal: bool = False) -> None:
    """Validate that a URL is safe for an outbound request (raises on failure).

    Thin wrapper over resolve_validated_ip for callers that only need the check and
    do not pin the connection. Prefer resolve_validated_ip + connection pinning for
    anything that actually issues the request.
    """
    resolve_validated_ip(url, allow_internal=allow_internal)
