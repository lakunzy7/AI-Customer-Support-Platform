.PHONY: help install dev lint test run docker-up docker-down migrate seed kind-up kind-down port-forward

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -e .

dev: ## Install development dependencies
	pip install -e ".[dev,otel]"

lint: ## Run linters
	ruff check src/ tests/
	ruff format --check src/ tests/

format: ## Auto-format code
	ruff check --fix src/ tests/
	ruff format src/ tests/

test: ## Run tests
	pytest -v --cov=src/ai_platform --cov-report=term-missing

run: ## Run development server
	uvicorn src.ai_platform.main:app --reload --host 0.0.0.0 --port 8000

docker-up: ## Start all services with docker-compose
	docker compose up -d --build

docker-down: ## Stop all services
	docker compose down -v

migrate: ## Run database migrations
	alembic -c src/ai_platform/db/alembic.ini upgrade head

seed: ## Seed Qdrant with sample FAQ data
	python scripts/seed_qdrant.py

kind-up: ## Create KIND cluster and deploy
	bash scripts/kind-setup.sh

kind-down: ## Delete KIND cluster
	kind delete cluster --name ai-platform

port-forward: ## Port-forward services from KIND
	bash scripts/port-forward.sh
