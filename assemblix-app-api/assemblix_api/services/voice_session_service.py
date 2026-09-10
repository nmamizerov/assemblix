"""Assembling everything a voice call needs, and recording what it did.

A call is not a request/response run, so this service has no FastAPI dependency
chain to hang off. It is built explicitly by the module-level functions below,
each of which owns a *short-lived* DB session: resolve, or write, then release.
A call lasts minutes and must not occupy a pooled connection for that long — so
the three moments that touch the database (setup, session opened, session closed)
are the only ones that ever hold one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from assemblix_api.billing.credit_service import CreditService
from assemblix_api.billing.plans import credit_config, get_plan_config
from assemblix_api.core.settings import get_settings
from assemblix_api.database.models.credit_transaction import CreditTransactionType
from assemblix_api.database.models.organization import Organization
from assemblix_api.database.repositories.credentials_repository import CredentialsRepository
from assemblix_api.database.repositories.credit_transaction_repository import (
    CreditTransactionRepository,
)
from assemblix_api.database.repositories.knowledge_base_repository import KnowledgeBaseRepository
from assemblix_api.database.repositories.knowledge_document_repository import (
    KnowledgeDocumentRepository,
)
from assemblix_api.database.repositories.organization_repository import OrganizationRepository
from assemblix_api.database.repositories.organization_user_repository import (
    OrganizationUserRepository,
)
from assemblix_api.database.repositories.project_repository import ProjectRepository
from assemblix_api.database.repositories.voice_agent_repository import VoiceAgentRepository
from assemblix_api.database.repositories.voice_session_repository import VoiceSessionRepository
from assemblix_api.external.voice import speech_out
from assemblix_api.external.voice.catalog.registry import (
    find_voice_model,
    has_realtime_route,
    supports_text_output,
)
from assemblix_api.external.voice.speech_out import SpeechOutput
from assemblix_api.schemas.voice_agent import VoiceAgentConfig
from assemblix_api.services.credentials_service import CredentialsService
from assemblix_api.services.knowledge_base_service import KnowledgeBaseService

logger = structlog.get_logger(__name__)

# Credit columns are Numeric(20, 8); anything finer is noise the column cannot hold.
_CREDITS_QUANTUM = Decimal("0.00000001")

# A call whose row is still "active" past this age belongs to a runtime that died
# without closing it. Counting it would let one crash hold a plan slot forever.
_ACTIVE_SESSION_CUTOFF = timedelta(hours=4)

# Where a realtime conversation connects. Deliberately NOT the chat/transcription
# base URL: a REST gateway that fronts /v1/chat/completions answers the WebSocket
# route with 404, so pointing conversations at it turns a working call into a dead
# one. Unset (the default) means talk to the provider directly.
_CONVERSATION_BASE_URL_SETTINGS = {
    "openai": "openai_realtime_base_url",
    "gemini": "gemini_live_base_url",
}


def resolve_conversation_base(provider: str) -> str | None:
    setting = _CONVERSATION_BASE_URL_SETTINGS.get(provider)
    if setting is None:
        return None
    return getattr(get_settings(), setting, None) or None


# A call ends for one of a handful of reasons. Everything else — notably a provider's
# WebSocket close frame, which is prose and can be any length — is diagnostics, and is
# logged rather than written into a column other code branches on.
_END_REASONS = frozenset({"user_hangup", "timeout", "error", "completed", "closed"})


def normalize_end_reason(reason: str) -> str:
    return reason if reason in _END_REASONS else "provider_closed"


@dataclass(frozen=True)
class VoiceSessionSetup:
    """A call's inputs, resolved once so the runtime itself touches no database."""

    instructions: str
    voice: str
    language: str
    params: dict
    provider: str
    model: str
    api_key: str
    # Configured transport base URL — the same gateway chat and transcription use.
    # None means the provider SDK's own endpoint.
    api_base: str | None
    # External synthesis target. None means the model speaks with its own voice.
    tts: SpeechOutput | None
    turn_workflow_id: str | None
    final_workflow_id: str | None
    # From the voice catalog. A conversation is billed by wall-clock rather than by
    # tokens: it is the one number both providers agree on the meaning of.
    cost_per_minute: float
    # True when the key came from the platform's own credentials (fallback), False
    # when the caller supplied their own. Margin only applies to the former — the
    # actual charging happens where this flag lands next, not here.
    uses_system_key: bool


