
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pathlib import Path
import shutil, os, threading
import multiprocessing as mp
from ..deps import get_db, get_current_user
from ..models import RAG, RAGMember, RoleEnum, User, Document



router = APIRouter(prefix="/rags", tags=["rags"])

class RAGOut(BaseModel):
    """Output schema representing a RAG workspace."""
    id: int
    name: str
    description: str | None = None

class ShareIn(BaseModel):
    """Input schema for sharing a RAG with another user."""
    user_email: str
class RagPatchOut(BaseModel):
    """Response schema for updated RAG metadata."""
    id: int
    name: str
    description: str | None = None



def _background_ingest_index(user_id: str)-> None:
    """
    Background ingestion and indexing pipeline.

    Runs the data ingestion and indexing process for uploaded documents.
    The process spawns a separate model server for layout extraction,
    processes files (OCR, chunking, entity extraction), and updates
    the user’s RAG index.

    Args:
        user_id (str): The ID of the user initiating ingestion.
    """
    import multiprocessing as mp
    from yaml import safe_load
    from ...core.Logger import LoggerManager
    from ...core.utils import FileManager
    from ...core.block_processor import BlockProcessor
    from ...modules.layout_extractor import LayoutExtractor
    from ...modules.document_loader import DocumentLoader
    from ...modules.entity_extractor import EntityExtractor
    from ...core.chunk_builder import ChunkBuilder
    from ...pipeline.ingestor import Ingestor
    from ...pipeline.indexer import Indexer
    from ...modules.model_server import model_server
    from pathlib import Path
    import time

    logger = LoggerManager(Path("storage/logs")).get_logger()
    files = FileManager(logger)
    cfg = safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))

    mp.set_start_method("spawn", force=True)
    manager = mp.Manager()
    server_req_q = manager.Queue()
    server_resp_q = manager.Queue()
    # Start model server for layout extraction
    server = mp.Process(
        target=model_server,
        args=(server_req_q, server_resp_q, "models/yolov8n-doclaynet.pt"),
    )
    server.start()
    time.sleep(3)
    # Initialize processing components
    blockproc = BlockProcessor(logger)
    layout = LayoutExtractor(
        files,
        Path("config/config.yaml"),
        server_req_q=server_req_q,
        server_resp_q=server_resp_q,
        ocr_lang="eng",
    )
    loader = DocumentLoader()
    entities = EntityExtractor(files, Path("config/config.yaml"))
    chunk_size = int(cfg["chunking"]["chunk_size"])
    tokenizer_model = cfg["tokenizer"]["model"]
    chunker = ChunkBuilder(
        chunk_size=chunk_size, tokenizer_model=tokenizer_model, logger=logger
    )

    # Ingest documents
    ing = Ingestor(
        config=cfg,
        file_manager=files,
        layout_extractor=layout,
        document_loader=loader,
        block_processor=blockproc,
        entity_extractor=entities,
        chunk_builder=chunker,
        logger=logger,
        user_id=user_id,
        mode="layout",
        server_req_q=server_req_q,
        server_resp_q=server_resp_q,
    )
    ing.run()

    # Stop model server
    server_req_q.put(None)
    server_resp_q.put(None)
    server.join()

    # Index ingested documents
    indexer = Indexer(cfg, files, logger, user_id)
    indexer.run()

@router.get("", response_model=list[RAGOut])
def list_rags(db: Session = Depends(get_db), user: User = Depends(get_current_user))-> List[RAGOut]:
    """
    Retrieve all RAG workspaces the current user is a member of.

    Args:
        db (Session): SQLAlchemy database session.
        user (User): Authenticated user.

    Returns:
        List[RAGOut]: A list of RAGs the user has access to.
    """
    q = (db.query(RAG)
        .join(RAGMember, RAGMember.rag_id == RAG.id)
        .filter(RAGMember.user_id == user.id, RAGMember.approved == True)
        .all())
    return [RAGOut(id=r.id, name=r.name, description=r.description) for r in q]

@router.post("", response_model=RAGOut, status_code=201)
async def create_rag(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)  
    )-> RAGOut:
    """
    Create a new RAG workspace and upload initial documents.

    Args:
        name (str): Name of the RAG workspace.
        description (Optional[str]): Optional description.
        files (List[UploadFile]): Initial set of documents to upload.
        db (Session): SQLAlchemy session.
        user (User): Authenticated user.

    Returns:
        RAGOut: The created RAG workspace metadata.
    """
    r = RAG(name=name, 
            description=description, 
            created_at=datetime.now(timezone.utc), 
            creator_user_id=user.id)
    db.add(r); db.flush()
    m = RAGMember(rag_id=r.id, 
                  user_id=user.id, 
                  role=RoleEnum.admin, 
                  approved=True, joined_at=datetime.now(timezone.utc))
    db.add(m)
    rag_dir = Path(os.getenv("DATA_DIR", "storage/data")) / str(user.id) / f"rag_{r.id}"
    rag_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        outp = rag_dir / f.filename
        with outp.open("wb") as fp:
            shutil.copyfileobj(f.file, fp)
        d = Document(rag_id=r.id, name=f.filename, 
                     path=str(outp), mime_type=f.content_type, 
                     size_bytes=outp.stat().st_size, 
                     uploaded_at=datetime.now(timezone.utc))
        db.add(d)
    db.commit(); db.refresh(r)
    mp.Process(target=_background_ingest_index, args=(str(user.id),)).start()
    return RAGOut(id=r.id, name=r.name, description=r.description)

