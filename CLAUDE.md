# Project: AI Customer Support Platform

## Efficiency Rules
- Read files directly, never ask the user to paste them
- Batch all related changes in one response
- No explanations unless asked
- No filler words: "Sure!", "Let me...", "I'll now..."
- Execute immediately when task is clear
- Code: just write it
- Errors: show fix only, no restatement
- Multiple files: edit all in one response
- Confirmation: one line max
- Before each task: read files silently, plan internally, execute in one shot, report what changed in 3 lines max
- Update MEMORY.md only on key decisions, keep entries under 2 lines, remove outdated entries
- Do NOT add Claude as co-author on commits

## Stack
- **Language**: Python 3.11
- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL 16 (asyncpg + SQLAlchemy async)
- **Cache**: Redis 7 (hiredis)
- **Vector DB**: Qdrant (fastembed for embeddings)
- **LLM**: Groq API (llama-3.3-70b-versatile)
- **Build**: Hatchling (pyproject.toml)
- **Linting**: Ruff (line-length 100, target py311, rules: E/F/I/N/W/UP/B/SIM/S)
- **Type Checking**: mypy (strict mode, pydantic plugin)
- **Testing**: Pytest + pytest-asyncio + pytest-cov (asyncio_mode=auto)
- **Orchestration**: Kubernetes (KIND) + Helm
- **Container Build**: Dockerfile (docker/api/Dockerfile)
- **CI/CD**: GitHub Actions (ci, release, security) + ArgoCD (app-of-apps)
- **Secrets**: Bitnami Sealed Secrets (encrypted in Git, decrypted in-cluster)
- **Observability**: OpenTelemetry + Prometheus (kube-prometheus-stack) + Grafana + Loki
- **File Parsing**: PyMuPDF, python-docx, openpyxl, python-pptx, odfpy, striprtf, ebooklib, beautifulsoup4

## Commands
| Action | Command |
|--------|---------|
| Install | `pip install -e .` |
| Install dev | `pip install -e ".[dev,otel]"` |
| Run | `uvicorn src.ai_platform.main:app --reload --host 0.0.0.0 --port 8000` |
| Test | `pytest -v --cov=src/ai_platform --cov-report=term-missing` |
| Lint | `ruff check src/ && ruff format --check src/` |
| Format | `ruff check --fix src/ && ruff format src/` |
| Migrate | `alembic -c src/ai_platform/db/alembic.ini upgrade head` |
| Seed | `python src/scripts/seed_qdrant.py` |
| KIND up | `bash scripts/kind-setup.sh` |
| KIND down | `kind delete cluster --name ai-platform` |
| Port forward | `bash scripts/port-forward.sh` |
| ArgoCD pass | `make argocd-pass` |
| Make help | `make help` |

## Key Files
- `src/ai_platform/main.py` — FastAPI app entrypoint
- `src/ai_platform/config.py` — Pydantic settings
- `src/ai_platform/dependencies.py` — FastAPI dependency injection
- `src/ai_platform/api/chat.py` — Chat endpoint
- `src/ai_platform/api/rag.py` — RAG endpoint
- `src/ai_platform/api/conversations.py` — Conversation CRUD
- `src/ai_platform/api/files.py` — File upload endpoint
- `src/ai_platform/api/file_extractors.py` — Document text extraction
- `src/ai_platform/api/health.py` — Health check
- `src/ai_platform/services/llm_client.py` — Groq LLM client
- `src/ai_platform/services/cache_service.py` — Redis cache layer
- `src/ai_platform/services/rag_service.py` — RAG with Qdrant
- `src/ai_platform/services/conversation_service.py` — Conversation persistence
- `src/ai_platform/models/conversation.py` — SQLAlchemy models
- `src/ai_platform/schemas/chat.py` — Chat request/response schemas
- `src/ai_platform/schemas/health.py` — Health schemas
- `src/ai_platform/db/` — Alembic config + env.py + 2 migrations (initial, add_conversation_title)
- `src/ai_platform/core/logging.py` — Structlog config
- `src/ai_platform/core/middleware.py` — Request middleware
- `src/ai_platform/core/telemetry.py` — OpenTelemetry setup
- `src/ai_platform/static/index.html` — Web UI (single-page)
- `src/tests/` — Tests: health, chat endpoint, llm_client, cache_service + conftest
- `src/scripts/seed_qdrant.py` — Vector DB seeder
- `docker/api/Dockerfile` — API container build
- `pyproject.toml` — Dependencies + ruff/pytest/mypy config
- `Makefile` — 14 dev commands
- `helm/ai-platform/` — Helm chart (deployment, service, HPA, PDB, ingress, canary, networkpolicy, secret)
- `helm/ai-platform/templates/api/job-migrate.yaml` — Helm hook: auto DB migration post-deploy
- `helm/ai-platform/templates/api/job-seed-qdrant.yaml` — Helm hook: auto Qdrant seeding post-deploy
- `helm/ai-platform/values.yaml` — Default Helm values
- `helm/ai-platform/values-dev.yaml` — Dev overrides (1 replica, reduced resources)
- `helm/ai-platform/values-prod.yaml` — Prod overrides (3 replicas, 20Gi storage)
- `k8s/kind/cluster-config.yaml` — KIND cluster config (3-node)
- `k8s/namespaces/` — Namespace + resource quota definitions
- `k8s/argocd/` — ArgoCD install + app-of-apps + app manifests
- `.github/workflows/` — ci.yml, release.yml, security.yml
- `monitoring/prometheus/` — Alert rules, ServiceMonitor, kube-prometheus-stack values
- `monitoring/grafana/` — API overview dashboard JSON + ConfigMap
- `monitoring/loki/` — Loki values
- `scripts/kind-setup.sh` — Full cluster bootstrap (KIND + ingress + ArgoCD + secrets + deploy)
- `scripts/port-forward.sh` — Port-forward services from KIND
- `docs/` — architecture.md, local-setup-guide.md, kubernetes-deployment-guide.md

## Do NOT
- Re-ask what is already in this file or MEMORY.md
- Repeat documented context back to the user
- Mix unrelated tasks in one response
- Add Claude as co-author on commits
- Suggest OpenRouter (user explicitly rejected it)
- Use Docker Compose for local dev (use KIND + port-forward instead)
