# StudyMate – AI-Powered Study Assistant (RAG Backend)

**StudyMate** is an open-source backend that transforms students’ notes, research papers, and study materials into intelligent, searchable, and conversational knowledge spaces using **Retrieval-Augmented Generation (RAG)**.  
It provides a complete local RAG pipeline, from document ingestion to embedding generation, semantic retrieval, and LLM-powered answering, all fully isolated per user.

---

##  Purpose

StudyMate allows each student to:
- Log in with email and password.
- Create *RAGs* (Retrieval-Augmented Knowledge spaces).
- Upload personal documents (PDF, DOCX, TXT).
- Ask questions and get contextual answers powered by a local LLM (via Ollama).
- Share RAGs with other users and manage permissions.
- Keep private discussion history per user per RAG.

The system is modular, multiprocessing-aware, and entirely local.

---
## 0) Quick Summary

- **Stack:** FastAPI, SQLAlchemy, Sentence-Transformers, ChromaDB (HNSWlib), Ollama (LLM), Loguru.  
- **OCR/Layout:** Background **YOLOv8** model server + **pytesseract** for OCR.  
- **RAG Pipeline:** ingestion → chunking → embedding → vector store → retrieval → (optional rerank) → LLM answer.  
- **Isolation:** Per-user, per-RAG collections in ChromaDB.  
- **Config:** `config/config.yaml` (embedding model = `all-MiniLM-L6-v2`, LLM = `llama2`, chunk_size = 500, top_k = 20, rerank_k = 5).  
- **YOLO weights (required):** `models/yolov8n-doclaynet.pt` (file not included; path referenced in code).

---

# 1) ENGINEERING NARRATIVE (How it works)

## 1.1 Purpose

StudyMate lets a student log in, create a **RAG workspace**, upload PDFs/DOCX/TXT, and then **search/ask questions** against their own materials. Everything runs **locally**.

## 1.2 High-Level Architecture

```
FastAPI
├─ /auth                 (JWT auth)
├─ /rags                 (list/create/delete + share/approve/revoke)
├─ /rags/{rag_id}/docs   (upload additional files)
├─ /rags/{rag_id}/search (semantic retrieval)
├─ /rags/{rag_id}/answer (LLM grounded answer)
└─ /rags/{rag_id}/discussions (per-user chat history)

Pipeline
├─ ingestor.py  (OCR + chunking coordinator)
├─ indexer.py   (embeddings → ChromaDB)
├─ searcher.py  (ANN retrieval, HNSW)
└─ answerer.py  (context + Ollama LLM)

Modules
├─ model_server.py (YOLOv8 background process)
├─ page_job.py     (per-page OCR job via pytesseract)
├─ reranker.py     (optional CrossEncoder logic)
└─ document/layout/entity extractors

Core
├─ block_processor.py (cleanup)
├─ chunk_builder.py   (semantic chunking)
├─ Logger.py          (Loguru setup)
└─ utils.py           (FileManager, YAML/JSON I/O)
```

## 1.3 End-to-End Flow

1) **Authentication** (`/auth`) issues a JWT token.  
2) **Create RAG** (`POST /rags`) with form-data: `name`, `description?`, `files[]`.  
3) **Ingestor** (`src/pipeline/ingestor.py`) launches:  
   - **YOLO server process** once (if down) via `model_server.py`.  
   - **Multiprocessing page workers** that call `page_job.py` for each PDF page:  
     - convert page → image → send to YOLO via `server_req_q` → receive layout boxes from `server_resp_q`.  
     - run **pytesseract** OCR per region → structured blocks (text + bbox + page).  
   - **BlockProcessor** cleans noise (headers/footers), **ChunkBuilder** segments text (≈500 tokens).  
