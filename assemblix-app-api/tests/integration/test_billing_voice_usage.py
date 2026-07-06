from decimal import Decimal
from uuid import uuid4

from assemblix_api.billing.credit_service import CreditService
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)
from assemblix_api.database.repositories.execution_repository import ExecutionRepository
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.database.repositories.workflow_repository import WorkflowRepository


async def test_deduct_writes_voice_usage_row(auth_user, db_session) -> None:
    """system_voice_cost_usd → a VOICE_USAGE ledger row and a balance decrement."""
    # Arrange — top up the org's balance; execution_id must reference a real row (FK).
    org_repo = OrganizationRepository(db_session)
    tx_repo = CreditTransactionRepository(db_session)
    org = await org_repo.get_by_id(auth_user.organization_id)
    org.credits_balance = Decimal("1000000")
    await org_repo.update(org)

    workflow = await WorkflowRepository(db_session).create(
        project_id=auth_user.project_id, slug=f"voice-usage-test-{uuid4()}", name="Voice Usage Test"
    )
    execution = await ExecutionRepository(db_session).create(workflow_id=workflow.id)

    service = CreditService(org_repo, tx_repo)

    # Act
    await service.deduct_for_execution(
        organization_id=auth_user.organization_id,
        execution_id=execution.id,
        system_key_cost_usd=Decimal("0"),
        own_key_cost_usd=Decimal("0"),
        system_voice_cost_usd=Decimal("0.003"),
        own_voice_cost_usd=Decimal("0"),
    )

    # Assert
    txs, _ = await service.get_transactions(auth_user.organization_id)
    assert any(t["type"] == CreditTransactionType.VOICE_USAGE.value for t in txs)
    refreshed = await org_repo.get_by_id(auth_user.organization_id)
    assert refreshed.credits_balance < Decimal("1000000")
