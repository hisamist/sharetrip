.DEFAULT_GOAL := help

.PHONY: help run test cov lint format \
        migrate migrate-down migrate-status migrate-history makemigration \
        up down logs shell \
        tf-plan tf-apply tf-destroy \
        deploy

# ─── Help ────────────────────────────────────────────────────────────────────

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Dev ─────────────────────────────────────────────────────────────────────

run: ## Start API in dev mode (hot-reload)
	uv run uvicorn src.sharetrip.main:app --reload

test: ## Run test suite
	uv run python -m pytest

cov: ## Run tests with coverage (fail under 80%)
	uv run python -m pytest --cov=src --cov-report=xml --cov-fail-under=80

lint: ## Lint with Ruff (auto-fix)
	uv run python -m ruff check . --fix

format: ## Format with Ruff
	uv run python -m ruff format .

# ─── Database / Migrations ───────────────────────────────────────────────────

migrate: ## Apply all pending migrations
	uv run alembic upgrade head

migrate-down: ## Rollback one migration
	uv run alembic downgrade -1

migrate-status: ## Show current migration revision
	uv run alembic current

migrate-history: ## Show full migration history
	uv run alembic history --verbose

makemigration: ## Generate a new migration (usage: make makemigration m="description")
	uv run alembic revision --autogenerate -m "$(m)"

# ─── Docker ──────────────────────────────────────────────────────────────────

up: ## Build and start all services (detached)
	docker compose up --build -d

down: ## Stop and remove containers
	docker compose down

logs: ## Follow API logs
	docker compose logs -f api

shell: ## Open shell inside the API container
	docker compose exec api sh

# ─── Terraform ───────────────────────────────────────────────────────────────

tf-plan: ## Preview infrastructure changes
	cd terraform && terraform plan

tf-apply: ## Apply infrastructure changes
	cd terraform && terraform apply

tf-destroy: ## Destroy provisioned infrastructure
	cd terraform && terraform destroy

# ─── Ansible ─────────────────────────────────────────────────────────────────

deploy: ## Deploy application via Ansible
	ansible-playbook ansible/playbooks/deploy.yml -i ansible/inventory/hosts.yml
