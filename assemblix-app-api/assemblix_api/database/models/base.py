"""
Base classes and shared mixins for models
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(
        default=uuid4,
        primary_key=True,
        nullable=False,
    )
