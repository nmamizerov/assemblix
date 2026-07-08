from assemblix_api.schemas.node import AgentNodeConfig, WorkflowAvatarConfig
from assemblix_api.schemas.workflow import parse_avatar_config


def test_agent_output_type_accepts_avatar():
    cfg = AgentNodeConfig(
        provider="openai", model="gpt-4o", instructions=[], output_type="avatar"
    )
    assert cfg.output_type == "avatar"


def test_parse_avatar_config_from_workflow_config():
    parsed = parse_avatar_config(
        {"avatar": {"provider": "anam", "avatarModel": "cara-4", "credentialId": "c1"}}
    )
    assert parsed is not None
    assert parsed.provider == "anam"
    assert parsed.avatar_model == "cara-4"
    assert parsed.credential_id == "c1"


def test_parse_avatar_config_absent_returns_none():
    assert parse_avatar_config({}) is None
