# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""
Payment response DTOs
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.dto.base import DTOModel, PaginatedResponse


class SubscriptionPaymentResponse(DTOModel):
    payment_id: UUID = Field(..., description="Payment ID")
    payment_url: str = Field(..., description="Checkout URL")
    amount: int = Field(..., description="Amount in kopecks")
    amount_rub: int = Field(..., description="Amount in rubles")
    description: str = Field(..., description="Payment description")
    target_plan: str = Field(..., description="Target plan tier")
    expires_at: datetime | None = Field(
        None,
        description="When the checkout link expires (usually 15 minutes)",
    )


class PaymentStatusResponse(DTOModel):
    payment_id: UUID = Field(..., description="Payment ID")
    status: str = Field(..., description="Payment status")
    amount: int = Field(..., description="Amount in kopecks")
    description: str = Field(..., description="Payment description")
    target_plan: str = Field(..., description="Target plan tier")
    payment_url: str | None = Field(None, description="Checkout URL")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class PaymentHistoryItem(DTOModel):
    payment_id: UUID = Field(..., description="Payment ID")
    status: str = Field(..., description="Payment status")
    amount: int = Field(..., description="Amount in kopecks")
    amount_rub: int = Field(..., description="Amount in rubles")
    description: str = Field(..., description="Payment description")
    target_plan: str = Field(..., description="Target plan tier")
    is_recurrent: bool = Field(..., description="Recurrent payment")
    created_at: datetime = Field(..., description="Created at")


class PaymentHistoryResponse(PaginatedResponse[PaymentHistoryItem]):
    pass
