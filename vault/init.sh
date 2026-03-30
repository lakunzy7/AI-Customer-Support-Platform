#!/usr/bin/env bash
set -euo pipefail

# Initialize Vault for AI Platform
# Run after: helm install vault hashicorp/vault -n vault

echo "==> Waiting for Vault pod..."
kubectl wait --for=condition=ready pod/vault-0 -n vault --timeout=120s

echo "==> Initializing Vault..."
kubectl exec -n vault vault-0 -- vault operator init \
  -key-shares=1 -key-threshold=1 \
  -format=json > vault-keys.json

UNSEAL_KEY=$(jq -r '.unseal_keys_b64[0]' vault-keys.json)
ROOT_TOKEN=$(jq -r '.root_token' vault-keys.json)

echo "==> Unsealing Vault..."
kubectl exec -n vault vault-0 -- vault operator unseal "$UNSEAL_KEY"

echo "==> Enabling Kubernetes auth..."
kubectl exec -n vault vault-0 -- sh -c "
  export VAULT_TOKEN=$ROOT_TOKEN
  vault auth enable kubernetes
  vault write auth/kubernetes/config \
    kubernetes_host=https://kubernetes.default.svc
"

echo "==> Writing policy..."
kubectl cp vault/policy.hcl vault/vault-0:/tmp/policy.hcl
kubectl exec -n vault vault-0 -- sh -c "
  export VAULT_TOKEN=$ROOT_TOKEN
  vault policy write ai-platform /tmp/policy.hcl
"

echo "==> Creating Kubernetes auth role..."
kubectl exec -n vault vault-0 -- sh -c "
  export VAULT_TOKEN=$ROOT_TOKEN
  vault write auth/kubernetes/role/ai-platform \
    bound_service_account_names=default \
    bound_service_account_namespaces=ai-platform \
    policies=ai-platform \
    ttl=1h
"

echo "==> Storing secrets..."
kubectl exec -n vault vault-0 -- sh -c "
  export VAULT_TOKEN=$ROOT_TOKEN
  vault secrets enable -path=secret kv-v2 2>/dev/null || true
  vault kv put secret/ai-platform/openrouter \
    api-key=\${OPENROUTER_API_KEY:-changeme}
"

echo "==> Vault initialized. Root token saved to vault-keys.json"
echo "WARNING: Store vault-keys.json securely and delete from disk!"
