# DocuChat Platform Scope (3 Weeks) — Product-Ready, Reusable Across Apps

Owner: Nilbre  
Branch: `OpenClawTesting`  
Mode: Budget-first / fast shipping / minimal infra cost

## 1) Product vision
Build **one reusable RAG backend platform** that powers many app experiences by configuration:
- different system prompts/personas
- different document sets/knowledge bases
- different FAISS indexes per app/tenant
- same API and runtime

Result: one platform, many chatbots.

---

## 2) Core product requirements

### Must-have (MVP+)
1. **Multi-App Projects**
   - Create project/app (`project_id`)
   - Each project has:
     - prompt template
     - model settings
     - retrieval settings
     - its own knowledge base/index storage

2. **Document Spaces**
   - Upload docs into a target project
   - Persist source metadata (filename, upload time, tags)
   - Isolated retrieval per project

3. **Per-Project Retrieval Config**
   - `top_k`, chunk size/overlap, optional rerank flag
   - filter by metadata/tags

4. **Chat API usable by many frontends**
   - Same endpoint contract for Next.js, Streamlit, internal apps
   - Include citations + confidence score + project context

5. **Local-first / low-cost runtime**
   - Ollama + local embeddings + FAISS
   - Docker Compose (no k8s in this phase)

6. **Basic production safeguards**
   - Prompt injection hardening template
   - Answer-abstain when confidence low
   - Request logging with latency + status

---

## 3) Target architecture (simple but scalable)

## Components
- **API**: FastAPI
- **LLM runtime**: Ollama
- **Embedding**: sentence-transformers/all-MiniLM-L6-v2
- **Index**: FAISS (one index per project)
- **Metadata store**: SQLite/Postgres (start SQLite, optional Postgres)
- **Frontend**: existing Next.js app

## Storage layout
```text
/data
  /projects
    /{project_id}
      config.json
      index/                  # FAISS + LlamaIndex persisted files
      documents/
      uploads_manifest.json
```

## Key design choice
Use **project_id isolation** as the core boundary. This gives multi-app behavior without heavy infra.

---

## 4) API contract (product-ready)

### Project management
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `PATCH /api/projects/{project_id}`

### Document ingestion
- `POST /api/projects/{project_id}/upload`
- `GET /api/projects/{project_id}/documents`
- `DELETE /api/projects/{project_id}/documents/{doc_id}`

### Chat/query
- `POST /api/projects/{project_id}/query`

Request body:
```json
{
  "question": "What is our refund policy?",
  "chat_history": [],
  "tags": ["policy"],
  "override_prompt": null
}
```

Response body:
```json
{
  "answer": "...",
  "citations": [
    {"filename": "policy.pdf", "chunk_id": "...", "score": 0.82}
  ],
  "confidence": 0.78,
  "abstained": false,
  "project_id": "support-bot"
}
```

---

## 5) Data model (minimal)

## `projects`
- `id`
- `name`
- `description`
- `system_prompt`
- `model`
- `top_k`
- `chunk_size`
- `chunk_overlap`
- `created_at`
- `updated_at`

## `documents`
- `id`
- `project_id`
- `filename`
- `path`
- `mime_type`
- `size_bytes`
- `tags`
- `created_at`

## `query_logs`
- `id`
- `project_id`
- `question`
- `latency_ms`
- `confidence`
- `abstained`
- `created_at`

---

## 6) 3-week delivery plan

## Week 1 — Multi-project foundation
- Refactor ingestion/query services to accept `project_id`
- Add project registry + per-project config
- Change storage to `/data/projects/{project_id}/...`
- Build project CRUD endpoints
- Upgrade query response with citations object

**Exit criteria:**
- 2 separate projects can answer using different docs/prompts

## Week 2 — Quality + reliability
- Confidence scoring + abstain threshold
- Prompt templates per project
- Basic query logging + latency metrics endpoint
- Add evaluation script (small test set per project)

**Exit criteria:**
- measurable quality and stable outputs

## Week 3 — Productization + Next.js integration
- Connect existing Next.js platform to new project APIs
- Build project switcher UI
- Upload manager + chat interface bound to selected project
- Add simple admin screen for prompt/settings edits
- Produce 3 showcase configs:
  1. Document Assistant
  2. Support Triage Assistant
  3. Compliance Assistant

**Exit criteria:**
- same platform serves 3 use-cases from configuration

---

## 7) Budget & infra plan

## Now (3 weeks)
- Local Ollama
- Local FAISS
- Docker Compose
- Zero/near-zero cloud spend

## Later (after traction)
- Move metadata DB to managed Postgres
- Add Redis queue for large ingestion
- Then consider Kubernetes only when uptime/load requires

---

## 8) Success metrics
- Time to create new app config: < 10 min
- Query p95 latency: < 6s local target
- Citation presence rate: > 90%
- Abstain accuracy on unknown questions: improving week-over-week
- 3 showcase apps running from same backend

---

## 9) Immediate implementation backlog (next coding steps)
1. Introduce `ProjectConfig` model + local project repository
2. Refactor `IngestionService.process_document(..., project_id)`
3. Refactor `RAGService.query(..., project_id)`
4. Add `/api/projects` routes
5. Add `/api/projects/{id}/query` and migrate UI calls
6. Add confidence + abstain logic in response payload
