# Incident Runbook

## Alert: HighErrorRate
**Severity**: Critical
**Condition**: 5xx error rate > 5% for 5 minutes

### Diagnosis
```bash
# Check pod status
kubectl get pods -n ai-platform

# Check recent logs
kubectl logs -n ai-platform -l app.kubernetes.io/component=api --tail=100

# Check if LLM provider is down
curl -s https://openrouter.ai/api/v1/models -H "Authorization: Bearer $OPENROUTER_API_KEY" | head

# Check database connectivity
kubectl exec -n ai-platform deploy/ai-platform-api -- python -c "
import asyncio, asyncpg
asyncio.run(asyncpg.connect('postgresql://aiplatform:aiplatform@ai-platform-postgresql:5432/aiplatform'))
print('DB OK')
"
```

### Resolution
1. If LLM provider is down → wait for recovery (cached responses still served)
2. If database is down → check PostgreSQL pod logs, PVC status
3. If OOM → scale up resources or add replicas
4. If deployment is bad → rollback:
```bash
# ArgoCD rollback
argocd app rollback ai-platform

# Or Helm rollback
helm rollback ai-platform -n ai-platform
```

---

## Alert: HighLatencyP95
**Severity**: Warning
**Condition**: P95 latency > 2 seconds for 5 minutes

### Diagnosis
```bash
# Check HPA status
kubectl get hpa -n ai-platform

# Check resource usage
kubectl top pods -n ai-platform

# Check Redis cache hit rate
kubectl exec -n ai-platform deploy/ai-platform-redis -- redis-cli info stats | grep keyspace
```

### Resolution
1. Scale API replicas: `kubectl scale deploy/ai-platform-api -n ai-platform --replicas=5`
2. Check if cache is cold (after restart) — will warm naturally
3. If LLM is slow → check OpenRouter status page
4. Lower HPA thresholds for faster scaling

---

## Alert: PodCrashLooping
**Severity**: Critical
**Condition**: > 3 restarts in 15 minutes

### Diagnosis
```bash
# Check events
kubectl describe pod -n ai-platform <pod-name>

# Check logs from previous crash
kubectl logs -n ai-platform <pod-name> --previous

# Check resource limits
kubectl get pod -n ai-platform <pod-name> -o jsonpath='{.spec.containers[0].resources}'
```

### Resolution
1. OOMKilled → increase memory limits in Helm values
2. CrashLoopBackOff → check startup logs for config errors
3. Readiness probe failing → check dependency health (Redis, PostgreSQL, Qdrant)

---

## Alert: LLMSlowResponse
**Severity**: Warning
**Condition**: LLM P95 > 10 seconds

### Diagnosis
```bash
# Check OpenRouter status
curl -s https://openrouter.ai/api/v1/models | python -m json.tool | head -20

# Check if we're hitting rate limits
kubectl logs -n ai-platform -l app.kubernetes.io/component=api --tail=50 | grep -i "rate\|429"
```

### Resolution
1. OpenRouter provider issue → wait or switch model
2. Rate limited → reduce concurrency or upgrade plan
3. Consider switching to a faster model temporarily

---

## General: Full Rollback Procedure

```bash
# 1. Identify last known good version
helm history ai-platform -n ai-platform

# 2. Rollback to specific revision
helm rollback ai-platform <revision> -n ai-platform

# 3. Verify
kubectl get pods -n ai-platform
curl http://localhost:8000/healthz
```
