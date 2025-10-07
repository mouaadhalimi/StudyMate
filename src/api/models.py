

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON, Index, BigInteger, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .db import Base
import enum

class RoleEnum(str, enum.Enum):
    """Enumerates user roles within a RAG workspace."""
    admin = "admin"
    user = "user"

class Organization(Base):
    """
    Represents an organization (e.g., company or group) that owns users and RAGs.
    """
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    users = relationship("User", back_populates="org")
    rags = relationship("RAG", back_populates="org")

class User(Base):
    """
    Represents an application user with optional organizational affiliation.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    org = relationship("Organization", back_populates="users")
    memberships = relationship("RAGMember", back_populates="user", cascade="all, delete-orphan")
    discussions = relationship("Discussion", back_populates="user")

class RAG(Base):
    """
    Represents a Retrieval-Augmented Generation (RAG) workspace.
    Each RAG belongs to an organization and has a creator (user).
    """
    __tablename__ = "rags"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    creator_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    org = relationship("Organization", back_populates="rags")
    members = relationship("RAGMember", back_populates="rag", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="rag", cascade="all, delete-orphan")
    discussions = relationship("Discussion", back_populates="rag", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_rags_org_name", "org_id", "name", unique=True),)

class RAGMember(Base):
    """
    Associates a user with a RAG workspace, defining their role and access state.
    """
    __tablename__ = "rag_members"
    id = Column(Integer, primary_key=True)
    rag_id = Column(Integer, ForeignKey("rags.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.user)
    approved = Column(Boolean, nullable=False, default=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    rag = relationship("RAG", back_populates="members")
    user = relationship("User", back_populates="memberships")
    __table_args__ = (Index("ix_rag_members_unique", "rag_id", "user_id", unique=True),)

class Document(Base):
    """
    Represents an uploaded document that belongs to a RAG workspace.
    """
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    rag_id = Column(Integer, ForeignKey("rags.id"), nullable=False, index=True)
    name = Column(String(512), nullable=False)
    path = Column(String(1024), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    rag = relationship("RAG", back_populates="documents")
    chunks = relationship("Chunk", back_populates="doc", cascade="all, delete-orphan")

class Chunk(Base):
    """
    Represents a text chunk extracted from a document for embedding or retrieval.
    """
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    doc = relationship("Document", back_populates="chunks")
    __table_args__ = (Index("ix_chunk_doc_idx", "doc_id", "chunk_index", unique=True),)

class Discussion(Base):
    """
    Represents a threaded discussion within a RAG workspace.
    Discussions contain multiple messages and are associated with one user.
    """
    __tablename__ = "discussions"
    id = Column(Integer, primary_key=True)
    rag_id = Column(Integer, ForeignKey("rags.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    rag = relationship("RAG", back_populates="discussions")
    user = relationship("User", back_populates="discussions")
    messages = relationship("Message", back_populates="discussion", cascade="all, delete-orphan")

class Message(Base):
    """
    Represents a single message within a discussion (e.g., user or assistant message).
    """
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    discussion_id = Column(Integer, ForeignKey("discussions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    discussion = relationship("Discussion", back_populates="messages")

class AuditLog(Base):
    """
    Represents an audit trail entry for tracking system actions.
    Useful for compliance, debugging, and monitoring user activities.
    """
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    details_json = Column(JSON, nullable=True)
    ip = Column(String(64), nullable=True)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
