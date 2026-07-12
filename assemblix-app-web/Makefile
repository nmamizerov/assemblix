.DEFAULT_GOAL := help
.PHONY: help dev build lint test preview install

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev: ## Run the Vite dev server with HMR (:5173)
	yarn dev

build: ## Type-check and build the production bundle
	yarn build

lint: ## Lint with ESLint
	yarn lint

test: ## Run unit tests (vitest)
	yarn test

preview: ## Preview the production build locally
	yarn preview

install: ## Install dependencies
	yarn install
