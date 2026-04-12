# Local Setup Guide

A step-by-step guide to get the AI Customer Support Platform running on your machine. No prior experience needed — just copy and paste each command.

---

## What You'll Need

Before starting, make sure you have these installed:

| Tool | Why You Need It | How to Check |
|------|----------------|--------------|
| **Python 3.11+** | Runs the application | `python3 --version` |
| **Docker** | Runs the database, cache, and vector store | `docker --version` |
| **Docker Compose** | Starts all services with one command | `docker compose version` |
| **Git** | Clone the project | `git --version` |

### Installing Prerequisites (if you don't have them)

**Ubuntu/Debian:**
```bash
# Python
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# Docker (official method)
# Follow: https://docs.docker.com/engine/install/ubuntu/

# Git
sudo apt install -y git
```

**macOS:**
```bash
# Install Homebrew first if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python
brew install python@3.13

# Docker Desktop (includes Docker Compose)
# Download from: https://www.docker.com/products/docker-desktop/

# Git
brew install git
```

**Windows (WSL2):**
```bash
# Inside your WSL2 terminal (Ubuntu):
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# Docker Desktop for Windows with WSL2 backend:
# Download from: https://www.docker.com/products/docker-desktop/
```

---

## Step 1: Get the Project

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/AI-Customer-Support-Platform.git

# Go into the project folder
cd AI-Customer-Support-Platform
```

> If you already have the project, just `cd` into the folder.

---

## Step 2: Get a Free Groq API Key

The app uses Groq for AI responses. It's free:

1. Go to https://console.groq.com/keys
2. Sign up or log in
3. Click **"Create API Key"**
4. Copy the key (starts with `gsk_...`)

You'll use this key in the next step.

---

## Step 3: Set Up Environment Variables

```bash
# Copy the example env file
cp .env.example .env
```

Now open `.env` in any text editor and replace `your-groq-api-key-here` with your actual key:

```bash
# Using nano (simple terminal editor):
nano .env
```

Find this line:
```
LLM_API_KEY=your-groq-api-key-here
```

Replace it with your key:
```
LLM_API_KEY=gsk_your_actual_key_here
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

> **Leave all other values as-is.** The defaults work for local development.

---

## Step 4: Start the Database Services

This starts PostgreSQL (database), Redis (cache), and Qdrant (vector search) in Docker containers:

```bash
docker compose up -d
```

You should see output like:
```
Container ai-customer-support-platform-main-postgres-1  Started
Container ai-customer-support-platform-main-redis-1     Started
Container ai-customer-support-platform-main-qdrant-1    Started
```

**Verify they're running:**
```bash
docker compose ps
```

All three should show `running` status.

---

## Step 5: Set Up Python Environment

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install the application and all its dependencies
pip install -e .
```

> Your terminal prompt should now start with `(.venv)` — this means the virtual environment is active.
>
> **Every time you open a new terminal**, you need to activate it again with:
> ```bash
> source .venv/bin/activate
> ```

---

## Step 6: Set Up the Database

Run the database migrations to create the required tables:

```bash
alembic -c src/ai_platform/db/alembic.ini upgrade head
```

You should see:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Add title column
```

---

## Step 7: Seed the FAQ Data

Load sample FAQ documents into the vector database (used for the RAG feature):

```bash
python src/scripts/seed_qdrant.py
```

You should see:
```
Connecting to Qdrant at localhost:6333...
Created collection 'faq_documents' (dim=768)
Embedding 6 documents via Groq...
Inserted 6 FAQ documents into 'faq_documents'
Done!
```

> If you see "No API key — using random vectors" that means your `.env` file doesn't have the Groq key set correctly. Go back to Step 3.

---

## Step 8: Start the Application

```bash
uvicorn ai_platform.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process using WatchFiles
```

---

## Step 9: Open the App

Open your browser and go to:

**http://localhost:8000**

You should see the ChatGPT-style web interface. Try typing a message like:

> "What is your return policy?"

---

## Quick Test (Optional)

Open a **new terminal** and run these commands to verify everything works:

```bash
# Health check
curl http://localhost:8000/healthz
# Expected: {"status":"ok"}

# Chat test
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you help me with?"}'

# RAG test (searches FAQ knowledge base)
curl -X POST http://localhost:8000/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reset my password?"}'
```

---

## Stopping and Restarting

### Stop the app
Press `Ctrl+C` in the terminal where uvicorn is running.

### Stop the database services
```bash
docker compose down
```

### Start everything again later
```bash
# 1. Start database services
docker compose up -d

# 2. Activate Python environment
source .venv/bin/activate

# 3. Start the app
uvicorn ai_platform.main:app --host 0.0.0.0 --port 8000 --reload
```

> You do NOT need to re-run migrations or seed data — they persist in Docker volumes.

---

## Running Tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

---

## Troubleshooting

### "python3-venv not installed"
```bash
# Replace 3.XX with your Python version (e.g., 3.11, 3.12, 3.13)
sudo apt install -y python3.XX-venv
```

### "docker: permission denied"
```bash
sudo usermod -aG docker $USER
# Then log out and log back in
```

### "Port 5432/6379/6333 already in use"
Another service is using that port. Stop it or change the port in `docker-compose.yml` and `.env`.

```bash
# Find what's using a port (e.g., 5432)
sudo lsof -i :5432
```

### "Connection refused" when starting the app
Make sure Docker services are running:
```bash
docker compose ps
```
If they're not running, start them: `docker compose up -d`

### App starts but chat returns errors
Check your Groq API key in `.env`. Make sure:
- No extra spaces around the key
- The key starts with `gsk_`
- You saved the file after editing

### "ModuleNotFoundError"
Make sure your virtual environment is activated:
```bash
source .venv/bin/activate
```

---

## What Each Service Does

| Service | Port | Purpose |
|---------|------|---------|
| **App (FastAPI)** | 8000 | The web UI and API |
| **PostgreSQL** | 5432 | Stores conversations and messages |
| **Redis** | 6379 | Caches AI responses to save API calls |
| **Qdrant** | 6333 | Vector search for FAQ answers (RAG) |

---

## Supported File Uploads

You can upload files in the chat and the AI will read their contents:

| Format | Extensions |
|--------|-----------|
| Text / Code | `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.csv`, `.html`, `.css`, `.sql`, `.sh`, `.log`, `.xml`, `.yaml`, `.yml` |
| Documents | `.pdf`, `.docx`, `.doc`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.rtf`, `.epub` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` (upload only — AI cannot analyze images) |
