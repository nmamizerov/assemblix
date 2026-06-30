# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""
Base class for payment providers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentInitResult:
    success: bool
    payment_id: str | None = None
    payment_url: str | None = None
    status: str | None = None
    error_message: str | None = None


class BasePaymentProvider(ABC):
    """
    Strategy interface for payment providers. Each provider implements
    payment initialization and webhook handling.
    """

    @abstractmethod
    async def init_payment(
        self,
        order_id: str,
        amount: int,  # In kopecks
        description: str,
        user_email: str,
        is_recurrent: bool = False,
        receipt: dict | None = None,
    ) -> PaymentInitResult:
        """Initialize a payment."""
        pass

    @abstractmethod
    def verify_notification(self, payload: dict) -> bool:
        """Verify the webhook signature."""
        pass

    @abstractmethod
    def parse_notification(self, payload: dict) -> dict:
        """Parse webhook data into {payment_id, status, order_id}."""
        pass