4) **Indexer** (`src/pipeline/indexer.py`) embeds chunks with **SentenceTransformer** (`all-MiniLM-L6-v2`) and stores vectors in **ChromaDB (PersistentClient)** — a **separate collection per user/RAG**.  
5) **Search** (`POST /rags/{id}/search`) embeds the query, runs **HNSW** ANN search, optional **rerank**, returns top_k chunks + metadata.  
6) **Answer** (`POST /rags/{id}/answer`) concatenates top contexts, calls **Ollama** LLM (`llama2`) to produce a grounded answer.  
7) **Discussions** (`GET/POST /rags/{id}/discussions`) store and list **per-user** chat history for that RAG only.

## 1.4 Multiprocessing Model (Real)

- **`model_server.py`**:  
  - Function `model_server(server_req_q, server_resp_q, model_path)` loads `YOLO(model_path)` and **stays alive**.  
  - The RAG pipeline sends images to `server_req_q` and reads detections from `server_resp_q`.  
  - **Weights path** referenced in code: `models/yolov8n-doclaynet.pt` (also appears in `src/main.py` and `src/api/routers/rags.py`).

- **`page_job.py`**:  
  - Function `page_job(args)` accepts `(page_number, page_png_bytes, ocr_lang, server_req_q, server_resp_q)`.  
  - Sends image → YOLO server, then runs **pytesseract** over detected regions, returns ordered blocks.

- **`ingestor.py`**:  
  - Creates queues, ensures YOLO server process is running, and **spawns a process pool** to call `page_job` on each page.  
  - Aggregates block outputs → cleans → chunking → hands off to `Indexer`.

This design **reuses YOLO** across pages/docs and **parallelizes pages**, keeping throughput high without reloading models per page.

## 1.5 Storage & Isolation

- Uploaded docs saved under `DATA_DIR` (default `storage/data`) — see `src/api/routers/documents.py`.  
- Vector DB stored under `paths.vector_db` (default `storage/vectors`) — see `config/config.yaml`.  
- Collections are **per-user-per-RAG** for strict isolation.

## 1.6 Logging

- Log manager: `src/core/Logger.py` → `logging_project.log` in `storage/logs/` with rotation (1MB, keep 5).  
- Logs include ingestion timings, indexing progress, search metadata, and user actions.

---

# 2) DEVELOPER REFERENCE (What exists in code)

## 2.1 Routers (Verified Endpoints)

**`src/api/routers/auth.py`** (prefix `/auth`)  
- `POST /auth/signup`  
- `POST /auth/login`  
- `POST /auth/change-password`

**`src/api/routers/rags.py`** (prefix `/rags`)  
- `GET  /rags`  
- `POST /rags` (multipart: `name`, `description?`, `files[]`)  
- `DELETE /rags/{rag_id}`  
- `POST /rags/{rag_id}/share`  
- `POST /rags/{rag_id}/share/{user_id}/approve`  
- `DELETE /rags/{rag_id}/share/{user_id}`

**`src/api/routers/documents.py`** (prefix `/rags`)  
- `POST /rags/{rag_id}/docs/upload`

**`src/api/routers/search.py`** (prefix `/rags`)  
- `POST /rags/{rag_id}/search` (body: `{"query": str, "top_k": int=20}`)  
- `POST /rags/{rag_id}/answer` (body: `{"query": str}`)

**`src/api/routers/discussions.py`** (prefix `/rags`)  
- `GET  /rags/{rag_id}/discussions`  
- `POST /rags/{rag_id}/discussions`

> All prefixes and paths come from reading these exact files in your repo.

## 2.2 Pipelines & Modules

- **`src/pipeline/ingestor.py`**  
  - Starts YOLO server process (if needed).  
  - Spawns page workers → `page_job`.  
  - Aggregates blocks → `BlockProcessor` → `ChunkBuilder`.  
  - Triggers `Indexer`.

- **`src/pipeline/indexer.py`**  
  - Uses `SentenceTransformer` for embeddings.  
  - Writes vectors to `ChromaDB PersistentClient` with **HNSW**.  
  - One collection per user/RAG.

- **`src/pipeline/searcher.py`**  
  - Encodes query with the **same embedding model**.  
  - Queries ANN index; returns hits (optionally reranked).

