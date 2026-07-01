# /external/llm/provider_config.py
"""Transport quirks of LLM providers (for the in-process litellm adapter).

These differences used to live in `LiteLLMConfig` inside each provider bootstrap.
Here they are collected declaratively: the litellm model prefix, the name of the
setting with `api_base`, the TLS verification flag, env-overrides and the env
variable for api_key.

Model parameters (temperature/visibility, etc.) do NOT live here — they are in
`models/<provider>.json` and are used for the UI schema and building ModelSettings.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderConfig:
    """Static transport facts of a single provider."""

    litellm_prefix: str = ""
    # Name of the Settings attribute that provides api_base (None → litellm default).
    api_base_setting: str | None = None
    # Name of the bool setting for TLS verification (None → verify, True).
    ssl_verify_setting: str | None = None
    # Static env-overrides applied before the call: {ENV_VAR: settings_attr}.
    settings_env_overrides: dict[str, str] = field(default_factory=dict)
    # If set — api_key is duplicated into this env variable (for providers that
    # authenticate via env, not via the api_key kwarg).
    api_key_env_var: str | None = None


PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        litellm_prefix="openai/",
        api_base_setting="openai_api_base_url",
    ),
    "anthropic": ProviderConfig(),
    "deepseek": ProviderConfig(litellm_prefix="deepseek/"),
    "gemini": ProviderConfig(
        litellm_prefix="gemini/",
        api_base_setting="gemini_api_base_url",
    ),
}


def get_provider_config(provider: str) -> ProviderConfig:
    """Provider config; an unknown provider → the default one (no prefix)."""
    return PROVIDER_CONFIGS.get(provider, ProviderConfig())
