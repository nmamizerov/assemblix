.DEFAULT_GOAL := help
.PHONY: help dev worker test test-cov test-external lint format typecheck security check

# Ephemeral secrets for test runs (unit tests never hit the app's fail-fast
# startup, but token/encryption helpers need non-empty values). Generated at
# runtime so no key is ever committed (keeps gitleaks green).
TEST_ENV = JWT_SECRET_KEY=$$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))') \
           ENCRYPTION_KEY=$$(python3 -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev: ## Run the dev server with autoreload
	uv run fastapi dev assemblix_api/main.py

worker: ## Run the Arq execution worker
	uv run arq assemblix_api.queue.worker.WorkerSettings

test: ## Run the base suite (unit + integration; needs Docker for the test DB)
	$(TEST_ENV) uv run pytest tests/unit tests/integration -m "not external"

test-cov: ## Run the base suite with coverage (enforces fail_under)
	$(TEST_ENV) uv run pytest tests/unit tests/integration -m "not external" \
		--cov --cov-report=term-missing

test-external: ## Run real-provider tests only (requires real API keys in env)
	uv run pytest -m external

lint: ## Lint with ruff
	uv run ruff check assemblix_api/ tests/
	uv run ruff format --check assemblix_api/ tests/

format: ## Auto-format and auto-fix with ruff
	uv run ruff format assemblix_api/ tests/
	uv run ruff check --fix assemblix_api/ tests/

typecheck: ## Static type checking with mypy
	uv run mypy assemblix_api/

security: ## SAST (bandit) + secret scan (gitleaks, if installed)
	uv run bandit -c pyproject.toml -r assemblix_api/ -q
	@command -v gitleaks >/dev/null 2>&1 && gitleaks detect --source . --no-banner || \
		echo "gitleaks not installed locally — skipping (CI still enforces it)"

check: lint typecheck security test-cov ## Run all gates (mirrors CI)
