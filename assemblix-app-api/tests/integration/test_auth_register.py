"""API test: user registration returns an access token immediately."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.database.engine import get_async_engine
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.enums import PlanTier


async def test_register_returns_token(client) -> None:
    """POST /api/auth/register with a simple email/password/name → 201 + token."""
    # Arrange
    payload = {
        "email": "alice@example.com",
        "password": "pass1234",
        "fullName": "Alice",
    }

    # Act
    resp = await client.post("/api/auth/register", json=payload)

    # Assert
    assert resp.status_code == 201
    body = resp.json()
    # Token is issued right away (camelCase on the wire).
    assert body["accessToken"]
    assert body["tokenType"] == "bearer"
    # Registration also provisions a personal org + default project.
    assert body["organizationId"]
    assert body["projectId"]


async def test_register_provisions_business_plan_on_self_host(api_client) -> None:
    """Self-host (billing disabled) → the personal org is created on the BUSINESS plan."""
    # Arrange / Act
    resp = await api_client.post(
        "/api/auth/register",
        json={"email": "selfhost@example.com", "password": "pass1234"},
    )
    assert resp.status_code == 201
    org_id = resp.json()["organizationId"]

    # Assert — the org lands on the unlimited BUSINESS tier for both plan and chat_plan.
    async with AsyncSession(get_async_engine()) as session:
        org = await OrganizationRepository(session).get_by_id(uuid.UUID(org_id))
        assert org.plan == PlanTier.BUSINESS
        assert org.chat_plan == PlanTier.BUSINESS


async def test_register_reports_business_plan_via_billing_api(api_client) -> None:
    """With billing disabled, a freshly registered user sees BUSINESS via the API the
    frontend reads (GET /api/billing/plan) — not FREE."""
    # Arrange — register a new user (self-host profile: BILLING_ENABLED=false).
    reg = await api_client.post(
        "/api/auth/register",
        json={"email": "newbie@example.com", "password": "pass1234"},
    )
    assert reg.status_code == 201
    jwt_headers = {"Authorization": f"Bearer {reg.json()['accessToken']}"}

    # Act — read the current plan the way the UI does.
    resp = await api_client.get("/api/billing/plan", headers=jwt_headers)

    # Assert — BUSINESS tier with unlimited agents (no FREE caps).
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == PlanTier.BUSINESS.value
    assert body["name"] == "Business"
    assert body["maxAgents"] is None
