"""
BagsToolBackend — scheme `bags`.

Owns the bounded set of `bags__*` tools and dispatches by flat tool_id.
Follows the v2 ToolBackend contract exactly so it slots into the
existing `tool_registry` via `tool_registry.register(BagsToolBackend())`
without touching EvanCore core.
"""
from __future__ import annotations

from typing import Any

from adapters.skills.base import Skill, SkillResult  # evancore
from core.backends.tool_backend import ToolBackend  # evancore

from signalbags.adapters.embedder import Embedder
from signalbags.skills.query_similar_launches import QuerySimilarLaunchesSkill


class BagsToolBackend(ToolBackend):
    scheme = "bags"

    def __init__(self, embedder: Embedder | None = None) -> None:
        # Skills that need embeddings share one Embedder so the 60-s
        # sentence-transformers boot happens at most once per process.
        self._embedder = embedder
        self._skills: dict[str, Skill] = {
            QuerySimilarLaunchesSkill.tool_id: QuerySimilarLaunchesSkill(embedder=embedder),
        }

    def list_tool_ids(self) -> list[str]:
        return list(self._skills.keys())

    def get_tool_def(self, tool_id: str) -> dict | None:
        skill = self._skills.get(tool_id)
        return skill.to_anthropic_tool() if skill else None

    def execute(
        self,
        tool_id: str,
        query: str,
        config: dict[str, Any] | None = None,
        *,
        use_mock: bool = False,
    ) -> SkillResult:
        skill = self._skills.get(tool_id)
        if skill is None:
            return SkillResult(
                tool_id=tool_id,
                success=False,
                output="",
                error=f"unknown tool_id {tool_id!r} for backend {self.scheme}",
            )
        if use_mock:
            return skill.mock(query)
        try:
            return skill.execute(query, config)
        except Exception as e:
            return SkillResult(
                tool_id=tool_id,
                success=False,
                output="",
                error=f"{type(e).__name__}: {e}",
            )
