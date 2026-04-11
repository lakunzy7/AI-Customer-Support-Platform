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

echo "==> Deploying App-of-Apps..."
kubectl apply -f "${ROOT_DIR}/k8s/argocd/app-of-apps.yaml"

echo "==> Waiting for ArgoCD to sync ai-platform app..."
sleep 30
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=ai-platform-api \
  -n ai-platform --timeout=300s 2>/dev/null || echo "  (app may still be syncing — check ArgoCD UI)"

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
