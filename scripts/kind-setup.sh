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

# ── Wait for Sealed Secrets controller (deployed by ArgoCD) ─────────────────
echo "==> Waiting for Sealed Secrets controller..."
echo "  (ArgoCD is syncing the sealed-secrets app — this may take 1-2 minutes)"
for i in $(seq 1 60); do
  if kubectl get pod -n kube-system -l app.kubernetes.io/name=sealed-secrets -o name 2>/dev/null | grep -q pod; then
    break
  fi
  sleep 3
done
kubectl wait --namespace kube-system \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=sealed-secrets \
  --timeout=180s

# ── Install kubeseal CLI if missing ─────────────────────────────────────────
if ! command -v kubeseal &>/dev/null; then
  echo "==> Installing kubeseal CLI..."
  KUBESEAL_VERSION="0.27.3"
  curl -sSL "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz" | \
    tar xz -C /tmp kubeseal
  sudo mv /tmp/kubeseal /usr/local/bin/
  echo "  kubeseal ${KUBESEAL_VERSION} installed"
fi

# ── Seal secrets from .env ──────────────────────────────────────────────────
ENV_FILE="${ROOT_DIR}/.env"
SEALED_DIR="${ROOT_DIR}/k8s/sealed-secrets"
SEALED_FILE="${SEALED_DIR}/ai-platform-secrets.yaml"

if [[ -f "$ENV_FILE" ]]; then
  LLM_KEY=$(grep '^LLM_API_KEY=' "$ENV_FILE" | cut -d'=' -f2-)
  if [[ -n "$LLM_KEY" ]]; then
    echo "==> Sealing secrets from .env..."
    CERT=$(mktemp /tmp/sealed-secrets-cert.XXXXXX.pem)
    kubeseal --fetch-cert \
      --controller-name=sealed-secrets-controller \
      --controller-namespace=kube-system \
      > "$CERT"

    mkdir -p "$SEALED_DIR"
    kubectl create secret generic ai-platform-secrets \
      --namespace=ai-platform \
      --from-literal=llm-api-key="${LLM_KEY}" \
      --dry-run=client -o yaml | \
    kubeseal --cert "$CERT" --format yaml > "$SEALED_FILE"

    rm -f "$CERT"
    echo "  SealedSecret written to k8s/sealed-secrets/ai-platform-secrets.yaml"

    # Apply immediately so the current cluster has the secret now
    kubectl apply -f "$SEALED_FILE"
    echo "  SealedSecret applied to cluster"

    # Commit and push so ArgoCD can sync it on future deploys
    if ! git -C "$ROOT_DIR" diff --quiet k8s/sealed-secrets/ 2>/dev/null; then
      echo "==> Committing SealedSecret to Git..."
      git -C "$ROOT_DIR" add k8s/sealed-secrets/ai-platform-secrets.yaml
      git -C "$ROOT_DIR" commit -m "chore: seal ai-platform-secrets for current cluster"
      git -C "$ROOT_DIR" push || echo "  WARNING: git push failed — push manually"
    fi
  else
    echo "  WARNING: LLM_API_KEY not found in .env — chat will fail"
  fi
else
  echo "  WARNING: .env file not found — create one with LLM_API_KEY"
fi

# ── Wait for API pods ───────────────────────────────────────────────────────
echo "==> Waiting for AI platform pods..."
sleep 15
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=ai-platform,app.kubernetes.io/component=api \
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
