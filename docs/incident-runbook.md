# Incident Runbook

## Quick Reference

| Alert | Severity | Condition | First Action |
|-------|----------|-----------|-------------|
| HighErrorRate | Critical | 5xx > 5% for 5min | Check pod logs + LLM status |
| HighLatencyP95 | Warning | P95 > 2s for 5min | Check HPA + Redis cache |
| PodCrashLooping | Critical | > 3 restarts in 15min | Check describe + previous logs |
| LLMSlowResponse | Warning | LLM P95 > 10s for 5min | Check Groq status |

---

## Alert: HighErrorRate

**Severity**: Critical
**Condition**: 5xx error rate > 5% for 5 minutes
**Prometheus rule**: `ai_platform:http_requests:error_ratio_5m > 0.05`

### Diagnosis

```bash
# 1. Check pod status
kubectl get pods -n ai-platform

# 2. Check recent error logs
kubectl logs -n ai-platform -l app.kubernetes.io/component=api --tail=100 | grep -i error

# 3. Check readiness of all dependencies
curl http://localhost:8000/readyz
# Expected: {"status":"ok","checks":{"database":"ok","redis":"ok","qdrant":"ok"}}

# 4. Check if Groq LLM provider is down
curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY" | head

# 5. Check database connectivity
kubectl exec -n ai-platform deploy/ai-platform-api -- python -c "
import asyncio, asyncpg
asyncio.run(asyncpg.connect('postgresql://aiplatform:aiplatform@ai-platform-postgresql:5432/aiplatform'))
print('DB OK')
"

# 6. Check Redis connectivity
kubectl exec -n ai-platform deploy/ai-platform-redis -- redis-cli ping
```

### Resolution

| Root Cause | Action |
|-----------|--------|
| LLM provider down | Wait for recovery — cached responses still served from Redis |
| Database down | Check PostgreSQL pod logs and PVC status |
| Redis down | Check Redis pod — API still works but without caching |
| Qdrant down | RAG endpoint fails, chat endpoint unaffected |
| OOM errors | Scale up resources in Helm values |
| Bad deployment | Rollback (see rollback procedure below) |

---

## Alert: HighLatencyP95

**Severity**: Warning
**Condition**: P95 latency > 2 seconds for 5 minutes

### Diagnosis

```bash
# 1. Check HPA status (is it scaling?)
kubectl get hpa -n ai-platform

# 2. Check resource usage
kubectl top pods -n ai-platform

# 3. Check Redis cache hit rate
kubectl exec -n ai-platform deploy/ai-platform-redis -- redis-cli info stats | grep keyspace

# 4. Check if requests are being cached
kubectl logs -n ai-platform -l app.kubernetes.io/component=api --tail=50 | grep cache_hit
```

### Resolution

| Root Cause | Action |
|-----------|--------|
| Not enough replicas | Scale manually: `kubectl scale deploy/ai-platform-api -n ai-platform --replicas=5` |
| Cold cache (after restart) | Will warm naturally — no action needed |
| LLM is slow | Check Groq status page |
| HPA not scaling fast enough | Lower target thresholds in `values.yaml` → `api.autoscaling.targetCPU` |

---

## Alert: PodCrashLooping

**Severity**: Critical
**Condition**: > 3 restarts in 15 minutes

### Diagnosis

```bash
# 1. Check events for the crashing pod
kubectl describe pod -n ai-platform <pod-name>

# 2. Check logs from the previous crash
kubectl logs -n ai-platform <pod-name> --previous

# 3. Check resource limits (OOMKilled?)
kubectl get pod -n ai-platform <pod-name> -o jsonpath='{.spec.containers[0].resources}'

# 4. Check if it's a config error
kubectl get pod -n ai-platform <pod-name> -o jsonpath='{.status.containerStatuses[0].state}'
```

### Resolution

| Root Cause | Action |
|-----------|--------|
| OOMKilled | Increase memory limits in Helm values → `api.resources.limits.memory` |
| Config error | Check env vars — missing `LLM_API_KEY`, wrong `DATABASE_URL`, etc. |
| Readiness probe failing | Check dependency health (Redis, PostgreSQL, Qdrant pods) |
| Image pull error | Verify image tag exists in ghcr.io registry |

---

## Alert: LLMSlowResponse

**Severity**: Warning
**Condition**: LLM P95 > 10 seconds for 5 minutes

### Diagnosis

```bash
# 1. Check Groq API status
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $LLM_API_KEY" | python -m json.tool | head -20

# 2. Check if hitting rate limits (HTTP 429)
kubectl logs -n ai-platform -l app.kubernetes.io/component=api --tail=50 | grep -i "rate\|429"

# 3. Check which model is being used
kubectl get deploy ai-platform-api -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].env}' | python -m json.tool | grep -A1 MODEL
```

### Resolution

| Root Cause | Action |
|-----------|--------|
| Groq provider issue | Wait for recovery or switch model |
| Rate limited | Reduce concurrency or upgrade Groq plan |
| Model is inherently slow | Switch to a faster model via Helm: `--set api.llm.model="faster-model"` |

---

## General: Full Rollback Procedure

### Via Helm

```bash
# 1. View deployment history
helm history ai-platform -n ai-platform

# 2. Rollback to specific revision
helm rollback ai-platform <revision> -n ai-platform

# 3. Verify pods are healthy
kubectl get pods -n ai-platform
kubectl rollout status deployment/ai-platform-api -n ai-platform

# 4. Verify endpoints
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### Via ArgoCD

```bash
# 1. View sync history
argocd app history ai-platform

# 2. Rollback
argocd app rollback ai-platform

# 3. Or sync to a specific Git commit
argocd app sync ai-platform --revision <commit-sha>
```

### Canary Rollback

```bash
# Disable canary immediately (all traffic to stable)
helm upgrade ai-platform helm/ai-platform -n ai-platform \
  --set api.canary.enabled=false
```

---

## Escalation Matrix

| Level | Condition | Action |
|-------|-----------|--------|
| L1 | Single alert firing | Follow runbook steps above |
| L2 | Multiple alerts or rollback fails | Check infrastructure (nodes, PVCs, network) |
| L3 | Cluster-wide issue | Check KIND/K8s control plane, node status |

## Key Monitoring URLs

| Tool | Local Access |
|------|-------------|
| API Swagger | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (admin/admin) |
| ArgoCD | http://localhost:30080 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
