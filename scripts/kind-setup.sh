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

echo "==> Loading local Docker image into KIND..."
docker build -t ai-platform:local -f "${ROOT_DIR}/docker/api/Dockerfile" "${ROOT_DIR}"
kind load docker-image ai-platform:local --name "${CLUSTER_NAME}"

echo "==> Installing Helm chart..."
helm upgrade --install ai-platform "${ROOT_DIR}/helm/ai-platform" \
  -n ai-platform \
  -f "${ROOT_DIR}/helm/ai-platform/values-dev.yaml" \
  --wait --timeout 180s

echo "==> Cluster ready! Pods:"
kubectl get pods -n ai-platform

echo ""
echo "Access the API at http://localhost (via ingress)"
echo "Or use: make port-forward"
