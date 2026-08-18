# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""
Paddle Billing payment provider (Merchant of Record)

Paddle manages subscriptions, taxes, and compliance.
Backend creates a transaction → gets checkout.url → frontend opens in popup.
Paddle sends webhooks for subscription lifecycle events.
"""

import hashlib
import hmac

import httpx
import structlog

from assemblix_api.core.settings import get_settings

from .base_provider import BasePaymentProvider, PaymentInitResult

logger = structlog.get_logger(__name__).bind(provider="paddle")


class PaddleProvider(BasePaymentProvider):
    """
    Paddle Billing provider

    init_payment: Creates a Paddle transaction → returns checkout.url
    verify_notification: HMAC-SHA256 verification of Paddle-Signature header
    parse_notification: Maps Paddle webhook events to internal PaymentStatus.
        Recurring billing is handled automatically by Paddle via webhooks.
    """

    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
        environment: str = "production",
    ):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = (
            "https://sandbox-api.paddle.com"
            if environment == "sandbox"
            else "https://api.paddle.com"
        )

    @staticmethod
    def price_for_plan(plan_code: str) -> str:
        """Paddle price id for a subscription plan, or "" when none is configured."""
        settings = get_settings()
        return {
            "pro": settings.paddle_price_pro,
            "business": settings.paddle_price_business,
        }.get(plan_code, "")

    @staticmethod
    def price_for_pack(pack_code: str) -> str:
        """Paddle price id for a credit pack, or "" when none is configured."""
        settings = get_settings()
        return {
            "s": settings.paddle_price_pack_s,
            "m": settings.paddle_price_pack_m,
            "l": settings.paddle_price_pack_l,
        }.get(pack_code.lower(), "")

    def supports_credit_pack(self, pack_code: str) -> bool:
        """A pack is sellable only once its Paddle price id exists in the dashboard."""
        return bool(self.price_for_pack(pack_code))

    async def init_payment(
        self,
        order_id: str,
        amount: int,
        description: str,
        user_email: str,
        is_recurrent: bool = False,
        receipt: dict | None = None,
    ) -> PaymentInitResult:
        """
        Create a Paddle transaction and return checkout URL.

        amount is ignored — price is determined by price_id in Paddle Dashboard.
        The receipt carries the payment kind plus what identifies the thing bought:
        ``target_plan`` for a subscription, ``pack_code`` for a credit pack.
        """
        receipt = receipt or {}

        # Extract what is being bought from the receipt
        target_plan = receipt.get("target_plan")
        pack_code = receipt.get("pack_code")
        organization_id = receipt.get("organization_id")
        # A pack carries no plan, so the kind is what selects the price map. Older
        # receipts predate the field; a pack_code identifies them just as well.
        kind = receipt.get("kind") or ("credit_pack" if pack_code else "subscription")

        if kind == "credit_pack":
            price_id = self.price_for_pack(pack_code) if pack_code else ""
            if not price_id:
                return PaymentInitResult(
                    success=False,
                    error_message=f"No Paddle price configured for credit pack: {pack_code}",
                )
        else:
            price_id = self.price_for_plan(target_plan) if target_plan else ""
            if not price_id:
                return PaymentInitResult(
                    success=False,
                    error_message=f"No Paddle price configured for plan: {target_plan}",
                )

        # Create transaction via Paddle API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/transactions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "items": [{"price_id": price_id, "quantity": 1}],
                        "customer": {"email": user_email},
                        "custom_data": {
                            "order_id": order_id,
                            "organization_id": organization_id,
                            "target_plan": target_plan,
                            "pack_code": pack_code,
                        },
                        "collection_mode": "automatic",
                    },
                )

            data = response.json()

            if response.status_code in (200, 201):
                txn = data.get("data", {})
                checkout_url = txn.get("checkout", {}).get("url", "")
                txn_id = txn.get("id", "")

                logger.info(
                    "payment_provider.transaction.created",
                    transaction_id=txn_id,
                    checkout_url=checkout_url,
                )

                return PaymentInitResult(
                    success=True,
                    payment_id=txn_id,
                    payment_url=checkout_url,
                    status="init",
                )
            else:
                error = data.get("error", {})
                error_msg = error.get("detail", str(data))
                logger.error(
                    "payment_provider.transaction.creation_failed",
                    error=error_msg,
                    status_code=response.status_code,
                )
                return PaymentInitResult(
                    success=False,
                    error_message=error_msg,
                )

        except httpx.RequestError as e:
            logger.exception("payment_provider.request.failed", error=str(e))
            return PaymentInitResult(
                success=False,
                error_message=f"Paddle API request failed: {str(e)}",
            )

    def verify_notification(self, payload: dict) -> bool:
        """
        Verify Paddle webhook signature (HMAC-SHA256).

        Paddle-Signature header format: ts=1234567890;h1=abcdef...
        Signed payload: "{ts}:{raw_body}"
        """
        raw_body = payload.get("_raw_body", "")
        signature_header = payload.get("_paddle_signature", "")

        if not raw_body or not signature_header:
            logger.warning("payment_provider.webhook.missing_signature")
            return False

        # Parse "ts=123456;h1=abcdef..."
        parts = {}
        for part in signature_header.split(";"):
            key, _, value = part.partition("=")
            if key and value:
                parts[key.strip()] = value.strip()

        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")

        if not ts or not h1:
            logger.warning(
                "payment_provider.webhook.invalid_signature_format",
                signature_header=signature_header,
            )
            return False

        signed_payload = f"{ts}:{raw_body}"
        computed = hmac.new(
            self.webhook_secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed, h1)

    def parse_notification(self, payload: dict) -> dict:
        """
        Parse Paddle webhook event into format compatible with PaymentService.

        Maps Paddle event types to internal PaymentStatus values.
        """
        event_type = payload.get("event_type", "")
        data = payload.get("data", {})
        custom_data = data.get("custom_data", {})

        # Map Paddle event → internal status
        status_map = {
            "transaction.paid": "confirmed",
            "transaction.completed": "confirmed",
            "transaction.canceled": "canceled",
            "transaction.past_due": "rejected",
            "subscription.canceled": "canceled",
        }

        mapped_status = status_map.get(event_type, "")
        if not mapped_status:
            logger.info("payment_provider.webhook.unhandled_event", event_type=event_type)
            mapped_status = "init"

        # Extract amount from transaction details
        totals = data.get("details", {}).get("totals", {})
        amount = totals.get("total") if totals else None

        return {
            "payment_id": data.get("id", ""),
            "status": mapped_status,
            "subscription_id": data.get("subscription_id"),
            "order_id": custom_data.get("order_id", ""),
            "amount": amount,
            "success": event_type in ("transaction.paid", "transaction.completed"),
        }
