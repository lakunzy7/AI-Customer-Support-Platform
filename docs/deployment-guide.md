# Deployment Guide

## Prerequisites
- Docker
- kubectl
- Helm 3
- KIND (for local dev)

## Local Development (docker-compose)

```bash
# Copy env vars and set your OpenRouter API key
cp .env.example .env
# Edit .env with your OPENROUTER_API_KEY

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
```

## KIND Cluster Deployment

```bash
# Create cluster + deploy everything
make kind-up

# Or step-by-step:
kind create cluster --config k8s/kind/cluster-config.yaml
kubectl apply -f k8s/namespaces/

# Build and load image
docker build -t ai-platform:local -f docker/api/Dockerfile .
kind load docker-image ai-platform:local --name ai-platform

# Deploy with Helm
helm upgrade --install ai-platform helm/ai-platform \
  -n ai-platform -f helm/ai-platform/values-dev.yaml --wait

# Access via port-forward
bash scripts/port-forward.sh
```

## Production Deployment

### With ArgoCD (GitOps)

```bash
# Install ArgoCD
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd -n argocd --create-namespace \
  -f k8s/argocd/install.yaml

# Apply app-of-apps
kubectl apply -f k8s/argocd/app-of-apps.yaml

# ArgoCD will now sync from Git automatically
```

### With Vault Secrets

```bash
# Install Vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace

# Initialize and configure
bash vault/init.sh

# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace

# Apply external secret config
kubectl apply -f vault/external-secret.yaml
```

### Canary Deployment

```bash
# Enable canary with 10% traffic
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.canary.enabled=true \
  --set api.canary.weight=10 \
  --set api.canary.model="anthropic/claude-sonnet-4-20250514"

# Increase to 50%
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.canary.weight=50

# Full rollout (promote canary to stable)
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.openrouter.model="anthropic/claude-sonnet-4-20250514" \
  --set api.canary.enabled=false
```

## Monitoring Setup

```bash
# Prometheus + Grafana (via ArgoCD or manual)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

# Apply alert rules
kubectl apply -f monitoring/prometheus/alert-rules.yaml

# Loki for logs
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack -n monitoring \
  -f monitoring/loki/values.yaml

# Access Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# Default: admin / admin
# Import dashboards from monitoring/grafana/dashboards/
```
