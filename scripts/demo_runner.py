"""
One-take demo runner — sequences the three validated scenarios from
docs/demo_script.md with clean formatting and pauses for narration.

Usage:
    python -m scripts.demo_runner             # interactive: press Enter between queries
    python -m scripts.demo_runner --auto      # no pauses, useful for rehearsal timing
    python -m scripts.demo_runner --query 2   # run just scenario 2 (1-indexed)

Pre-warms the embedder + assembles the harness once, so on-camera you
don't eat a 60-second sentence-transformers boot between queries.
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

_evancore_home = _root / ".evancore-signal"
_evancore_home.mkdir(exist_ok=True)
os.environ["EVANCORE_HOME"] = str(_evancore_home)

from signalbags.adapters.model_patches import apply_minimax_patches  # noqa: E402
apply_minimax_patches()

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.rule import Rule  # noqa: E402
from rich.text import Text  # noqa: E402

console = Console()


# Scenarios mirror docs/demo_script.md. Do not reorder without updating
# the script — each scenario's pre-roll talking point is position-specific.
SCENARIOS = [
    {
        "label": "Scenario 1 / 3 — Strong-match",
        "intent": "A pitch with comparable Bags precedent — show Signal citing real data",
        "query": (
            "A token for an AI agent that auto-trades memecoins based on volume "
            "trends and social sentiment — holders get a cut of the agent's PnL "
            "and vote on trading parameters."
        ),
        "watch_for": (
            "Signal calls bags__query_similar_launches on its own, cites "
            "comparable AI-agent tokens (e.g. BTI, BOND, RAI), returns 3 paths, "
            "ends with clarifying questions instead of a hype recommendation."
        ),
    },
    {
        "label": "Scenario 2 / 3 — Honest uncertainty",
        "intent": "A pitch with only one weak comp — show Signal refusing to fabricate",
        "query": (
            "I want to launch a subscription-based AI code reviewer token. "
            "Holders pay to redeem PR-review credits and vote on the review "
            "rules the AI follows."
        ),
        "watch_for": (
            "Signal names TURINGMIND as the closest comp (~0.58) but flags "
            "its feed status as None — 'may have failed, verify first'. "
            "Next-steps block does NOT commit to a path."
        ),
    },
    {
        "label": "Scenario 3 / 3 — Clone detection",
        "intent": "An existing draft description — show Signal catching the clone",
        "query": (
            "Here is the description I drafted for my Bags token: "
            "'A token inspired by community content.' Please audit it "
            "before I go live."
        ),
        "watch_for": (
            "MiniMax extracts the quoted draft, tool returns two existing "
            "'Community Token' launches at ~0.70 each. Signal opens with "
            "'Verdict: high duplicate risk' and calls the draft 'word-for-word "
            "identical' to existing launches."
        ),
    },
]


def _pause(auto: bool, prompt: str) -> None:
    if auto:
        return
    console.print(f"\n[dim]↵ {prompt}[/dim]", end="")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]aborted[/yellow]")
        sys.exit(0)


def _prewarm(console: Console) -> None:
    """Boot the embedder + register backends + assemble harness.

    Returns the harness + engine so all scenarios reuse the same wiring.
    """
    console.log("pre-warming embedder (first run only: ~60s; cached: ~1s)…")
    # Pre-load the embedder so the first query doesn't pay 60s on camera.
    from signalbags.adapters.embedder import Embedder
    from signalbags.skills.query_similar_launches import QuerySimilarLaunchesSkill
    shared_embedder = Embedder()

    from core.backends import role_registry, tool_registry
    from signalbags.backends.signal_role_backend import SignalRoleBackend
    from signalbags.backends.bags_tool_backend import BagsToolBackend
    role_registry.register(SignalRoleBackend(), replace=True)
    # Share the pre-warmed embedder into the skill so the first tool call
    # doesn't re-instantiate.
    tool_registry.register(
        BagsToolBackend(embedder=shared_embedder), replace=True,
    )
    # Reference QuerySimilarLaunchesSkill so import-time side effects
    # (if any) happen now, not mid-demo.
    _ = QuerySimilarLaunchesSkill

    from core.models.harness_spec import HarnessSpec
    from core.assembly.assembler import HarnessAssembler
    spec = HarnessSpec.from_yaml(str(_root / "specs" / "signal.yaml"))
    # Honor runtime MINIMAX_MODEL env override the same way run_signal.py does.
    model = os.environ.get("MINIMAX_MODEL")
    if model and model != spec.model.model_id:
        spec.model.model_id = model
    harness = HarnessAssembler().assemble(spec)

    # Rewire OPENAI_ env from MINIMAX_ so OpenAIModelClient finds them.
    key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        console.print("[red]MINIMAX_API_KEY not set in .env[/red]")
        sys.exit(2)
    os.environ["OPENAI_API_KEY"] = key
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")

    from core.runtime.engine import RuntimeEngine
    engine = RuntimeEngine()
    console.log(
        f"harness ready: [bold]{harness.harness_id}[/bold]  "
        f"role=[cyan]{harness.role.name}[/cyan]  "
        f"tools={harness.tool_ids()}"
    )
    return harness, engine


def _run_scenario(harness, engine, idx: int, scn: dict, auto: bool) -> None:
    console.print(Rule(f"[bold]{scn['label']}[/bold]", style="magenta"))
    console.print(Text(scn["intent"], style="italic dim"))
    console.print()
    console.print(Panel.fit(scn["query"], title=f"trigger · query {idx}", border_style="cyan"))
    console.print(Panel.fit(scn["watch_for"], title="what to narrate", border_style="yellow"))

    _pause(auto, "press Enter to send this trigger to Signal…")

    console.log("dispatching to MiniMax + tool chain…")
    result = engine.run(harness.harness_id, scn["query"])

    status_color = "green" if result.success else "red"
    console.print(Panel(
        result.output or "(empty output)",
        title=f"[{status_color}]Signal · scenario {idx} result[/{status_color}]",
        border_style=status_color,
    ))
    if result.error:
        console.print(f"[red]error:[/red] {result.error}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true", help="skip all pauses; for rehearsal")
    ap.add_argument("--query", type=int, choices=[1, 2, 3], help="run only one scenario (1-indexed)")
    args = ap.parse_args()

    console.print(Rule("[bold magenta]Signal — Live Demo Runner[/bold magenta]"))
    harness, engine = _prewarm(console)

    scenarios = [SCENARIOS[args.query - 1]] if args.query else SCENARIOS
    for i, scn in enumerate(scenarios, start=args.query or 1):
        _run_scenario(harness, engine, i, scn, args.auto)
        if i < (args.query or len(SCENARIOS)):
            _pause(args.auto, "press Enter for the next scenario…")

    console.print(Rule("[bold green]demo complete[/bold green]"))


if __name__ == "__main__":
    main()
