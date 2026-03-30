#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="ai-platform"

echo "Port-forwarding services..."
echo "  API:      http://localhost:8000"
echo "  Qdrant:   http://localhost:6333"
echo ""
echo "Press Ctrl+C to stop."

kubectl port-forward -n "$NAMESPACE" svc/ai-platform-api 8000:8000 &
kubectl port-forward -n "$NAMESPACE" svc/ai-platform-qdrant 6333:6333 &

wait
