"""
Signal bootstrap — assemble signal.yaml and run one turn loop.

Wires MiniMax (via OpenAI-compatible endpoint) into EvanCore, registers
Signal's custom role + tool backends, then dispatches a user query
through Claude-equivalent tool-use flow.

Usage:
    # simplest
    python -m scripts.run_signal "我想为我的直播社区发一个 AI 助手币"

    # with explicit model override
    MINIMAX_MODEL=MiniMax-M2.7-highspeed python -m scripts.run_signal "..."

Env vars (set in .env or shell):
    MINIMAX_API_KEY      — required. Your MiniMax platform API key.
    MINIMAX_BASE_URL     — default https://api.minimax.io/v1
                           China alternative: https://api.minimaxi.com/v1
    MINIMAX_MODEL        — default MiniMax-M2.7

Under the hood we translate MINIMAX_* → OPENAI_* because EvanCore's
OpenAIModelClient reads the OPENAI_ names. MiniMax's /v1/chat/completions
is OpenAI-compatible including function calling (tool_calls array).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_root / ".env")

# Point EvanCore's config root to a Signal-local dir so the default
# symlinked ~/.evancore/mcp_servers.yaml (which advertises a demo
# server Signal doesn't ship) isn't auto-loaded. Must be set BEFORE
# any evancore import triggers mcp_tool_backend's default lookup.
_evancore_home = _root / ".evancore-signal"
_evancore_home.mkdir(exist_ok=True)
os.environ["EVANCORE_HOME"] = str(_evancore_home)

# Patch EvanCore's OpenAIModelClient to strip MiniMax's <think> blocks
# from both user-facing output and multi-turn message history.
from signalbags.adapters.model_patches import apply_minimax_patches  # noqa: E402
apply_minimax_patches()

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.syntax import Syntax  # noqa: E402

console = Console()


DEFAULT_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_MODEL = "MiniMax-M2.7"


def _wire_minimax_env() -> tuple[str, str]:
    """Translate MINIMAX_* env → OPENAI_* that EvanCore's OpenAIModelClient expects."""
    key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        console.print("[red]MINIMAX_API_KEY 未设置。请在 .env 里填入 key。[/red]")
        sys.exit(2)
    base_url = os.environ.get("MINIMAX_BASE_URL", DEFAULT_BASE_URL)
    model = os.environ.get("MINIMAX_MODEL", DEFAULT_MODEL)

    # EvanCore's OpenAIModelClient reads these names directly.
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = base_url
    return base_url, model


def _register_signal_backends() -> None:
    """Plug Signal's role + tool backends into EvanCore's registries."""
    from core.backends import role_registry, tool_registry

    from signalbags.backends.signal_role_backend import SignalRoleBackend
    from signalbags.backends.bags_tool_backend import BagsToolBackend

    # replace=True so re-runs in the same process (e.g. notebook) don't raise.
    role_registry.register(SignalRoleBackend(), replace=True)
    tool_registry.register(BagsToolBackend(), replace=True)


def _override_model_if_needed(spec, model_id: str):
    """Respect MINIMAX_MODEL env override over whatever signal.yaml names."""
    if spec.model.model_id != model_id:
        spec.model.model_id = model_id
    return spec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trigger", nargs="?", help="用户要 Signal 帮判断的发射想法/叙事")
    ap.add_argument("--spec", default=str(_root / "specs" / "signal.yaml"))
    ap.add_argument("--dry-run", action="store_true",
                    help="Assemble + register only; skip LLM call. Smoke-test wiring.")
    args = ap.parse_args()

    if not args.trigger and not args.dry_run:
        ap.error("Pass a trigger query, or use --dry-run for wiring smoke-test.")

    base_url, model = _wire_minimax_env() if not args.dry_run else (DEFAULT_BASE_URL, DEFAULT_MODEL)

    # Lazy imports — these pull in the heavy EvanCore runtime.
    _register_signal_backends()
    from core.models.harness_spec import HarnessSpec
    from core.assembly.assembler import HarnessAssembler

    console.log(f"loading spec: {args.spec}")
    spec = HarnessSpec.from_yaml(args.spec)
    spec = _override_model_if_needed(spec, model)

    console.log(f"assembling harness ({spec.id}) …")
    assembler = HarnessAssembler()
    harness = assembler.assemble(spec)
    console.log(
        f"harness ready: id={harness.harness_id} role={harness.role.name} "
        f"tools={harness.tool_ids()}"
    )

    if args.dry_run:
        console.print(Panel.fit(
            f"[green]✓ wiring OK[/green]\n"
            f"role persona preview:\n[dim]{harness.role.persona[:200]}...[/dim]",
            title="dry-run complete",
        ))
        return

    console.log(f"model: openai/{model} @ {base_url}")
    console.print(Panel.fit(args.trigger, title="user trigger"))

    from core.runtime.engine import RuntimeEngine
    engine = RuntimeEngine()
    result = engine.run(harness.harness_id, args.trigger)

    status_color = "green" if result.success else "red"
    console.print(Panel(
        result.output or "(empty output)",
        title=f"[{status_color}]Signal result · success={result.success}[/{status_color}]",
    ))
    if result.error:
        console.print(f"[red]error:[/red] {result.error}")


if __name__ == "__main__":
    main()
