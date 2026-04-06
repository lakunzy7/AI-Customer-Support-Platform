# AI Customer Support Platform

An AI-powered customer support assistant that uses Groq LLM inference to answer customer questions. Features a ChatGPT-style web UI, conversation history, file uploads, and a RAG pipeline for FAQ-based answers.

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Gateway | FastAPI |
| LLM Service | Groq (Cloud LLM) |
| Caching | Redis |
| Database | PostgreSQL |
| Vector Store | Qdrant |

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- A free [Groq API key](https://console.groq.com/keys)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/AI-Customer-Support-Platform.git
cd AI-Customer-Support-Platform

# Copy env file and add your Groq API key
cp .env.example .env
# Edit .env and set LLM_API_KEY=gsk_your_key_here
```

### 2. Start database services

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, and Qdrant in the background.

### 3. Set up Python and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4. Run database migrations and seed data

```bash
alembic -c src/ai_platform/db/alembic.ini upgrade head
python src/scripts/seed_qdrant.py
```

### 5. Start the application

```bash
uvicorn ai_platform.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

### Verify it works

```bash
# Health check
curl http://localhost:8000/healthz

# Chat
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your return policy?"}'

# RAG (FAQ search)
curl -X POST http://localhost:8000/v1/rag \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reset my password?"}'
```

> For a detailed beginner-friendly walkthrough with troubleshooting, see [src/docs/local-setup-guide.md](src/docs/local-setup-guide.md).

## Web UI Features

The platform includes a ChatGPT-style web interface served at `/`:

- **Sidebar** — Conversation history with click-to-load, inline rename, delete
- **Auto-titles** — LLM generates short titles for new conversations
- **Markdown rendering** — Bold, italic, lists, tables, headings, blockquotes (via marked.js)
- **Code blocks** — Syntax-highlighted with copy button (via highlight.js)
- **Voice input** — Browser-native speech recognition (Chrome/Edge/Safari)
- **File upload** — Attach files and the AI reads their contents (see supported formats below)
- **Mobile responsive** — Sidebar toggle with hamburger menu

## Supported File Uploads

Upload files in the chat and the AI will read and understand their contents:

| Format | Extensions |
|--------|-----------|
| Text / Code | `.txt`, `.md`, `.py`, `.js`, `.ts`, `.json`, `.csv`, `.html`, `.css`, `.sql`, `.sh`, `.log`, `.xml`, `.yaml`, `.yml` |
| Documents | `.pdf`, `.docx`, `.doc`, `.xlsx`, `.pptx`, `.odt`, `.ods`, `.rtf`, `.epub` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` (upload only — AI cannot analyze images) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Chat web UI |
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe (checks DB, Redis, Qdrant) |
| POST | `/v1/chat` | Chat with AI assistant (supports `file_ids` for attachments) |
| GET | `/v1/conversations` | List all conversations (with auto-generated titles) |
| GET | `/v1/conversations/{id}/messages` | Get full message history |
| PATCH | `/v1/conversations/{id}` | Rename a conversation |
| DELETE | `/v1/conversations/{id}` | Delete a conversation |
| POST | `/v1/upload` | Upload a file (max 10MB, returns file_id) |
| GET | `/v1/files/{id}` | Download an uploaded file |
| POST | `/v1/rag` | RAG query against FAQ knowledge base |
| GET | `/docs` | Swagger UI (dev only) |

## Project Structure

```
AI-Customer-Support-Platform/
├── src/
│   ├── ai_platform/              # FastAPI application
│   │   ├── main.py               # App entry point with lifespan hooks
│   │   ├── config.py             # Pydantic Settings (all env vars)
│   │   ├── dependencies.py       # FastAPI dependency injection
│   │   ├── api/                  # Route handlers
│   │   │   ├── health.py         # GET /healthz, GET /readyz
│   │   │   ├── chat.py           # POST /v1/chat (with file context + auto-title)
│   │   │   ├── conversations.py  # GET/PATCH/DELETE /v1/conversations
│   │   │   ├── files.py          # POST /v1/upload, GET /v1/files/{id}
│   │   │   ├── file_extractors.py # Text extraction for all supported file types
│   │   │   └── rag.py            # POST /v1/rag
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── services/             # Business logic
│   │   │   ├── llm_client.py     # Groq API client (chat + embeddings)
│   │   │   ├── cache_service.py  # Redis caching (SHA-256 keys, TTL)
│   │   │   ├── rag_service.py    # RAG pipeline (embed → search → LLM)
│   │   │   └── conversation_service.py  # PostgreSQL conversation history
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── db/                   # Alembic migrations
│   │   ├── static/               # Chat web UI (index.html)
│   │   └── core/                 # Logging, telemetry, middleware
│   ├── tests/                    # Unit + integration tests (15 tests, 69% coverage)
│   ├── scripts/                  # Utility scripts (seed_qdrant.py)
│   └── docs/                     # Architecture docs, setup guide
├── docker-compose.yml            # PostgreSQL + Redis + Qdrant
├── pyproject.toml                # Python deps + tool config
├── .env.example                  # Environment variable template
└── .gitignore
```

## Running Tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

## Stopping and Restarting

```bash
# Stop the app: Ctrl+C in the terminal

# Stop database services
docker compose down

# Start everything again
docker compose up -d
source .venv/bin/activate
uvicorn ai_platform.main:app --host 0.0.0.0 --port 8000 --reload
```
