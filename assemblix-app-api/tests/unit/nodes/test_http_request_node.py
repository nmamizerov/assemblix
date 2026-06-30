"""Unit tests for the HTTP_REQUEST node (assemblix_api/nodes/http_request_node.py).

The node renders CEL ``{{...}}`` templates in URL / headers / body / query params,
runs the request via httpx, parses the response (JSON when content-type says so,
otherwise text), and returns ``status_code`` / ``body`` / ``headers`` / ``ok``. It
also blocks SSRF to private/internal hosts before making the request.

Outbound HTTP is stubbed with ``respx`` (httpx mock). DNS resolution inside the SSRF
guard is stubbed via ``socket.getaddrinfo`` so a public host resolves to a public IP
without real network access; the loopback test needs no DNS (127.0.0.1 is blocked by
IP-range checks directly).
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from assemblix_api.nodes.http_request_node import HTTPRequestNode

from ._helpers import build_node, make_context, node_input


def _http(config: dict) -> HTTPRequestNode:
    """Build an HTTP_REQUEST node from its config dict."""
    return build_node(HTTPRequestNode, "http_request", config)  # type: ignore[return-value]


@pytest.fixture
def public_dns(mocker):
    """Make the SSRF guard see any host as resolving to a public IP (no real DNS)."""
    mocker.patch(
        "assemblix_api.core.ssrf.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    )


@respx.mock
async def test_get_returns_json_body(public_dns) -> None:
    """A successful GET parses the JSON body and reports status_code / ok."""
    # Arrange
    respx.get("https://api.example.com/users").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "Alice"})
    )
    context = make_context()
    node = _http({"url": "https://api.example.com/users", "method": "GET"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.data["status_code"] == 200
    assert output.data["ok"] is True
    assert output.data["body"] == {"id": 1, "name": "Alice"}


@respx.mock
async def test_post_sends_json_body(public_dns) -> None:
    """A POST with a JSON body string sends parsed JSON and returns the response."""
    # Arrange
    route = respx.post("https://api.example.com/items").mock(
        return_value=httpx.Response(201, json={"created": True})
    )
    context = make_context()
    node = _http(
        {
            "url": "https://api.example.com/items",
            "method": "POST",
            "body": '{"title": "hello"}',
        }
    )

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.data["status_code"] == 201
    assert output.data["body"] == {"created": True}
    assert route.called
    sent = route.calls.last.request
    # The node parses the JSON body string into a dict and sends it via httpx `json=`,
    # which re-serializes it (compact form), so compare the decoded payload.
    assert json.loads(sent.content) == {"title": "hello"}


@respx.mock
async def test_url_cel_templating(public_dns) -> None:
    """CEL templates in the URL are rendered from state before the request runs."""
    # Arrange
    respx.get("https://api.example.com/users/42").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    context = make_context(state={"user_id": 42})
    node = _http({"url": "https://api.example.com/users/{{state.user_id}}", "method": "GET"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.metadata is not None
    assert output.metadata["url"] == "https://api.example.com/users/42"
    assert output.data["status_code"] == 200


@respx.mock
async def test_non_json_response_returns_text(public_dns) -> None:
    """A text/plain response is returned as a raw string body."""
    # Arrange
    respx.get("https://api.example.com/ping").mock(
        return_value=httpx.Response(200, text="pong", headers={"content-type": "text/plain"})
    )
    context = make_context()
    node = _http({"url": "https://api.example.com/ping", "method": "GET"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.data["body"] == "pong"
    assert output.data["ok"] is True


@respx.mock
async def test_4xx_returns_ok_false(public_dns) -> None:
    """A 4xx response is returned with ok=False (the node does not raise on 4xx)."""
    # Arrange
    respx.get("https://api.example.com/missing").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    context = make_context()
    node = _http({"url": "https://api.example.com/missing", "method": "GET"})

    # Act
    output = await node.execute(node_input({}, context))

    # Assert
    assert output.data["status_code"] == 404
    assert output.data["ok"] is False


async def test_ssrf_blocks_loopback_host() -> None:
    """A request to a loopback address is blocked with a RuntimeError before sending."""
    # Arrange
    context = make_context()
    node = _http({"url": "http://127.0.0.1:8000/admin", "method": "GET"})

    # Act + Assert
    with pytest.raises(RuntimeError, match="Blocked outbound request"):
        await node.execute(node_input({}, context))


def test_resolve_validated_ip_returns_vetted_address(mocker) -> None:
    """The SSRF guard returns a single validated IP to pin the connection to."""
    # Arrange
    from assemblix_api.core import ssrf

    mocker.patch(
        "assemblix_api.core.ssrf.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    )

    # Act
    pinned = ssrf.resolve_validated_ip("https://api.example.com/x", allow_internal=False)

    # Assert
    assert pinned == "93.184.216.34"


def test_resolve_validated_ip_skips_pinning_when_internal_allowed(mocker) -> None:
    """With allow_internal the guard returns None (no resolution, no pinning)."""
    # Arrange
    from assemblix_api.core import ssrf

    spy = mocker.patch("assemblix_api.core.ssrf.socket.getaddrinfo")

    # Act
    pinned = ssrf.resolve_validated_ip("http://internal.svc/x", allow_internal=True)

    # Assert
    assert pinned is None
    spy.assert_not_called()


def test_resolve_validated_ip_blocks_rebinding_mixed_records(mocker) -> None:
    """A host resolving to one public AND one private IP is blocked (rebinding guard)."""
    # Arrange
    from assemblix_api.core import ssrf

    mocker.patch(
        "assemblix_api.core.ssrf.socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("169.254.169.254", 0)),  # cloud metadata
        ],
    )

    # Act + Assert
    with pytest.raises(ssrf.SSRFValidationError, match="blocked address"):
        ssrf.resolve_validated_ip("https://rebind.example/x", allow_internal=False)
