"""Unit test: the default org plan is driven by the billing feature flag."""

from __future__ import annotations

import pytest

from assemblix_api.billing.plans import get_default_plan
from assemblix_api.core.settings import get_settings
from assemblix_api.enums import PlanTier


def test_default_plan_is_business_when_billing_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Self-host (billing off) provisions the unlimited BUSINESS tier."""
    # Arrange
    monkeypatch.setattr(get_settings(), "billing_enabled", False)

    # Act / Assert
    assert get_default_plan() == PlanTier.BUSINESS


def test_default_plan_is_free_when_billing_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hosted build (billing on) still starts every org on FREE."""
    # Arrange
    monkeypatch.setattr(get_settings(), "billing_enabled", True)

    # Act / Assert
    assert get_default_plan() == PlanTier.FREE