class VoiceSessionService:
    def __init__(
        self,
        voice_agents: VoiceAgentRepository,
        projects: ProjectRepository,
        organizations: OrganizationRepository,
        knowledge_bases: KnowledgeBaseService,
        credentials: CredentialsService,
        sessions: VoiceSessionRepository,
        transactions: CreditTransactionRepository,
        credits: CreditService,
    ) -> None:
        self._voice_agents = voice_agents
        self._projects = projects
        self._organizations = organizations
        self._knowledge_bases = knowledge_bases
        self._credentials = credentials
        self._sessions = sessions
        self._transactions = transactions
        self._credits = credits

    async def build_setup(self, *, voice_agent_id: UUID, project_id: UUID) -> VoiceSessionSetup:
        """Resolve the agent's configuration into what the runtime needs.

        Raises:
            HTTPException 404: the agent does not exist in this project.
        """
        agent = await self._voice_agents.get_by_id(voice_agent_id)
        if agent is None or agent.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice agent not found for this session",
            )

        config = VoiceAgentConfig(**agent.config)

        # Resolved for its side effect: a project with no live organisation cannot
        # host a call, and failing here beats failing once audio is flowing.
        await self._organization_for_project(project_id)

        knowledge = ""
        if config.knowledge_base_ids:
            knowledge = await self._knowledge_bases.get_combined_content(
                [UUID(kb_id) for kb_id in config.knowledge_base_ids]
            )

        api_key, uses_system_key = await self._credentials.get_voice_api_key_with_fallback(
            credentials_id=UUID(config.voice.credential_id) if config.voice.credential_id else None,
            project_id=project_id,
            voice_provider=config.voice.provider,
        )

        tts = None
        if config.tts is not None:
            if not supports_text_output(config.voice.provider, config.voice.model):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Model {config.voice.model} cannot answer in text, "
                        "so an external voice cannot speak for it"
                    ),
                )
            if not has_realtime_route(config.tts.provider, config.tts.model):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Voice model {config.tts.model} has no streaming route",
                )
            tts = await speech_out.resolve(
                config.tts, project_id=project_id, credentials=self._credentials
            )

        catalog_entry = find_voice_model(config.voice.provider, config.voice.model)

        return VoiceSessionSetup(
            instructions=self._build_instructions(config, knowledge),
            voice=config.voice.voice_id or "",
            language=config.language,
            params=config.params,
            provider=config.voice.provider,
            model=config.voice.model,
            api_key=api_key,
            api_base=resolve_conversation_base(config.voice.provider),
            tts=tts,
            turn_workflow_id=config.turn_workflow_id,
            final_workflow_id=config.final_workflow_id,
            cost_per_minute=(catalog_entry.cost_per_minute or 0.0) if catalog_entry else 0.0,
            uses_system_key=uses_system_key,
        )

    async def open_session(
        self,
        *,
        voice_agent_id: UUID,
        project_id: UUID,
        is_debug: bool = True,
        client_id: str | None = None,
    ) -> UUID:
        """Create the call's row before any audio flows.

        It exists first because the analysis hooks stamp their executions with its
        id — a hook fired mid-call has nothing to point at otherwise.

        Raises:
            HTTPException 402: the balance cannot cover even a minute of the call.
            HTTPException 429: the plan's concurrent-call ceiling is already reached.
        """
        if get_settings().billing_enabled:
            organization = await self._organization_for_project(project_id)
            # One minute of platform fee is the floor to start a call. Reserving the
            # worst case instead (the whole session cap at provider prices) would
            # exceed an entire Free monthly grant and forbid Free calls outright.
            # check_balance also rolls the monthly grant forward first, which is the
            # only thing on the voice path that does.
            await self._credits.check_balance(
                organization.id, credit_config.voice_platform_fee_credits(Decimal(1))
            )

            ceiling = get_plan_config(organization.plan).concurrent_calls
            live = await self._sessions.count_active_by_organization(
                organization.id, cutoff=datetime.now(UTC) - _ACTIVE_SESSION_CUTOFF
            )
            if live >= ceiling:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Concurrent call limit reached for this plan: {ceiling}.",
                )

        session = await self._sessions.create(
            voice_agent_id=voice_agent_id,
            project_id=project_id,
            status="active",
            is_debug=is_debug,
            client_id=client_id,
        )
        return session.id

    async def close_session(
        self,
        *,
        voice_session_id: UUID,
        transcript: list[dict],
        duration_sec: float,
        end_reason: str,
        input_tokens: int,
        output_tokens: int,
        cost_per_minute: float,
        uses_system_key: bool,
        tts_cost_usd: Decimal = Decimal(0),
        tts_uses_system_key: bool = False,
    ) -> None:
        """Write everything the call produced, and bill it, in one go."""
        session = await self._sessions.get_by_id(voice_session_id)
        if session is None:
            return

        reason = normalize_end_reason(end_reason)
        if reason != end_reason:
            # The raw text is a provider's close frame — useful to read once, not to
            # store in a status column that code branches on.
            logger.info(
                "voice.session.closed_by_provider",
                voice_session_id=str(voice_session_id),
                detail=end_reason,
            )

        fee_credits, margin_credits = compute_session_credits(
            duration_sec,
            cost_per_minute,
            uses_system_key=uses_system_key,
            tts_cost_usd=tts_cost_usd,
            tts_uses_system_key=tts_uses_system_key,
        )
        credits = fee_credits + margin_credits

        # What the minutes cost at the provider. On a system key that is our cost and is
        # already priced into the margin credits; on the caller's own key it is what they
        # paid directly, and the only place that figure is ever recorded.
        minutes = Decimal(str(duration_sec)) / Decimal(60)
        provider_cost_usd = Decimal(0)
        own_key_cost_usd = Decimal(0)
        for spend, on_system_key in (
            (minutes * Decimal(str(cost_per_minute)), uses_system_key),
            (tts_cost_usd, tts_uses_system_key),
        ):
            if on_system_key:
                provider_cost_usd += spend
            else:
                own_key_cost_usd += spend

        await self._sessions.update(
            session,
            status="failed" if reason == "error" else "completed",
            ended_at=datetime.now(UTC),
            duration_sec=duration_sec,
            transcript=transcript,
            total_credits=credits,
            own_key_cost_usd=own_key_cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            end_reason=reason,
        )

        agent = await self._voice_agents.get_by_id(session.voice_agent_id)
        if agent is not None:
            await self._voice_agents.update(
                agent,
                session_count=agent.session_count + 1,
                total_credits=agent.total_credits + credits,
                own_key_cost_usd=agent.own_key_cost_usd + own_key_cost_usd,
            )

        await self._charge(
            project_id=session.project_id,
            voice_session_id=voice_session_id,
            fee_credits=fee_credits,
            margin_credits=margin_credits,
            provider_cost_usd=provider_cost_usd,
            uses_system_key=uses_system_key,
        )

    async def _charge(
        self,
        *,
        project_id: UUID,
        voice_session_id: UUID,
        fee_credits: Decimal,
        margin_credits: Decimal,
        provider_cost_usd: Decimal,
        uses_system_key: bool,
    ) -> None:
        """Deduct a finished call from the organisation's balance and itemize it.

        Both parts leave the balance in one atomic deduction, so a call can never be
        half-charged. Minutes already spent cannot be un-spent, so a balance too thin
        to cover them is drained to zero rather than left untouched: the account is
        then below the floor `open_session` gates on, which is what bounds an
        overdrawn org to a single free call. The unpaid remainder is recorded.
        """
        if not get_settings().billing_enabled:
            return

        total = fee_credits + margin_credits
        if total <= 0:
            return

        organization = await self._organization_for_project(project_id)
        charged = await self._organizations.deduct_credits_up_to(organization.id, total)
        shortfall = total - charged
        if shortfall > 0:
            logger.warning(
                "voice.session.insufficient_credits",
                voice_session_id=str(voice_session_id),
                organization_id=str(organization.id),
                required=str(total),
                charged=str(charged),
                shortfall=str(shortfall),
            )
        if charged <= 0:
            return

        # What was actually taken pays the platform fee first; only what is left over
        # buys down the provider margin.
        charged_fee = min(fee_credits, charged)
        charged_margin = charged - charged_fee

        meta = {
            "voice_session_id": str(voice_session_id),
            "uses_system_key": uses_system_key,
            "shortfall_credits": float(shortfall),
            # Stamped per row so a historical charge stays re-derivable after the
            # config moves, exactly as execution rows do.
            "credit_value_usd": float(credit_config.credit_value_usd),
            "margin_multiplier": float(credit_config.margin_multiplier),
        }
        if charged_fee > 0:
            await self._transactions.create(
                organization_id=organization.id,
                amount_credits=-charged_fee,
                amount_usd=-credit_config.credits_to_usd(charged_fee),
                type=CreditTransactionType.REQUEST_FEE,
                description=f"Platform fee for voice session {voice_session_id}",
                meta=meta,
            )
        if charged_margin > 0:
            # amount_usd is what we paid the provider, never the margined price we
            # charged for it — the credit column already carries that. Same meaning
            # as on execution rows, so summing the column answers "what did the
            # providers cost us?" across both.
            charged_provider_usd = (
                provider_cost_usd * charged_margin / margin_credits
                if margin_credits > 0
                else Decimal(0)
            )
            await self._transactions.create(
                organization_id=organization.id,
                amount_credits=-charged_margin,
                amount_usd=-charged_provider_usd,
                type=CreditTransactionType.VOICE_USAGE,
                description=f"Conversation usage (system keys) for voice session {voice_session_id}",
                meta=meta,
            )

    async def _organization_for_project(self, project_id: UUID) -> Organization:
        """Resolve a project to the organisation whose balance and plan govern it."""
        project = await self._projects.get_by_id(project_id)
        organization = (
            await self._organizations.get_by_id(project.organization_id) if project else None
        )
        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found for this session",
            )
        return organization

    @staticmethod
    def _build_instructions(config: VoiceAgentConfig, knowledge: str) -> str:
        """Knowledge bases are inlined once, at session start — no retrieval mid-call."""
        parts = [instruction.content for instruction in config.instructions]
        if knowledge:
            parts.append(f"---\nБаза знаний:\n{knowledge}\n---")
        if config.first_message:
            parts.append(f"Начни разговор с фразы: {config.first_message}")
        return "\n\n".join(parts)


