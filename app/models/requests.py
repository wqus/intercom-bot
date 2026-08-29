from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, Float, Boolean, Integer, BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InboundEvent(Base):
    """Read-only mapping of the main Intercom application's inbound_events table."""

    __tablename__ = "inbound_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(255))
    provider_event_id: Mapped[str] = mapped_column(String(128))
    topic: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportInteraction(Base):
    """Read-only mapping of the main application's support_interactions table."""

    __tablename__ = "support_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_id: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(32))
    question: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(64))
    kb_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    automated: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EscalatedConversation(Base):
    """Read-only mapping of the main application's escalation blocklist."""

    __tablename__ = "escalated_conversations"

    conversation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(64))
    source_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

