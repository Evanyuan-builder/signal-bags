"""
W1 indexer: pull Bags pool universe → enrich via Helius → land in SQLite.

Usage:
    python -m scripts.index_bags            # default: 500 most-recent-suffix mints
    python -m scripts.index_bags --limit 20 # small run for smoke tests
    python -m scripts.index_bags --feed-only  # only refresh the live-100 feed window

The "most-recent-suffix" ordering is a heuristic: Bags pool response is not
explicitly sorted by launch time, but the pool list *tail* is empirically
the newest additions (confirmed by spot-checking tokenMint suffixes against
the live feed). We take the tail slice for now and revisit once we have
launchSignature → slot mapping for every pool.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Bootstrap path so the script can import sibling packages when run as a file.
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_root / ".env")

from rich.console import Console  # noqa: E402
from sqlalchemy import select  # noqa: E402

from signalbags.adapters.bags_client import BagsClient  # noqa: E402
from signalbags.adapters.helius_client import HeliusClient  # noqa: E402
from signalbags.core.db import Launch, init_db, session_factory, utcnow  # noqa: E402

console = Console()


def upsert_from_feed(Session, bags: BagsClient) -> int:
    items = bags.get_feed()
    with Session() as s:
        for item in items:
            row = s.get(Launch, item.token_mint)
            if row is None:
                row = Launch(token_mint=item.token_mint, first_seen_at=utcnow())
                s.add(row)
            row.name = item.name or row.name
            row.symbol = item.symbol or row.symbol
            row.description = item.description or row.description
            row.image = item.image or row.image
            row.feed_status = item.status
            row.twitter = item.twitter
            row.website = item.website
            row.launch_signature = item.raw.get("launchSignature")
            row.dbc_config_key = item.raw.get("dbcConfigKey") or row.dbc_config_key
            row.dbc_pool_key = item.raw.get("dbcPoolKey") or row.dbc_pool_key
            row.raw_feed = item.raw
        s.commit()
    return len(items)


def upsert_pools(Session, bags: BagsClient, limit: int, seed: int | None = None) -> list[str]:
    pools = bags.get_pools()
    if seed is not None:
        random.seed(seed)
    if limit < len(pools):
        slice_ = random.sample(pools, limit)
        console.log(f"pools total: {len(pools)}, random sample of {limit} (seed={seed})")
    else:
        slice_ = pools
        console.log(f"pools total: {len(pools)}, taking all")
    mints = []
    with Session() as s:
        for p in slice_:
            mint = p.get("tokenMint")
            if not mint:
                continue
            mints.append(mint)
            row = s.get(Launch, mint)
            if row is None:
                row = Launch(token_mint=mint, first_seen_at=utcnow())
                s.add(row)
            row.dbc_config_key = p.get("dbcConfigKey") or row.dbc_config_key
            row.dbc_pool_key = p.get("dbcPoolKey") or row.dbc_pool_key
        s.commit()
    return mints


def enrich_with_helius(Session, helius: HeliusClient, mints: list[str]) -> int:
    assets = helius.get_asset_batch(mints)
    enriched = 0
    with Session() as s:
        for mint, asset in zip(mints, assets):
            md = HeliusClient.extract_metadata(asset)
            if not md:
                continue
            row = s.get(Launch, mint)
            if row is None:
                row = Launch(token_mint=mint, first_seen_at=utcnow())
                s.add(row)
            for k in ("name", "symbol", "description", "image", "interface", "decimals", "last_indexed_slot"):
                if md.get(k) is not None:
                    setattr(row, k, md[k])
            row.raw_helius = asset
            row.last_enriched_at = utcnow()
            enriched += 1
        s.commit()
    return enriched


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2000, help="random sample size from pool universe to enrich")
    ap.add_argument("--seed", type=int, default=42, help="random seed for reproducible sampling")
    ap.add_argument("--feed-only", action="store_true", help="skip pool+helius enrichment; only refresh live feed")
    args = ap.parse_args()

    init_db()
    Session = session_factory()

    with BagsClient() as bags:
        console.log("refresh live feed (recent 100) …")
        n_feed = upsert_from_feed(Session, bags)
        console.log(f"feed upserted: {n_feed}")

        if args.feed_only:
            return

        console.log(f"pull pool universe, random sample={args.limit} …")
        mints = upsert_pools(Session, bags, args.limit, seed=args.seed)

    with HeliusClient() as helius:
        console.log(f"enrich via Helius getAssetBatch for {len(mints)} mints …")
        n_enriched = enrich_with_helius(Session, helius, mints)
        console.log(f"enriched: {n_enriched}/{len(mints)}")

    with Session() as s:
        total = s.scalar(select(Launch).with_only_columns(Launch.token_mint).order_by(None)) and "ok"  # noqa: F841
        count = s.execute(select(Launch)).all()
        with_name = [r for r in count if r[0].name]
        console.log(f"DB summary: total={len(count)}  with_name={len(with_name)}")


if __name__ == "__main__":
    main()
