from datetime import datetime
from uuid import UUID

from pydantic import Field

from assemblix_api.database.models.credentials import CredentialsType
from assemblix_api.dto.base import DTOModel


class CredentialsResponse(DTOModel):
    """
    IMPORTANT: the ``value`` field is NEVER returned to the frontend for security
    reasons. Keys are used only on the backend for LLM provider calls.
    """

    id: UUID = Field(description="Unique identifier of the credential")
    type: CredentialsType = Field(
        description="Type of the credential (e.g. 'openai', 'gemini', 'gigachat')"
    )
    name: str | None = Field(default=None, description="Optional display name for the credential")
    created_at: datetime = Field(description="Timestamp when the credential was created")
    updated_at: datetime = Field(description="Timestamp when the credential was last updated")
