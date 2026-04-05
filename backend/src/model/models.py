import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, JSON, Index, Column,
)
from sqlalchemy.orm import relationship

from src.datasource.sqlite.sqlite import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    id              = Column(String(36), primary_key=True, default=_uuid)
    title           = Column(String(255), nullable=False, default="New Chat")
    summary         = Column(Text, nullable=True)
    provider        = Column(String(50), nullable=False, default="openai")
    model           = Column(String(100), nullable=True)
    system_prompt   = Column(Text, nullable=True)
    meta            = Column(JSON, nullable=True)
    created_at      = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at      = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    messages = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan", lazy="select"
    )
    files = relationship(
        "File", back_populates="session", cascade="all, delete-orphan", lazy="select"
    )


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id           = Column(String(36), primary_key=True, default=_uuid)
    session_id   = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role         = Column(String(20), nullable=False)       # user | assistant | tool
    content      = Column(Text, nullable=True)
    tool_calls   = Column(JSON, nullable=True)              # outgoing tool invocations
    tool_results = Column(JSON, nullable=True)              # results fed back to LLM
    token_count  = Column(Integer, nullable=True)
    meta         = Column(JSON, nullable=True)
    created_at   = Column(DateTime(timezone=True), nullable=False, default=_now)

    session   = relationship("Session", back_populates="messages")
    tool_logs = relationship(
        "ToolLog", back_populates="message", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        Index("ix_messages_session_id_created_at", "session_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Tool log
# ---------------------------------------------------------------------------

class ToolLog(Base):
    __tablename__ = "tool_logs"

    id                 = Column(String(36), primary_key=True, default=_uuid)
    session_id         = Column(String(36), nullable=False)
    message_id         = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    tool_name          = Column(String(100), nullable=False)
    tool_call_id       = Column(String(100), nullable=True)
    parameters         = Column(JSON, nullable=True)
    result             = Column(JSON, nullable=True)
    error              = Column(Text, nullable=True)
    execution_time_ms  = Column(Float, nullable=True)
    created_at         = Column(DateTime(timezone=True), nullable=False, default=_now)

    message = relationship("Message", back_populates="tool_logs")

    __table_args__ = (
        Index("ix_tool_logs_session_id", "session_id"),
    )


# ---------------------------------------------------------------------------
# File
# ---------------------------------------------------------------------------

class File(Base):
    __tablename__ = "files"

    id            = Column(String(36), primary_key=True, default=_uuid)
    session_id    = Column(String(36), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    original_name = Column(String(512), nullable=False)
    storage_path  = Column(String(1024), nullable=False)
    mime_type     = Column(String(128), nullable=False)
    size_bytes    = Column(Integer, nullable=False)
    parsed_text   = Column(Text, nullable=True)
    chunks        = Column(JSON, nullable=True)
    meta          = Column(JSON, nullable=True)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=_now)
    expires_at    = Column(DateTime(timezone=True), nullable=True)

    session = relationship("Session", back_populates="files")

    __table_args__ = (
        Index("ix_files_session_id", "session_id"),
        Index("ix_files_expires_at", "expires_at"),
    )


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id                 = Column(String(36), primary_key=True, default=_uuid)
    name               = Column(String(255), unique=True, nullable=False)
    version            = Column(Integer, nullable=False, default=1)
    system_prompt      = Column(Text, nullable=True)
    few_shot_examples  = Column(JSON, nullable=True)
    is_active          = Column(Boolean, nullable=False, default=True)
    created_at         = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at         = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
