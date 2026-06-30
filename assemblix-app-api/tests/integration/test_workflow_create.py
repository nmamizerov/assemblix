"""API test: creating a new workflow in the user's default project."""

from __future__ import annotations


async def test_create_workflow(client, auth_user, auth_headers) -> None:
    """POST /api/workflows/ with a project + name → 201 + a draft workflow."""
    # Arrange
    payload = {
        "projectId": str(auth_user.project_id),
        "name": "My Workflow",
    }

    # Act
    resp = await client.post("/api/workflows/", json=payload, headers=auth_headers)

    # Assert
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["name"] == "My Workflow"
    # A freshly created workflow is an unpublished draft.
    assert body["isPublished"] is False
    # With no graph supplied, the service seeds a default starter graph
    # (a START node, etc.) rather than leaving it empty.
    node_types = [n["type"] for n in body["nodes"]]
    assert "start" in node_types


async def test_create_workflow_requires_auth(client, auth_user) -> None:
    """Without credentials the create endpoint is rejected (401/403)."""
    # Arrange
    payload = {"projectId": str(auth_user.project_id), "name": "X"}

    # Act
    resp = await client.post("/api/workflows/", json=payload)

    # Assert
    assert resp.status_code in (401, 403)
