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
    │    OpenRouter API        │◄──────┘
    │  (LLM + Embeddings)      │
    └──────────────────────────┘
```

## Components

### FastAPI Application
- **Health endpoints**: `/healthz` (liveness), `/readyz` (readiness with dependency checks)
- **Chat endpoint**: `POST /v1/chat` — conversational AI with history persistence
- **RAG endpoint**: `POST /v1/rag` — retrieval-augmented generation from FAQ knowledge base

### Data Flow — Chat
1. Client sends message to `POST /v1/chat`
2. Check Redis cache (SHA-256 keyed) for cached response
3. Load/create conversation in PostgreSQL
4. Build message history and call OpenRouter API
5. Cache response in Redis, persist to PostgreSQL
6. Return response with conversation ID

### Data Flow — RAG
1. Client sends question to `POST /v1/rag`
2. Check Redis cache for cached answer
3. Embed question via OpenRouter embeddings API
4. Search Qdrant for top-k similar documents
5. Augment prompt with retrieved context
6. Call OpenRouter chat API for final answer
7. Cache and return

### Infrastructure
- **Kubernetes**: KIND (dev) / managed K8s (prod)
- **Helm**: Umbrella chart with API, Redis, PostgreSQL, Qdrant templates
- **CI/CD**: GitHub Actions → ghcr.io → ArgoCD (GitOps)
- **Observability**: Prometheus + Grafana + Loki + OpenTelemetry
- **Secrets**: HashiCorp Vault + External Secrets Operator

## Deployment Models

### Standard
Single model version serving all traffic.

### Canary
Two deployments (stable + canary) with NGINX ingress weight-based routing.
Adjust `api.canary.weight` in Helm values to shift traffic (e.g., 10% → 50% → 100%).

### Rollback
ArgoCD supports instant rollback to any previous Git commit state.
