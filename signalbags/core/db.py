"""
Local SQLite schema for Signal.

Four tables power the strategy engine:

- launches         : per-mint registry (Bags pools + Helius metadata)
- launch_refresh   : per-mint refresh marker (when we last touched it)
- narrative_clusters : optional clustering assignments (filled by a later job)
- runs             : per-session strategy runs (for the web UI + MCP history)

Tables are additive; the schema is not final and we'll migrate with a
simple "drop + recreate" during hackathon dev since no user data is held.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Launch(Base):
    __tablename__ = "launches"

    token_mint = Column(String, primary_key=True)

    # From /solana/bags/pools
    dbc_config_key = Column(String)
    dbc_pool_key = Column(String)

    # From Helius DAS (may be NULL if enrichment hasn't run or mint had no metadata)
    name = Column(String)
    symbol = Column(String)
    description = Column(Text)
    image = Column(String)
    interface = Column(String)
    decimals = Column(Integer)
    last_indexed_slot = Column(Integer)

    # From /token-launch/feed (only populated for recent-100 at time of ingest)
    feed_status = Column(String)  # PRE_GRAD / MIGRATED / ...
    twitter = Column(String)
    website = Column(String)
    launch_signature = Column(String)

    # Raw envelope payloads for debugging / future re-parsing
    raw_helius = Column(JSON)
    raw_feed = Column(JSON)

    # Bookkeeping
    first_seen_at = Column(DateTime, default=utcnow)
    last_enriched_at = Column(DateTime)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    started_at = Column(DateTime, default=utcnow)
    user_input = Column(Text)
    result_json = Column(JSON)


class LaunchEmbedding(Base):
    """
    Separate from Launch so the schema stays additive during dev
    (no ALTER TABLE, no migrations needed while we iterate on models).
    """
    __tablename__ = "launch_embeddings"

    token_mint = Column(String, primary_key=True)
    model = Column(String, primary_key=True)  # composite PK: same mint, different models coexist
    dim = Column(Integer)
    embedding_json = Column(Text)  # JSON list[float]; 2k × 384-dim = ~3MB total, fine
    source_text = Column(Text)     # the exact string we embedded (for audit / re-embed)
    created_at = Column(DateTime, default=utcnow)


def get_engine(db_path: str | None = None):
    path = db_path or os.environ.get("SIGNAL_DB_PATH") or "./db/signal.sqlite"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True)


def init_db(db_path: str | None = None) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def session_factory(db_path: str | None = None):
    return sessionmaker(bind=get_engine(db_path), expire_on_commit=False, future=True)
