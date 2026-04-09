# Kubernetes Deployment Guide (KIND)

A beginner-friendly, step-by-step guide to deploy the AI Customer Support Platform on a local Kubernetes cluster using KIND (Kubernetes in Docker). No Kubernetes experience needed — just copy and paste each command.

---

## What You'll Learn

By the end of this guide, you'll have:

- A 3-node Kubernetes cluster running on your machine
- The full AI platform (API + PostgreSQL + Redis + Qdrant) running in K8s pods
- NGINX Ingress routing traffic to your app
- The web chat accessible from your browser

---

## Prerequisites

Before starting, make sure you have:

| Tool | Why You Need It | How to Check |
|------|----------------|--------------|
| **Docker** | KIND runs K8s nodes as Docker containers | `docker --version` |
| **Git** | Clone the project | `git --version` |
| **curl** | Download tools and test endpoints | `curl --version` |
| **sudo access** | Install tools to `/usr/local/bin` | `sudo whoami` (should print `root`) |

> **Important:** The project must already be cloned and you should have a Groq API key ready (see the [Local Setup Guide](local-setup-guide.md) Steps 1-2 if you don't).

---

## Architecture Overview

Here's what we're building:

```
Your Browser
     |
     v
[ NGINX Ingress Controller ]  <-- Runs on control-plane node, ports 80/443
     |
     v
[ ai-platform-api Pod ]       <-- FastAPI app (your Docker image)
     |
     +---> [ PostgreSQL Pod ]  <-- Stores conversations (StatefulSet + PVC)
     +---> [ Redis Pod ]       <-- Caches responses (Deployment)
     +---> [ Qdrant Pod ]      <-- Vector search (StatefulSet + PVC)
```

All running inside a KIND cluster with **1 control-plane node** and **2 worker nodes**.

---

## Step 1: Install KIND, kubectl, and Helm

These are the three tools you need to manage Kubernetes:

| Tool | What It Does |
|------|-------------|
| **KIND** | Creates a Kubernetes cluster using Docker containers as nodes |
| **kubectl** | Talks to the Kubernetes cluster (deploy, inspect, debug) |
| **Helm** | Packages and deploys applications using templates (like `docker compose` for K8s) |

### Install KIND

```bash
# Download KIND v0.24.0
curl -Lo /tmp/kind https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64

# Make it executable and move to PATH
chmod +x /tmp/kind
sudo mv /tmp/kind /usr/local/bin/kind

# Verify
kind version
```

Expected output:
```
kind v0.24.0 go1.22.6 linux/amd64
```

### Install kubectl

```bash
# Download kubectl v1.31.0
curl -Lo /tmp/kubectl "https://dl.k8s.io/release/v1.31.0/bin/linux/amd64/kubectl"

# Make it executable and move to PATH
chmod +x /tmp/kubectl
sudo mv /tmp/kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

Expected output:
```
Client Version: v1.31.0
```

### Install Helm

```bash
# Download and install Helm 3 (official script)
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
```

Expected output (version may vary):
```
version.BuildInfo{Version:"v3.20.x", ...}
```

> **macOS users:** Replace `linux-amd64` with `darwin-amd64` (Intel) or `darwin-arm64` (Apple Silicon) in the KIND and kubectl URLs. Helm's install script auto-detects your OS.

---

## Step 2: Create the KIND Cluster

The project includes a pre-configured cluster definition at `k8s/kind/cluster-config.yaml`. It creates:

- **1 control-plane node** with port mappings for ingress (ports 80, 443, 30000)
- **2 worker nodes** for running your application pods

### Create the cluster

```bash
# Navigate to the project root
cd /path/to/AI-Customer-Support-Platform

# Make sure ports 80 and 443 are free
sudo ss -tlnp | grep -E ':80 |:443 '
# If anything shows up, stop that service first

# Create the cluster (takes 1-3 minutes)
kind create cluster --config k8s/kind/cluster-config.yaml
```

Expected output:
```
Creating cluster "ai-platform" ...
 ✓ Ensuring node image (kindest/node:v1.31.0) 🖼
 ✓ Preparing nodes 📦 📦 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
 ✓ Joining worker nodes 🚜
Set kubectl context to "kind-ai-platform"
```

### Verify all nodes are ready

```bash
# Wait for all nodes (up to 2 minutes)
kubectl wait --for=condition=Ready nodes --all --timeout=120s

# Check node status
kubectl get nodes
```

Expected output:
```
NAME                        STATUS   ROLES           AGE   VERSION
ai-platform-control-plane   Ready    control-plane   60s   v1.31.0
ai-platform-worker          Ready    <none>          45s   v1.31.0
ai-platform-worker2         Ready    <none>          45s   v1.31.0
```

> **What just happened?** KIND created 3 Docker containers, each acting as a Kubernetes node. Inside each container runs a full K8s node with kubelet, container runtime, etc. Run `docker ps` to see them.

---

## Step 3: Install the NGINX Ingress Controller

The Ingress Controller is what routes HTTP traffic from outside the cluster to your application pods. Without it, your app is only accessible inside the cluster.

```bash
# Install the KIND-specific NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for it to be ready (up to 2 minutes)
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

Expected output:
```
pod/ingress-nginx-controller-xxxxx condition met
```

### Fix: Ingress controller scheduling (if needed)

The ingress controller **must** run on the control-plane node (where ports 80/443 are mapped). If it schedules elsewhere, traffic won't reach it.

```bash
# Check where it landed
kubectl get pods -n ingress-nginx -o wide
```

If the `NODE` column does NOT show `ai-platform-control-plane`, fix it:

```bash
# Force it to the control-plane node
kubectl patch deployment ingress-nginx-controller -n ingress-nginx --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/nodeSelector", "value": {"kubernetes.io/os": "linux", "ingress-ready": "true"}}]'

# If it gets stuck in Pending due to CPU limits, reduce its CPU request
kubectl patch deployment ingress-nginx-controller -n ingress-nginx --type=json \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "25m"}]'

# Wait for it to be ready again
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

> **Why does this happen?** The control-plane node runs system pods (CoreDNS, kube-proxy, etcd, scheduler, controller-manager) which already consume most of the CPU budget. Lowering the ingress controller's CPU request to 25m is fine for local development.

---

## Step 4: Build and Load the Docker Image

Kubernetes pulls container images to run your app. In a cloud environment, you'd push to a registry (like Docker Hub or GHCR). With KIND, we build locally and load the image directly into the cluster.

### Build the image

```bash
# From the project root directory
docker build -t ai-platform:local -f docker/api/Dockerfile .
```

This takes 2-5 minutes the first time (it downloads Python packages). Expected last line:
```
Successfully tagged ai-platform:local
```

### Load it into KIND

```bash
# Load the image into all cluster nodes
kind load docker-image ai-platform:local --name ai-platform
```

Expected output:
```
Image: "ai-platform:local" with ID "sha256:..." not yet present on node "ai-platform-worker", loading...
Image: "ai-platform:local" with ID "sha256:..." not yet present on node "ai-platform-control-plane", loading...
Image: "ai-platform:local" with ID "sha256:..." not yet present on node "ai-platform-worker2", loading...
```

> **Every time you change your code**, you need to rebuild the image and reload it into KIND. The dev values file sets `imagePullPolicy: Never` so Kubernetes won't try to pull from a registry.

---

## Step 5: Deploy with Helm

The Helm chart at `helm/ai-platform/` defines all the Kubernetes resources (Deployments, StatefulSets, Services, Ingress, Secrets, PVCs). The `values-dev.yaml` file has settings optimized for local development.

### Deploy

Replace `YOUR_GROQ_API_KEY` with your actual Groq API key:

```bash
helm install ai-platform helm/ai-platform \
  -f helm/ai-platform/values-dev.yaml \
  --set api.llm.apiKey="YOUR_GROQ_API_KEY"
```

Expected output:
```
NAME: ai-platform
LAST DEPLOYED: ...
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

### Wait for all pods to be ready

```bash
# Wait up to 3 minutes for everything to come up
kubectl wait --for=condition=ready pod --all --timeout=180s
```

### Verify everything is running

```bash
# Check pods
kubectl get pods -o wide

# Check services
kubectl get svc

# Check ingress
kubectl get ingress

# Check persistent volumes
kubectl get pvc
```

Expected pod output (all should show `1/1 Running`):
```
NAME                                 READY   STATUS    RESTARTS   AGE
ai-platform-api-xxxxx-xxxxx         1/1     Running   0          60s
ai-platform-postgresql-0             1/1     Running   0          60s
ai-platform-qdrant-0                 1/1     Running   0          60s
ai-platform-redis-xxxxx-xxxxx       1/1     Running   0          60s
```

> **What Helm created:**
> - `ai-platform-api` — Deployment with 1 replica of your FastAPI app
> - `ai-platform-postgresql` — StatefulSet with 1Gi persistent storage
> - `ai-platform-redis` — Deployment (no persistent storage needed for cache)
> - `ai-platform-qdrant` — StatefulSet with 1Gi persistent storage
> - Services, Secrets, and an Ingress rule for each

---

## Step 6: Run Database Migrations

The fresh PostgreSQL instance has no tables yet. Run the Alembic migrations from inside the API pod:

```bash
kubectl exec deploy/ai-platform-api -- bash -c '
  cp /app/src/ai_platform/db/alembic.ini /tmp/alembic_k8s.ini
  sed -i "s|script_location = %(here)s|script_location = /app/src/ai_platform/db|g" /tmp/alembic_k8s.ini
  sed -i "s|localhost|ai-platform-postgresql|g" /tmp/alembic_k8s.ini
  python3 -m alembic -c /tmp/alembic_k8s.ini upgrade head
'
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema — conversations and messages.
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Add title column to conversations.
```

> **Why the sed commands?** The `alembic.ini` file has `localhost` as the database host (for local development). Inside Kubernetes, PostgreSQL is at `ai-platform-postgresql` (the service name). We also fix the script location since we copy the ini file to `/tmp`.

---

## Step 7: Verify End-to-End Connectivity

### Test via localhost (from the server)

If you're on the same machine:

```bash
# Health check
curl http://localhost/healthz
# Expected: {"status":"ok"}

# Readiness check
curl http://localhost/readyz
# Expected: {"status":"ok","checks":{"database":"ok","redis":"ok","qdrant":"ok"}}
# Note: qdrant may show "error" until you seed the FAQ collection — that's normal

# Test chat
curl -X POST http://localhost/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
# Expected: {"conversation_id":"...","message":"...","cached":false}

# List conversations
curl http://localhost/v1/conversations
# Expected: {"conversations":[{"id":"...","title":"...","created_at":"..."}]}

# Open the web UI
# Visit http://localhost in your browser
```

### Test from a remote machine (cloud VM)

If your cluster is on a cloud VM and you want to access it from your laptop:

**Option A: kubectl port-forward (recommended)**

On the server:
```bash
# Forward port 8080 on all interfaces to the API service
kubectl port-forward svc/ai-platform-api 8080:8000 --address 0.0.0.0
```

Then add a firewall rule (GCP example):
```bash
gcloud compute firewall-rules create allow-8080 \
  --allow=tcp:8080 \
  --project=YOUR_PROJECT \
  --source-ranges=0.0.0.0/0
```

Open in your browser: `http://YOUR_SERVER_IP:8080`

**Option B: SSH tunnel (more secure, no firewall changes)**

From your local machine:
```bash
# GCP
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE --project=YOUR_PROJECT -- -L 8080:localhost:80

# Generic SSH
ssh -L 8080:localhost:80 user@YOUR_SERVER_IP
```

Open in your browser: `http://localhost:8080`

---

## Useful Commands Reference

### Viewing logs

```bash
# API logs
kubectl logs deploy/ai-platform-api

# Follow logs in real-time
kubectl logs deploy/ai-platform-api -f

# PostgreSQL logs
kubectl logs statefulset/ai-platform-postgresql

# Qdrant logs
kubectl logs statefulset/ai-platform-qdrant

# Ingress controller logs
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller
```

### Debugging pods

```bash
# Describe a pod (shows events, errors, resource usage)
kubectl describe pod ai-platform-api-xxxxx

# Open a shell inside the API pod
kubectl exec -it deploy/ai-platform-api -- bash

# Check environment variables in a pod
kubectl exec deploy/ai-platform-api -- env | grep LLM
```

### Updating the application

After code changes:

```bash
# 1. Rebuild the Docker image
docker build -t ai-platform:local -f docker/api/Dockerfile .

# 2. Reload into KIND
kind load docker-image ai-platform:local --name ai-platform

# 3. Restart the API pods to pick up the new image
kubectl rollout restart deploy/ai-platform-api

# 4. Wait for the new pod to be ready
kubectl rollout status deploy/ai-platform-api
```

### Updating Helm values

```bash
# Change a value (e.g., replicas)
helm upgrade ai-platform helm/ai-platform \
  -f helm/ai-platform/values-dev.yaml \
  --set api.llm.apiKey="YOUR_GROQ_API_KEY" \
  --set api.replicas=2
```

### Checking resource usage

```bash
# Node resources
kubectl describe nodes | grep -A 10 "Allocated resources"

# Pod resource requests/limits
kubectl get pods -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory
```

---

## Cleanup

### Delete the Helm release (keeps the cluster)

```bash
helm uninstall ai-platform
```

### Delete the entire cluster

```bash
kind delete cluster --name ai-platform
```

This removes all nodes, pods, volumes, and configurations. Your Docker images remain on the host.

### Delete the firewall rule (if created)

```bash
gcloud compute firewall-rules delete allow-8080 --project=YOUR_PROJECT
```

---

## Troubleshooting

### Pods stuck in `Pending`

```bash
# Check why
kubectl describe pod POD_NAME
```

Common causes:
- **Insufficient CPU/memory** — The nodes don't have enough resources. Check with `kubectl describe nodes | grep -A5 "Allocated resources"`. You can reduce resource requests in `values-dev.yaml`.
- **PVC not binding** — Run `kubectl get pvc`. If stuck in `Pending`, the StorageClass may not be provisioning. KIND includes a default StorageClass, but check with `kubectl get storageclass`.

### Pods in `CrashLoopBackOff`

```bash
# Check the logs
kubectl logs POD_NAME --previous
```

Common causes:
- **Missing environment variables** — Check `kubectl exec deploy/ai-platform-api -- env`
- **Database not ready** — PostgreSQL might still be starting. Wait and check `kubectl logs statefulset/ai-platform-postgresql`
- **Wrong image** — Make sure you ran `kind load docker-image` after building

### Ingress returns `502 Bad Gateway`

The API pod isn't ready or the endpoint isn't registered:

```bash
# Check if the API pod is ready
kubectl get pods -l app.kubernetes.io/component=api

# Check if the endpoint exists
kubectl get endpoints ai-platform-api
# Should show an IP:PORT — if empty, the pod isn't ready yet
```

### Ingress returns empty response / connection reset

The ingress controller is likely on the wrong node:

```bash
# Check which node it's on
kubectl get pods -n ingress-nginx -o wide

# It MUST be on ai-platform-control-plane (where ports 80/443 are mapped)
# If not, follow the fix in Step 3
```

### Chat endpoint returns `500 Internal Server Error`

Database tables probably don't exist. Run the migrations (Step 6):

```bash
kubectl logs deploy/ai-platform-api --tail=20
# Look for: "relation "conversations" does not exist"
```

### "connection refused" on localhost

```bash
# Make sure the cluster is running
kind get clusters
# Should list: ai-platform

# Make sure pods are up
kubectl get pods

# Make sure ingress is working
kubectl get pods -n ingress-nginx
```

### Port 80 already in use when creating the cluster

```bash
# Find what's using port 80
sudo ss -tlnp | grep :80

# Stop that service, then create the cluster
```

---

## What's Next?

Now that the app is running on Kubernetes, the next steps are:

1. **Deploy the Monitoring Stack** — Prometheus (metrics & alerts), Grafana (dashboards), Loki (logs)
2. **Initialize Vault** — HashiCorp Vault for secure secret management
3. **Set Up ArgoCD** — GitOps continuous deployment (auto-sync from Git)
4. **Run CI/CD Pipelines** — GitHub Actions for automated testing and deployment

Each of these has pre-written configurations in the repo (`monitoring/`, `vault/`, `k8s/argocd/`, `.github/workflows/`).

---

## Quick Reference Card

| Action | Command |
|--------|---------|
| Check cluster status | `kubectl get nodes` |
| Check all pods | `kubectl get pods -o wide` |
| Check all services | `kubectl get svc` |
| View API logs | `kubectl logs deploy/ai-platform-api -f` |
| Restart API | `kubectl rollout restart deploy/ai-platform-api` |
| Scale API to 3 replicas | `kubectl scale deploy/ai-platform-api --replicas=3` |
| Open shell in API pod | `kubectl exec -it deploy/ai-platform-api -- bash` |
| Port-forward API | `kubectl port-forward svc/ai-platform-api 8080:8000` |
| Update Helm release | `helm upgrade ai-platform helm/ai-platform -f helm/ai-platform/values-dev.yaml --set api.llm.apiKey="KEY"` |
| Delete everything | `kind delete cluster --name ai-platform` |
