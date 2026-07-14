"""
Notification channels REST API endpoints.

Channels are configured per project and determine where to send notifications
about technical workflow execution errors (status=FAILED).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from assemblix_api.core.auth_context import AuthContext
from assemblix_api.dependencies import (
    get_auth_context,
    get_notification_channel_service,
    get_project_service,
)
from assemblix_api.dto.requests.notification_channel import (
    NotificationChannelCreateRequest,
    NotificationChannelUpdateRequest,
)
from assemblix_api.dto.responses.notification_channel import (
    NotificationChannelResponse,
    NotificationChannelTestResponse,
)
from assemblix_api.services.notification_channel_service import (
    NotificationChannelService,
)
from assemblix_api.services.project_service import ProjectService

router = APIRouter(prefix="/notification-channels", tags=["Notification Channels"])


@router.get("/", response_model=list[NotificationChannelResponse])
async def list_notification_channels(
    project_id: UUID = Query(..., description="Project ID"),
    auth: AuthContext = Depends(get_auth_context),
    service: NotificationChannelService = Depends(get_notification_channel_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """List a project's notification channels (secrets masked)."""
    await project_service.authorize_project_access(auth, project_id)
    return await service.get_project_channels(project_id)


@router.get("/{channel_id}", response_model=NotificationChannelResponse)
async def get_notification_channel(
    channel_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: NotificationChannelService = Depends(get_notification_channel_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Get a notification channel by ID."""
    channel = await service.get_by_id(channel_id)
    await project_service.authorize_project_access(auth, channel.project_id)
    return await service.get_channel(channel_id, channel.project_id)


@router.post(
    "/",
    response_model=NotificationChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_channel(
    data: NotificationChannelCreateRequest,
    project_id: UUID = Query(..., description="Project ID"),
    auth: AuthContext = Depends(get_auth_context),
    service: NotificationChannelService = Depends(get_notification_channel_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """
    Create a notification channel for a project.

    The `data` field is encrypted before storage; secrets are masked in the response.
    """
    await project_service.authorize_project_access(auth, project_id)
    return await service.create_channel(project_id=project_id, data=data)


@router.patch("/{channel_id}", response_model=NotificationChannelResponse)
async def update_notification_channel(
    channel_id: UUID,
    data: NotificationChannelUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: NotificationChannelService = Depends(get_notification_channel_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Update a notification channel. All fields are optional."""
    channel = await service.get_by_id(channel_id)
    await project_service.authorize_project_access(auth, channel.project_id)
    return await service.update_channel(
        channel_id=channel_id, project_id=channel.project_id, data=data
    )


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_channel(
    channel_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: NotificationChannelService = Depends(get_notification_channel_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Delete a notification channel."""
    channel = await service.get_by_id(channel_id)
    await project_service.authorize_project_access(auth, channel.project_id)
    await service.delete_channel(channel_id, channel.project_id)


@router.post("/{channel_id}/test", response_model=NotificationChannelTestResponse)
async def test_notification_channel(
    channel_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    service: NotificationChannelService = Depends(get_notification_channel_service),
    project_service: ProjectService = Depends(get_project_service),
):
    """Send a test message to the channel to verify its configuration."""
    channel = await service.get_by_id(channel_id)
    await project_service.authorize_project_access(auth, channel.project_id)
    return await service.test_channel(channel_id, channel.project_id)
