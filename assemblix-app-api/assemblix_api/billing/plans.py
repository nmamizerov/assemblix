# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Subscription plan and credit system configuration."""

from dataclasses import dataclass
from decimal import Decimal

from assemblix_api.enums import PlanTier


@dataclass
class CreditConfig:
    """Credit system configuration. Prices are stored in USD and converted to credits."""

    # USD value of 1 credit
    credit_value_usd: Decimal = Decimal("0.0001")

    # Margin applied to LLM costs (30% => 1.3)
    margin_multiplier: Decimal = Decimal("1.3")

    # Per-request fee in USD ($0.0001 = 1 credit by default)
    request_fee_usd: Decimal = Decimal("0.0001")

    @property
    def request_fee_credits(self) -> Decimal:
        return self.usd_to_credits(self.request_fee_usd)

    def usd_to_credits(self, amount_usd: Decimal, with_margin: bool = False) -> Decimal:
        """Convert USD to credits (margin applied for system keys), rounded to 8 decimals."""
        base = amount_usd / self.credit_value_usd
        if with_margin:
            base *= self.margin_multiplier
        return base.quantize(Decimal("0.00000001"))

    def credits_to_usd(self, credits: Decimal) -> Decimal:
        return credits * self.credit_value_usd


@dataclass(frozen=True)
class PlanConfig:
    """Subscription plan configuration (max_agents=None means unlimited)."""

    name: str
    price_rub: int
    max_agents: int | None  # None = unlimited
    credits_per_month: int
    can_use_own_keys: bool
    has_project_variables: bool
    support_level: str
    rpm_limit: int  # Requests per minute


PLAN_CONFIGS: dict[PlanTier, PlanConfig] = {
    PlanTier.FREE: PlanConfig(
        name="Free",
        price_rub=0,
        max_agents=1,
        credits_per_month=1000,
        can_use_own_keys=False,  # system keys only
        has_project_variables=False,
        support_level="community",
        rpm_limit=10,
    ),
    PlanTier.STARTER: PlanConfig(
        name="Starter",
        price_rub=490,
        max_agents=5,
        credits_per_month=5000,
        can_use_own_keys=True,
        has_project_variables=True,
        support_level="email_24h",
        rpm_limit=30,
    ),
    PlanTier.PRO: PlanConfig(
        name="Pro",
        price_rub=1990,
        max_agents=None,
        credits_per_month=20000,
        can_use_own_keys=True,
        has_project_variables=True,
        support_level="email_24h",
        rpm_limit=60,
    ),
    PlanTier.BUSINESS: PlanConfig(
        name="Business",
        price_rub=4990,
        max_agents=None,
        credits_per_month=100000,
        can_use_own_keys=True,
        has_project_variables=True,
        support_level="priority_4h_slack",
        rpm_limit=150,
    ),
}


def _get_credit_config_from_settings() -> CreditConfig:
    """Build CreditConfig from app settings, falling back to defaults if unavailable."""
    try:
        from assemblix_api.core.settings import get_settings

        settings = get_settings()

        return CreditConfig(
            credit_value_usd=Decimal(str(settings.credit_value_usd)),
            margin_multiplier=Decimal(str(1 + settings.credit_margin_percent / 100)),
            request_fee_usd=Decimal(str(settings.request_fee_usd)),
        )
    except Exception:
        return CreditConfig()


credit_config = _get_credit_config_from_settings()


def get_plan_config(plan: PlanTier) -> PlanConfig:
    return PLAN_CONFIGS[plan]


def get_default_plan() -> PlanTier:
    """Plan assigned to a new organization.

    Self-host builds (billing disabled) start on the top tier so usage is
    effectively unlimited; the hosted build starts every org on FREE.
    """
    from assemblix_api.core.settings import get_settings

    return PlanTier.FREE if get_settings().billing_enabled else PlanTier.BUSINESS


@dataclass(frozen=True)
class ChatPlanConfig:
    """Subscription plan configuration for Chat widgets (None means unlimited)."""

    name: str
    price_rub: int
    max_widgets: int | None  # None = unlimited
    credits_per_month: int
    messages_per_month: int | None  # None = unlimited


CHAT_PLAN_CONFIGS: dict[PlanTier, ChatPlanConfig] = {
    PlanTier.FREE: ChatPlanConfig(
        name="Free",
        price_rub=0,
        max_widgets=1,
        credits_per_month=0,
        messages_per_month=100,
    ),
    PlanTier.STARTER: ChatPlanConfig(
        name="Starter",
        price_rub=980,
        max_widgets=5,
        credits_per_month=5000,
        messages_per_month=None,
    ),
    PlanTier.PRO: ChatPlanConfig(
        name="Pro",
        price_rub=3980,
        max_widgets=None,
        credits_per_month=20000,
        messages_per_month=None,
    ),
    PlanTier.BUSINESS: ChatPlanConfig(
        name="Business",
        price_rub=9980,
        max_widgets=None,
        credits_per_month=100000,
        messages_per_month=None,
    ),
}


def get_chat_plan_config(plan: PlanTier) -> ChatPlanConfig:
    return CHAT_PLAN_CONFIGS[plan]