@router.delete("/{rag_id}")
def delete_rag(
    rag_id: int,
    scope: str = Query("me", pattern="^(me|global)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)  
    )-> dict:
    """
    Delete a RAG workspace or remove the current user from it.

    Args:
        rag_id (int): The RAG ID.
        scope (str): 'me' to remove only self, 'global' to delete entirely (admin only).
        db (Session): SQLAlchemy session.
        user (User): Authenticated user.

    Returns:
        dict: Details of the operation outcome.
    """
    m = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user.id).first()
    if not m:
        raise HTTPException(404, "Not a member")
    if scope == "global":
        if m.role != RoleEnum.admin:
            raise HTTPException(403, "Only admin can delete globally")
        r = db.get(RAG, rag_id)
        if not r: raise HTTPException(404, "Not found")
        db.delete(r); db.commit()
        return {"detail": "rag deleted globally"}
    else:
        db.delete(m); db.commit()
        remaining = db.query(RAGMember).filter(RAGMember.rag_id == rag_id).order_by(RAGMember.joined_at.asc()).all()
        if not remaining:
            r = db.get(RAG, rag_id)
            if r:
                db.delete(r); db.commit()
            return {"detail": "rag removed from your dashboard (rag deleted as no members left)"}
        if not any(mem.role == RoleEnum.admin for mem in remaining):
            remaining[0].role = RoleEnum.admin
            db.add(remaining[0]); db.commit()
        return {"detail": "rag removed from your dashboard"}



@router.post("/{rag_id}/share")
def share_rag(rag_id: int, body: ShareIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Share a RAG workspace with another user via email.

    Args:
        rag_id (int): The RAG ID.
        body (ShareIn): Target user's email.
        db (Session): SQLAlchemy session.
        user (User): Authenticated user.

    Returns:
        dict: Sharing status and approval information.
    """
    me = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user.id).first()
    if not me:
        raise HTTPException(403, "No access")
    target = db.query(User).filter(User.email == body.user_email).first()
    if not target:
        raise HTTPException(404, "Target user not found")
    exists = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == target.id).first()
    if exists:
        raise HTTPException(409, "Already a member")
    approved = True if me.role == RoleEnum.admin else False
    m = RAGMember(rag_id=rag_id, user_id=target.id, role=RoleEnum.user, approved=approved, joined_at=datetime.now(timezone.utc))
    db.add(m); db.commit()
    return {"detail": "shared" if approved else "pending_approval", "approved": approved}

@router.post("/{rag_id}/share/{user_id}/approve")
def approve_share(rag_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user))-> dict:
    """
    Approve a pending membership request for a RAG workspace.

    Only admins can approve pending invitations.

    Args:
        rag_id (int): The RAG ID.
        user_id (int): ID of the invited user.
        db (Session): SQLAlchemy session.
        user (User): Authenticated user.

    Returns:
        dict: Confirmation message.
    """
    me = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user.id).first()
    if not me or me.role != RoleEnum.admin:
        raise HTTPException(403, "Only admin approves")
    m = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user_id).first()
    if not m:
        raise HTTPException(404, "Membership not found")
    m.approved = True
    db.add(m); db.commit()
    return {"detail": "approved"}

@router.delete("/{rag_id}/share/{user_id}")
def remove_member(rag_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user))-> dict:
    """
    Remove a member from a RAG workspace (admin-only).

    Args:
        rag_id (int): RAG workspace ID.
        user_id (int): ID of the member to remove.
        db (Session): SQLAlchemy session.
        user (User): Authenticated admin.

    Returns:
        dict: Confirmation message.
    """
    me = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user.id).first()
    if not me or me.role != RoleEnum.admin:
        raise HTTPException(403, "Only admin can remove members")
    m = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user_id).first()
    if not m:
        raise HTTPException(404, "Member not found")
    db.delete(m); db.commit()
    return {"detail": "removed"}



@router.patch("/{rag_id}", response_model=RagPatchOut)
async def modify_rag(
    rag_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
    )-> RagPatchOut:
    """
    Modify a RAG workspace’s metadata or upload new documents.

    Only admins can modify RAG details or add new documents.

    Args:
        rag_id (int): The RAG ID.
        name (Optional[str]): New name for the RAG.
        description (Optional[str]): Updated description.
        files (Optional[List[UploadFile]]): Additional files to upload.
        db (Session): SQLAlchemy session.
        user (User): Authenticated user.

    Returns:
        RagPatchOut: Updated RAG workspace information.
    """
    me = db.query(RAGMember).filter(RAGMember.rag_id == rag_id, RAGMember.user_id == user.id, RAGMember.approved == True).first()
    if not me or me.role != RoleEnum.admin:
        raise HTTPException(403, "Only admin can modify")
    r = db.get(RAG, rag_id)
    if not r:
        raise HTTPException(404, "Not found")
    if name is not None: r.name = name
    if description is not None: r.description = description
    db.add(r)
    if files:
        rag_dir = Path(os.getenv("DATA_DIR", "storage/data")) / str(r.creator_user_id) / f"rag_{r.id}"
        rag_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            outp = rag_dir / f.filename
            with outp.open("wb") as fp:
                shutil.copyfileobj(f.file, fp)
            d = Document(rag_id=r.id, name=f.filename, path=str(outp), mime_type=f.content_type, size_bytes=outp.stat().st_size, uploaded_at=datetime.now(timezone.utc))
            db.add(d)
    db.commit(); db.refresh(r)
    threading.Thread(target=_background_ingest_index, args=(str(r.creator_user_id),), daemon=True).start()
    return RagPatchOut(id=r.id, name=r.name, description=r.description)
