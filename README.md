# StudyMate – End-to-End Retrieval-Augmented Generation (RAG) Backend

**StudyMate** is a robust, open-source, production-ready **Retrieval-Augmented Generation (RAG)** backend designed to provide a full local, private, and cost-free solution for document ingestion, semantic search, and contextual AI-assisted answering.  
Built using **FastAPI**, **SQLAlchemy**, **Sentence-Transformers**, **ChromaDB**, **HNSWlib**, and **Ollama**, it combines traditional backend engineering with modern AI capabilities.

---

##  Overview

StudyMate empowers developers and organizations to build **intelligent assistants**, **enterprise knowledge bases**, or **educational tools** that can understand, search, and answer questions from user-provided documents — all locally, without sending data to external APIs.

Each user has isolated document sets, embeddings, and vector databases, ensuring both **privacy** and **multi-tenant scalability**.

---

##  Features

### Core Capabilities
- **Multi-User Support:** Isolated RAG environments per user (secured with JWT-based authentication).  
- **Document Ingestion:** Upload, extract, and parse PDFs, DOCX, and TXT files.  
- **Layout Detection & OCR:** YOLOv8 model for document layout structure + Tesseract OCR for text recognition.  
- **Text Preprocessing:** Removes redundant headers/footers, merges small paragraphs, and normalizes text content.  
- **Chunking Engine:** Context-aware text splitting for improved embedding performance.  
- **Vector Storage:** Local, persistent vector database using **ChromaDB** + approximate nearest neighbor index via **HNSWlib**.  
- **Semantic Search:** Efficient retrieval of document snippets relevant to a given query.  
- **Cross-Encoder Reranking:** Sentence-Transformers’ CrossEncoder model to improve relevance ranking.  
- **Local Answer Generation:** Uses **Ollama** to generate contextual answers based on retrieved document content.  

### System & Dev Features
- FastAPI with modular router design.
- Centralized Loguru logging (with rotation, file + console).  
- Secure middlewares (CORS, trusted hosts, security headers).  
- Configurable chunk size, embedding model, and tokenizer.  
- Scalable multiprocessing ingestion via YOLO Model Server.  
- Fully open-source and free to deploy (no API keys required).

---

##  Architecture

```
                ┌──────────────────────────────┐
                │        File Upload           │
                │ (PDF, DOCX, TXT Documents)   │
                └──────────────┬───────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  LayoutExtractor (YOLOv8) │
                  │ + OCR via Tesseract       │
                  └─────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  BlockProcessor          │
                  │ (Cleans headers/footers) │
                  └─────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  ChunkBuilder            │
                  │ (Merge & split blocks)   │
                  └─────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  Indexer (Embed + Store) │
                  │ (ChromaDB + HNSWlib)     │
                  └─────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  Searcher (Semantic ANN) │
                  └─────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  Reranker (CrossEncoder) │
                  └─────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  Answerer (Ollama LLM)   │
                  └─────────────────────────┘
```

---

##  Repository Structure

```
StudyMate/
├── src/
│   ├── api/                       # FastAPI application
│   │   ├── routers/               # Routes: auth, rags, search, docs, discussions
│   │   ├── db.py                  # SQLAlchemy base & engine
│   │   ├── deps.py                # JWT, hashing, auth utilities
│   │   ├── models.py              # ORM Models: User, RAG, Document, Discussion, etc.
│   │   └── main.py                # API app initialization
│   ├── core/                      # Core logic (logging, processing, chunking)
│   ├── modules/                   # OCR, YOLOv8 model server, entity extraction, reranking
│   ├── pipeline/                  # Ingestor, Indexer, Searcher, Answerer
│   └── main.py                    # CLI entrypoint
│
├── config/config.yaml             # Configuration (paths, models, chunking)
├── models/yolov8n-doclaynet.pt    # YOLOv8 model (for layout detection)
├── storage/                       # Logs, data, and vector DBs (auto-generated)
├── requirements.txt
└── README.md
```

---

