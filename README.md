# StudyMate – AI-Powered Study Assistant (RAG Backend)

**StudyMate** is an open-source, intelligent backend platform designed to help **students and independent learners** manage, explore, and understand their study materials more effectively using **Retrieval-Augmented Generation (RAG)** technology.  
It enables users to upload documents, search semantically through their content, and receive AI-generated, context-aware answers — all running locally and privately, without external API costs.

---

## Overview

StudyMate offers a **personalized study experience** through an intuitive backend that organizes knowledge in “RAGs” — **Retrieval-Augmented Knowledge Spaces**.  
Each RAG combines your uploaded study documents with advanced natural language search and AI reasoning capabilities.

After logging in securely, users can:
- Create multiple RAGs (collections of related documents).  
- Upload course notes, articles, or research papers.  
- Ask complex questions and receive precise, source-grounded answers.  
- Review past conversations and discussions tied to each RAG.  
- Share selected RAGs with other users for collaborative learning.

All processing — from text extraction to embedding generation and retrieval — is done locally, ensuring **privacy, reproducibility, and zero dependence on commercial APIs**.

---

## Key Features

###  Intelligent RAG Engine
- Create, organize, and manage custom knowledge spaces.
- Automatically process and embed uploaded documents (PDF, DOCX, TXT).  
- Perform semantic search to instantly locate relevant text segments.  
- Retrieve context-aware AI answers grounded in your uploaded materials.

###  Secure Multi-User System
- User authentication and JWT-based session management.  
- Each user’s data (documents, embeddings, and discussion history) remains isolated.  
- Token-based authorization protects every API route.

###  Full RAG Lifecycle
- **Create RAG:** Provide a name, optional description, and documents. StudyMate handles text extraction, chunking, embedding, and storage.  
- **Modify RAG:** Admins (creators) can edit or add new materials; updates automatically propagate to shared users.  
- **Delete RAG:** Cleanly removes embeddings, documents, and related discussions. Shared RAGs are removed only from the user’s dashboard.  
- **Share RAG:** Share access with specific users by email; admins control permissions and ownership.  
- **Admin Control:** If an admin deletes their own RAG, ownership transfers automatically to the next user with shared access.

###  Personalized AI Discussions
- Each user maintains private chat sessions per RAG.  
- Conversations are stored locally and isolated from other users.  
- Users can revisit prior discussions to track study progress.

---

## System Architecture

```
┌───────────────────────────────┐
│           User Login          │
│ (Email + Password Auth via JWT)│
└───────────────┬───────────────┘
                │
                ▼
         ┌──────────────┐
         │   Dashboard  │
         └──────┬───────┘
                │
  ┌─────────────┼──────────────────────────────────────────────────────┐
  │             │                                                      │
  ▼             ▼                                                      ▼
Create RAG   Manage RAGs (Edit/Delete/Share)                    AI Chat / Search
│            │                                                  │
│            ▼                                                  ▼
│     ┌────────────┐                                   ┌────────────────────────┐
│     │ Embeddings │ ← Sentence-Transformers           │ Local LLM (Ollama)     │
│     └────────────┘   + ChromaDB + HNSWlib            │ Contextual Answers     │
│                                                         Based on User Docs     │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Core Technologies
| Component | Technology | Description |
|------------|-------------|-------------|
| **Backend Framework** | FastAPI | High-performance web framework |
| **Database Layer** | SQLAlchemy + Alembic | ORM and migrations |
| **Vector Search** | ChromaDB + HNSWlib | Embedding storage and ANN search |
| **Embeddings** | Sentence-Transformers | Converts text to numerical vectors |
| **LLM Runtime** | Ollama (Llama3) | Local large language model |
| **OCR + Layout** | Tesseract + YOLOv8 | PDF parsing and text detection |
| **Logging** | Loguru | Structured logging with rotation |

---

## Repository Structure

```
StudyMate/
├── src/
│   ├── api/              # FastAPI app: routers (auth, rags, search, docs, discussions)
│   ├── core/             # Logging, text normalization, and chunking utilities
│   ├── modules/          # OCR, YOLOv8 layout model, embedding, reranking
│   ├── pipeline/         # Ingestion, indexing, semantic search, and answer generation
│   └── main.py           # CLI entrypoint for RAG operations
├── config/               # Configuration files (models, paths, thresholds)
├── storage/              # Logs, uploaded data, and vector database
├── docker-compose.yml    # Local deployment setup
├── requirements.txt      # Dependencies list
└── README.md             # Documentation
```

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/StudyMate.git
cd StudyMate
```

