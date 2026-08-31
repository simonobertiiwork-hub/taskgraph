"""PostgreSQL/pgvector model for versioned engineering-document chunks."""

from uuid import UUID as PyUUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIDocumentChunk(Base):
    __tablename__ = "ai_document_chunks"
    __table_args__ = (
        UniqueConstraint("source_path", "chunk_index", name="uq_ai_chunk_source_index"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_path: Mapped[str] = mapped_column(String(500), index=True)
    section: Mapped[str] = mapped_column(String(500))
    scenario: Mapped[str | None] = mapped_column(String(80), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    document_version: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
