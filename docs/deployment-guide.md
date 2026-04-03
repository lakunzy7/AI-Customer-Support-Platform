# Deployment Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Git | 2.x | Clone the repository |
| Python | 3.11+ | Application runtime |
| Docker | 24+ | Containerization |
| Docker Compose | 2.x | Local multi-service orchestration |
| kubectl | 1.28+ | Kubernetes CLI |
| Helm | 3.x | Package manager |
| KIND | 0.20+ | Local Kubernetes cluster |
| gh | 2.x | GitHub CLI (optional) |

## 1. Clone the Repository

```bash
git clone https://github.com/lakunzy7/AI-Customer-Support-Platform.git
cd AI-Customer-Support-Platform
```

## 2. Get a Groq API Key

1. Go to https://console.groq.com/keys
2. Sign up (free) and create a new API key
3. Copy the key — it starts with `gsk_`

## 3. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and set your Groq API key
# Replace the placeholder with your actual key:
#   LLM_API_KEY=gsk_your-actual-key-here
```

Your `.env` should look like:
```
LLM_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

## 4. Run with Docker Compose

```bash
# Start all services (API + PostgreSQL + Redis + Qdrant)
docker compose up -d

# Wait for services to be healthy (about 15 seconds)
# Then verify everything is running
docker compose ps

# Check health
curl http://localhost:8000/healthz
# → {"status":"ok"}

curl http://localhost:8000/readyz
# → {"status":"ok","checks":{"database":"ok","redis":"ok","qdrant":"ok"}}
```

### Services started

| Service | Port | URL |
|---------|------|-----|
| API + Web UI | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | `postgresql://aiplatform:aiplatform@localhost:5432/aiplatform` |
| Redis | 6379 | `redis://localhost:6379/0` |
| Qdrant | 6333 | http://localhost:6333 |

## 5. Open the Web UI

Open your browser and go to:

```
http://localhost:8000
```

You'll see the ChatGPT-style interface with:
- Chat area with markdown rendering and code highlighting
- Sidebar with conversation history
- Voice input button (microphone)
- File upload button (paperclip)

## 6. Test the API Endpoints

### Chat

```bash
# Send a message
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your return policy?"}'

# Continue a conversation
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Can you explain more?", "conversation_id": "<id-from-above>"}'
```

### File Upload

```bash
# Upload a file
curl -F "file=@document.pdf" http://localhost:8000/v1/upload
# → {"file_id":"01KN...","filename":"document.pdf","size":1234,"ext":".pdf"}

# Chat about the file
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize this document", "file_ids": ["01KN..."]}'

# Download a file
curl http://localhost:8000/v1/files/01KN... -o downloaded.pdf
```

### Conversations

```bash
# List all conversations
curl http://localhost:8000/v1/conversations

# Get messages from a conversation
curl http://localhost:8000/v1/conversations/<id>/messages

# Rename a conversation
curl -X PATCH http://localhost:8000/v1/conversations/<id> \
  -H "Content-Type: application/json" \
  -d '{"title": "My custom title"}'

# Delete a conversation
curl -X DELETE http://localhost:8000/v1/conversations/<id>
```

### RAG (Knowledge Base)

```bash
# Seed Qdrant with FAQ data first
make seed

# Query the knowledge base
curl -X POST http://localhost:8000/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reset my password?"}'
```

### Swagger UI

```
http://localhost:8000/docs
```

## 7. Run Tests Locally

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests (15 tests, 69% coverage)
pytest -v --cov=src/ai_platform --cov-report=term-missing

# Lint
ruff check src/ tests/
ruff format --check src/ tests/
```

**Expected output**: 15 passed, 69% coverage

### Dev Mode (hot reload)

The `docker-compose.override.yml` mounts `src/` into the container and enables `--reload`. Code changes are reflected immediately without rebuilding.

## 8. KIND Cluster Deployment

### One-command setup

```bash
make kind-up
```

This runs `scripts/kind-setup.sh` which:
1. Creates a 3-node KIND cluster (1 control-plane + 2 workers)
2. Installs NGINX Ingress Controller
3. Creates namespaces (ai-platform, monitoring, argocd)
4. Builds and loads the Docker image into KIND
5. Deploys with Helm using `values-dev.yaml`

### Step-by-step setup

```bash
# Create cluster
kind create cluster --config k8s/kind/cluster-config.yaml

