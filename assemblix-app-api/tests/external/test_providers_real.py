"""Real-provider tests — EXCLUDED from the base scope.

Everything here is marked ``external`` and is skipped by the default run
(``-m "not external"`` in CI and ``make test``). Run explicitly with real keys:

    make test-external            # or: pytest -m external

These call paid third-party APIs and require credentials in the environment
(``SYSTEM_OPENAI_API_KEY``, ``SYSTEM_GEMINI_API_KEY``, ...). When a key is
missing the test skips rather than fails, so the suite stays green without keys.

This file is a template proving the gate works; add concrete provider checks here.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.external


def test_openai_key_present_then_smoke() -> None:
    """Placeholder gate: skips without a real key, runs only when one is set."""
    api_key = os.environ.get("SYSTEM_OPENAI_API_KEY")
    if not api_key:
        pytest.skip("SYSTEM_OPENAI_API_KEY not set — real-provider test skipped")
    # Real provider call goes here (no mock_llm in this layer).
    assert api_key
