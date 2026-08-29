"""add pgvector document chunks

Revision ID: a13f5b27c901
Revises: 68777da3491b
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "a13f5b27c901"
down_revision = "68777da3491b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "ai_document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("section", sa.String(length=500), nullable=False),
        sa.Column("scenario", sa.String(length=80), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_path", "chunk_index", name="uq_ai_chunk_source_index"),
    )
    op.create_index("ix_ai_document_chunks_source_path", "ai_document_chunks", ["source_path"])
    op.create_index("ix_ai_document_chunks_scenario", "ai_document_chunks", ["scenario"])
    op.create_index("ix_ai_document_chunks_content_hash", "ai_document_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_table("ai_document_chunks")
