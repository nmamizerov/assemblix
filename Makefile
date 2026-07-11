.DEFAULT_GOAL := help
.PHONY: help setup dev prod up down down-prod logs logs-prod install check

API_DIR := assemblix-app-api
WEB_DIR := assemblix-app-web
DEV := docker compose -f docker-compose.dev.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## One-command bootstrap: checks Docker, generates secrets, writes .env, brings the stack up
	./setup.sh

dev: ## Start the full dev stack with live reload (web :5173, api :8000)
	$(DEV) up

prod: up ## Alias for `up` — start the lean prod stack
up: ## Start the lean prod stack in the background (web :8080, api :8000)
	docker compose up -d --build

down: ## Stop the dev stack
	$(DEV) down

down-prod: ## Stop the prod stack
	docker compose down

logs: ## Follow dev stack logs
	$(DEV) logs -f

logs-prod: ## Follow prod stack logs
	docker compose logs -f

install: ## First-time setup: sync backend deps + install frontend deps
	cd $(API_DIR) && uv sync
	cd $(WEB_DIR) && yarn install

check: ## Run all quality gates across both apps (mirrors CI)
	$(MAKE) -C $(API_DIR) check
	$(MAKE) -C $(WEB_DIR) test
	$(MAKE) -C $(WEB_DIR) lint
