# /external/llm/litellm_model.py
"""In-process litellm adapter for Pydantic AI (option C of the Phase 2 refactor).

Pydantic AI's `LiteLLMProvider` is designed for a separate LiteLLM Proxy service, but
we need in-process translation (like Dify/n8n). So we subclass `OpenAIChatModel` and
swap the HTTP client for a shim that routes `chat.completions.create(...)` to
`litellm.acompletion(...)`. All message/tool/response mapping (OpenAI format) is reused
from `OpenAIChatModel` — litellm also speaks the OpenAI format.

Caveat: `litellm.ModelResponse` is not an instance of `openai.types.chat.ChatCompletion`,
but pydantic-ai requires exactly that → we revalidate via `.model_validate(resp.model_dump())`.
"""

from __future__ import annotations

import os
from typing import Any, cast

import litellm
from openai import AsyncOpenAI, NotGiven, Omit
from openai.types.chat import ChatCompletion
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from assemblix_api.core.settings import get_settings
from assemblix_api.external.llm.provider_config import get_provider_config

# litellm must not flood our logs with debug output.
litellm.set_verbose = False
litellm.suppress_debug_info = True


def _strip_sentinels(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Drop OpenAI sentinels (OMIT/NOT_GIVEN) and None that pydantic-ai substitutes
    for omitted parameters — litellm does not understand them."""
    return {
        k: v for k, v in kwargs.items() if v is not None and not isinstance(v, (Omit, NotGiven))
    }


class _Completions:
    def __init__(
        self,
        defaults: dict[str, Any],
        env_overrides: dict[str, str],
        api_key_env_var: str | None,
        api_key: str | None,
    ):
        self._defaults = defaults
        self._env_overrides = env_overrides
        self._api_key_env_var = api_key_env_var
        self._api_key = api_key

    async def create(self, **kwargs: Any) -> ChatCompletion:
        # Apply env-overrides (e.g. GIGACHAT_SCOPE) and env-auth (GIGACHAT_CREDENTIALS).
        for env_name, value in self._env_overrides.items():
            os.environ[env_name] = value
        if self._api_key_env_var and self._api_key:
            os.environ[self._api_key_env_var] = self._api_key

        merged = {**self._defaults, **_strip_sentinels(kwargs)}
        resp = await litellm.acompletion(**merged)
        # litellm.ModelResponse → real openai ChatCompletion (pydantic-ai isinstance check).
        # warnings=False: the litellm schema is slightly wider than the openai types; without
        # this it emits UserWarning.
        return ChatCompletion.model_validate(resp.model_dump(warnings=False))


class _Chat:
    def __init__(self, completions: _Completions):
        self.completions = completions


class _ShimClient:
    """Minimal slice of AsyncOpenAI that OpenAIChatModel touches."""

    def __init__(self, completions: _Completions):
        self.chat = _Chat(completions)
        # OpenAIChatModel/OpenAIProvider read client.base_url only for logging/
        # representation. The real HTTP requests are made by litellm inside create(), not
        # by this client, so this is a placeholder marker that goes nowhere.
        self.base_url = "litellm://in-process"


class LiteLLMModel(OpenAIChatModel):
    """Pydantic AI model that executes requests via in-process `litellm.acompletion`."""

    def __init__(
        self,
        litellm_model: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        ssl_verify: bool = True,
        env_overrides: dict[str, str] | None = None,
        api_key_env_var: str | None = None,
        response_format: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        num_retries: int | None = None,
    ) -> None:
        defaults: dict[str, Any] = {"drop_params": True}
        # Only forward `ssl_verify` when verification must be DISABLED (e.g. GigaChat's Sber
        # self-signed certs). litellm 1.80.x does not list `ssl_verify` in `all_litellm_params`,
        # so a forwarded value leaks into the provider request body — OpenAI then 400s with
        # "Unrecognized request argument supplied: ssl_verify". True is litellm's own default,
        # so omitting it keeps verification on without the leak.
        if not ssl_verify:
            defaults["ssl_verify"] = ssl_verify
        if api_key:
            defaults["api_key"] = api_key
        if api_base:
            defaults["api_base"] = api_base
        # Reliability (Phase 3): litellm handles per-call timeout and transient-error retries
        # itself — we only forward the knobs. `num_retries` retries retryable errors with
        # backoff; `timeout` caps a single completion (seconds). See plan: we deliberately do
        # NOT set `retry_strategy` (a Router-level feature, not guaranteed on bare acompletion).
        if timeout is not None:
            defaults["timeout"] = timeout
        if num_retries is not None:
            defaults["num_retries"] = num_retries
        # response_format always goes into the litellm call (litellm will drop it itself if
        # the provider does not support it, thanks to drop_params=True).
        if response_format:
            defaults["response_format"] = response_format
        # Node sampling parameters (temperature/max_tokens/reasoning_effort/...) go into
        # litellm as is; drop_params=True filters out those unsupported by the model.
        if params:
            defaults.update(params)

        completions = _Completions(
            defaults=defaults,
            env_overrides=env_overrides or {},
            api_key_env_var=api_key_env_var,
            api_key=api_key,
        )
        shim = _ShimClient(completions)
        # model_name = the prefixed litellm name ("gigachat/GigaChat-Pro") — the same one
        # that goes into litellm.acompletion(model=...). The shim replaces AsyncOpenAI via
        # duck typing (OpenAIChatModel touches only .chat.completions.create / .base_url).
        super().__init__(
            litellm_model,
            provider=OpenAIProvider(openai_client=cast(AsyncOpenAI, shim)),
        )


def build_litellm_model(
    provider: str,
    model: str,
    api_key: str,
    *,
    response_format: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
    num_retries: int | None = None,
) -> LiteLLMModel:
    """Build a `LiteLLMModel` for (provider, model), applying transport quirks.

    What the factory does per provider (the data lives in `provider_config.py`):
    - **openai**: `openai/` prefix + `api_base` from `openai_api_base_url`.
    - **deepseek**: only the `deepseek/` prefix (OpenAI-compatible endpoint).
    - **gigachat**: `gigachat/` prefix, `ssl_verify` from `gigachat_verify_ssl`
      (Sber self-signed certs), and api_key is duplicated into env `GIGACHAT_CREDENTIALS`
      + `GIGACHAT_SCOPE` — the litellm GigaChat integration authenticates via env,
      not via a kwarg.
    - **gemini**: `gemini/` prefix + `api_base` from `gemini_api_base_url` (our
      proxy). IMPORTANT about Gemini: thinking parameters are not set here — they come
      in `params` from the node config (`reasoning_effort` or `thinking_budget`/
      `thinking_level`) and go into litellm as is; `drop_params=True` strips what a
      particular Gemini model does not support, so a single code path works both for
      2.5 (`thinking_budget`) and for 3+ (`thinking_level`). If the proxy/thinking
      via litellm does not work with production keys — fall back to the native
      `GoogleModel` of Pydantic AI for Gemini only, without touching other providers.

    Args:
        provider: provider key ("openai"/"deepseek"/"gigachat"/"gemini"/...).
        model: the "bare" model id without prefix ("gpt-4o", "GigaChat-Pro").
        api_key: key for the call (system or user).
        response_format: optional litellm response_format (json_object / json_schema).
        params: optional node sampling parameters (temperature/max_tokens/thinking/...).
        timeout: per-call timeout in seconds (litellm `timeout`); defaults to
            `llm_request_timeout_seconds`.
        num_retries: how many times litellm retries a transient error of a single call
            (litellm `num_retries`); defaults to `llm_num_retries`.

    Returns:
        LiteLLMModel — a Pydantic AI model that executes calls via in-process
        `litellm.acompletion` (see the class above).
    """
    cfg = get_provider_config(provider)
    settings = get_settings()

    litellm_model = f"{cfg.litellm_prefix}{model}"
    api_base = getattr(settings, cfg.api_base_setting) if cfg.api_base_setting else None
    ssl_verify = getattr(settings, cfg.ssl_verify_setting) if cfg.ssl_verify_setting else True
    env_overrides = {
        env_name: getattr(settings, attr) for env_name, attr in cfg.settings_env_overrides.items()
    }

    return LiteLLMModel(
        litellm_model,
        api_key=api_key,
        api_base=api_base,
        ssl_verify=ssl_verify,
        env_overrides=env_overrides,
        api_key_env_var=cfg.api_key_env_var,
        response_format=response_format,
        params=params,
        timeout=timeout if timeout is not None else settings.llm_request_timeout_seconds,
        num_retries=num_retries if num_retries is not None else settings.llm_num_retries,
    )
