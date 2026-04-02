# Production-Grade AI Platform: DevOps for AI Systems

## Project Overview

This project focuses on building and operating the infrastructure required to run an AI-powered application in a production environment. Instead of developing complex AI models, you will treat the AI system as a service that must be deployed, scaled, monitored, and continuously delivered using modern DevOps practices.

The goal is to simulate how real companies run AI systems in production—ensuring high availability, efficient resource usage, safe deployments, and full observability. By the end, you will have built a platform capable of reliably serving AI workloads at scale.

## Case Study

A SaaS company is introducing an AI-powered customer support assistant to reduce operational costs and improve response times. While the AI component already exists, the company lacks the infrastructure to run it in production reliably.

They need a DevOps team to:
- Deploy the AI system across environments
- Ensure uptime and scalability
- Implement CI/CD pipelines for rapid updates
- Monitor performance and failures
- Handle production incidents

## Problem Statement

> Design and implement a production-ready DevOps platform that can reliably deploy, scale, monitor, and update an AI service under real-world conditions.

## Core Objectives

By completing this project, mentees should be able to:
- Deploy multi-service applications using containers
- Orchestrate services using Kubernetes
- Build CI/CD pipelines for AI services
- Implement observability (metrics, logs, tracing)
- Design for high availability and fault tolerance
- Perform safe deployments (zero downtime)
- Manage configuration, secrets, and environments

## Tech Stack

### Application Layer

| Component | Technology |
|-----------|------------|
| API Gateway | FastAPI |
| LLM Service | Groq (Cloud LLM) |
| Caching | Redis |
| Database | PostgreSQL |
| Vector Store | Qdrant |

### Containerization & Orchestration

| Component | Technology |
|-----------|------------|
| Containers | Docker |
| Orchestration | Kubernetes (KIND) |
| Package Manager | Helm |

### CI/CD & GitOps

| Component | Technology |
|-----------|------------|
| CI/CD | GitHub Actions |
| GitOps | ArgoCD |

### Observability

| Component | Technology |
|-----------|------------|
| Metrics | Prometheus |
| Dashboards | Grafana |
| Logs | Loki |
| Tracing | OpenTelemetry |

### Security & Config

| Component | Technology |
|-----------|------------|
| Secrets Management | HashiCorp Vault |
| Secret Sync | External Secrets Operator |
| Network Security | Kubernetes Network Policies |

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Core Application + Docker | Done |
| Phase 2 | Kubernetes + Helm | Done |
| Phase 3 | CI/CD + GitOps | Done |
| Phase 4 | Observability | Done |
| Phase 5 | Security + MLOps | Done |

- **81 files** across all phases
- **15 tests passing** with **69% code coverage**
- Python 3.11 | FastAPI | async throughout

## Project Structure

