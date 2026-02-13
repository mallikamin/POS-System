# =============================================================================
# POS System - Makefile
# =============================================================================
# Usage: make <target>
# Run `make help` to see all available targets.
# =============================================================================

.DEFAULT_GOAL := help
COMPOSE := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE_TEST := docker compose -f docker-compose.yml -f docker-compose.test.yml

# -- Colors for help output --------------------------------------------------
CYAN := \033[36m
RESET := \033[0m

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "POS System - Available Commands"
	@echo "================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Development
# =============================================================================

.PHONY: dev
dev: ## Start all services (attached, with logs)
	$(COMPOSE) up --build

.PHONY: dev-d
dev-d: ## Start all services (detached)
	$(COMPOSE) up --build -d

.PHONY: down
down: ## Stop all services
	$(COMPOSE) down

.PHONY: down-v
down-v: ## Stop all services and remove volumes (full reset)
	$(COMPOSE) down -v

.PHONY: build
build: ## Rebuild all Docker images
	$(COMPOSE) build

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: logs-backend
logs-backend: ## Tail backend logs only
	$(COMPOSE) logs -f backend

.PHONY: logs-frontend
logs-frontend: ## Tail frontend logs only
	$(COMPOSE) logs -f frontend

# =============================================================================
# Database
# =============================================================================

.PHONY: migrate
migrate: ## Run database migrations (alembic upgrade head)
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: migrate-new
migrate-new: ## Create a new migration (usage: make migrate-new MSG="add users table")
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(MSG)"

.PHONY: migrate-down
migrate-down: ## Rollback the last migration
	$(COMPOSE) exec backend alembic downgrade -1

.PHONY: seed
seed: ## Seed the database with sample data
	$(COMPOSE) exec backend python -m app.scripts.seed

.PHONY: psql
psql: ## Open a psql shell to the database
	$(COMPOSE) exec postgres psql -U pos_admin -d pos_system

# =============================================================================
# Testing
# =============================================================================

.PHONY: test
test: ## Run tests in Docker (isolated postgres + redis)
	$(COMPOSE_TEST) run --rm test
	$(COMPOSE_TEST) down

.PHONY: test-local
test-local: ## Run tests locally (requires local Python env)
	cd backend && pytest -v --tb=short

.PHONY: lint
lint: ## Run linters (backend + frontend)
	$(COMPOSE) exec backend ruff check app/
	$(COMPOSE) exec backend ruff format --check app/
	$(COMPOSE) exec frontend npm run lint

# =============================================================================
# Production
# =============================================================================

.PHONY: build-prod
build-prod: ## Build production Docker images
	$(COMPOSE_PROD) build

.PHONY: deploy-staging
deploy-staging: ## Deploy to staging environment
	./scripts/deploy.sh staging

.PHONY: deploy-prod
deploy-prod: ## Deploy to production environment
	./scripts/deploy.sh production

# =============================================================================
# Utilities
# =============================================================================

.PHONY: shell-backend
shell-backend: ## Open a bash shell in the backend container
	$(COMPOSE) exec backend bash

.PHONY: shell-frontend
shell-frontend: ## Open a bash shell in the frontend container
	$(COMPOSE) exec frontend sh

.PHONY: redis-cli
redis-cli: ## Open a Redis CLI session
	$(COMPOSE) exec redis redis-cli

.PHONY: clean
clean: ## Remove all containers, volumes, images, and orphans
	$(COMPOSE) down -v --rmi local --remove-orphans
	$(COMPOSE_TEST) down -v --rmi local --remove-orphans 2>/dev/null || true
	docker system prune -f
