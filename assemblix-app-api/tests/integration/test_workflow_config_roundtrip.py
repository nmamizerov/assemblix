"""Integration test: workflow-level `config` (avatar persona) round-trips via CRUD DTOs."""

from __future__ import annotations

from uuid import uuid4

from assemblix_api.database.repositories.workflow_repository import WorkflowRepository


async def _make_workflow(db_session, project_id):
    return await WorkflowRepository(db_session).create(
        project_id=project_id,
        slug=f"config-roundtrip-{uuid4()}",
        name="Config Roundtrip Workflow",
        config={},
    )


async def test_update_persists_config_avatar_and_get_returns_it(
    client, auth_user, auth_headers, db_session
) -> None:
    """PATCH workflow with `config.avatar` persists it; GET returns it back untouched."""
    # Arrange: a workflow with no avatar config
    wf = await _make_workflow(db_session, auth_user.project_id)

    avatar_cfg = {
        "provider": "anam",
        "avatarModel": "cara-4",
        "credentialId": None,
    }

    # Act: PATCH the workflow with config.avatar, then GET it back
    patch = await client.patch(
        f"/api/workflows/{wf.id}",
        headers=auth_headers,
        json={"config": {"avatar": avatar_cfg}},
    )
    assert patch.status_code == 200

    got = await client.get(f"/api/workflows/{wf.id}", headers=auth_headers)
    assert got.status_code == 200

    # Assert: config.avatar round-tripped (camelCase preserved inside the free-form dict)
    assert got.json()["config"]["avatar"]["provider"] == "anam"
    assert got.json()["config"]["avatar"]["avatarModel"] == "cara-4"
