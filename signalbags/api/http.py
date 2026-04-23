"""
FastAPI server — single POST /api/query endpoint wrapping the Signal harness.

Architecture:
    startup   → pre-warm embedder + register backends + assemble harness once
    /api/query → reuse the shared harness + engine for every request
    /         → serves web/index.html

The harness is singleton. Concurrent requests share one engine, which is
safe here because EvanCore's RuntimeEngine is thread-safe in principle
and the free-tier MiniMax rate limit will be hit long before any
contention matters for a demo.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WEB_ROOT = _PROJECT_ROOT / "web"


class QueryRequest(BaseModel):
    trigger: str


class QueryResponse(BaseModel):
    success: bool
    output: str
    error: str | None = None
    duration_ms: int
    tool_calls: int = 0


def _bootstrap() -> dict[str, Any]:
    """Wire MiniMax env, register backends, assemble harness. Returns app.state payload."""
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")

    # Point EvanCore's config root to a Signal-local empty dir so the
    # default ~/.evancore symlink's demo MCP servers don't auto-load.
    evancore_home = _PROJECT_ROOT / ".evancore-signal"
    evancore_home.mkdir(exist_ok=True)
    os.environ["EVANCORE_HOME"] = str(evancore_home)

    # Translate MINIMAX_* → OPENAI_* that EvanCore's OpenAIModelClient reads.
    key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("MINIMAX_API_KEY not set — edit .env before launching.")
    os.environ["OPENAI_API_KEY"] = key
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")

    from signalbags.adapters.model_patches import apply_minimax_patches
    apply_minimax_patches()

    from signalbags.adapters.embedder import Embedder
    shared_embedder = Embedder()

    from core.backends import role_registry, tool_registry
    from signalbags.backends.signal_role_backend import SignalRoleBackend
    from signalbags.backends.bags_tool_backend import BagsToolBackend
    role_registry.register(SignalRoleBackend(), replace=True)
    tool_registry.register(BagsToolBackend(embedder=shared_embedder), replace=True)

    from core.models.harness_spec import HarnessSpec
    from core.assembly.assembler import HarnessAssembler
    spec = HarnessSpec.from_yaml(str(_PROJECT_ROOT / "specs" / "signal.yaml"))
    model = os.environ.get("MINIMAX_MODEL")
    if model and model != spec.model.model_id:
        spec.model.model_id = model
    harness = HarnessAssembler().assemble(spec)

    from core.runtime.engine import RuntimeEngine
    engine = RuntimeEngine()

    return {
        "harness": harness,
        "engine": engine,
        "embedder": shared_embedder,
        "model_id": spec.model.model_id,
        "indexed_count": _count_indexed_launches(),
    }


def _count_indexed_launches() -> int:
    try:
        from signalbags.core.db import Launch, session_factory
        from sqlalchemy import func, select

        Session = session_factory()
        with Session() as s:
            return s.scalar(select(func.count()).select_from(Launch)) or 0
    except Exception:
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = _bootstrap()
    app.state.harness = state["harness"]
    app.state.engine = state["engine"]
    app.state.model_id = state["model_id"]
    app.state.indexed_count = state["indexed_count"]
    yield


app = FastAPI(
    title="Signal — Bags Launch Intelligence",
    description="Pre-launch strategy copilot for Bags.fm creators.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: open for localhost dev; demo is same-origin so this is mostly a
# safety net if you hit the API from a different port during testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/meta")
async def meta() -> dict:
    return {
        "model_id": getattr(app.state, "model_id", "unknown"),
        "indexed_launches": getattr(app.state, "indexed_count", 0),
        "harness_id": getattr(app.state, "harness", None) and app.state.harness.harness_id,
    }


@app.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    trigger = (req.trigger or "").strip()
    if not trigger:
        raise HTTPException(status_code=400, detail="trigger is empty")

    t0 = time.time()
    result = app.state.engine.run(app.state.harness.harness_id, trigger)
    duration_ms = int((time.time() - t0) * 1000)

    tool_calls = 0
    # best-effort: count tool events in the harness's last session
    try:
        from core.runtime.session_store import session_store
        session = session_store.load(app.state.harness.harness_id, result.session_id)
        if session is not None:
            for turn in session.turns:
                tool_calls += len(getattr(turn, "tool_calls", []) or [])
    except Exception:
        pass

    return QueryResponse(
        success=bool(result.success),
        output=result.output or "",
        error=result.error,
        duration_ms=duration_ms,
        tool_calls=tool_calls,
    )


# ── Streaming endpoint ────────────────────────────────────────────────────
#
# /api/query/stream pushes EvanCore HarnessEvents to the browser as they
# happen (tool calls, tool results, task lifecycle), then emits a final
# `done` event with the aggregated output. Uses SSE-framed chunks over
# a POST body — standard EventSource can't POST, so the frontend reads
# the response body as a stream via fetch + getReader.

_MAX_PAYLOAD_CHARS = 600  # trim huge tool_result strings before sending


def _safe_jsonable(obj: Any) -> Any:
    """Recursively convert an arbitrary payload to JSON-serializable form.

    HarnessEvent.payload may carry pydantic models, enums, datetimes,
    or long strings. We normalize to primitives and trim strings so a
    verbose tool_result doesn't dominate the SSE frame.
    """
    from enum import Enum
    from datetime import datetime as _dt

    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return obj if len(obj) <= _MAX_PAYLOAD_CHARS else obj[:_MAX_PAYLOAD_CHARS] + "…"
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, _dt):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _safe_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_safe_jsonable(v) for v in obj]
    # pydantic v2 model
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return _safe_jsonable(dump())
        except Exception:
            pass
    return repr(obj)[:_MAX_PAYLOAD_CHARS]


def _sse_frame(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/query/stream")
async def query_stream(req: QueryRequest):
    trigger = (req.trigger or "").strip()
    if not trigger:
        raise HTTPException(status_code=400, detail="trigger is empty")

    harness = app.state.harness
    engine = app.state.engine
    harness_id = harness.harness_id

    # Thread-safe queue pipes bus events from the worker thread to the
    # async generator running on the event loop.
    q: queue.Queue = queue.Queue()

    from events.bus import bus  # evancore

    def _handler(ev) -> None:
        # Only forward events for our harness; other harnesses in the
        # same process (unlikely here) should stay isolated.
        if getattr(ev, "harness_id", None) != harness_id:
            return
        q.put(("event", {
            "type": ev.type.value,
            "event_id": ev.event_id,
            "timestamp": ev.timestamp.isoformat(),
            "payload": _safe_jsonable(ev.payload or {}),
        }))

    bus.subscribe_all(_handler)

    def _runner() -> None:
        try:
            t0 = time.time()
            result = engine.run(harness_id, trigger)
            duration_ms = int((time.time() - t0) * 1000)
            q.put(("done", {
                "success": bool(result.success),
                "output": result.output or "",
                "error": result.error,
                "duration_ms": duration_ms,
            }))
        except Exception as e:
            q.put(("error", {"error": f"{type(e).__name__}: {e}"}))
        finally:
            q.put(("close", {}))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

    async def _generator():
        try:
            # Announce start so the client can render the timeline
            # immediately, before the first bus event arrives.
            yield _sse_frame("start", {"harness_id": harness_id, "trigger": trigger[:200]})
            while True:
                kind, data = await asyncio.to_thread(q.get)
                if kind == "event":
                    yield _sse_frame("harness", data)
                elif kind == "done":
                    yield _sse_frame("done", data)
                elif kind == "error":
                    yield _sse_frame("error", data)
                elif kind == "close":
                    break
        finally:
            # Best-effort handler removal — EvanCore's bus has no
            # per-handler unsubscribe, so we reach into the private
            # wildcards list. Pragmatic for this demo.
            try:
                bus._wildcards.remove(_handler)  # noqa: SLF001
            except ValueError:
                pass

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering if any
        },
    )


# Serve the single-page UI. Mount last so /api/* routes win.
if _WEB_ROOT.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_ROOT), html=True), name="web")
