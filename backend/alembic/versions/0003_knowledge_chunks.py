"""RAG store: knowledge chunks with pgvector embeddings.

The vector column has no fixed dimension so any embedding provider fits; rows are always
filtered by `embedding_model`, so vectors from different providers never mix.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),  # methodology | ledger_note
        sa.Column("source_ref", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False, index=True),
        sa.Column("embedding", Vector(), nullable=False),
        sa.UniqueConstraint("embedding_model", "source", "source_ref", "content_hash"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
