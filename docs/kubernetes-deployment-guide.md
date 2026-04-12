# Kubernetes Deployment Guide — AI Customer Support Platform

> **Type**: Kubernetes Deployment (NOT local development — for local setup see [local-setup-guide.md](local-setup-guide.md))
> **Audience**: Beginners in DevOps who want to deploy a production-grade Kubernetes application from scratch.
> **Platform**: Expadox Lab — AI Customer Support Platform
> **Last Updated**: April 2026

---

## Table of Contents

1. [What Are We Deploying?](#1-what-are-we-deploying)
2. [Architecture Overview](#2-architecture-overview)
3. [System Requirements](#3-system-requirements)
4. [Prerequisites — Install Required Tools](#4-prerequisites--install-required-tools)
5. [Step 1 — Clone the Repository](#step-1--clone-the-repository)
6. [Step 2 — Get Your Groq API Key](#step-2--get-your-groq-api-key)
7. [Step 3 — Create the KIND Cluster](#step-3--create-the-kind-cluster)
8. [Step 4 — Install the NGINX Ingress Controller](#step-4--install-the-nginx-ingress-controller)
9. [Step 5 — Create Namespaces and Resource Quotas](#step-5--create-namespaces-and-resource-quotas)
10. [Step 6 — Install ArgoCD](#step-6--install-argocd)
11. [Step 7 — Seed Secrets](#step-7--seed-secrets)
12. [Step 8 — Deploy with App-of-Apps](#step-8--deploy-with-app-of-apps)
13. [Step 9 — Run Database Migrations](#step-9--run-database-migrations)
14. [Step 10 — Seed the Vector Database (RAG)](#step-10--seed-the-vector-database-rag)
15. [Step 11 — Access the Application](#step-11--access-the-application)
16. [Step 12 — Verify Monitoring](#step-12--verify-monitoring)
17. [Concepts Explained](#concepts-explained)
18. [The Automated Way (One Command)](#the-automated-way-one-command)
19. [CI/CD Pipeline Explained](#cicd-pipeline-explained)
20. [Useful Commands Reference](#useful-commands-reference)
21. [Troubleshooting](#troubleshooting)
22. [Cleanup](#cleanup)

---

## 1. What Are We Deploying?

This is a **production-grade AI Customer Support Platform** that includes:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Server** | FastAPI (Python 3.11) | Handles chat, RAG, file uploads, conversations |
| **LLM Backend** | Groq API (Llama 3.3 70B) | Generates AI responses |
| **Database** | PostgreSQL 16 | Stores conversations and messages |
| **Cache** | Redis 7 | Caches LLM responses for speed |
| **Vector Database** | Qdrant v1.12.5 | Stores document embeddings for RAG search |
| **Web UI** | Single-page HTML/JS | ChatGPT-style interface with voice input |
| **Ingress** | NGINX Ingress Controller | Routes external traffic to the API |
| **GitOps** | ArgoCD | Automatically deploys from Git |
| **Monitoring** | Prometheus + Grafana + Loki | Metrics, dashboards, and log aggregation |
| **CI/CD** | GitHub Actions | Linting, testing, building, security scanning |

---

## 2. Architecture Overview

### System Architecture Diagram

![AI Platform Architecture](../img/Architecture%20Diagram%20For%20AI%20Customer%20Support%20Platform.jpg)

> *If the image above doesn't render, see the ASCII version below.*

Here is how all the pieces fit together inside the Kubernetes cluster:

```
                        Internet / Your Browser
                                |
                        [ NGINX Ingress Controller ]
                        (routes HTTP traffic to pods)
                                |
                    +-----------+-----------+
                    |                       |
            [ API Stable ]          [ API Canary ] (optional)
            (main version)          (new version, 10% traffic)
                    |
        +-----------+-----------+-----------+
        |           |           |           |
  [ PostgreSQL ] [ Redis ]  [ Qdrant ]  [ Groq API ]
  (conversations) (cache)   (vectors)   (LLM cloud)
        |           |           |
    [ PVC ]     (in-memory)  [ PVC ]
  (persistent)              (persistent)

                    [ ArgoCD ]
                (watches Git repo, auto-syncs)

        [ Prometheus ] --> [ Grafana ] --> Dashboards
              |
      [ ServiceMonitor ]  (scrapes /metrics from API pods)
              |
        [ AlertManager ]  (fires alerts on errors/latency)
              |
          [ Loki ] <-- [ Promtail ] (collects pod logs)
```

**How traffic flows:**
1. Your browser hits port 80/443 on the host machine
2. KIND maps those ports into the cluster's control-plane node
3. The NGINX Ingress Controller picks up the request and routes it to the API Service
4. The API pod processes the request, talking to PostgreSQL/Redis/Qdrant/Groq as needed
5. The response flows back through Ingress to your browser

---

## 3. System Requirements

### Minimum (for local KIND deployment)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 4 cores | 8 cores |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 20 GB free | 40 GB free |
| **OS** | Linux (Ubuntu 20.04+), macOS 12+, Windows 11 (WSL2) | Ubuntu 22.04 / Debian 12 |
| **Network** | Internet access (for pulling images + Groq API) | Stable broadband |

### Why these requirements?
- **CPU**: Kubernetes control plane + 7 pods (API, PostgreSQL, Redis, Qdrant, Prometheus, Grafana, Loki) need CPU
- **RAM**: The monitoring stack alone uses ~1.5 GB; PostgreSQL and Qdrant need memory for data
- **Disk**: Docker images, persistent volumes for databases, and container layers add up

### Cloud VM (if deploying on a cloud server)

Any of these work:
- **AWS**: t3.xlarge (4 vCPU, 16 GB RAM)
- **GCP**: e2-standard-4 (4 vCPU, 16 GB RAM)
- **Azure**: Standard_D4s_v3 (4 vCPU, 16 GB RAM)
- **DigitalOcean**: s-4vcpu-8gb (minimum) or s-8vcpu-16gb (recommended)

> **Important**: If using a cloud VM, make sure ports 80, 443, and 30080 are open in your firewall/security group.

---

## 4. Prerequisites — Install Required Tools

You need **6 tools** installed on your machine before starting. Here is how to install each one.

### 4.1 Docker

Docker runs containers. KIND uses Docker to simulate Kubernetes nodes.

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER
# LOG OUT AND LOG BACK IN after this for group change to take effect

# Verify
docker --version
# Expected: Docker version 24.x or higher
```

**macOS**: Download Docker Desktop from https://www.docker.com/products/docker-desktop/

### 4.2 kubectl

`kubectl` is the command-line tool to talk to Kubernetes clusters.

```bash
# Download the latest stable version
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify
kubectl version --client
# Expected: Client Version: v1.3x.x
```

### 4.3 KIND (Kubernetes IN Docker)

KIND creates a full Kubernetes cluster using Docker containers as "nodes". It's perfect for local development — no cloud account needed.

```bash
# Linux (amd64)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.25.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/

# macOS (arm64 / Apple Silicon)
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.25.0/kind-darwin-arm64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/

# Verify
kind version
# Expected: kind v0.25.0
```

**Why KIND and not Minikube?**
KIND is lighter, faster to start, supports multi-node clusters, and is what the Kubernetes project itself uses for testing. Our cluster has 1 control-plane + 2 worker nodes.

### 4.4 Helm

Helm is the "package manager for Kubernetes" — it templates YAML manifests so you can deploy complex apps with one command.

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
# Expected: version.BuildInfo{Version:"v3.1x.x"}
```

### 4.5 Git

```bash
# Ubuntu/Debian
sudo apt install -y git

# Verify
git --version
```

### 4.6 Groq Account (Free)

You need a free Groq API key for the LLM. Sign up at https://console.groq.com and create a key.

### Verify All Tools

Run this to confirm everything is installed:

```bash
echo "Docker:  $(docker --version 2>/dev/null || echo 'NOT FOUND')"
echo "kubectl: $(kubectl version --client --short 2>/dev/null || echo 'NOT FOUND')"
echo "kind:    $(kind version 2>/dev/null || echo 'NOT FOUND')"
echo "helm:    $(helm version --short 2>/dev/null || echo 'NOT FOUND')"
echo "git:     $(git --version 2>/dev/null || echo 'NOT FOUND')"
```

All 5 should print a version. If any says "NOT FOUND", go back and install it.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/lakunzy7/AI-Customer-Support-Platform.git
cd AI-Customer-Support-Platform
```

Take a moment to see the project layout:

```
AI-Customer-Support-Platform/
├── src/                    # Python application code
│   ├── ai_platform/        # FastAPI app (main.py, api/, services/, models/)
│   ├── tests/              # Pytest test suite
│   └── scripts/            # Utility scripts (seed_qdrant.py)
├── helm/ai-platform/       # Helm chart (Kubernetes manifests as templates)
│   ├── Chart.yaml           # Chart metadata
│   ├── values.yaml          # Production default values
│   ├── values-dev.yaml      # KIND/dev override values
│   └── templates/           # Templated K8s manifests (deployment, service, etc.)
├── k8s/                    # Kubernetes infrastructure
│   ├── kind/                # KIND cluster configuration
│   ├── namespaces/          # Namespace + resource quota definitions
│   └── argocd/              # ArgoCD install config + app definitions
├── monitoring/             # Observability stack
│   ├── prometheus/          # ServiceMonitor, alert rules, Prometheus values
│   ├── grafana/             # Dashboard JSON + ConfigMap
│   └── loki/                # Loki + Promtail values
├── docker/api/             # Dockerfile for the API
├── scripts/                # Automation scripts (kind-setup.sh, port-forward.sh)
├── .github/workflows/      # CI/CD pipelines (ci.yml, release.yml, security.yml)
├── Makefile                # Developer shortcuts
└── pyproject.toml          # Python dependencies + tool config
```

---

## Step 2 — Get Your Groq API Key

1. Go to https://console.groq.com/keys
2. Click **Create API Key**
3. Copy the key (starts with `gsk_...`)
4. Create the `.env` file:

```bash
echo "LLM_API_KEY=gsk_your_actual_key_here" > .env
```

> **Why Groq?** Groq provides extremely fast LLM inference using their custom LPU hardware. The free tier is generous for development and testing. This project uses `llama-3.3-70b-versatile` — a powerful open-source model.

---

## Step 3 — Create the KIND Cluster

This creates a 3-node Kubernetes cluster running inside Docker containers.

```bash
kind create cluster --config k8s/kind/cluster-config.yaml --wait 60s
```

**What this does:**
- Creates a Docker network called `kind`
- Spins up 3 Docker containers: `ai-platform-control-plane`, `ai-platform-worker`, `ai-platform-worker2`
- Each container runs a full Kubernetes node (kubelet, container runtime, etc.)
- Maps host ports 80, 443, and 30000 into the control-plane container

**The cluster config** (`k8s/kind/cluster-config.yaml`):

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ai-platform
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"   # <-- Tells ingress to use this node
    extraPortMappings:
      - containerPort: 80        # HTTP
        hostPort: 80
      - containerPort: 443       # HTTPS
        hostPort: 443
      - containerPort: 30000     # NodePort (for ArgoCD)
        hostPort: 30000
  - role: worker                 # Worker node 1
  - role: worker                 # Worker node 2
```

**Why 3 nodes?**
- 1 control-plane: runs the Kubernetes API server, scheduler, etcd
- 2 workers: run your application pods. This simulates a real production cluster where pods spread across multiple machines for high availability.

**Verify the cluster is running:**

```bash
kubectl cluster-info
# Expected: Kubernetes control plane is running at https://127.0.0.1:xxxxx

kubectl get nodes
# Expected:
# NAME                         STATUS   ROLES           AGE   VERSION
# ai-platform-control-plane    Ready    control-plane   1m    v1.31.x
# ai-platform-worker           Ready    <none>          1m    v1.31.x
# ai-platform-worker2          Ready    <none>          1m    v1.31.x
```

---

## Step 4 — Install the NGINX Ingress Controller

An **Ingress Controller** is a reverse proxy that sits at the edge of your cluster and routes incoming HTTP/HTTPS traffic to the correct pods based on rules you define.

Think of it like this:
- Without Ingress: each service needs its own port (8000, 8001, 8002...)
- With Ingress: all traffic enters on port 80/443 and gets routed by hostname/path

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```

**Wait for it to be ready** (this pulls the nginx image and starts the controller pod):

```bash
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

**Verify:**

```bash
kubectl get pods -n ingress-nginx
# Expected: One pod with STATUS "Running"
# NAME                                        READY   STATUS    RESTARTS   AGE
# ingress-nginx-controller-xxxxxxxxxx-xxxxx   1/1     Running   0          1m
```

**How it works in our cluster:**
1. The KIND config labels the control-plane node with `ingress-ready=true`
2. The NGINX Ingress Controller is configured to run on nodes with that label
3. Since ports 80/443 are mapped from host → control-plane, traffic from your browser goes: `localhost:80 → Docker container port 80 → NGINX Ingress Controller → your API pods`

---

## Step 5 — Create Namespaces and Resource Quotas

Namespaces are like folders in Kubernetes — they separate resources into logical groups.

```bash
kubectl apply -f k8s/namespaces/
```

This creates 3 namespaces:

| Namespace | Purpose |
|-----------|---------|
| `ai-platform` | Your application pods (API, PostgreSQL, Redis, Qdrant) |
| `monitoring` | Prometheus, Grafana, Loki, Alertmanager |
| `argocd` | ArgoCD server and controllers |

It also applies a **Resource Quota** to the `ai-platform` namespace:

```yaml
spec:
  hard:
    requests.cpu: "4"          # Total CPU requests can't exceed 4 cores
    requests.memory: 8Gi       # Total memory requests can't exceed 8 GB
    limits.cpu: "8"            # Total CPU limits can't exceed 8 cores
    limits.memory: 16Gi        # Total memory limits can't exceed 16 GB
    pods: "30"                 # No more than 30 pods
    persistentvolumeclaims: "10"  # No more than 10 persistent disks
```

**Why quotas?** In a real cluster shared by teams, quotas prevent one namespace from consuming all resources and starving others.

**Verify:**

```bash
kubectl get namespaces
# Should see: ai-platform, monitoring, argocd, plus defaults

kubectl get resourcequota -n ai-platform
# Should see: ai-platform-quota
```

---

## Step 6 — Install ArgoCD

ArgoCD is the **GitOps engine**. It watches your Git repository and automatically deploys any changes to the cluster. You push code → ArgoCD notices → deploys it. No manual `kubectl apply` needed.

### 6.1 Add the Helm Repository

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
```

### 6.2 Install ArgoCD

```bash
helm upgrade --install argocd argo/argo-cd -n argocd \
  -f k8s/argocd/install.yaml \
  --wait --timeout 180s
```

**What the install values do** (`k8s/argocd/install.yaml`):

```yaml
server:
  extraArgs:
    - --insecure       # No TLS at ArgoCD (KIND only — ingress handles TLS in prod)
  service:
    type: NodePort
    nodePortHttp: 30080  # Access ArgoCD UI at localhost:30080
configs:
  params:
    server.insecure: true
  cm:
    timeout.reconciliation: 30s  # Check Git for changes every 30 seconds
```

### 6.3 Wait for ArgoCD to Be Ready

```bash
kubectl wait --namespace argocd \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=argocd-server \
  --timeout=120s
```

### 6.4 Get the ArgoCD Admin Password

ArgoCD generates a random admin password on first install:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

Save this password! You'll use it to log into the ArgoCD web UI.

**Access the ArgoCD UI:**
- Open http://localhost:30080 in your browser
- Username: `admin`
- Password: (the one you just copied)

**Verify:**

```bash
kubectl get pods -n argocd
# Expected: 5-7 pods all Running (server, repo-server, application-controller, redis, dex, etc.)
```

---

## Step 7 — Seed Secrets

Your API needs the Groq API key to function. We create a Kubernetes Secret that the API pods will read:

```bash
# Read the key from your .env file and create the secret
LLM_KEY=$(grep '^LLM_API_KEY=' .env | cut -d'=' -f2-)

kubectl create secret generic ai-platform-secrets -n ai-platform \
  --from-literal=llm-api-key="$LLM_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

**What's happening here:**
1. `grep` extracts the API key from your `.env` file
2. `kubectl create secret` creates a Kubernetes Secret object
3. `--dry-run=client -o yaml | kubectl apply` makes this idempotent (safe to run multiple times)
4. The API Deployment references this secret via `secretKeyRef` in its environment variables

**Verify:**

```bash
kubectl get secret ai-platform-secrets -n ai-platform
# Expected: NAME                  TYPE     DATA   AGE
#           ai-platform-secrets   Opaque   1      10s
```

> **Security Note**: The secret is stored encrypted in etcd (Kubernetes' backing store). In production, you would use an external secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.) instead of `kubectl create secret`.

---

## Step 8 — Deploy with App-of-Apps

This is the **single most important command** in the entire deployment. It triggers a cascade that deploys everything.

```bash
kubectl apply -f k8s/argocd/app-of-apps.yaml
```

### What Is App-of-Apps?

The **App-of-Apps pattern** is an ArgoCD strategy where one "parent" Application manages multiple "child" Applications. Think of it as a tree:

```
app-of-apps.yaml (parent)
    |
    ├── reads k8s/argocd/apps/ directory in Git
    |
    ├── ai-platform.yaml ──────> Helm chart → API + PostgreSQL + Redis + Qdrant
    ├── monitoring.yaml ────────> kube-prometheus-stack → Prometheus + Grafana + Alertmanager
    └── monitoring-extras.yaml ─> Custom dashboards + alert rules + ServiceMonitor
```

**The parent Application** (`k8s/argocd/app-of-apps.yaml`):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ai-platform-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/lakunzy7/AI-Customer-Support-Platform.git
    targetRevision: main
    path: k8s/argocd/apps        # <-- ArgoCD reads all YAML files in this folder
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true                # Delete resources removed from Git
      selfHeal: true             # Revert manual changes back to Git state
```

**Why App-of-Apps?**
1. **Single entry point**: One `kubectl apply` deploys your entire infrastructure
2. **GitOps**: Everything is defined in Git. No manual `helm install` commands needed
3. **Self-healing**: If someone manually deletes a pod, ArgoCD recreates it
4. **Pruning**: If you remove a file from Git, ArgoCD removes it from the cluster
5. **Scalable**: Adding a new service = adding one YAML file to `k8s/argocd/apps/`

### What Each Child App Deploys

**ai-platform.yaml** — Your application:
- Uses the Helm chart at `helm/ai-platform/` with `values.yaml`
- Deploys: API Deployment (2 replicas), PostgreSQL StatefulSet, Redis Deployment, Qdrant StatefulSet
- Also creates: Services, Ingress, HPA, PDB, NetworkPolicy, Secrets

**monitoring.yaml** — The monitoring stack:
- Installs `kube-prometheus-stack` Helm chart from the Prometheus community
- Deploys: Prometheus, Grafana, Alertmanager, kube-state-metrics, node-exporter, Prometheus Operator
- Configured with open selectors so it discovers ServiceMonitors from any namespace

**monitoring-extras.yaml** — Custom monitoring configs:
- Deploys files from `monitoring/prometheus/` and `monitoring/grafana/` directly
- Includes: ServiceMonitor (scrape API metrics), Alert rules, Grafana dashboard

### Wait for Deployment

ArgoCD needs time to pull images and start everything. Wait for the API pods:

```bash
# Watch ArgoCD sync (the apps will appear one by one)
kubectl get applications -n argocd -w

# Wait for the AI platform API to be ready (may take 2-5 minutes)
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=ai-platform,app.kubernetes.io/component=api \
  -n ai-platform --timeout=300s
```

**Verify all pods:**

```bash
kubectl get pods -n ai-platform
# Expected:
# NAME                                READY   STATUS    RESTARTS   AGE
# ai-platform-api-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
# ai-platform-api-xxxxxxxxxx-yyyyy   1/1     Running   0          2m
# ai-platform-postgresql-0           1/1     Running   0          2m
# ai-platform-redis-xxxxxxxxxx-zzz   1/1     Running   0          2m
# ai-platform-qdrant-0               1/1     Running   0          2m

kubectl get pods -n monitoring
# Expected: ~8-10 pods (prometheus, grafana, alertmanager, operator, exporters)

kubectl get pods -n argocd
# Expected: 5-7 ArgoCD pods all Running
```

---

## Step 9 — Run Database Migrations

The PostgreSQL database is empty. We need to create the tables (conversations, messages):

```bash
kubectl exec -n ai-platform deploy/ai-platform-api -- python3 -c "
from alembic.config import Config
from alembic import command
cfg = Config('src/ai_platform/db/alembic.ini')
cfg.set_main_option('sqlalchemy.url', 'postgresql+asyncpg://aiplatform:aiplatform@ai-platform-postgresql:5432/aiplatform')
command.upgrade(cfg, 'head')
"
```

**What this does:**
1. `kubectl exec` opens a shell inside a running API pod
2. Runs Alembic (Python migration tool) to create database tables
3. The connection string points to `ai-platform-postgresql` (the K8s Service name)
4. `upgrade(cfg, 'head')` applies all pending migration files

**Verify:**

```bash
kubectl exec -n ai-platform deploy/ai-platform-api -- python3 -c "
from alembic.config import Config
from alembic import command
cfg = Config('src/ai_platform/db/alembic.ini')
cfg.set_main_option('sqlalchemy.url', 'postgresql+asyncpg://aiplatform:aiplatform@ai-platform-postgresql:5432/aiplatform')
command.current(cfg, verbose=True)
"
# Should show: head (indicating all migrations are applied)
```

---

## Step 10 — Seed the Vector Database (RAG)

For the RAG (Retrieval-Augmented Generation) feature to work, Qdrant needs some documents:

```bash
# First, port-forward Qdrant so the seed script can reach it
kubectl port-forward -n ai-platform svc/ai-platform-qdrant 6333:6333 &

# Run the seed script
python src/scripts/seed_qdrant.py

# Stop the port-forward
kill %1
```

This populates Qdrant with FAQ documents. When users ask questions, the system searches these documents for relevant context and includes it in the LLM prompt — this is **RAG (Retrieval-Augmented Generation)**.

---

## Step 11 — Access the Application

### 11.1 Port-Forward the API

The API runs inside the cluster. To access it from your browser:

```bash
bash scripts/port-forward.sh
```

This runs:
```bash
kubectl port-forward -n ai-platform svc/ai-platform-api 8000:8000 &
kubectl port-forward -n ai-platform svc/ai-platform-qdrant 6333:6333 &
```

### 11.2 Open the Application

| Service | URL | Credentials |
|---------|-----|------------|
| **Web UI** | http://localhost:8000 | None needed |
| **API Docs** (Swagger) | http://localhost:8000/docs | None needed |
| **Health Check** | http://localhost:8000/healthz | None needed |
| **ArgoCD** | http://localhost:30080 | admin / (see step 6.4) |

### 11.3 Quick Smoke Test

```bash
# Test health endpoint
curl http://localhost:8000/healthz
# Expected: {"status":"healthy","checks":{"database":"ok","redis":"ok","qdrant":"ok"}}

# Test chat
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello! What can you help me with?"}'
# Expected: A JSON response with the AI's reply

# Test RAG
curl -X POST http://localhost:8000/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reset my password?"}'
# Expected: A JSON response with answer + source documents
```

### 11.4 Cloud VM Access

If deploying on a remote server, use SSH tunneling:

```bash
# From your local machine
ssh -L 8000:localhost:8000 -L 30080:localhost:30080 user@your-server-ip
```

Then open http://localhost:8000 in your local browser.

---

## Step 12 — Verify Monitoring

### 12.1 Access Grafana

```bash
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
```

Open http://localhost:3000
- Username: `admin`
- Password: `admin`

### 12.2 Check Prometheus Targets

```bash
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &
```

Open http://localhost:9090/targets — you should see `ai-platform-api` targets with state **UP**.

### 12.3 How Monitoring Works Together

Here is the complete monitoring flow:

```
API Pod (/metrics endpoint)
    |
    |  scraped every 15 seconds
    v
ServiceMonitor (tells Prometheus WHERE to scrape)
    |
    v
Prometheus (stores time-series metrics)
    |
    ├──> PrometheusRule (evaluates alert conditions)
    |       |
    |       v
    |   Alertmanager (sends notifications when alerts fire)
    |
    ├──> Grafana (visualizes metrics as dashboards)
    |       |
    |       └── Dashboard ConfigMap (pre-built panels: request rate, latency, errors)
    |
    └──> Recording Rules (pre-computes SLO metrics like availability)

Pod Logs (stdout/stderr)
    |
    |  collected by
    v
Promtail (DaemonSet on every node)
    |
    v
Loki (stores logs, searchable in Grafana)
```

**The metrics the API exposes** (via `prometheus-fastapi-instrumentator`):
- `http_requests_total` — Total request count, labeled by status code and method
- `http_request_duration_highr_seconds_bucket` — Request latency histogram
- `llm_request_duration_seconds_bucket` — LLM call latency histogram

**Alert rules that fire automatically:**

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | >5% of requests return 5xx for 5 minutes | Critical |
| HighLatencyP95 | P95 latency > 2 seconds for 5 minutes | Warning |
| PodCrashLooping | Pod restarts > 3 times in 15 minutes | Critical |
| LLMSlowResponse | LLM P95 latency > 10 seconds for 5 minutes | Warning |

**SLO Recording Rules:**
- `ai_platform:http_requests:error_ratio_5m` — Error rate over 5 minutes
- `ai_platform:http_requests:availability_5m` — Availability (target: 99.5%)

**The Grafana dashboard** (`AI Platform - API Overview`) shows 7 panels:
1. Request Rate (req/s)
2. Error Rate (%)
3. Latency (P50 / P95 / P99)
4. LLM Request Duration (P95)
5. Active Pods
6. CPU Usage per pod
7. Memory Usage per pod

---

## Concepts Explained

### What Is Helm and Why Do We Use It?

Imagine you need to deploy 15 Kubernetes YAML files (Deployment, Service, ConfigMap, Secret, Ingress, HPA, PDB, StatefulSets, etc.). Without Helm, you'd copy-paste values like image names, ports, and passwords into each file.

**Helm** lets you:
1. Write YAML **templates** with variables: `image: "{{ .Values.api.image.repository }}:{{ .Values.api.image.tag }}"`
2. Define a `values.yaml` with defaults: `repository: ghcr.io/lakunzy7/ai-platform`
3. Have **different values files** for different environments:
   - `values.yaml` — production (2 replicas, HPA enabled, 5Gi storage)
   - `values-dev.yaml` — local development (1 replica, no HPA, 1Gi storage)

Our Helm chart lives at `helm/ai-platform/` and produces these Kubernetes resources:

| Template | Kubernetes Resource | Purpose |
|----------|-------------------|---------|
| `api/deployment.yaml` | Deployment | Runs API pods with health probes |
| `api/service.yaml` | Service (ClusterIP) | Internal DNS name for the API |
| `api/ingress.yaml` | Ingress | External access via NGINX |
| `api/hpa.yaml` | HorizontalPodAutoscaler | Scales pods 2-10 based on CPU/memory |
| `api/pdb.yaml` | PodDisruptionBudget | At least 1 pod always available during updates |
| `api/secret.yaml` | Secret | Stores the LLM API key |
| `api/networkpolicy.yaml` | NetworkPolicy | Firewall rules (production only) |
| `api/canary-ingress.yaml` | Deployment + Service + Ingress | Canary deployment (optional) |
| `postgresql/statefulset.yaml` | StatefulSet + PVC | Persistent database |
| `postgresql/service.yaml` | Service (Headless) | Stable DNS for PostgreSQL |
| `redis/deployment.yaml` | Deployment | In-memory cache |
| `redis/service.yaml` | Service (ClusterIP) | Internal DNS for Redis |
| `qdrant/statefulset.yaml` | StatefulSet + PVC | Persistent vector database |
| `qdrant/service.yaml` | Service (ClusterIP) | Internal DNS for Qdrant |

### What Is Canary Deployment?

A **canary deployment** lets you test a new version of your API with a small percentage of real traffic before rolling it out to everyone.

```
                100% of traffic
                      |
              [ NGINX Ingress ]
                      |
            +---------+---------+
            |                   |
    90% traffic           10% traffic
            |                   |
    [ API Stable ]      [ API Canary ]
    (current version)   (new version / different model)
```

**How it works in this project:**

1. Set `api.canary.enabled: true` in `values.yaml`
2. Configure the canary weight (e.g., `weight: 10` = 10% of traffic)
3. The canary runs a separate Deployment + Service + Ingress
4. The canary Ingress uses NGINX annotations:
   ```yaml
   nginx.ingress.kubernetes.io/canary: "true"
   nginx.ingress.kubernetes.io/canary-weight: "10"
   ```
5. NGINX automatically splits traffic: 90% to stable, 10% to canary
6. Both share the same PostgreSQL, Redis, and Qdrant
7. You monitor the canary in Grafana — if errors are low, increase the weight
8. When confident, promote the canary image to stable and disable canary

**To enable canary**, update `helm/ai-platform/values.yaml`:

```yaml
api:
  canary:
    enabled: true
    replicas: 1
    weight: 10          # Start with 10% of traffic
    model: "llama-3.3-70b-versatile"
    image:
      repository: ghcr.io/lakunzy7/ai-platform
      tag: v2.0.0       # New version to test
```

Push to Git → ArgoCD syncs → canary pod appears → 10% of users get the new version.

### What Is the NetworkPolicy?

A **NetworkPolicy** is a firewall for pods. It controls which pods can talk to which.

In this project, the NetworkPolicy is **only active in production** (`global.env: production`). It restricts the API pods to:

**Ingress (who can send traffic TO the API):**
- NGINX Ingress Controller (port 8000) — so users can reach the API
- Prometheus (port 8000) — so it can scrape `/metrics`

**Egress (where the API can send traffic):**
- DNS (port 53 UDP/TCP) — needed for service name resolution
- PostgreSQL (port 5432) — database queries
- Redis (port 6379) — cache reads/writes
- Qdrant (port 6333) — vector search
- HTTPS (port 443) — Groq API calls

**Why?** In production, if an attacker compromises the API pod, the NetworkPolicy prevents them from reaching other services in the cluster that the API shouldn't talk to.

### What Is a StatefulSet vs Deployment?

| | Deployment | StatefulSet |
|--|-----------|-------------|
| **Use for** | Stateless apps (API, Redis) | Stateful apps (PostgreSQL, Qdrant) |
| **Pod names** | Random (`api-7d8f9-x4kl2`) | Predictable (`postgresql-0`) |
| **Storage** | Shared or none | Each pod gets its own PVC |
| **Scaling** | Pods created/deleted in any order | Ordered: 0, then 1, then 2... |
| **DNS** | Via Service only | Each pod gets stable DNS |

PostgreSQL and Qdrant use StatefulSets because they store data on disk. If a pod restarts, it re-attaches to the same persistent volume and picks up where it left off.

### What Is HPA (HorizontalPodAutoscaler)?

The HPA automatically scales the number of API pods based on load:

```yaml
spec:
  minReplicas: 2       # Never fewer than 2 pods
  maxReplicas: 10      # Never more than 10 pods
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          averageUtilization: 70   # Scale up when CPU > 70%
    - type: Resource
      resource:
        name: memory
        target:
          averageUtilization: 80   # Scale up when memory > 80%
```

**How it works:**
1. Metrics server reports current CPU/memory usage per pod
2. HPA checks every 15 seconds
3. If average CPU across all pods > 70%, HPA adds a pod
4. If average CPU drops, HPA removes pods (down to minReplicas)
5. This handles traffic spikes automatically

### What Is PDB (PodDisruptionBudget)?

A PDB ensures your app stays available during planned disruptions (node upgrades, cluster scaling):

```yaml
spec:
  minAvailable: 1    # At least 1 API pod must always be running
```

Without a PDB, Kubernetes could drain all your pods at once during a node upgrade, causing downtime. With `minAvailable: 1`, Kubernetes will drain pods one at a time, waiting for the replacement to be ready before draining the next.

---

## The Automated Way (One Command)

Everything above can be done automatically with the setup script:

```bash
bash scripts/kind-setup.sh
```

This script runs all steps 3-9 in sequence:
1. Creates the KIND cluster
2. Installs NGINX Ingress Controller
3. Creates namespaces
4. Installs ArgoCD via Helm
5. Reads `.env` and creates the LLM API key secret
6. Applies the App-of-Apps
7. Waits for pods to be ready
8. Runs database migrations
9. Prints the ArgoCD password and access URLs

After it finishes:

```bash
# Start port-forwarding
bash scripts/port-forward.sh

# Open the app
open http://localhost:8000
```

Or use Make:

```bash
make kind-up         # Same as: bash scripts/kind-setup.sh
make port-forward    # Same as: bash scripts/port-forward.sh
make argocd-pass     # Print the ArgoCD admin password
```

---

## CI/CD Pipeline Explained

The project has 3 GitHub Actions workflows that run automatically.

### Pipeline 1: CI (`ci.yml`)

**Triggers**: Every push to `main` and every pull request targeting `main`.

```
  Push / PR to main
        |
   [ Lint Job ]
   ruff check src/
   ruff format --check src/
        |
   (must pass)
        |
   [ Test Job ]
   pytest -v --cov=src/ai_platform
        |
   (must pass, main branch only)
        |
   [ Build Job ]
   docker build → push to ghcr.io/lakunzy7/ai-platform:latest
```

**What happens at each stage:**

1. **Lint**: Checks code style and formatting using Ruff (Python's fastest linter). Catches bugs like unused imports, bare excepts, and security issues.

2. **Test**: Runs the full pytest test suite with coverage reporting. Tests mock external services (Groq, PostgreSQL, Redis, Qdrant) so they run fast without needing real infrastructure.

3. **Build** (main branch only): Builds the Docker image using the multi-stage Dockerfile and pushes it to GitHub Container Registry (GHCR). The image is tagged with both the commit SHA and `latest`.

### Pipeline 2: Release (`release.yml`)

**Triggers**: When you push a version tag like `v1.0.0`.

```bash
# To create a release:
git tag v1.0.0
git push origin v1.0.0
```

This triggers:
1. Docker image built and pushed as `ghcr.io/lakunzy7/ai-platform:1.0.0` + `latest`
2. GitHub Release created automatically with auto-generated release notes

### Pipeline 3: Security Scan (`security.yml`)

**Triggers**: Every push/PR to main + weekly Monday at 6am UTC.

1. **Trivy**: Scans the Docker image for known vulnerabilities (CVEs) in OS packages and Python libraries. Results uploaded to GitHub Security tab in SARIF format.

2. **pip-audit**: Scans Python dependencies specifically for known vulnerable versions.

### How CI/CD Connects to ArgoCD

The full flow from code change to live deployment:

```
Developer pushes code to main
        |
        v
GitHub Actions CI runs (lint → test → build)
        |
        v
Docker image pushed to ghcr.io/lakunzy7/ai-platform:latest
        |
        v
ArgoCD detects the updated image tag (polls every 30 seconds)
        |
        v
ArgoCD syncs: updates the Deployment with the new image
        |
        v
Kubernetes performs a rolling update:
  - Starts new pod with new image
  - Waits for readiness probe (/readyz) to pass
  - Routes traffic to new pod
  - Terminates old pod
        |
        v
Zero-downtime deployment complete!
```

---

## Useful Commands Reference

### Cluster Management

```bash
# View cluster info
kubectl cluster-info
kubectl get nodes

# View all pods across all namespaces
kubectl get pods -A

# View pod resource usage (requires metrics-server)
kubectl top pods -n ai-platform

# View logs for a specific pod
kubectl logs -n ai-platform -l app.kubernetes.io/component=api --tail=100 -f

# Open a shell inside a running pod
kubectl exec -it -n ai-platform deploy/ai-platform-api -- /bin/bash

# View events (useful for debugging)
kubectl get events -n ai-platform --sort-by='.lastTimestamp'
```

### ArgoCD

```bash
# View all ArgoCD applications
kubectl get applications -n argocd

# Force ArgoCD to sync an application
kubectl patch application ai-platform -n argocd \
  --type merge -p '{"operation":{"sync":{"revision":"HEAD"}}}'

# View ArgoCD application status
kubectl describe application ai-platform -n argocd

# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

### Helm

```bash
# List installed Helm releases
helm list -A

# View what a Helm chart would render (dry-run)
helm template ai-platform helm/ai-platform/ -f helm/ai-platform/values.yaml

# View Helm release history
helm history ai-platform -n ai-platform
```

### Monitoring

```bash
# Port-forward Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80

# Port-forward Prometheus
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090

# Check Prometheus targets (from inside the cluster)
kubectl exec -n monitoring deploy/monitoring-grafana -- \
  curl -s http://monitoring-kube-prometheus-prometheus:9090/api/v1/targets | head -c 2000

# View active alerts
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-alertmanager 9093:9093
# Then open http://localhost:9093
```

### Debugging

```bash
# Why is a pod not starting?
kubectl describe pod <pod-name> -n ai-platform

# View pod logs
kubectl logs <pod-name> -n ai-platform

# Check if services can reach each other (from API pod)
kubectl exec -n ai-platform deploy/ai-platform-api -- \
  python3 -c "import socket; socket.create_connection(('ai-platform-postgresql', 5432)); print('PostgreSQL: OK')"

kubectl exec -n ai-platform deploy/ai-platform-api -- \
  python3 -c "import socket; socket.create_connection(('ai-platform-redis', 6379)); print('Redis: OK')"

kubectl exec -n ai-platform deploy/ai-platform-api -- \
  python3 -c "import socket; socket.create_connection(('ai-platform-qdrant', 6333)); print('Qdrant: OK')"
```

### Makefile Shortcuts

```bash
make help           # Show all available commands
make kind-up        # Create cluster + deploy everything
make kind-down      # Delete the cluster
make port-forward   # Forward API + Qdrant to localhost
make argocd-pass    # Print ArgoCD admin password
make test           # Run tests locally
make lint           # Run linter locally
make format         # Auto-format code
make migrate        # Run database migrations
make seed           # Seed Qdrant with FAQ documents
```

---

## Troubleshooting

### Pod stuck in `Pending`

```bash
kubectl describe pod <pod-name> -n ai-platform
```

Common causes:
- **Insufficient resources**: The node doesn't have enough CPU/memory. Check `kubectl describe node` and the resource quota.
- **PVC pending**: The PersistentVolumeClaim hasn't been bound. Check `kubectl get pvc -n ai-platform`.
- **Image pull failure**: The Docker image can't be pulled. Check image name and registry access.

### Pod in `CrashLoopBackOff`

```bash
kubectl logs <pod-name> -n ai-platform --previous
```

Common causes:
- **Missing secret**: The `ai-platform-secrets` secret doesn't exist. Run Step 7 again.
- **Database not ready**: The API starts before PostgreSQL. Kubernetes will restart it and it should connect on the next attempt.
- **Invalid API key**: Check that your `.env` has a valid Groq key.

### ArgoCD App Stuck in "Progressing"

```bash
kubectl describe application ai-platform -n argocd
```

Common causes:
- **Image not found**: The GHCR image hasn't been pushed yet. For local dev, build and load the image:
  ```bash
  docker build -t ai-platform:local -f docker/api/Dockerfile .
  kind load docker-image ai-platform:local --name ai-platform
  ```
- **Helm render error**: Check Helm chart syntax: `helm template ai-platform helm/ai-platform/`

### Grafana Shows "No Data"

1. Check Prometheus targets: http://localhost:9090/targets — the `ai-platform-api` target should be **UP**
2. Check the ServiceMonitor exists: `kubectl get servicemonitor -n monitoring`
3. Check the dashboard uses the Prometheus datasource (not Loki)
4. Verify the API pod exposes metrics: `kubectl exec -n ai-platform deploy/ai-platform-api -- curl -s http://localhost:8000/metrics | head -20`

### Cannot Access ArgoCD UI

```bash
# Check if ArgoCD pods are running
kubectl get pods -n argocd

# Check if the NodePort is open
kubectl get svc -n argocd argocd-server
# Should show: NodePort, 30080

# For cloud VMs, ensure the firewall allows port 30080
```

### Port 80 Already in Use

```bash
# Check what's using port 80
sudo lsof -i :80

# If Apache/Nginx is running, stop it
sudo systemctl stop apache2  # or nginx
```

### KIND Cluster Won't Start

```bash
# Check Docker is running
docker info

# Check for existing clusters
kind get clusters

# Delete old cluster and try again
kind delete cluster --name ai-platform
kind create cluster --config k8s/kind/cluster-config.yaml --wait 60s
```

---

## Cleanup

### Delete the Cluster (Everything Gone)

```bash
kind delete cluster --name ai-platform
```

This removes all Docker containers, pods, data, and networking. Everything is gone.

Or use Make:

```bash
make kind-down
```

### Keep Cluster, Remove Application Only

```bash
kubectl delete application ai-platform-apps -n argocd
```

ArgoCD will cascade-delete all child applications and their resources.

### Keep Cluster, Remove Monitoring Only

```bash
kubectl delete application monitoring -n argocd
kubectl delete application monitoring-extras -n argocd
```

---

## Summary

Here is everything you deployed, in order:

| Step | What | Command | Why |
|------|------|---------|-----|
| 1 | Clone repo | `git clone ...` | Get the code |
| 2 | API key | Create `.env` | LLM needs authentication |
| 3 | KIND cluster | `kind create cluster ...` | Kubernetes environment |
| 4 | Ingress | `kubectl apply -f ...nginx...` | Route external traffic |
| 5 | Namespaces | `kubectl apply -f k8s/namespaces/` | Organize resources |
| 6 | ArgoCD | `helm upgrade --install ...` | GitOps engine |
| 7 | Secrets | `kubectl create secret ...` | Store API key securely |
| 8 | App-of-Apps | `kubectl apply -f app-of-apps.yaml` | Deploy EVERYTHING |
| 9 | Migrations | `kubectl exec ... alembic ...` | Create database tables |
| 10 | Seed Qdrant | `python seed_qdrant.py` | Load FAQ documents for RAG |
| 11 | Access | `bash scripts/port-forward.sh` | Reach the app from browser |
| 12 | Verify | Check Grafana + Prometheus | Confirm monitoring works |

**Total time**: ~10-15 minutes (mostly waiting for images to pull).

**One-command alternative**: `bash scripts/kind-setup.sh` does steps 3-9 automatically.

---

> **Built by Expadox Lab** | AI Customer Support Platform | Production-Grade Kubernetes Deployment
