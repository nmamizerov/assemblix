# /nodes/http_request_node.py

import json
from datetime import datetime
from typing import Any

import httpcore
import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from assemblix_api.core.node_registry import register_node
from assemblix_api.core.settings import get_settings
from assemblix_api.core.ssrf import SSRFValidationError, resolve_validated_ip
from assemblix_api.enums import NodeType, TransienceClass
from assemblix_api.execution.error_taxonomy import classify_error
from assemblix_api.schemas.execution import NodeInput, NodeOutput
from assemblix_api.schemas.node import BaseNode, HTTPRequestNodeConfig


def _is_transient_http(exc: BaseException) -> bool:
    """tenacity predicate: retry only transient failures (timeouts, connection drops,
    429/5xx) using the Phase-1 taxonomy."""
    return isinstance(exc, Exception) and classify_error(exc) is TransienceClass.TRANSIENT


class _PinnedBackend(httpcore.AsyncNetworkBackend):
    """Network backend that forces the TCP connect to a pre-validated IP literal
    instead of re-resolving the hostname. This is what closes the SSRF DNS-rebinding
    TOCTOU: the address vetted by the SSRF guard is the address actually dialed.

    It wraps the pool's real backend (delegating TLS, unix sockets, sleep) and only
    rewrites the connect target. TLS SNI / certificate verification and the HTTP Host
    header still use the original hostname (carried by the request URL), so virtual
    hosting and cert checks are unaffected.
    """

    def __init__(self, pinned_ip: str, inner: httpcore.AsyncNetworkBackend) -> None:
        self._pinned_ip = pinned_ip
        self._inner = inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._inner.connect_tcp(
            self._pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._inner.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _PinnedTransport(httpx.AsyncHTTPTransport):
    """httpx transport whose connection pool dials a pinned IP (see _PinnedBackend).

    Pinning happens below handle_async_request, so test mocks that patch the transport
    (e.g. respx) bypass it transparently — the hostname-based URL is untouched.
    """

    def __init__(self, pinned_ip: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pool._network_backend = _PinnedBackend(pinned_ip, self._pool._network_backend)


@register_node(NodeType.HTTP_REQUEST)
class HTTPRequestNode(BaseNode):
    """
    Node for executing HTTP requests.

    Features:
    - Supports GET, POST, PUT, PATCH, DELETE methods
    - CEL template evaluation in URL, headers, body, query_params
    - Query parameters for GET requests
    - JSON body for POST/PUT/PATCH requests
    - Returns status_code, body, headers, ok flag

    Output format:
        {
            "status_code": 200,
            "body": {...} or "text",
            "headers": {...},
            "ok": true/false
        }
    """

    def __init__(self, node_config: dict):
        super().__init__(node_config)
        self.typed_config = HTTPRequestNodeConfig(**node_config["config"])

    async def execute(self, node_input: NodeInput) -> NodeOutput:
        """
        Execute HTTP request.

        Process:
        1. Evaluate CEL templates in URL, headers, body, query_params
        2. Build HTTP request
        3. Execute request via httpx
        4. Parse response
        5. Return NodeOutput

        Returns:
            NodeOutput with response data and metadata
        """
        context = node_input.context
        start_time = datetime.now()

        # 1. Evaluate templates
        url = context.templates.render(self.typed_config.url, context, node_input.data)

        # SSRF protection: block requests to private/internal addresses unless the
        # self-host explicitly allowed it via HTTP_NODE_ALLOW_INTERNAL. The returned IP
        # is pinned for the actual connection to close the DNS-rebinding TOCTOU.
        try:
            pinned_ip = resolve_validated_ip(
                url, allow_internal=get_settings().http_node_allow_internal
            )
        except SSRFValidationError as e:
            raise RuntimeError(f"Blocked outbound request: {str(e)}") from e

        headers = context.templates.render_dict(self.typed_config.headers, context, node_input.data)
        query_params = context.templates.render_dict(
            self.typed_config.query_params, context, node_input.data
        )

        # 2. Prepare body (for POST/PUT/PATCH)
        body = None
        if self.typed_config.body and self.typed_config.method in [
            "POST",
            "PUT",
            "PATCH",
        ]:
            body_str = context.templates.render(self.typed_config.body, context, node_input.data)
            # Try to parse as JSON if it looks like JSON
            if body_str.strip().startswith(("{", "[")):
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    # If parsing fails, send as string
                    body = body_str
            else:
                body = body_str

        # 3. Execute HTTP request, retrying transient failures (timeouts, 429, 5xx)
        #    with exponential backoff + jitter (tenacity). 429/5xx are surfaced as an
        #    HTTPStatusError inside the attempt so the taxonomy marks them retryable; once
        #    retries are exhausted we still return the response (ok=False) — unchanged behavior.
        max_retries = self.typed_config.max_retries
        if max_retries is None:
            max_retries = get_settings().http_node_num_retries

        # Pin the connection to the validated IP (None when internal targets are allowed,
        # in which case the default resolver is used).
        transport = _PinnedTransport(pinned_ip) if pinned_ip is not None else None

        async def _do_request() -> httpx.Response:
            async with httpx.AsyncClient(
                timeout=self.typed_config.timeout,
                follow_redirects=False,
                transport=transport,
            ) as client:
                resp = await client.request(
                    method=self.typed_config.method,
                    url=url,
                    headers=headers,
                    params=query_params if self.typed_config.method == "GET" else None,
                    json=(
                        body
                        if isinstance(body, dict) and self.typed_config.method != "GET"
                        else None
                    ),
                    content=(
                        body
                        if isinstance(body, str) and self.typed_config.method != "GET"
                        else None
                    ),
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                # Raise so tenacity retries; classify_error treats 429/5xx as transient.
                resp.raise_for_status()
            return resp

        try:
            response: httpx.Response
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries + 1),
                wait=wait_exponential_jitter(),
                retry=retry_if_exception(_is_transient_http),
                reraise=True,
            ):
                with attempt:
                    response = await _do_request()

            # 4. Parse response
            response_body = self._parse_response_body(response)
            response_headers = dict(response.headers)

            # Calculate duration
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # 5. Return NodeOutput
            return NodeOutput(
                data={
                    "status_code": response.status_code,
                    "body": response_body,
                    "headers": response_headers,
                    "ok": response.status_code < 400,
                },
                metadata={
                    "url": url,
                    "method": self.typed_config.method,
                    "duration_ms": duration_ms,
                },
            )

        except httpx.HTTPStatusError as e:
            # Retries exhausted on a persistent 429/5xx — fall back to returning the
            # response with ok=False (unchanged behavior: the node never failed on status).
            response = e.response
            response_body = self._parse_response_body(response)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return NodeOutput(
                data={
                    "status_code": response.status_code,
                    "body": response_body,
                    "headers": dict(response.headers),
                    "ok": False,
                },
                metadata={
                    "url": url,
                    "method": self.typed_config.method,
                    "duration_ms": duration_ms,
                },
            )
        except (httpx.TimeoutException, httpx.RequestError):
            # Preserve the httpx exception type so the error taxonomy classifies
            # timeouts / connection drops as transient (retryable in Phase 3).
            raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error in HTTP request: {str(e)}") from e

    def _parse_response_body(self, response: httpx.Response) -> Any:
        """
        Parse response body - try JSON first, fallback to text.

        Returns:
            Parsed JSON dict/list or raw text string
        """
        content_type = response.headers.get("content-type", "")

        # Try JSON parsing if content-type suggests JSON
        if "application/json" in content_type:
            try:
                return response.json()
            except json.JSONDecodeError:
                # Fallback to text if JSON parsing fails
                return response.text

        # For other content types, return as text
        return response.text

    def validate_config(self) -> list[str]:
        """Validate node configuration"""
        errors = []

        if not self.typed_config.url:
            errors.append("URL is required")

        if self.typed_config.timeout <= 0:
            errors.append("Timeout must be positive")

        return errors

    @classmethod
    def descriptor(cls):
        """Catalog entry for the HTTP Request node.

        Properties mirror HTTPRequestNodeConfig: url, method, headers,
        body (shown only for mutating methods), query_params, timeout, max_retries.
        """
        from assemblix_api.schemas.node_descriptor import (
            NodeDescriptor,
            NodeDisplayCondition,
            NodeProperty,
            NodePropertyOption,
        )

        return NodeDescriptor(
            type="http_request",
            display_name="HTTP Request",
            description="Makes an outbound HTTP request and returns the response.",
            category="io",
            icon="Globe",
            color="node-http",
            properties=[
                NodeProperty(
                    name="url",
                    display_name="URL",
                    type="string",
                    required=True,
                    placeholder="https://api.example.com/endpoint",
                    description="Target URL. Supports CEL templates: {{state.base_url}}.",
                ),
                NodeProperty(
                    name="method",
                    display_name="Method",
                    type="options",
                    default="GET",
                    options=[
                        NodePropertyOption(value="GET", label="GET"),
                        NodePropertyOption(value="POST", label="POST"),
                        NodePropertyOption(value="PUT", label="PUT"),
                        NodePropertyOption(value="PATCH", label="PATCH"),
                        NodePropertyOption(value="DELETE", label="DELETE"),
                    ],
                ),
                NodeProperty(
                    name="headers",
                    display_name="Headers",
                    type="key_value",
                    description="HTTP headers. Values support CEL templates.",
                ),
                NodeProperty(
                    name="body",
                    display_name="Body",
                    type="text",
                    show_when=NodeDisplayCondition(field="method", values=["POST", "PUT", "PATCH"]),
                    description="Request body (JSON or plain text). Supports CEL templates.",
                ),
                NodeProperty(
                    name="query_params",
                    display_name="Query parameters",
                    type="key_value",
                    description="URL query parameters. Values support CEL templates.",
                ),
                NodeProperty(
                    name="timeout",
                    display_name="Timeout (s)",
                    type="number",
                    default=30,
                    description="Request timeout in seconds.",
                ),
                NodeProperty(
                    name="max_retries",
                    display_name="Max retries",
                    type="number",
                    default=None,
                    description="Retry count on transient errors (429/5xx/timeout). "
                    "Leave blank to use the server default.",
                ),
            ],
        )
