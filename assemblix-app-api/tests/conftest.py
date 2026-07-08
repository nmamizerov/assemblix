"""Root test config: container bootstrap + fixture-plugin registration.

The actual fixtures are split into focused modules under ``tests/plugins/`` and
registered here via ``pytest_plugins`` (the idiomatic way to keep a large fixture
set modular). This file holds only what must live in the root conftest: the
session bootstrap hooks (hermetic env + throwaway Postgres container + migrations).

Fixture modules:
* ``tests.plugins.database`` — app runtime, transactional ``db_session``, ``committed_db``;
* ``tests.plugins.app``      — ``app`` / ``client`` (rolled back) and ``api_client`` (committed);
* ``tests.plugins.auth``     — ``user_factory`` / ``auth_user`` / ``auth_headers`` / ``api_key``;
* ``tests.plugins.llm``      — ``mock_llm`` (the ``litellm.acompletion`` seam) and ``fake_redis``.

Scope-local fixtures live in nested conftests, e.g. ``tests/integration/queue/conftest.py``.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

import pytest

pytest_plugins = [
    "tests.plugins.database",
    "tests.plugins.app",
    "tests.plugins.auth",
    "tests.plugins.llm",
    "tests.plugins.tts_ws",
]

# assemblix-app-api/ — one level up from tests/.
API_DIR = Path(__file__).resolve().parent.parent

# Held at module scope so pytest_unconfigure can tear the container down.
_pg_container: Any = None


def _ensure_ephemeral_secrets() -> None:
    """Generate the two fail-fast secrets if the environment does not supply them.

    Mirrors what the Makefile/CI do, so the suite never depends on a real .env.
    """
    if not os.environ.get("JWT_SECRET_KEY"):
        os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
    if not os.environ.get("ENCRYPTION_KEY"):
        from cryptography.fernet import Fernet

        os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()


def pytest_configure(config: pytest.Config) -> None:
    """Set the hermetic test profile and start the DB container.

    Runs before any ``assemblix_api`` import triggers ``get_settings()``, so the
    container ``DATABASE_URL`` and the feature-flag overrides below are picked up
    on first settings instantiation (settings read os.environ at construction).
    """
    # Force a self-host-like, single-process profile regardless of repo-root .env.
    os.environ["BILLING_ENABLED"] = "false"
    os.environ["EXECUTION_QUEUE_ENABLED"] = "false"
    os.environ["DEBUG_EVENTS_USE_REDIS"] = "false"
    os.environ["EXECUTION_CHECKPOINTING_ENABLED"] = "false"
    os.environ["METRICS_ENABLED"] = "false"
    # The auth rate limiter uses a process-global in-memory backend in tests (no Redis),
    # so registrations/logins accumulate across the whole session against the default
    # 10-per-5-min window. Lift it so the base suite never trips a 429 on register/login.
    os.environ["LOGIN_RATE_LIMIT_PER_5MIN"] = "100000"
    os.environ["REDIS_URL"] = ""  # no Redis in the base scope; use fakeredis fixtures
    # Dummy system LLM keys so credential resolution succeeds for mocked agent runs
    # (the LLM call itself is patched). setdefault keeps any real keys for `external`.
    os.environ.setdefault("SYSTEM_OPENAI_API_KEY", "sk-test-system-openai")
    os.environ.setdefault("SYSTEM_GEMINI_API_KEY", "test-system-gemini")
    os.environ.setdefault("SYSTEM_DEEPSEEK_API_KEY", "test-system-deepseek")
    _ensure_ephemeral_secrets()

    # Skip the container when only collecting (e.g. --collect-only / -h).
    if config.getoption("--collect-only"):
        return

    # Disable the Ryuk reaper container — we stop our container in
    # pytest_unconfigure ourselves, and Ryuk's port mapping is a known flaky
    # point (ConnectionError on port 8080) on some Docker setups.
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

    global _pg_container
    from testcontainers.postgres import PostgresContainer

    _pg_container = PostgresContainer(
        "postgres:16-alpine", username="test", password="test", dbname="test"
    )
    _pg_container.start()
    host = _pg_container.get_container_host_ip()
    port = _pg_container.get_exposed_port(5432)
    os.environ["DATABASE_URL"] = f"postgresql://test:test@{host}:{port}/test"

    # Settings are @lru_cache'd; clear so the container URL wins on first real use.
    from assemblix_api.core.settings import get_settings

    get_settings.cache_clear()

    _apply_migrations()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Destroy the throwaway container at the end of the session."""
    global _pg_container
    if _pg_container is not None:
        _pg_container.stop()
        _pg_container = None


def _apply_migrations() -> None:
    """Build the schema on the fresh container by running Alembic to head.

    Using the real migration chain (not ``create_all``) means the suite also
    guards the migrations themselves.
    """
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
