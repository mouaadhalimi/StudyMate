
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ..deps import get_db, get_current_user
from ..models import Discussion, Message, RAGMember

router = APIRouter(prefix="/rags", tags=["discussions"])

class MsgIn(BaseModel):
    """Input schema for a single message in a discussion."""
    role: str
    content: str

class DiscussionIn(BaseModel):
    """Input schema for creating a discussion with an initial list of messages."""
    messages: list[MsgIn]

@router.get("/{rag_id}/discussions")
def list_discussions(
    rag_id: int, 
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
    )-> list[dict]:
    """
    Retrieve all discussions for a given RAG that belong to the current user.

    The endpoint checks if the authenticated user is a member of the specified
    RAG (Retrieval-Augmented Generation) workspace. If authorized, it returns a list
    of all discussions created by the user, including their messages and timestamps.

    Args:
        rag_id (int): Identifier of the RAG workspace.
        db (Session): SQLAlchemy database session dependency.
        user: The currently authenticated user (injected via dependency).

    Raises:
        HTTPException: 
            - 403 if the user is not a member of the given RAG.

    Returns:
        list[dict]: A list of discussions, each containing:
            - id (int): Discussion ID.
            - created_at (str): ISO 8601 creation timestamp.
            - updated_at (str): ISO 8601 update timestamp.
            - messages (list[dict]): List of messages (role, content, created_at).
    """
    if not db.query(RAGMember).filter(
        RAGMember.rag_id == rag_id, 
        RAGMember.user_id == user.id
        ).first():
        raise HTTPException(403, "No access")
    discs = db.query(Discussion).filter(
        Discussion.rag_id == rag_id, 
        Discussion.user_id == user.id
        ).all()
    out = []
    for d in discs:
        out.append({
            "id": d.id,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
            "messages": [{"role": m.role,
                           "content": m.content, 
                           "created_at": m.created_at.isoformat()} for m in d.messages],
        })
    return out

@router.post("/{rag_id}/discussions", status_code=201)
def create_discussion(rag_id: int,
                       body: DiscussionIn, 
                       db: Session = Depends(get_db), 
                       user=Depends(get_current_user)
                       )-> dict:
    """
    Create a new discussion within a given RAG workspace.

    This endpoint allows a user to start a new discussion and optionally
    include an initial list of messages. Only RAG members are authorized to create discussions.

    Args:
        rag_id (int): Identifier of the RAG workspace where the discussion is created.
        body (DiscussionIn): Input data containing a list of messages (role, content).
        db (Session): SQLAlchemy database session dependency.
        user: The currently authenticated user (injected via dependency).

    Raises:
        HTTPException: 
            - 403 if the user is not a member of the given RAG.

    Returns:
        dict: A dictionary containing the new discussion ID.
            Example: `{"id": 42}`
    """
    if not db.query(RAGMember).filter(
        RAGMember.rag_id == rag_id, 
        RAGMember.user_id == user.id
        ).first():
        raise HTTPException(403, "No access")
    d = Discussion(rag_id=rag_id,
                    user_id=user.id, 
                    created_at=datetime.now(timezone.utc), 
                    updated_at=datetime.now(timezone.utc))
    db.add(d); db.flush()
    for msg in body.messages:
        db.add(Message(discussion_id=d.id, 
                       role=msg.role, content=msg.content, 
                       created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"id": d.id}
