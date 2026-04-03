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

### FastAPI Application (90+ files, 15 tests passing, 69% coverage)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | ChatGPT-style web UI |
| `/healthz` | GET | Liveness probe — process is alive |
| `/readyz` | GET | Readiness probe — checks DB, Redis, Qdrant |
| `/v1/chat` | POST | Conversational AI with history, file context, auto-title |
| `/v1/conversations` | GET | List conversations with auto-generated titles |
| `/v1/conversations/{id}/messages` | GET | Full message history for a conversation |
| `/v1/conversations/{id}` | PATCH | Rename a conversation |
| `/v1/conversations/{id}` | DELETE | Delete a conversation (cascades messages) |
| `/v1/upload` | POST | Upload files (text, code, PDF, images — max 10MB) |
| `/v1/files/{id}` | GET | Download an uploaded file |
| `/v1/rag` | POST | RAG: embed → vector search → augmented LLM |
| `/docs` | GET | Swagger UI (dev environments only) |

### Services Layer

| Service | Responsibility |
|---------|---------------|
| `LLMClient` | Async httpx client for Groq (chat completions + embeddings) |
| `CacheService` | Redis cache with SHA-256 keys and configurable TTL |
| `ConversationService` | PostgreSQL conversation CRUD + title management via async SQLAlchemy |
| `RagService` | Full RAG pipeline: embed → Qdrant search → context-augmented LLM call |

### Data Stores

| Store | Purpose | K8s Resource |
|-------|---------|-------------|
| PostgreSQL 16 | Conversations + messages + titles | StatefulSet + PVC |
| Redis 7 | Response cache (SHA-256 keys, TTL) | Deployment |
| Qdrant v1.12.5 | Vector store (FAQ embeddings, 1536-dim) | StatefulSet + PVC |
| File Storage | Uploaded files + metadata (Docker volume) | PersistentVolume |

## Data Flow — Chat

```
Client → POST /v1/chat { message, conversation_id?, file_ids? }
  ├── 1. Check Redis cache (SHA-256 of message)
  │     ├── HIT → return cached response
  │     └── MISS ↓
  ├── 2. Load/create conversation in PostgreSQL
  ├── 3. Build message history
  ├── 4. If file_ids: read file contents (text or PDF via PyMuPDF)
  │     └── Inject file text as LLM context message
  ├── 5. Call Groq chat/completions API
  ├── 6. Cache response in Redis
  ├── 7. Persist assistant message to PostgreSQL
  ├── 8. If new conversation: auto-generate title (background task)
  └── 9. Return response + conversation_id
```

## Data Flow — File Upload

```
Client → POST /v1/upload (multipart form)
  ├── 1. Validate file type and size (max 10MB)
  ├── 2. Save file to /tmp/ai-platform-uploads/<ULID>.<ext>
  ├── 3. Save metadata to <ULID>.meta.json (original filename)
  └── 4. Return file_id for use in chat
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

## Web UI

The platform serves a ChatGPT-style single-page application at `/` built with vanilla HTML/CSS/JS.

| Feature | Implementation |
|---------|---------------|
| Markdown rendering | marked.js — headings, lists, tables, blockquotes, links |
| Code highlighting | highlight.js — syntax-highlighted code blocks with copy button |
| Sidebar | Conversation history — list, load, rename, delete |
| Auto-title | Background LLM call generates 3-5 word title after first reply |
| Voice input | Web Speech API (browser-native, Chrome/Edge/Safari) |
| File upload | Attach button, preview chips, PDF text extraction via PyMuPDF |
| Mobile responsive | Hamburger toggle for sidebar, adaptive layout |

### Supported File Types

| Category | Extensions |
|----------|-----------|
| Text/code | .txt, .md, .csv, .json, .xml, .yaml, .py, .js, .ts, .html, .css, .sql, .sh, .log |
| Documents | .pdf (text extracted via PyMuPDF, up to 8000 chars) |
| Images | .png, .jpg, .jpeg, .gif, .webp (stored, not analyzed by LLM) |

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
