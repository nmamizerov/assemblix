"""
User credentials model for LLM providers
"""

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project


class CredentialsType(str, Enum):
    OPENAI_TOKEN = "openai_token"
    ANTHROPIC_TOKEN = "anthropic_token"
    GEMINI_TOKEN = "gemini_token"
    DEEPSEEK_TOKEN = "deepseek_token"
    ELEVENLABS_TOKEN = "elevenlabs_token"
    ANAM_TOKEN = "anam_token"
    YANDEX_SPEECHKIT_TOKEN = "yandex_speechkit_token"


class Credentials(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "credentials"

    # Ownership
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provider
    type: Mapped[CredentialsType] = mapped_column(nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100), default=None)

    # Value
    value: Mapped[str] = mapped_column(String(1255), nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="credentials")