##  Installation

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/StudyMate.git
cd StudyMate
```

### 2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Install and run Ollama
Ollama is required to run local LLMs such as Llama3:
```bash
ollama pull llama3
```

### 5. Ensure Tesseract is installed
```bash
tesseract --version
```

---

##  Running the FastAPI API

### Start server
```bash
uvicorn src.api.main:app --reload
```

### Access docs
```
http://localhost:8000/docs
```

---

##  Authentication Endpoints

| Method | Endpoint | Description |
|--------|-----------|-------------|
| `POST` | `/auth/signup` | Register a new user |
| `POST` | `/auth/login` | Authenticate and obtain JWT token |
| `POST` | `/auth/change-password` | Change user password |

---

##  RAG API Endpoints

| Method | Endpoint | Description |
|--------|-----------|-------------|
| `POST` | `/rags/{rag_id}/docs/upload` | Upload document to RAG |
| `GET`  | `/rags/{rag_id}/discussions` | Retrieve discussions |
| `POST` | `/rags/{rag_id}/search` | Perform semantic search |
| `POST` | `/rags/{rag_id}/answer` | Generate contextual answer |

---

##  CLI Usage

```bash
python -m src.main ingest <user_id>
python -m src.main index <user_id>
python -m src.main search <user_id> "Explain HCL"
python -m src.main answer <user_id> "Summarize uploaded PDF"
```

### CLI Stages
| Stage | Description |
|--------|--------------|
| `ingest` | Extracts text + layout, cleans, chunks |
| `index` | Generates embeddings and stores vectors |
| `search` | Finds most relevant chunks using ANN |
| `answer` | Generates a grounded answer using LLM |

---

##  Key Components Explained

### **LayoutExtractor**
- Uses YOLOv8 for block segmentation and Tesseract for text extraction.
- Processes PDFs and DOCX files using multiprocessing.

### **BlockProcessor**
- Removes repeated headers/footers and noisy patterns.
- Merges small text blocks to form meaningful units.

### **ChunkBuilder**
- Splits clean text into context-aware chunks suitable for embedding models.

### **Indexer**
- Encodes chunks with Sentence-Transformers.
- Stores embeddings in ChromaDB + HNSWlib for efficient search.

### **Searcher**
- Performs vector similarity search across user-specific embeddings.
- Retrieves most semantically relevant document parts.

### **Reranker**
- Uses CrossEncoder model for improved ranking precision.

### **Answerer**
- Builds context and queries local Ollama LLM for natural-language answers.

---

##  Logging

- All logs are managed via Loguru.
- Default log file: `storage/logs/logging_project.log`
- Automatic log rotation (1MB max, keep 5 files)
- Logs contain ingestion progress, errors, and search traces.

---

## Environment Variables

| Variable | Default | Description |
|-----------|----------|-------------|
| `DATABASE_URL` | `sqlite:///./rag.db` | SQLAlchemy database path |
| `RAG_JWT_SECRET` | `dev-secret` | JWT signing key |
| `JWT_TTL_MIN` | `60` | Token expiration (minutes) |
| `DATA_DIR` | `storage/data` | Uploaded files directory |
| `VECTOR_DIR` | `storage/vectors` | Chroma/HNSW vector database |
| `OLLAMA_API_URL` | `http://localhost:11434` | Local Ollama endpoint |

---

##  Deployment

### Docker
```bash
docker-compose up --build
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

---

##  Roadmap

- [ ] Add streaming answers via SSE  
- [ ] Multilingual OCR support  
- [ ] Frontend dashboard (Next.js)  
- [ ] User analytics and admin panel  
- [ ] Vector DB abstraction layer (FAISS, Milvus)  

---

##  License

This project is licensed under the **MIT License**.  
Feel free to use, modify, and distribute for personal or commercial purposes.

---

##  Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/)
- [Sentence-Transformers](https://www.sbert.net/)
- [ChromaDB](https://docs.trychroma.com/)
- [HNSWlib](https://github.com/nmslib/hnswlib)
- [Ollama](https://ollama.ai)
- [YOLOv8](https://github.com/ultralytics/ultralytics)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
