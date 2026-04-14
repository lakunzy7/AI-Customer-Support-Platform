#!/usr/bin/env bash
set -euo pipefail

# Re-seal secrets from .env using the current cluster's Sealed Secrets controller.
# Usage: bash scripts/seal-secret.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${ROOT_DIR}/.env"
SEALED_DIR="${ROOT_DIR}/k8s/sealed-secrets"
OUTPUT="${SEALED_DIR}/ai-platform-secrets.yaml"

# ── Preflight checks ────────────────────────────────────────────────────────
if ! command -v kubeseal &>/dev/null; then
  echo "ERROR: kubeseal CLI not found. Install it:"
  echo "  KUBESEAL_VERSION=0.27.3"
  echo "  curl -sSL https://github.com/bitnami-labs/sealed-secrets/releases/download/v\${KUBESEAL_VERSION}/kubeseal-\${KUBESEAL_VERSION}-linux-amd64.tar.gz | tar xz -C /tmp kubeseal"
  echo "  sudo mv /tmp/kubeseal /usr/local/bin/"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found at ${ENV_FILE}"
  echo "Create it with: echo 'LLM_API_KEY=gsk_your_key_here' > .env"
  exit 1
fi

LLM_KEY=$(grep '^LLM_API_KEY=' "$ENV_FILE" | cut -d'=' -f2-)
if [[ -z "$LLM_KEY" ]]; then
  echo "ERROR: LLM_API_KEY not found in .env"
  exit 1
fi

# ── Verify controller is running ────────────────────────────────────────────
echo "Checking Sealed Secrets controller..."
kubectl wait --namespace kube-system \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=sealed-secrets \
  --timeout=60s 2>/dev/null || {
    echo "ERROR: Sealed Secrets controller not ready in kube-system"
    exit 1
  }

# ── Fetch public cert and seal ──────────────────────────────────────────────
echo "Fetching sealing certificate..."
CERT=$(mktemp /tmp/sealed-secrets-cert.XXXXXX.pem)
kubeseal --fetch-cert \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  > "$CERT"

echo "Sealing secret from .env..."
mkdir -p "$SEALED_DIR"
kubectl create secret generic ai-platform-secrets \
  --namespace=ai-platform \
  --from-literal=llm-api-key="${LLM_KEY}" \
  --dry-run=client -o yaml | \
kubeseal --cert "$CERT" --format yaml > "$OUTPUT"

rm -f "$CERT"
echo "SealedSecret written to k8s/sealed-secrets/ai-platform-secrets.yaml"

# ── Optional: commit and push ───────────────────────────────────────────────
if git -C "$ROOT_DIR" diff --quiet k8s/sealed-secrets/ 2>/dev/null; then
  echo "SealedSecret unchanged — no commit needed"
else
  echo ""
  read -rp "Commit and push to Git? [y/N] " REPLY
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    git -C "$ROOT_DIR" add k8s/sealed-secrets/ai-platform-secrets.yaml
    git -C "$ROOT_DIR" commit -m "chore: re-seal ai-platform-secrets"
    git -C "$ROOT_DIR" push || echo "WARNING: git push failed — push manually"
  else
    echo "Skipped. Remember to commit and push for GitOps sync."
  fi
fi
