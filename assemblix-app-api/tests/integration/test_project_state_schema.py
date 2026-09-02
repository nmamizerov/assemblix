"""Project state schema is readable and replaceable via the scoped /projects/state
endpoints, which an API key may call without naming its project."""

from __future__ import annotations

VARIABLES = [
    {"name": "counter", "type": "number", "defaultValue": 0},
    {"name": "lang", "type": "string", "defaultValue": "ru"},
]


async def test_state_schema_defaults_to_key_project(client, api_key) -> None:
    # Act
    resp = await client.get("/api/projects/state", headers=api_key.headers)
    # Assert
    assert resp.status_code == 200
    assert resp.json() == []


async def test_update_state_schema_round_trips(client, api_key) -> None:
    # Act
    put = await client.put(
        "/api/projects/state",
        json={"stateSchema": VARIABLES},
        headers=api_key.headers,
    )
    # Assert: the reply and a fresh read both carry the new variables.
    assert put.status_code == 200
    assert put.json() == VARIABLES
    readback = await client.get("/api/projects/state", headers=api_key.headers)
    assert readback.json() == VARIABLES


async def test_update_state_schema_replaces_previous(client, api_key) -> None:
    # Arrange
    await client.put(
        "/api/projects/state", json={"stateSchema": VARIABLES}, headers=api_key.headers
    )
    # Act
    resp = await client.put(
        "/api/projects/state",
        json={"stateSchema": [VARIABLES[1]]},
        headers=api_key.headers,
    )
    # Assert
    assert resp.json() == [VARIABLES[1]]


async def test_state_schema_rejects_foreign_project(client, api_key, auth_headers) -> None:
    # Arrange: another project in the same org the key is not scoped to.
    proj = await client.post("/api/projects/", json={"name": "Other"}, headers=auth_headers)
    other_id = proj.json()["id"]
    # Act
    resp = await client.get(f"/api/projects/state?project_id={other_id}", headers=api_key.headers)
    # Assert
    assert resp.status_code == 403


async def test_state_schema_jwt_without_project_id_returns_400(client, auth_headers) -> None:
    # Act
    resp = await client.get("/api/projects/state", headers=auth_headers)
    # Assert
    assert resp.status_code == 400
