"""
Launch the Signal web UI.

Opens the browser to http://127.0.0.1:8000 after the server accepts
its first request (by then bootstrap has completed, including the
~60s sentence-transformers warm).

Usage:
    python -m scripts.serve           # start on :8000
    python -m scripts.serve --port 9000
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _wait_and_open(port: int) -> None:
    """Poll /api/meta until it 200s, then open the browser. Bootstrap
    includes a 60s embedder warm on first run, so we wait patiently."""
    url = f"http://127.0.0.1:{port}"
    probe = f"{url}/api/meta"
    deadline = time.time() + 180  # 3 minutes is generous for first boot
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(probe, timeout=2) as r:
                if r.status == 200:
                    webbrowser.open(url)
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1.0)
    print(f"[serve] gave up waiting for {probe}; open {url} manually.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")
    args = ap.parse_args()

    if not args.no_browser:
        threading.Thread(target=_wait_and_open, args=(args.port,), daemon=True).start()

    import uvicorn
    uvicorn.run(
        "signalbags.api.http:app",
        host="127.0.0.1",
        port=args.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
