"""LiveKit settings: off unless fully configured."""

from assemblix_api.core.settings import get_settings


def test_livekit_disabled_by_default() -> None:
    assert get_settings().livekit_enabled is False


def test_livekit_enabled_only_when_all_four_are_set(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_url", "wss://rtc.example.com")
    monkeypatch.setattr(settings, "livekit_public_url", "wss://rtc.example.com")
    monkeypatch.setattr(settings, "livekit_api_key", "key")
    assert settings.livekit_enabled is False

    monkeypatch.setattr(settings, "livekit_api_secret", "secret")
    assert settings.livekit_enabled is True


def test_avatar_join_timeout_default() -> None:
    assert get_settings().avatar_join_timeout_seconds == 20.0