- **`src/pipeline/answerer.py`**  
  - Builds context from search results.  
  - Calls **Ollama** (LLM = `llama2`, per `config/config.yaml`).

- **`src/modules/model_server.py`**  
  - `model_server(req_q, resp_q, model_path)` with **Ultralytics YOLO**.  
  - Used by `ingestor.py` and `src/main.py` (CLI-style).

- **`src/modules/page_job.py`**  
  - `page_job(args)` runs OCR per page with **pytesseract**.

- **`src/modules/reranker.py`**  
  - Cross-encoder reranking logic (optional).

- **`src/core/block_processor.py`**  
  - Cleans OCR noise, removes boilerplate.

- **`src/core/chunk_builder.py`**  
  - Segments text into chunks (≈500 tokens by config).

- **`src/core/Logger.py` → `LoggerManager`**  
  - Centralizes Loguru setup with rotation.

- **`src/core/utils.py` → `FileManager`**  
  - `load_yaml`, `save_json`, `ensure_dir`, etc.

## 2.3 Configuration (`config/config.yaml`)

```yaml
paths:
  data_dir: storage/data
  chunks_file: storage/chunks.json
  vector_db: storage/vectors
models:
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  llm_model: llama2
tokenizer:
  model: bert-base-uncased
chunking:
  chunk_size: 500
retrieval:
  top_k: 20
  rerank_k: 5
layout:
  pdf_dpi: 150
  score_thresh: 0.5
ner:
  model: en_core_web_trf
```

> YOLO weights **not bundled**. Code references: `"models/yolov8n-doclaynet.pt"`.

## 2.4 Environment Variables

- `DATA_DIR` → used by `documents.py` (default `storage/data`).  
- `VECTOR_DIR` → configured via YAML (`paths.vector_db`).  
- `DATABASE_URL` → SQLAlchemy (default likely SQLite path in settings/models).  
- `OLLAMA_API_URL` → local Ollama endpoint (`http://localhost:11434`).

## 2.5 Request Examples

**Search**  
```http
POST /rags/{rag_id}/search
Content-Type: application/json
Authorization: Bearer <JWT>

{
  "query": "What is gradient descent?",
  "top_k": 20
}
```

**Answer**  
```http
POST /rags/{rag_id}/answer
Content-Type: application/json
Authorization: Bearer <JWT>

{ "query": "Summarize chapter 3 key results." }
```

**Upload documents**  
```http
POST /rags/{rag_id}/docs/upload
Content-Type: multipart/form-data
Authorization: Bearer <JWT>

files[]=@notes.pdf
```

---

# 3) INSTALL & RUN

```bash
git clone https://github.com/mouaadhalimi/StudyMate.git
cd StudyMate
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Required: install pytesseract on your OS
# Optional: download YOLO weights:
#   mkdir -p models && cp /path/to/yolov8n-doclaynet.pt models/yolov8n-doclaynet.pt

uvicorn src.api.main:app --reload
# Swagger: http://localhost:8000/docs
```

**CLI (from `src/main.py`)**  
```bash
python -m src.main ingest <user_id>
python -m src.main index  <user_id>
python -m src.main search <user_id> "your question"
python -m src.main answer <user_id> "your question"
```

---

# 4) CHARACTERISTICS

| Feature | Verified From |
|--------|----------------|
| YOLO model server process | `src/modules/model_server.py`, `src/api/routers/rags.py`, `src/main.py` |
| pytesseract OCR per page  | `src/modules/page_job.py` |
| ChromaDB (HNSW) vectors   | `src/pipeline/indexer.py`, `src/pipeline/searcher.py` |
| Sentence-Transformers     | `src/pipeline/indexer.py`, `src/pipeline/searcher.py` |
| Ollama LLM client         | `src/pipeline/answerer.py`, `src/api/routers/search.py` |
| Logging with rotation     | `src/core/Logger.py` |
| Per-user RAG isolation    | Implementation notes across `pipeline` + `routers` |

---

# 5) LICENSE

MIT — suitable for personal, academic, or commercial use.