def compute_session_credits(
    duration_sec: float,
    cost_per_minute: float,
    *,
    uses_system_key: bool,
    tts_cost_usd: Decimal = Decimal(0),
    tts_uses_system_key: bool = False,
) -> tuple[Decimal, Decimal]:
    """Return (platform_fee_credits, provider_margin_credits) for a finished call.

    The platform fee is charged on every conversation. Margin is the sum of two
    independent terms: the conversation minutes and the speech synthesized for it.
    The two system-key flags are independent because the two keys are — a call can
    run the model on our key and the voice on the caller's, or the reverse.
    """
    minutes = Decimal(str(duration_sec)) / Decimal(60)
    fee = credit_config.voice_platform_fee_credits(minutes)
    provider_usd = Decimal(0)
    if uses_system_key:
        provider_usd += minutes * Decimal(str(cost_per_minute))
    if tts_uses_system_key:
        provider_usd += tts_cost_usd
    margin = credit_config.usd_to_credits(provider_usd, with_margin=True)
    return fee.quantize(_CREDITS_QUANTUM), margin.quantize(_CREDITS_QUANTUM)


@asynccontextmanager
async def _voice_session_service() -> AsyncIterator[VoiceSessionService]:
    """Composition root for the non-request path: open a DB session, act, release."""
    from assemblix_api.database import get_async_session

    async for session in get_async_session():
        yield _build_service(session)
        await session.commit()
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No database session available",
    )


