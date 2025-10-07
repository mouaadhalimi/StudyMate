import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
from ..deps import get_db, get_current_user
from ..models import RAGMember
from ...pipeline.searcher import Searcher
from ...core.utils import FileManager
from ...core.Logger import LoggerManager
from pathlib import Path
from ...modules.reranker import Reranker
import requests

router = APIRouter(prefix="/rags", tags=["search"])

class SearchIn(BaseModel):
    """Input schema for a RAG search request."""
    query: str
    top_k: int = 20

class AnswerIn(BaseModel):
    """Input schema for an answer-generation request."""
    query: str

@router.post("/{rag_id}/search")
def search_rag(
    rag_id: int,
    body: SearchIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
    )-> dict:
    """
    Perform a semantic search within a RAG workspace.

    This endpoint retrieves the most relevant document chunks
    for a given query using vector search.

    Args:
        rag_id (int): Identifier of the RAG workspace.
        body (SearchIn): Contains the query and `top_k` parameter.
        db (Session): SQLAlchemy database session dependency.
        user: Authenticated user object from JWT.

    Raises:
        HTTPException: 
            - 403 if the user does not have access to the RAG.

    Returns:
        dict: A dictionary containing a list of retrieved documents, e.g.
              `{"results": [{"text": "...", "score": 0.83}, ...]}`
    """
 
    m = db.query(RAGMember).filter(
        RAGMember.rag_id == rag_id,
        RAGMember.user_id == user.id
    ).first()
    if not m:
        raise HTTPException(403, "No access")

   
    log_manager = LoggerManager(Path("storage/logs"))
    logger = log_manager.get_logger()
    files = FileManager(logger)


    cfg = {
        "paths": {"vector_db": os.getenv("VECTOR_DIR", "storage/vectors")},
        "models": {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"}
    }


    searcher = Searcher(cfg, files, logger, str(user.id))


    res = searcher.search(body.query, top_k=body.top_k)


    logger.info(f"Search done for user {user.id} | query='{body.query}' | results={len(res)}")

    return {"results": res}

@router.post("/{rag_id}/answer")
def get_answer(
    rag_id: int,
    body: AnswerIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
    )-> dict:
    """
    Generate a context-grounded answer from RAG documents.

    This endpoint executes a hybrid retrieval pipeline:
    1. Retrieves top documents via vector search.
    2. Reranks them for relevance.
    3. Generates an answer using a local Ollama LLM model.

    Args:
        rag_id (int): Identifier of the RAG workspace.
        body (AnswerIn): Contains the user's query.
        db (Session): SQLAlchemy database session dependency.
        user: Authenticated user.

    Raises:
        HTTPException:
            - 403 if the user lacks access.
            - 500 if the LLM (Ollama) service fails.

    Returns:
        dict: Contains the generated answer and reranked document contexts.
              Example:
              ```json
              {
                  "answer": "Paris is the capital of France.",
                  "reranked_contexts": [{"text": "...", "score": 0.91}, ...]
              }
              ```
    """
    
    m = db.query(RAGMember).filter(
        RAGMember.rag_id == rag_id,
        RAGMember.user_id == user.id
    ).first()
    if not m:
        raise HTTPException(403, "No access")


    log_manager = LoggerManager(Path("storage/logs"))
    logger = log_manager.get_logger()
    files = FileManager(logger)


    cfg = {
        "paths": {"vector_db": os.getenv("VECTOR_DIR", "storage/vectors")},
        "models": {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"}
    }


    searcher = Searcher(cfg, files, logger, str(user.id))
    retrieved_docs = searcher.search(body.query, top_k=20)

    if not retrieved_docs:
        return {"answer": "No relevant documents found for this question."}

 
    reranker = Reranker(logger=logger)
    reranked_docs = reranker.rerank(body.query, retrieved_docs, top_k=5)

 
    context_texts = "\n\n".join([d["text"] for d in reranked_docs])

  
    prompt = f"""
    You are a helpful assistant. Answer the question using only the information below.
    Question: {body.query}
    Context:\n{context_texts}
    Answer:
    """

    try:
        ollama_host = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": "llama3", "prompt": prompt},
            stream=True
        )
        response.raise_for_status()

   
        answer_parts = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                if "response" in data:
                    answer_parts.append(data["response"])
                if data.get("done"):
                    break
            except json.JSONDecodeError:
                continue

        answer_text = "".join(answer_parts).strip()

    except Exception as e:  
        logger.error(f"Ollama error: {e}")
        raise HTTPException(500, "Ollama service error")

    logger.info(f"Ollama answer generated for query='{body.query}'")

    return {
        "answer": answer_text,
        "reranked_contexts": reranked_docs
    }

