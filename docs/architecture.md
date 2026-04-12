# Architecture

## System Overview

```
                    ┌──────────────┐
                    │   Ingress    │
                    │   (NGINX)    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │ (canary %) │ (stable %) │
              ▼            ▼            │
    ┌──────────────┐ ┌──────────────┐  │
    │  API Canary  │ │  API Stable  │  │
    │  (v2 model)  │ │  (v1 model)  │  │
    └──────┬───────┘ └──────┬───────┘  │
           └────────┬───────┘          │
                    │                  │
         ┌──────────┼──────────┐       │
         ▼          ▼          ▼       │
    ┌─────────┐ ┌────────┐ ┌────────┐ │
    │  Redis  │ │PostgreSQL│ │ Qdrant │ │
    │ (cache) │ │ (state) │ │(vectors)│ │
    └─────────┘ └────────┘ └────────┘ │
                                       │
              External                 │
    ┌──────────────────────────┐       │
    │      Groq API            │◄──────┘
    │  (LLM + Embeddings)      │
    └──────────────────────────┘
```

## Components

### FastAPI Application (90+ files, 15 tests passing, 69% coverage)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | ChatGPT-style web UI |
| `/healthz` | GET | Liveness probe — process is alive |
| `/readyz` | GET | Readiness probe — checks DB, Redis, Qdrant |
| `/v1/chat` | POST | Conversational AI with history, file context, auto-title |
| `/v1/conversations` | GET | List conversations with auto-generated titles |
| `/v1/conversations/{id}/messages` | GET | Full message history for a conversation |
| `/v1/conversations/{id}` | PATCH | Rename a conversation |
| `/v1/conversations/{id}` | DELETE | Delete a conversation (cascades messages) |
| `/v1/upload` | POST | Upload files (text, code, PDF, images — max 10MB) |
| `/v1/files/{id}` | GET | Download an uploaded file |
| `/v1/rag` | POST | RAG: embed → vector search → augmented LLM |
| `/docs` | GET | Swagger UI (dev environments only) |

### Services Layer

| Service | Responsibility |
|---------|---------------|
| `LLMClient` | Async httpx client for Groq (chat completions + embeddings) |
| `CacheService` | Redis cache with SHA-256 keys and configurable TTL |
| `ConversationService` | PostgreSQL conversation CRUD + title management via async SQLAlchemy |
| `RagService` | Full RAG pipeline: embed → Qdrant search → context-augmented LLM call |

### Data Stores

| Store | Purpose | K8s Resource |
|-------|---------|-------------|
| PostgreSQL 16 | Conversations + messages + titles | StatefulSet + PVC |
| Redis 7 | Response cache (SHA-256 keys, TTL) | Deployment |
| Qdrant v1.12.5 | Vector store (FAQ embeddings, 1536-dim) | StatefulSet + PVC |
| File Storage | Uploaded files + metadata (Docker volume) | PersistentVolume |

## Data Flow — Chat

```
Client → POST /v1/chat { message, conversation_id?, file_ids? }
  ├── 1. Check Redis cache (SHA-256 of message)
  │     ├── HIT → return cached response
  │     └── MISS ↓
  ├── 2. Load/create conversation in PostgreSQL
  ├── 3. Build message history
  ├── 4. If file_ids: read file contents (text or PDF via PyMuPDF)
  │     └── Inject file text as LLM context message
  ├── 5. Call Groq chat/completions API
  ├── 6. Cache response in Redis
  ├── 7. Persist assistant message to PostgreSQL
  ├── 8. If new conversation: auto-generate title (background task)
  └── 9. Return response + conversation_id
```

## Data Flow — File Upload

```
Client → POST /v1/upload (multipart form)
  ├── 1. Validate file type and size (max 10MB)
  ├── 2. Save file to /tmp/ai-platform-uploads/<ULID>.<ext>
  ├── 3. Save metadata to <ULID>.meta.json (original filename)
  └── 4. Return file_id for use in chat
```

## Data Flow — RAG

```
Client → POST /v1/rag
  ├── 1. Check Redis cache (SHA-256 of question)
  │     ├── HIT → return cached answer
  │     └── MISS ↓
  ├── 2. Embed question via Groq embeddings API
  ├── 3. Search Qdrant for top-k similar documents
  ├── 4. Build context from retrieved documents
  ├── 5. Send augmented prompt to Groq chat API
  ├── 6. Cache result in Redis
  └── 7. Return answer + source documents
```

## Web UI

The platform serves a ChatGPT-style single-page application at `/` built with vanilla HTML/CSS/JS.

| Feature | Implementation |
|---------|---------------|
| Markdown rendering | marked.js — headings, lists, tables, blockquotes, links |
| Code highlighting | highlight.js — syntax-highlighted code blocks with copy button |
| Sidebar | Conversation history — list, load, rename, delete |
| Auto-title | Background LLM call generates 3-5 word title after first reply |
| Voice input | Web Speech API (browser-native, Chrome/Edge/Safari) |
| File upload | Attach button, preview chips, PDF text extraction via PyMuPDF |
| Mobile responsive | Hamburger toggle for sidebar, adaptive layout |

### Supported File Types

| Category | Extensions |
|----------|-----------|
| Text/code | .txt, .md, .csv, .json, .xml, .yaml, .py, .js, .ts, .html, .css, .sql, .sh, .log |
| Documents | .pdf (text extracted via PyMuPDF, up to 8000 chars) |
| Images | .png, .jpg, .jpeg, .gif, .webp (stored, not analyzed by LLM) |
