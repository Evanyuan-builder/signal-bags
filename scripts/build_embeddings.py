"""
One-shot embedding build over the current launches table.

Usage:
    python -m scripts.build_embeddings
    python -m scripts.build_embeddings --query "AI agent that trades"   # build + demo search
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_root / ".env")

from rich.console import Console  # noqa: E402

from signalbags.adapters.embedder import Embedder  # noqa: E402
from signalbags.core.db import init_db  # noqa: E402
from signalbags.core.narrative import build_index, search  # noqa: E402

console = Console()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", type=str, default=None, help="if given, run a demo search after build")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()

    init_db()

    console.log("booting embedder (first run downloads ~80MB) …")
    t0 = time.time()
    embedder = Embedder()
    console.log(f"loaded {embedder.model_name} on {embedder.device}, dim={embedder.dim} ({time.time()-t0:.1f}s)")

    console.log("embedding all launches …")
    t1 = time.time()
    n = build_index(embedder)
    console.log(f"embedded {n} rows in {time.time()-t1:.1f}s")

    if args.query:
        console.log(f"demo search: {args.query!r}")
        hits = search(embedder, args.query, k=args.k)
        for h in hits:
            console.print(f"  [bold]{h.score:.3f}[/bold] [{h.symbol:10}] {h.name[:30]:30} | {h.description[:70]}")


if __name__ == "__main__":
    main()
