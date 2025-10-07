
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime, timezone
import shutil, os
from ..deps import get_db, get_current_user
from ..models import RAGMember, Document

router = APIRouter(prefix="/rags", tags=["documents"])
# Base directory for document storage (default: ./storage/data)
STORAGE_DATA = Path(os.getenv("DATA_DIR", "storage/data")).resolve()
STORAGE_DATA.mkdir(parents=True, exist_ok=True)

@router.post("/{rag_id}/docs/upload", status_code=201)
async def upload_document(rag_id: int, 
                          file: UploadFile = File(...), 
                          db: Session = Depends(get_db), 
                          user=Depends(get_current_user)
                          ) -> dict:
    
    """
    Upload a document to a specific RAG (Retrieval-Augmented Generation) workspace.

    This endpoint allows authorized RAG members to upload files that will be
    stored on the server and registered in the database. Uploaded files are stored
    under a directory structure specific to the RAG (e.g., `storage/data/rag_1/`).

    Args:
        rag_id (int): Identifier of the target RAG workspace.
        file (UploadFile): The uploaded file, automatically handled by FastAPI.
        db (Session): SQLAlchemy database session dependency.
        user: The currently authenticated user (injected via dependency).

    Raises:
        HTTPException:
            - 403 if the user is not a member of the specified RAG.

    Returns:
        dict: Metadata about the uploaded document, including:
            - id (int): Document ID.
            - name (str): Original filename.
            - path (str): Absolute storage path on the server.
    """
    # Check RAG membership for access authorization
    m = db.query(RAGMember).filter(
        RAGMember.rag_id == rag_id, 
        RAGMember.user_id == user.id
        ).first()
    if not m: raise HTTPException(403, "No access to this RAG")

    # Ensure RAG-specific storage directory exists
    rag_dir = STORAGE_DATA / f"rag_{rag_id}"
    rag_dir.mkdir(parents=True, exist_ok=True)

    # Save the uploaded file to disk
    out_path = rag_dir / file.filename
    with out_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create a new document record in the database
    d = Document(rag_id=rag_id, 
                 name=file.filename, 
                 path=str(out_path), 
                 mime_type=file.content_type, 
                 size_bytes=out_path.stat().st_size, 
                 uploaded_at=datetime.now(timezone.utc))
    db.add(d); db.commit(); db.refresh(d)
    return {"id": d.id, "name": d.name, "path": d.path}