### 2. Create a Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Ollama and Pull the Model
Ollama is required to run local LLMs (e.g., Llama3):
```bash
ollama pull llama3
```

### 5. Verify Tesseract Installation
```bash
tesseract --version
```

---

## Running the Backend Server

Start the FastAPI development server:
```bash
uvicorn src.api.main:app --reload
```

Access the interactive API documentation at:
```
http://localhost:8000/docs
```

---

## API Overview

### Authentication Routes

| Method | Endpoint | Description |
|--------|-----------|-------------|
| `POST` | `/auth/signup` | Register a new user |
| `POST` | `/auth/login` | Login and obtain JWT token |
| `POST` | `/auth/change-password` | Change user password |

### RAG Management Routes

| Method | Endpoint | Description |
|--------|-----------|-------------|
| `POST` | `/rags/create` | Create a new RAG |
| `POST` | `/rags/{rag_id}/docs/upload` | Upload documents to RAG |
| `DELETE` | `/rags/{rag_id}` | Delete RAG |
| `POST` | `/rags/{rag_id}/share` | Share RAG with another user |
| `POST` | `/rags/{rag_id}/search` | Perform semantic search |
| `POST` | `/rags/{rag_id}/answer` | Generate contextual answer |
| `GET` | `/rags/{rag_id}/discussions` | Retrieve user’s personal discussions |

---

## Environment Configuration

| Variable | Default | Description |
|-----------|----------|-------------|
| `DATABASE_URL` | `sqlite:///./rag.db` | Database connection URI |
| `RAG_JWT_SECRET` | `dev-secret` | JWT signing secret |
| `DATA_DIR` | `storage/data` | Directory for uploaded files |
| `VECTOR_DIR` | `storage/vectors` | Directory for vector databases |
| `OLLAMA_API_URL` | `http://localhost:11434` | Local Ollama endpoint |

---

## Logging & Monitoring

StudyMate uses **Loguru** for logging.  
Logs capture ingestion progress, embedding status, semantic search operations, and user actions.

Default log path:
```
storage/logs/logging_project.log
```
Logs automatically rotate when they exceed the configured size limit.

---

## Deployment Options

###  Docker Deployment
```bash
docker-compose up --build
```

###  Kubernetes Deployment
```bash
kubectl apply -f k8s/
```

Both setups create a self-contained backend environment with persistent storage.

---

## Roadmap

- [ ] Add web-based student dashboard (Next.js)  
- [ ] Implement real-time chat with streaming responses  
- [ ] Support multilingual OCR and question answering  
- [ ] Integrate FAISS and Milvus as alternative vector databases  
- [ ] Add metrics dashboard for learning analytics  

---

## License

**MIT License** — you are free to use, modify, and distribute StudyMate for personal, academic, or commercial purposes.

---

## Acknowledgements

StudyMate integrates a rich open-source ecosystem:

- [FastAPI](https://fastapi.tiangolo.com/)  
- [Sentence-Transformers](https://www.sbert.net/)  
- [ChromaDB](https://docs.trychroma.com/)  
- [HNSWlib](https://github.com/nmslib/hnswlib)  
- [Ollama](https://ollama.ai)  
- [YOLOv8](https://github.com/ultralytics/ultralytics)  
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)  

---

**StudyMate** transforms your study materials into an interactive, searchable knowledge space — helping you learn, recall, and understand information with the assistance of modern AI.