```
Ai-systems/
├── src/ai_platform/              # FastAPI application
│   ├── main.py                   # App entry point with lifespan hooks
│   ├── config.py                 # Pydantic Settings (all env vars)
│   ├── dependencies.py           # FastAPI dependency injection
│   ├── api/                      # Route handlers
│   │   ├── health.py             # GET /healthz, GET /readyz
│   │   ├── chat.py               # POST /v1/chat
│   │   └── rag.py                # POST /v1/rag
│   ├── schemas/                  # Pydantic request/response models
│   ├── services/                 # Business logic
│   │   ├── llm_client.py         # Groq API client (chat + embeddings)
│   │   ├── cache_service.py      # Redis caching (SHA-256 keys, TTL)
│   │   ├── rag_service.py        # RAG pipeline (embed → search → LLM)
│   │   └── conversation_service.py  # PostgreSQL conversation history
│   ├── models/                   # SQLAlchemy ORM models
│   ├── db/                       # Alembic migrations
│   └── core/                     # Logging, telemetry, middleware
├── tests/                        # Unit + integration tests (15 tests, 69% coverage)
│   ├── test_health.py            # Health endpoint tests
│   ├── test_chat_endpoint.py     # Chat API tests
│   ├── test_llm_client.py        # LLM client tests
│   └── test_cache_service.py     # Cache service tests
├── docker/api/Dockerfile         # Multi-stage build, non-root user
├── docker-compose.yml            # Local dev (API + Redis + PostgreSQL + Qdrant)
├── docker-compose.override.yml   # Dev overrides (hot reload)
├── helm/ai-platform/             # Helm umbrella chart
│   ├── templates/api/            # Deployment, Service, HPA, PDB, Ingress, Canary, NetworkPolicy
│   ├── templates/redis/          # Deployment + Service
│   ├── templates/postgresql/     # StatefulSet + Service + PVC
│   ├── templates/qdrant/         # StatefulSet + Service + PVC
│   ├── values.yaml               # Defaults
│   ├── values-dev.yaml           # KIND overrides
│   └── values-prod.yaml          # Production overrides
├── k8s/
│   ├── kind/cluster-config.yaml  # 3-node KIND cluster
│   ├── namespaces/               # Namespace + ResourceQuota manifests
│   └── argocd/                   # ArgoCD app-of-apps pattern
├── monitoring/
│   ├── prometheus/               # Alert rules + SLO recording rules
│   ├── grafana/dashboards/       # API overview JSON dashboard
│   └── loki/                     # Loki-stack Helm values
├── vault/                        # Policies, init script, External Secrets
├── scripts/                      # KIND setup, port-forward, seed data
├── .github/workflows/            # CI, release, security scan
│   ├── ci.yml                    # lint → test → build → push to ghcr.io
│   ├── release.yml               # Tag-triggered release
│   └── security.yml              # Trivy + pip-audit
├── docs/                         # Architecture, deployment guide, incident runbook
├── Makefile                      # Developer automation
└── pyproject.toml                # Python deps + tool config
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe (checks DB, Redis, Qdrant) |
| POST | `/v1/chat` | Chat with AI assistant (with conversation history) |
| POST | `/v1/rag` | RAG query against FAQ knowledge base |
| GET | `/docs` | Swagger UI (dev only) |

## DevOps Pipeline

### CI Pipeline
1. Linting & testing (ruff + pytest)
2. Build Docker images (multi-stage)
3. Tag images (Git SHA + latest)
4. Push to ghcr.io container registry
5. Security scanning (Trivy + pip-audit)

### CD Pipeline
1. ArgoCD watches Git repository
2. Detects changes to Helm chart or values
3. Auto-syncs to Kubernetes cluster
4. Self-heals on drift

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose

### Run Tests

```bash
# Create virtual environment and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -v --cov=src/ai_platform --cov-report=term-missing
```

### Run Locally with Docker

```bash
# Copy env vars and set your Groq API key
cp .env.example .env
# Edit .env with your LLM_API_KEY (get one at https://console.groq.com/keys)

# Start all services
make docker-up

# Run database migrations
make migrate

# Seed Qdrant with FAQ data
make seed

# Test endpoints
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your return policy?"}'

curl -X POST http://localhost:8000/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reset my password?"}'
```

### Deploy to KIND Cluster

```bash
make kind-up        # Create cluster + deploy
make port-forward   # Access services locally
make kind-down      # Tear down
```

## Test Coverage

```
15 tests passing — 69% overall coverage

Module                              Coverage
─────────────────────────────────────────────
schemas/                            100%
models/                             100%
services/cache_service.py           100%
services/llm_client.py              100%
api/health.py                       100%
core/middleware.py                   100%
config.py                           100%
api/chat.py                          81%
main.py                              79%
services/conversation_service.py     82%
```

## Make Commands

```
make help           Show all available commands
make install        Install production dependencies
make dev            Install development dependencies
make lint           Run linters (ruff)
make format         Auto-format code
make test           Run tests with coverage
make run            Run development server
make docker-up      Start all services with docker-compose
make docker-down    Stop all services
make migrate        Run database migrations
make seed           Seed Qdrant with sample FAQ data
make kind-up        Create KIND cluster and deploy
make kind-down      Delete KIND cluster
make port-forward   Port-forward services from KIND
```

## Documentation
- [Architecture](docs/architecture.md) — System overview, data flows, deployment models
- [Deployment Guide](docs/deployment-guide.md) — Local, KIND, production, canary, monitoring setup
- [Incident Runbook](docs/incident-runbook.md) — Alert response procedures and rollback steps
