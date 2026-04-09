# AI Customer Support Platform

A production-grade AI-powered customer support assistant built with FastAPI, Groq LLM inference, and a full DevOps pipeline. Features a ChatGPT-style web UI, conversation history, file uploads, RAG-based FAQ answers, and end-to-end Kubernetes deployment with observability.

![Architecture Diagram](img/Architecture%20Diagram%20For%20AI%20Customer%20Support%20Platform.jpg)

## Tech Stack

| Layer | Technology |
|-------|------------|
| **API** | FastAPI (async, OpenAPI docs) |
| **LLM** | Groq Cloud (llama-3.3-70b-versatile) |
| **Embeddings** | fastembed (local, nomic-embed-text-v1) |
| **Database** | PostgreSQL (asyncpg + SQLAlchemy) |
| **Cache** | Redis (with hiredis) |
| **Vector Store** | Qdrant |
| **Containerization** | Docker + Docker Compose |
| **Orchestration** | Kubernetes (KIND for local dev) |
| **Package Management** | Helm (umbrella chart) |
| **CI/CD** | GitHub Actions + ArgoCD (GitOps) |
| **Observability** | Prometheus + Grafana + Loki + OpenTelemetry |
| **Secrets** | HashiCorp Vault + External Secrets Operator |

## Quick Start (Docker Compose)

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- A free [Groq API key](https://console.groq.com/keys)

### 1. Clone and configure

```bash
git clone https://github.com/lakunzy7/AI-Customer-Support-Platform.git
cd AI-Customer-Support-Platform

# Copy env file and add your Groq API key
cp .env.example .env
# Edit .env and set LLM_API_KEY=gsk_your_key_here
```

### 2. Start all services

```bash
docker compose up -d --build
```

This starts the API, PostgreSQL, Redis, and Qdrant. The API runs migrations automatically on startup.

### 3. Seed the FAQ knowledge base

```bash
docker compose exec api python3 /app/src/scripts/seed_qdrant.py
```

### 4. Open the app

Open **http://localhost:8000** in your browser.

### Verify it works

```bash
# Health check
curl http://localhost:8000/healthz

# Readiness (checks DB, Redis, Qdrant)
curl http://localhost:8000/readyz

# Chat
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your return policy?"}'

# RAG (FAQ search)
curl -X POST http://localhost:8000/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reset my password?"}'
```

## Kubernetes Deployment (KIND)

For production-like local deployment on Kubernetes:

```bash
# 1. Create KIND cluster (3 nodes)
bash scripts/kind-setup.sh

# 2. Build and load image into KIND
docker build -t ai-platform-api:latest -f docker/api/Dockerfile .
kind load docker-image ai-platform-api:latest --name ai-platform

# 3. Deploy with Helm
kubectl create namespace ai-platform
helm install ai-platform helm/ai-platform -n ai-platform

# 4. Run migrations
kubectl exec -n ai-platform deploy/ai-platform-api -- bash -c \
  'cd /app && alembic -c src/ai_platform/db/alembic.ini upgrade head'

# 5. Port-forward to access
kubectl port-forward -n ai-platform svc/ai-platform-api 8080:8000 --address 0.0.0.0
```

See [k8s/kubernetes-deployment-guide.md](k8s/kubernetes-deployment-guide.md) for the full step-by-step guide.

## Observability Stack

The monitoring stack runs in the `monitoring` namespace and includes:

| Component | Role |
|-----------|------|
| **Prometheus** | Scrapes `/metrics` from the API every 15s |
| **Grafana** | Dashboards (request rate, latency P50/P95/P99, error rate, pod CPU/memory) |
| **Alertmanager** | Fires alerts (HighErrorRate, HighLatency, PodCrashLooping, LLMSlowResponse) |
| **Loki + Promtail** | Centralized log aggregation (7-day retention) |
| **OpenTelemetry** | Distributed tracing with OTLP export |

```bash
# Install monitoring stack
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring -f monitoring/prometheus/kube-prometheus-stack-values.yaml

helm install loki grafana/loki-stack \
  -n monitoring -f monitoring/loki/values.yaml

# Apply custom resources
kubectl apply -f monitoring/prometheus/servicemonitor.yaml
kubectl apply -f monitoring/prometheus/alert-rules.yaml
kubectl apply -f monitoring/grafana/dashboard-configmap.yaml

# Access Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80 --address 0.0.0.0
# Login: admin / admin
```

### Grafana Dashboard Panels
1. Request Rate (req/s)
2. Error Rate (%)
3. Latency (P50 / P95 / P99)
4. LLM Request Duration (P95)
5. Active Pods
6. CPU Usage by Pod
7. Memory Usage by Pod

## Web UI Features

The platform includes a ChatGPT-style web interface served at `/`:

- **Sidebar** -- Conversation history with click-to-load, inline rename, delete
- **Auto-titles** -- LLM generates short titles for new conversations
- **Markdown rendering** -- Bold, italic, lists, tables, headings, blockquotes (via marked.js)
- **Code blocks** -- Syntax-highlighted with copy button (via highlight.js)
- **Voice input** -- Browser-native speech recognition (Chrome/Edge/Safari)
- **File upload** -- Attach files and the AI reads their contents (see supported formats below)
- **Mobile responsive** -- Sidebar toggle with hamburger menu

## Supported File Uploads

Upload files in the chat and the AI will read and understand their contents:

| Format | Extensions |
|--------|-----------|
| Text / Code | `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.csv`, `.html`, `.css`, `.sql`, `.sh`, `.log`, `.xml`, `.yaml`, `.yml` |
| Documents | `.pdf`, `.docx`, `.doc`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.rtf`, `.epub` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` (upload only) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Chat web UI |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe (checks DB, Redis, Qdrant) |
| `GET` | `/metrics` | Prometheus metrics endpoint |
| `POST` | `/v1/chat` | Chat with AI assistant (supports `file_ids`) |
| `GET` | `/v1/conversations` | List conversations (with auto-generated titles) |
| `GET` | `/v1/conversations/{id}/messages` | Get full message history |
| `PATCH` | `/v1/conversations/{id}` | Rename a conversation |
| `DELETE` | `/v1/conversations/{id}` | Delete a conversation |
| `POST` | `/v1/upload` | Upload a file (max 10MB, returns `file_id`) |
| `GET` | `/v1/files/{id}` | Download an uploaded file |
| `POST` | `/v1/rag` | RAG query against FAQ knowledge base |
| `GET` | `/docs` | Swagger UI |

## Project Structure

```
AI-Customer-Support-Platform/
├── src/
│   ├── ai_platform/              # FastAPI application
│   │   ├── main.py               # App entry point (lifespan, telemetry, /metrics)
│   │   ├── config.py             # Pydantic Settings (all env vars)
│   │   ├── dependencies.py       # FastAPI dependency injection
│   │   ├── api/                  # Route handlers
│   │   │   ├── health.py         # GET /healthz, GET /readyz
│   │   │   ├── chat.py           # POST /v1/chat (file context + auto-title)
│   │   │   ├── conversations.py  # GET/PATCH/DELETE /v1/conversations
│   │   │   ├── files.py          # POST /v1/upload, GET /v1/files/{id}
│   │   │   ├── file_extractors.py # Text extraction for all file types
│   │   │   └── rag.py            # POST /v1/rag
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── services/             # Business logic
│   │   │   ├── llm_client.py     # Groq chat + fastembed local embeddings
│   │   │   ├── cache_service.py  # Redis caching (SHA-256 keys, TTL)
│   │   │   ├── rag_service.py    # RAG pipeline (embed -> search -> LLM)
│   │   │   └── conversation_service.py
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── db/                   # Alembic migrations
│   │   ├── static/               # Chat web UI (index.html)
│   │   └── core/                 # Logging, telemetry (OTel + Prometheus)
│   ├── tests/                    # 15 tests (unit + integration)
│   ├── scripts/                  # seed_qdrant.py
│   └── docs/                     # Architecture docs, setup guide
├── docker/                       # Dockerfiles
│   └── api/Dockerfile
├── docker-compose.yml            # Local dev (API + PostgreSQL + Redis + Qdrant)
├── helm/
│   └── ai-platform/              # Umbrella Helm chart
│       ├── templates/            # K8s manifests (API, PG, Redis, Qdrant)
│       ├── values.yaml           # Default values
│       ├── values-dev.yaml       # Dev overrides
│       └── values-prod.yaml      # Production overrides
├── k8s/
│   ├── kind/                     # KIND cluster config (3 nodes)
│   ├── argocd/                   # ArgoCD app-of-apps GitOps config
│   ├── namespaces/               # Namespace definitions
│   └── kubernetes-deployment-guide.md
├── monitoring/
│   ├── prometheus/               # ServiceMonitor, alert rules, kube-prometheus values
│   ├── grafana/                  # Dashboard JSON + ConfigMap
│   └── loki/                     # Loki + Promtail Helm values
├── vault/                        # Vault policies, External Secrets config
├── scripts/                      # kind-setup.sh, port-forward.sh
├── .github/workflows/            # CI, release, security scanning
├── img/                          # Architecture diagram
├── pyproject.toml                # Python deps + tool config
└── .env.example                  # Environment variable template
```

## CI/CD Pipeline

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | Push / PR to main | Lint (ruff), type-check (mypy), test (pytest), build Docker image |
| `release.yml` | Tag `v*` | Build + push image to GHCR, create GitHub release |
| `security.yml` | Schedule + PR | Trivy container scan, pip-audit, CodeQL |

ArgoCD watches the `main` branch and auto-syncs Helm chart changes to the cluster.

## Running Tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | Groq API key | (required) |
| `LLM_BASE_URL` | LLM API base URL | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Chat model name | `llama-3.3-70b-versatile` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `QDRANT_HOST` | Qdrant hostname | `localhost` |
| `QDRANT_PORT` | Qdrant port | `6333` |
| `CACHE_TTL_SECONDS` | Redis cache TTL | `3600` |

## License

MIT

---

Powered by Groq & Expadox Lab
