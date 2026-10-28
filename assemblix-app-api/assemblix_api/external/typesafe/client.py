"""Thin async client for TypeSafe's `POST /v1/systemone` (the Jev model).

Retries rate limits (429), overload (529), 5xx and network errors with exponential
backoff + jitter; any other error status is raised immediately as `TypeSafeError`
carrying the API's `detail`.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from assemblix_api.core.settings import get_settings

_RETRY_WAIT = wait_exponential_jitter(initial=0.5, max=8)
_LONG_CONTEXT_HEADER = "TypeSafe-Danger-Zone-Long-Context"


class TypeSafeError(RuntimeError):
    """A TypeSafe request failed (non-retryable status or retries exhausted)."""


class _RetryableError(Exception):
    pass


def _detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    return str(data.get("detail", data) if isinstance(data, dict) else data)


async def system_one(
    *,
    api_key: str,
    model: str,
    state: Any,
    questions: dict[str, dict],
    long_context: bool = False,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> dict:
    """Send one System One request and return the parsed response body."""
    url = f"{get_settings().typesafe_api_base_url.rstrip('/')}/v1/systemone"
    headers = {"Authorization": f"Bearer {api_key}"}
    if long_context:
        headers[_LONG_CONTEXT_HEADER] = "true"
    body = {"model": model, "state": state, "questions": questions}

    async def _attempt() -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=body, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise _RetryableError(f"network error: {e}") from e
        if response.status_code in (429, 529) or response.status_code >= 500:
            raise _RetryableError(f"HTTP {response.status_code}: {_detail(response)}")
        return response

    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(_RetryableError),
            wait=_RETRY_WAIT,
            stop=stop_after_attempt(max_retries + 1),
            reraise=True,
        ):
            with attempt:
                response = await _attempt()
    except _RetryableError as e:
        raise TypeSafeError(f"TypeSafe request failed after retries: {e}") from e

    if response.status_code >= 400:
        raise TypeSafeError(f"TypeSafe HTTP {response.status_code}: {_detail(response)}")
    return response.json()
