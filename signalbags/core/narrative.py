"""
Narrative search over indexed Bags launches.

Workflow:
  build_index(embedder)      — embed every launch with usable text, persist
  load_index(model)          — pull stored embeddings + mint list into memory
  search(query, k=8)         — cosine-NN against the in-memory matrix

We keep this intentionally brute-force: a 2k × 384 matrix is 3 MB and
a single cosine call is sub-millisecond. FAISS/Annoy are overkill at
this scale and add deploy friction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from signalbags.adapters.embedder import Embedder
from signalbags.core.db import Launch, LaunchEmbedding, session_factory, utcnow


MIN_TEXT_LEN = 10  # below this the embedding is mostly noise from the ticker alone


def launch_source_text(row: Launch) -> str:
    """
    Build the text we embed for a launch.

    We concatenate name + symbol + description so that tickers with empty
    descriptions still contribute something, and narratives with tickers
    like 'XYZ for AI agents' get both signal sources.
    """
    parts = []
    if row.name:
        parts.append(row.name)
    if row.symbol and row.symbol != (row.name or ""):
        parts.append(f"(${row.symbol})")
    if row.description:
        parts.append(row.description)
    return " — ".join(parts).strip()


@dataclass
class SearchHit:
    token_mint: str
    symbol: str
    name: str
    description: str
    score: float
    feed_status: str | None


def build_index(embedder: Embedder, *, min_text_len: int = MIN_TEXT_LEN) -> int:
    """
    Embed every launch row whose (name|symbol|description) concatenated
    exceeds `min_text_len` chars. Upsert into launch_embeddings under
    the embedder's model name.

    Returns count of rows embedded.
    """
    Session = session_factory()
    with Session() as s:
        rows = list(s.scalars(select(Launch)))
        pairs: list[tuple[Launch, str]] = []
        for r in rows:
            text = launch_source_text(r)
            if len(text) >= min_text_len:
                pairs.append((r, text))

        if not pairs:
            return 0

        texts = [t for _, t in pairs]
        vectors = embedder.encode(texts)

        for (row, text), vec in zip(pairs, vectors):
            existing = s.get(LaunchEmbedding, (row.token_mint, embedder.model_name))
            if existing is None:
                existing = LaunchEmbedding(
                    token_mint=row.token_mint,
                    model=embedder.model_name,
                )
                s.add(existing)
            existing.dim = embedder.dim
            existing.embedding_json = json.dumps(vec.tolist())
            existing.source_text = text
            existing.created_at = utcnow()
        s.commit()
        return len(pairs)


def load_index(model_name: str) -> tuple[np.ndarray, list[str]]:
    """
    Load every embedding for the given model into a matrix + parallel mint list.

    Returns (matrix[n, dim], mints[n]).
    """
    Session = session_factory()
    with Session() as s:
        rows = list(
            s.scalars(
                select(LaunchEmbedding).where(LaunchEmbedding.model == model_name)
            )
        )
    if not rows:
        return np.zeros((0, 0)), []
    mints = [r.token_mint for r in rows]
    mat = np.array([json.loads(r.embedding_json) for r in rows], dtype=np.float32)
    return mat, mints


def search(embedder: Embedder, query: str, k: int = 8, *, matrix: np.ndarray | None = None, mints: list[str] | None = None) -> list[SearchHit]:
    if matrix is None or mints is None:
        matrix, mints = load_index(embedder.model_name)
    if matrix.size == 0:
        return []

    q = embedder.encode_one(query).astype(np.float32)
    # embeddings are already unit-normalized, so dot = cosine
    scores = matrix @ q
    top_idx = np.argsort(-scores)[:k]

    Session = session_factory()
    hits: list[SearchHit] = []
    with Session() as s:
        for i in top_idx:
            mint = mints[int(i)]
            row = s.get(Launch, mint)
            if row is None:
                continue
            hits.append(
                SearchHit(
                    token_mint=mint,
                    symbol=row.symbol or "",
                    name=row.name or "",
                    description=(row.description or "")[:200],
                    score=float(scores[int(i)]),
                    feed_status=row.feed_status,
                )
            )
    return hits
