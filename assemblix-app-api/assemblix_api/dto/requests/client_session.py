"""
Request DTOs for client sessions
"""

from datetime import datetime

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class UpdateClientSessionMetadataRequest(DTOModel):
    metadata: dict = Field(
        description="Metadata key-value pairs to merge into the existing client session metadata. Existing keys are overwritten, new keys are added"
    )


class ClientSessionFilters(DTOModel):
    include_debug: bool = Field(
        default=False,
        description="If true, include debug sessions in the results. Defaults to false to exclude them",
    )
    date_from: datetime | None = Field(
        default=None,
        description="Include only client sessions with last activity at or after this datetime (inclusive, ISO 8601)",
    )
    date_to: datetime | None = Field(
        default=None,
        description="Include only client sessions with last activity at or before this datetime (inclusive, ISO 8601)",
    )
    active_only: bool = Field(
        default=False,
        description="If true, return only active client sessions (sessions that have not expired or been closed)",
    )
