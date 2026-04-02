# Architecture

## System Overview

```
                    ┌──────────────┐
                    │   Ingress    │
                    │   (NGINX)    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │ (canary %) │ (stable %) │
              ▼            ▼            │
    ┌──────────────┐ ┌──────────────┐  │
    │  API Canary  │ │  API Stable  │  │
    │  (v2 model)  │ │  (v1 model)  │  │
    └──────┬───────┘ └──────┬───────┘  │
           └────────┬───────┘          │
                    │                  │
         ┌──────────┼──────────┐       │
         ▼          ▼          ▼       │
    ┌─────────┐ ┌────────┐ ┌────────┐ │
    │  Redis  │ │PostgreSQL│ │ Qdrant │ │
    │ (cache) │ │ (state) │ │(vectors)│ │
    └─────────┘ └────────┘ └────────┘ │
                                       │
              External                 │
    ┌──────────────────────────┐       │
    │      Groq API            │◄──────┘
    │  (LLM + Embeddings)      │
    └──────────────────────────┘
```

## Components

### FastAPI Application (81 files, 15 tests passing, 69% coverage)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Liveness probe — process is alive |
| `/readyz` | GET | Readiness probe — checks DB, Redis, Qdrant |
| `/v1/chat` | POST | Conversational AI with history persistence |
| `/v1/rag` | POST | RAG: embed → vector search → augmented LLM |
| `/docs` | GET | Swagger UI (dev environments only) |

### Services Layer

| Service | Responsibility |
|---------|---------------|
| `LLMClient` | Async httpx client for Groq (chat completions + embeddings) |
| `CacheService` | Redis cache with SHA-256 keys and configurable TTL |
| `ConversationService` | PostgreSQL conversation history via async SQLAlchemy |
| `RagService` | Full RAG pipeline: embed → Qdrant search → context-augmented LLM call |

### Data Stores

| Store | Purpose | K8s Resource |
|-------|---------|-------------|
| PostgreSQL 16 | Conversations + messages | StatefulSet + PVC |
| Redis 7 | Response cache (SHA-256 keys, TTL) | Deployment |
| Qdrant v1.12.5 | Vector store (FAQ embeddings, 1536-dim) | StatefulSet + PVC |

## Data Flow — Chat

```
Client → POST /v1/chat
  ├── 1. Check Redis cache (SHA-256 of message)
  │     ├── HIT → return cached response
  │     └── MISS ↓
  ├── 2. Load/create conversation in PostgreSQL
  ├── 3. Build message history
  ├── 4. Call Groq chat/completions API
  ├── 5. Cache response in Redis
  ├── 6. Persist assistant message to PostgreSQL
  └── 7. Return response + conversation_id
```

## Data Flow — RAG

```
Client → POST /v1/rag
  ├── 1. Check Redis cache (SHA-256 of question)
  │     ├── HIT → return cached answer
  │     └── MISS ↓
  ├── 2. Embed question via Groq embeddings API
  ├── 3. Search Qdrant for top-k similar documents
  ├── 4. Build context from retrieved documents
  ├── 5. Send augmented prompt to Groq chat API
  ├── 6. Cache result in Redis
  └── 7. Return answer + source documents
```

## Infrastructure

### Kubernetes (KIND for dev, managed K8s for prod)

| Resource | Component | Details |
|----------|-----------|---------|
| Deployment | API (stable) | 2 replicas (prod), HPA 2→10 based on CPU/memory |
| Deployment | API (canary) | 1 replica, weight-based routing via NGINX |
| Deployment | Redis | 1 replica |
| StatefulSet | PostgreSQL | 1 replica, 5Gi PVC (20Gi prod) |
| StatefulSet | Qdrant | 1 replica, 5Gi PVC (20Gi prod) |
| Ingress | NGINX | Canary annotations for traffic splitting |
| HPA | API | Scale on CPU (70%) and memory (80%) |
| PDB | API | minAvailable: 1 (dev), 2 (prod) |
| NetworkPolicy | API | Production only — restricts ingress/egress |
| ResourceQuota | Namespace | CPU: 4 req / 8 limit, Memory: 8Gi req / 16Gi limit |

### Helm Chart (values per environment)

| File | Environment | Key Differences |
|------|------------|-----------------|
| `values.yaml` | Default/prod | 2 replicas, HPA on, PDB on, rate limiting |
| `values-dev.yaml` | KIND/local | 1 replica, HPA off, PDB off, local images |
| `values-prod.yaml` | Production | 3 replicas, HPA 3→20, stricter limits, SSL |

### CI/CD Pipeline

```
Push to main
  ├── GitHub Actions CI
  │     ├── ruff lint + format check
  │     ├── pytest (15 tests, 69% coverage)
  │     ├── Docker build (multi-stage, non-root)
  │     ├── Push to ghcr.io (SHA tag + latest)
  │     └── Security scan (Trivy + pip-audit)
  └── ArgoCD (GitOps)
        ├── Watches repo for Helm chart changes
        ├── Auto-syncs to Kubernetes
        └── Self-heals on drift
```

### Observability Stack

| Tool | Purpose | Config Location |
|------|---------|----------------|
| OpenTelemetry | Traces (OTLP export) | `src/ai_platform/core/telemetry.py` |
| Prometheus | Metrics + alert rules | `monitoring/prometheus/alert-rules.yaml` |
| Grafana | Dashboards | `monitoring/grafana/dashboards/api-overview.json` |
| Loki + Promtail | Centralized logs | `monitoring/loki/values.yaml` |

### Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | 5xx > 5% for 5min | Critical |
| HighLatencyP95 | P95 > 2s for 5min | Warning |
| PodCrashLooping | > 3 restarts in 15min | Critical |
| LLMSlowResponse | LLM P95 > 10s for 5min | Warning |

### Security

| Component | Description |
|-----------|-------------|
| HashiCorp Vault | Secret storage with Kubernetes auth |
| External Secrets Operator | Syncs Vault secrets → K8s secrets |
| Network Policies | Restrict API pod ingress/egress (prod only) |
| Resource Quotas | Namespace-level CPU/memory/pod limits |
| Non-root containers | Dockerfile uses dedicated `appuser` |
| Trivy | Container image vulnerability scanning |
| pip-audit | Python dependency vulnerability scanning |

## Deployment Models

### Standard
Single model version serving all traffic via stable Deployment.

### Canary
Two deployments (stable + canary) with NGINX ingress weight-based routing.
Adjust `api.canary.weight` in Helm values to shift traffic (e.g., 10% → 50% → 100%).

```yaml
# Enable canary in values
api:
  canary:
    enabled: true
    weight: 10          # 10% traffic to canary
    model: "new-model"  # Different model for canary
```

### Rollback
- **ArgoCD**: Instant rollback to any previous Git commit state
- **Helm**: `helm rollback ai-platform <revision> -n ai-platform`