def _build_service(session: AsyncSession) -> VoiceSessionService:
    return VoiceSessionService(
        VoiceAgentRepository(session),
        ProjectRepository(session),
        OrganizationRepository(session),
        KnowledgeBaseService(
            KnowledgeBaseRepository(session), KnowledgeDocumentRepository(session)
        ),
        CredentialsService(CredentialsRepository(session), OrganizationUserRepository(session)),
        VoiceSessionRepository(session),
        CreditTransactionRepository(session),
        CreditService(OrganizationRepository(session), CreditTransactionRepository(session)),
    )


async def load_voice_session_setup(*, voice_agent_id: UUID, project_id: UUID) -> VoiceSessionSetup:
    async with _voice_session_service() as service:
        return await service.build_setup(voice_agent_id=voice_agent_id, project_id=project_id)


async def open_voice_session(
    *,
    voice_agent_id: UUID,
    project_id: UUID,
    is_debug: bool = True,
    client_id: str | None = None,
) -> UUID:
    async with _voice_session_service() as service:
        return await service.open_session(
            voice_agent_id=voice_agent_id,
            project_id=project_id,
            is_debug=is_debug,
            client_id=client_id,
        )


async def close_voice_session(
    *,
    voice_session_id: UUID,
    transcript: list[dict],
    duration_sec: float,
    end_reason: str,
    input_tokens: int,
    output_tokens: int,
    cost_per_minute: float,
    uses_system_key: bool,
    tts_cost_usd: Decimal = Decimal(0),
    tts_uses_system_key: bool = False,
) -> None:
    async with _voice_session_service() as service:
        await service.close_session(
            voice_session_id=voice_session_id,
            transcript=transcript,
            duration_sec=duration_sec,
            end_reason=end_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_per_minute=cost_per_minute,
            uses_system_key=uses_system_key,
            tts_cost_usd=tts_cost_usd,
            tts_uses_system_key=tts_uses_system_key,
        )
