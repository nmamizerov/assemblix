"""project_id is implicit for API keys: the three endpoints that used to require it
(workflows list/create, executions list) now default to the key's scoped project."""

from __future__ import annotations


async def test_list_workflows_defaults_to_key_project(client, api_key) -> None:
    # Arrange: api_key is scoped to its own project; send NO project_id.
    # Act
    resp = await client.get("/api/workflows/", headers=api_key.headers)
    # Assert
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_create_workflow_defaults_to_key_project(client, api_key) -> None:
    # Arrange: body carries no projectId.
    # Act
    resp = await client.post("/api/workflows/", json={"name": "WF"}, headers=api_key.headers)
    # Assert: created (defaulting worked) and readable back under the key's scope,
    # which proves it landed in the key's project (a foreign one would 403 by id).
    assert resp.status_code == 201
    workflow_id = resp.json()["id"]
    readback = await client.get(f"/api/workflows/{workflow_id}", headers=api_key.headers)
    assert readback.status_code == 200


async def test_list_executions_defaults_to_key_project(client, api_key) -> None:
    # Act
    resp = await client.get("/api/executions/", headers=api_key.headers)
    # Assert
    assert resp.status_code == 200
    assert "data" in resp.json()


async def test_create_workflow_rejects_explicit_foreign_project(
    client, api_key, auth_headers
) -> None:
    # Arrange: a second project in the same org that the key is NOT scoped to.
    proj = await client.post("/api/projects/", json={"name": "Other"}, headers=auth_headers)
    other_project_id = proj.json()["id"]
    # Act: the key tries to create in the foreign project by passing it explicitly.
    resp = await client.post(
        "/api/workflows/",
        json={"name": "WF", "projectId": other_project_id},
        headers=api_key.headers,
    )
    # Assert: explicit foreign project is still rejected (not laundered via the key).
    assert resp.status_code == 403


async def test_list_workflows_jwt_without_project_id_returns_400(client, auth_headers) -> None:
    # Arrange: JWT caller carries no scoped project, so project_id is still required.
    # Act
    resp = await client.get("/api/workflows/", headers=auth_headers)
    # Assert
    assert resp.status_code == 400


async def test_list_executions_jwt_without_project_id_returns_400(client, auth_headers) -> None:
    # Act
    resp = await client.get("/api/executions/", headers=auth_headers)
    # Assert
    assert resp.status_code == 400


async def test_create_workflow_jwt_without_project_id_returns_400(client, auth_headers) -> None:
    # Act
    resp = await client.post("/api/workflows/", json={"name": "WF"}, headers=auth_headers)
    # Assert
    assert resp.status_code == 400
