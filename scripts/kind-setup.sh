#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="ai-platform"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Creating KIND cluster '${CLUSTER_NAME}'..."
kind create cluster --config "${ROOT_DIR}/k8s/kind/cluster-config.yaml" --wait 60s

echo "==> Installing NGINX Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "==> Waiting for Ingress controller to be ready..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

echo "==> Creating namespaces..."
kubectl apply -f "${ROOT_DIR}/k8s/namespaces/"

echo "==> Installing ArgoCD..."
helm repo add argo https://argoproj.github.io/argo-helm 2>/dev/null || true
helm repo update
helm upgrade --install argocd argo/argo-cd -n argocd \
  -f "${ROOT_DIR}/k8s/argocd/install.yaml" \
  --wait --timeout 180s

echo "==> Waiting for ArgoCD server to be ready..."
kubectl wait --namespace argocd \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=argocd-server \
  --timeout=120s

echo "==> Seeding secrets from .env..."
ENV_FILE="${ROOT_DIR}/.env"
if [[ -f "$ENV_FILE" ]]; then
  LLM_KEY=$(grep '^LLM_API_KEY=' "$ENV_FILE" | cut -d'=' -f2-)
  if [[ -n "$LLM_KEY" ]]; then
    kubectl create secret generic ai-platform-secrets -n ai-platform \
      --from-literal=llm-api-key="$LLM_KEY" \
      --dry-run=client -o yaml | kubectl apply -f -
    echo "  Secret seeded from .env"
  else
    echo "  WARNING: LLM_API_KEY not found in .env — chat will fail"
  fi
else
  echo "  WARNING: .env file not found — create one with LLM_API_KEY"
fi

echo "==> Deploying App-of-Apps..."
kubectl apply -f "${ROOT_DIR}/k8s/argocd/app-of-apps.yaml"

echo "==> Waiting for ArgoCD to sync ai-platform app..."
sleep 30
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=ai-platform-api \
  -n ai-platform --timeout=300s 2>/dev/null || echo "  (app may still be syncing — check ArgoCD UI)"

echo "==> Running database migrations..."
kubectl exec -n ai-platform deploy/ai-platform-api -- python3 -c "
from alembic.config import Config
from alembic import command
cfg = Config('src/ai_platform/db/alembic.ini')
cfg.set_main_option('sqlalchemy.url', 'postgresql+asyncpg://aiplatform:aiplatform@ai-platform-postgresql:5432/aiplatform')
command.upgrade(cfg, 'head')
" 2>/dev/null || echo "  (migrations may need manual run — check DB connectivity)"

ARGOCD_PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

echo ""
echo "==> Cluster ready!"
echo ""
kubectl get pods -n ai-platform
echo ""
echo "ArgoCD UI:  http://localhost:30080"
echo "  User:     admin"
echo "  Password: ${ARGOCD_PASS}"
echo ""
echo "API:        http://localhost:8000 (use: make port-forward)"
