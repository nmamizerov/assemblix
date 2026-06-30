# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""Payment provider factory."""

from assemblix_api.core.settings import get_settings

from .base_provider import BasePaymentProvider
from .paddle_provider import PaddleProvider


class PaymentProviderFactory:
    """Selects the payment provider based on the PAYMENT_PROVIDER setting."""

    @staticmethod
    def create() -> BasePaymentProvider:
        settings = get_settings()

        if settings.payment_provider == "paddle":
            return PaddleProvider(
                api_key=settings.paddle_api_key,
                webhook_secret=settings.paddle_webhook_secret,
                environment=settings.paddle_environment,
            )

        raise ValueError(
            f"Unknown payment provider: {settings.payment_provider}. "
            "Supported providers: paddle"
        )
