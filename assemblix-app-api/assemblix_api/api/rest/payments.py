# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""
Payments REST API endpoints
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

logger = structlog.get_logger(__name__)

from assemblix_api.database.models.organization import Organization
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_current_organization,
    get_current_user,
    get_payment_service,
)
from assemblix_api.dto.requests.payment import CreateSubscriptionRequest
from assemblix_api.dto.responses.payment import (
    PaymentHistoryItem,
    PaymentHistoryResponse,
    PaymentStatusResponse,
    SubscriptionPaymentResponse,
)
from assemblix_api.enums import PlanTier
from assemblix_api.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/subscribe", response_model=SubscriptionPaymentResponse)
async def create_subscription(
    request_data: CreateSubscriptionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    current_organization: Annotated[Organization, Depends(get_current_organization)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> SubscriptionPaymentResponse:
    """
    Create a subscription payment and return a checkout URL.

    Flow: the client calls this endpoint, receives a payment_url, and pays
    there; the provider then posts a webhook to /payments/notification and the
    system activates the subscription.
    """
    try:
        # Validate the plan.
        try:
            target_plan = PlanTier(request_data.target_plan.lower())
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan: {request_data.target_plan}. "
                f"Valid plans: free, starter, pro, business",
            ) from e

        payment = await payment_service.create_subscription_payment(
            organization_id=current_organization.id,
            user_email=current_user.email,
            target_plan=target_plan,
            is_recurrent=request_data.is_recurrent,
        )

        # Checkout links typically expire after 15 minutes.
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        # On success create_subscription_payment always sets payment_url
        # (otherwise it raises ValueError).
        assert payment.payment_url is not None

        return SubscriptionPaymentResponse(
            payment_id=payment.id,
            payment_url=payment.payment_url,
            amount=payment.amount,
            amount_rub=payment.amount // 100,
            description=payment.description,
            target_plan=payment.target_plan.value,
            expires_at=expires_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("payment.subscription.create_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment. Please try again later.",
        ) from e


@router.post("/notification")
async def payment_notification(
    request: Request,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> Response:
    """
    Webhook for payment-provider notifications (e.g. Paddle), fired on payment
    status changes to process the event and activate subscriptions.

    This endpoint is unauthenticated because it is called by an external
    system; security relies on signature verification.

    Returns "OK" on success.
    """
    try:
        # Read raw body (for Paddle HMAC verification) and JSON.
        raw_body = await request.body()
        payload = await request.json()

        # Attach raw data for providers that use HMAC signatures.
        payload["_raw_body"] = raw_body.decode()
        payload["_paddle_signature"] = request.headers.get("Paddle-Signature", "")

        event_type = payload.get("event_type", "unknown")
        logger.info("payment.notification.received", event_type=event_type)

        success = await payment_service.process_notification(payload)

        if success:
            return Response(content="OK", media_type="text/plain")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process notification",
            )

    except ValueError as e:
        # Invalid signature or payment not found: log details, but keep the
        # response generic (the caller is an external payment system).
        logger.warning("payment.notification.validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification",
        ) from e
    except Exception as e:
        logger.exception("payment.notification.processing_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error",
        ) from e


@router.get("/{payment_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    current_organization: Annotated[Organization, Depends(get_current_organization)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentStatusResponse:
    """
    Get the payment status, e.g. to poll after redirect from the checkout page.
    """
    payment = await payment_service.get_payment(payment_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )

    # Enforce that the payment belongs to the organization.
    if payment.organization_id != current_organization.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this payment",
        )

    return PaymentStatusResponse(
        payment_id=payment.id,
        status=payment.status.value,
        amount=payment.amount,
        description=payment.description,
        target_plan=payment.target_plan.value,
        payment_url=payment.payment_url,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


@router.get("/history", response_model=PaymentHistoryResponse)
async def get_payment_history(
    current_user: Annotated[User, Depends(get_current_user)],
    current_organization: Annotated[Organization, Depends(get_current_organization)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
) -> PaymentHistoryResponse:
    """Get the organization's paginated payment history."""
    payments, total = await payment_service.get_organization_payments(
        organization_id=current_organization.id,
        skip=skip,
        limit=limit,
    )

    page = (skip // limit) + 1

    return PaymentHistoryResponse(
        data=[
            PaymentHistoryItem(
                payment_id=p.id,
                status=p.status.value,
                amount=p.amount,
                amount_rub=p.amount // 100,
                description=p.description,
                target_plan=p.target_plan.value,
                is_recurrent=p.is_recurrent,
                created_at=p.created_at,
            )
            for p in payments
        ],
        total=total,
        page=page,
        limit=limit,
    )
