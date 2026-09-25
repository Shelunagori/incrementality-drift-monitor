"""Chunking, indexing and cosine search.

Sources:
- `docs/METHODOLOGY.md`, split at `## ` headings.
- Ledger notes (free text typed by humans). They are indexed so the agent can find context,
  but they are returned flagged as untrusted data, never as instructions.

Indexing is incremental: a chunk is embedded only if (model, source, ref, content hash) is new;
stale chunks are deleted. Vectors from any other embedding model are dropped first, so switching
EMBEDDING_PROVIDER (e.g. Gemini -> Cloudflare bge-m3) re-indexes once and never mixes
dimensions. Re-running with the same model embeds nothing.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.embeddings import Embeddings
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeChunk
from app.services import monitor

REPO_ROOT = Path(__file__).resolve().parents[3]
METHODOLOGY_PATH = REPO_ROOT / "docs" / "METHODOLOGY.md"


@dataclass(frozen=True)
class Chunk:
    source: str
    source_ref: str
    title: str
    content: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


def chunk_markdown(text: str) -> list[Chunk]:
    """One chunk per `## ` section (the preamble becomes its own chunk)."""
    parts = re.split(r"(?m)^## ", text)
    chunks = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        title = part.splitlines()[0].lstrip("# ").strip() if i else "Overview"
        chunks.append(Chunk("methodology", f"section-{i}", title, part))
    return chunks


def ledger_chunks(session: Session) -> list[Chunk]:
    return [
        Chunk("ledger_note", f"ledger-{e.id}", e.test_name, f"[{e.channel}] {e.notes}")
        for e in monitor.load_ledger(session)
        if e.notes.strip()
    ]


def sync_index(
    session: Session, embedder: Embeddings, model_id: str, methodology: Path = METHODOLOGY_PATH
) -> int:
    """Bring the index for `model_id` up to date. Returns the number of chunks embedded."""
    wanted = chunk_markdown(methodology.read_text()) + ledger_chunks(session)
    session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.embedding_model != model_id))
    existing = session.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.embedding_model == model_id)
    ).all()
    have = {(c.source, c.source_ref, c.content_hash) for c in existing}
    keep = {(c.source, c.source_ref, c.content_hash) for c in wanted}
    stale = [c.id for c in existing if (c.source, c.source_ref, c.content_hash) not in keep]
    if stale:
        session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.id.in_(stale)))
    new = [c for c in wanted if (c.source, c.source_ref, c.content_hash) not in have]
    if new:
        vectors = embedder.embed_documents([c.content for c in new])
        session.add_all(
            KnowledgeChunk(
                source=c.source,
                source_ref=c.source_ref,
                title=c.title,
                content=c.content,
                content_hash=c.content_hash,
                embedding_model=model_id,
                embedding=v,
            )
            for c, v in zip(new, vectors, strict=True)
        )
    session.flush()
    return len(new)


def search(
    session: Session, embedder: Embeddings, model_id: str, query: str, k: int = 3
) -> list[dict]:
    """Top-k chunks by cosine distance."""
    qv = embedder.embed_query(query)
    rows = session.execute(
        select(KnowledgeChunk, KnowledgeChunk.embedding.cosine_distance(qv).label("dist"))
        .where(KnowledgeChunk.embedding_model == model_id)
        .order_by("dist")
        .limit(k)
    ).all()
    return [
        {
            "source": c.source,
            "ref": c.source_ref,
            "title": c.title,
            "content": c.content,
            "similarity": round(1 - float(d), 3),
        }
        for c, d in rows
    ]
