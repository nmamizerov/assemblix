# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""
Billing REST API endpoints
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from assemblix_api.billing.plans import PLAN_CONFIGS, get_plan_config
from assemblix_api.billing.service import BillingService
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.database.models.organization import Organization
from assemblix_api.database.models.user import User
from assemblix_api.dependencies import (
    get_billing_service,
    get_current_organization,
    get_current_user,
)
from assemblix_api.dto.responses.billing import (
    AllPlansResponse,
    CreditsInfo,
    CreditTransactionListResponse,
    CreditTransactionResponse,
    OrganizationUsageResponse,
    PlanInfoResponse,
)

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/usage", response_model=OrganizationUsageResponse)
async def get_organization_usage(
    current_user: User = Depends(get_current_user),
    current_organization: Organization = Depends(get_current_organization),
    billing_service: BillingService = Depends(get_billing_service),
):
    """
    Get resource usage for the current organization.

    Returns:
    - Current plan
    - Agent usage (current/limit)
    - Request usage (current/limit)
    - Available features
    - Billing period information
    """
    return await billing_service.get_organization_usage(current_organization.id)


@router.get("/plan", response_model=PlanInfoResponse)
async def get_current_plan(
    current_user: User = Depends(get_current_user),
    current_organization: Organization = Depends(get_current_organization),
):
    """
    Get the organization's current plan.

    Returns detailed plan information including:
    - Name and price
    - Limits (agents, requests)
    - Available features
    - Support level
    """
    config = get_plan_config(current_organization.plan)

    return PlanInfoResponse(
        plan=current_organization.plan.value,
        name=config.name,
        price_rub=config.price_rub,
        max_agents=config.max_agents,
        credits_per_month=config.credits_per_month,
        can_use_own_keys=config.can_use_own_keys,
        has_project_variables=config.has_project_variables,
        support_level=config.support_level,
        rpm_limit=config.rpm_limit,
    )


@router.get("/plans", response_model=AllPlansResponse)
async def get_all_plans(
    current_user: User = Depends(get_current_user),
):
    """
    List all available plans.

    Returns information about all plans for selection and comparison:
    - FREE - free plan with basic capabilities
    - PRO - plan for professionals
    - BUSINESS - business plan with maximum limits
    """
    plans = []
    for plan_tier, config in PLAN_CONFIGS.items():
        plans.append(
            PlanInfoResponse(
                plan=plan_tier.value,
                name=config.name,
                price_rub=config.price_rub,
                max_agents=config.max_agents,
                credits_per_month=config.credits_per_month,
                can_use_own_keys=config.can_use_own_keys,
                has_project_variables=config.has_project_variables,
                support_level=config.support_level,
                rpm_limit=config.rpm_limit,
            )
        )

    return AllPlansResponse(plans=plans)


@router.get("/credits", response_model=CreditsInfo)
async def get_credits_balance(
    current_user: User = Depends(get_current_user),
    current_organization: Organization = Depends(get_current_organization),
    billing_service: BillingService = Depends(get_billing_service),
):
    """
    Get the organization's credit balance.

    Returns:
    - Current credit balance
    - Balance in USD
    - Plan and limit information
    - Period dates and next reset date
    """
    balance_info = await billing_service._credit_service.get_balance(current_organization.id)
    return balance_info


@router.get("/credits/transactions", response_model=CreditTransactionListResponse)
async def get_credit_transactions(
    current_user: User = Depends(get_current_user),
    current_organization: Organization = Depends(get_current_organization),
    billing_service: BillingService = Depends(get_billing_service),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    transaction_type: str | None = Query(
        None,
        description="Filter by transaction type (plan_grant, llm_usage, request_fee, manual_topup, refund)",
    ),
    from_date: datetime | None = Query(None, description="Filter transactions from this date"),
    to_date: datetime | None = Query(None, description="Filter transactions until this date"),
) -> CreditTransactionListResponse:
    """
    Get the organization's credit transaction history.

    Query Parameters:
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records (1-1000)
    - transaction_type: Filter by transaction type
    - from_date: Period start (ISO 8601 datetime)
    - to_date: Period end (ISO 8601 datetime)

    Returns a list of transactions with:
    - ID and transaction type
    - Amounts in credits and USD
    - Description and metadata
    - Creation date
    """
    tx_type_enum = None
    if transaction_type:
        try:
            tx_type_enum = CreditTransactionType(transaction_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transaction type. Valid types: {[t.value for t in CreditTransactionType]}",
            ) from e

    transactions, total_count = await billing_service._credit_service.get_transactions(
        organization_id=current_organization.id,
        skip=skip,
        limit=limit,
        transaction_type=tx_type_enum,
        from_date=from_date,
        to_date=to_date,
    )

    page = (skip // limit) + 1

    return CreditTransactionListResponse(
        data=[CreditTransactionResponse.model_validate(tx) for tx in transactions],
        total=total_count,
        page=page,
        limit=limit,
    )
