from assemblix_api.external.avatar.avatar_catalog import (
    AVATAR_PROVIDER_LABELS,
    AVATAR_WORKFLOW_PROVIDERS,
    find_avatar_model,
    list_avatar_models,
    list_avatar_providers,
)


def test_anam_is_registered():
    assert AVATAR_PROVIDER_LABELS["anam"] == "Anam"


def test_list_providers_returns_anam():
    assert "anam" in list_avatar_providers()


def test_list_and_find_model():
    models = list_avatar_models("anam")
    assert models, "anam.json must declare at least one avatar model"
    first = models[0]
    assert find_avatar_model("anam", first.id) == first
    assert first.avatar_model  # non-empty provider avatar model id


def test_unknown_provider_is_empty():
    assert list_avatar_models("nope") == []
    assert find_avatar_model("nope", "x") is None


def test_bithuman_is_registered_for_voice_agents_only():
    assert AVATAR_PROVIDER_LABELS["bithuman"] == "bitHuman"
    assert "bithuman" in list_avatar_providers()
    assert [m.avatar_model for m in list_avatar_models("bithuman")] == [
        "essence-2",
        "expression-2",
        "essence-1",
        "expression-1",
    ]
    assert "anam" in AVATAR_WORKFLOW_PROVIDERS
    assert "bithuman" not in AVATAR_WORKFLOW_PROVIDERS
