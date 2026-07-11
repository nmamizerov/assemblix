"""Tests for avatar-related settings."""

from assemblix_api.core.settings import get_settings


def test_anam_base_url_default():
    assert get_settings().anam_api_base_url == "https://api.anam.ai"