# Create namespaces
kubectl apply -f k8s/namespaces/

# Build and load image
docker build -t ai-platform:local -f docker/api/Dockerfile .
kind load docker-image ai-platform:local --name ai-platform

# Deploy with Helm
helm upgrade --install ai-platform helm/ai-platform \
  -n ai-platform -f helm/ai-platform/values-dev.yaml --wait

# Verify pods are running
kubectl get pods -n ai-platform

# Access via port-forward
make port-forward
# API → http://localhost:8000
# Qdrant → http://localhost:6333
```

### Tear down

```bash
make kind-down
```

## 9. Production Deployment

### With ArgoCD (GitOps)

```bash
# Install ArgoCD
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd -n argocd --create-namespace \
  -f k8s/argocd/install.yaml

# Apply app-of-apps (manages all applications)
kubectl apply -f k8s/argocd/app-of-apps.yaml

# ArgoCD will now auto-sync:
#   - ai-platform (Helm chart)
#   - monitoring (kube-prometheus-stack)
```

The GitOps flow:
```
Push to main → GitHub Actions CI → Build + push image → ArgoCD detects change → Auto-sync to cluster
```

### With Vault Secrets

```bash
# Install Vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace

# Initialize Vault (creates unseal key, enables K8s auth, writes policy)
bash vault/init.sh

# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace

# Apply SecretStore + ExternalSecret
kubectl apply -f vault/external-secret.yaml

# Verify secrets are synced
kubectl get externalsecret -n ai-platform
```

### Canary Deployment

Canary routing uses NGINX ingress annotations to split traffic between stable and canary deployments.

```bash
# Step 1: Enable canary with 10% traffic
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.canary.enabled=true \
  --set api.canary.weight=10 \
  --set api.canary.model="new-model-to-test"

# Step 2: Monitor metrics in Grafana, check error rates

# Step 3: Increase to 50%
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.canary.weight=50

# Step 4: Full rollout (promote canary → stable)
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.llm.model="llama-3.3-70b-versatile" \
  --set api.canary.enabled=false

# Rollback if needed
helm rollback ai-platform -n ai-platform
```

## 10. Monitoring Setup

```bash
# Prometheus + Grafana
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

# Apply custom alert rules (error rate, latency, crashes, LLM latency)
kubectl apply -f monitoring/prometheus/alert-rules.yaml

# Loki for centralized logs
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack -n monitoring \
  -f monitoring/loki/values.yaml

# Access Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# Login: admin / admin
# Import dashboard from monitoring/grafana/dashboards/api-overview.json
```

### Grafana Dashboard Panels

The `api-overview.json` dashboard includes:
- Request rate (req/s)
- Error rate (%)
- Latency percentiles (P50, P95, P99)
- LLM request duration (P95)
- Active pod count
- CPU usage per pod
- Memory usage per pod

## 11. Stopping & Cleanup

```bash
# Stop Docker containers
docker compose down

# Stop and remove all data (volumes)
docker compose down -v

# Delete KIND cluster
make kind-down
```

## Make Commands Reference

```
make help           Show all available commands
make install        Install production dependencies
make dev            Install development dependencies (includes test + lint tools)
make lint           Run linters (ruff check + format check)
make format         Auto-format code (ruff fix + format)
make test           Run tests with coverage (15 tests, 69% coverage)
make run            Run development server (uvicorn with --reload)
make docker-up      Start all services with docker-compose
make docker-down    Stop all services and remove volumes
make migrate        Run Alembic database migrations
make seed           Seed Qdrant with sample FAQ data
make kind-up        Create KIND cluster and deploy everything
make kind-down      Delete KIND cluster
make port-forward   Port-forward services from KIND cluster
```
