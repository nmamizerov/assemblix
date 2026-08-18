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

    credit_value_usd: Decimal = Decimal("0.0001")
    margin_multiplier: Decimal = Decimal("1.1")
    request_fee_usd: Decimal = Decimal("0.0001")
    voice_platform_fee_usd_per_minute: Decimal = Decimal("0.02")

    @property
    def request_fee_credits(self) -> Decimal:
        return self.usd_to_credits(self.request_fee_usd)

    def voice_platform_fee_credits(self, minutes: Decimal) -> Decimal:
        return self.usd_to_credits(minutes * self.voice_platform_fee_usd_per_minute)

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
    """Subscription plan configuration."""

    name: str
    price_usd_cents: int
    credits_per_month: int
    support_level: str
    rpm_limit: int
    concurrent_calls: int


PLAN_CONFIGS: dict[PlanTier, PlanConfig] = {
    PlanTier.FREE: PlanConfig(
        name="Free",
        price_usd_cents=0,
        credits_per_month=5_000,
        support_level="community",
        rpm_limit=10,
        concurrent_calls=1,
    ),
    PlanTier.PRO: PlanConfig(
        name="Pro",
        price_usd_cents=1900,
        credits_per_month=60_000,
        support_level="email_24h",
        rpm_limit=60,
        concurrent_calls=5,
    ),
    PlanTier.BUSINESS: PlanConfig(
        name="Business",
        price_usd_cents=4900,
        credits_per_month=200_000,
        support_level="priority_4h_slack",
        rpm_limit=150,
        concurrent_calls=15,
    ),
}


@dataclass(frozen=True)
class CreditPack:
    """One-off credit purchase, available on any plan."""

    code: str
    price_usd_cents: int
    credits: int


CREDIT_PACKS: dict[str, CreditPack] = {
    "s": CreditPack(code="s", price_usd_cents=1000, credits=25_000),
    "m": CreditPack(code="m", price_usd_cents=2500, credits=70_000),
    "l": CreditPack(code="l", price_usd_cents=5000, credits=160_000),
}


def get_credit_pack(code: str) -> CreditPack:
    pack = CREDIT_PACKS.get(code.lower())
    if pack is None:
        raise ValueError(f"Unknown credit pack: {code}")
    return pack


def _get_credit_config_from_settings() -> CreditConfig:
    """Build CreditConfig from app settings, falling back to defaults if unavailable."""
    try:
        from assemblix_api.core.settings import get_settings

        settings = get_settings()

        return CreditConfig(
            credit_value_usd=Decimal(str(settings.credit_value_usd)),
            margin_multiplier=Decimal(str(1 + settings.credit_margin_percent / 100)),
            request_fee_usd=Decimal(str(settings.request_fee_usd)),
            voice_platform_fee_usd_per_minute=Decimal(
                str(settings.voice_platform_fee_usd_per_minute)
            ),
        )
    except Exception:
        return CreditConfig()


credit_config = _get_credit_config_from_settings()


def get_plan_config(plan: PlanTier) -> PlanConfig:
    return PLAN_CONFIGS[plan]


def get_default_plan() -> PlanTier:
    """Plan assigned to a new organization.

    Self-host builds (billing disabled) start on the top tier so usage is
    effectively unlimited; the hosted build starts every org on FREE. With no
    build-time gates left, BUSINESS here only selects sane RPM/concurrency
    numbers should someone enable billing later.
    """
    from assemblix_api.core.settings import get_settings

    return PlanTier.FREE if get_settings().billing_enabled else PlanTier.BUSINESS
