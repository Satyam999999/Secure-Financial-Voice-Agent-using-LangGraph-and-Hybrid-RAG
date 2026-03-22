"""
SQLAlchemy ORM models for PostgreSQL.
Replaces: hardcoded DEMO_USERS + SQLite interactions table.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Float,
    DateTime, Text, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base
import uuid as uuid_lib

class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    username      = Column(String(50), unique=True, nullable=False, index=True)
    email         = Column(String(255), unique=True, nullable=False)
    full_name     = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    account_id    = Column(String(50), unique=True, nullable=False)
    role          = Column(String(20), default="customer")  # customer | agent | admin
    is_active     = Column(Boolean, default=True)
    is_verified   = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    interactions  = relationship("Interaction", back_populates="user", lazy="dynamic")
    sessions      = relationship("UserSession", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username}>"

class UserSession(Base):
    __tablename__ = "user_sessions"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_token = Column(String(500), unique=True, nullable=False)
    chat_session_id = Column(String(100), nullable=True)
    ip_address    = Column(String(45), nullable=True)
    user_agent    = Column(Text, nullable=True)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    last_seen     = Column(DateTime(timezone=True), server_default=func.now())

    user          = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_session_token", "session_token"),
        Index("idx_session_user_id", "user_id"),
    )

class Interaction(Base):
    __tablename__ = "interactions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id    = Column(String(100), nullable=False, index=True)
    timestamp     = Column(DateTime(timezone=True), server_default=func.now())
    question      = Column(Text, nullable=False)
    intent        = Column(String(50), nullable=True, index=True)
    answer        = Column(Text, nullable=True)
    tool_used     = Column(String(100), nullable=True)
    blocked       = Column(Boolean, default=False)
    num_chunks    = Column(Integer, default=0)
    sources       = Column(JSONB, default=list)
    confidence    = Column(Float, nullable=True)
    confidence_label = Column(String(10), nullable=True)
    flagged       = Column(Boolean, default=False)
    flag_reason   = Column(String(200), nullable=True)
    error         = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    user          = relationship("User", back_populates="interactions")

    __table_args__ = (
        Index("idx_interaction_session", "session_id"),
        Index("idx_interaction_intent", "intent"),
        Index("idx_interaction_timestamp", "timestamp"),
    )

class Escalation(Base):
    __tablename__ = "escalations"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(String(100), nullable=False)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    timestamp     = Column(DateTime(timezone=True), server_default=func.now())
    reason        = Column(Text, nullable=False)
    conversation  = Column(JSONB, default=list)
    status        = Column(String(20), default="pending", index=True)
    agent_response = Column(Text, nullable=True)
    resolved_at   = Column(DateTime(timezone=True), nullable=True)
    resolved_by   = Column(String(50), nullable=True)