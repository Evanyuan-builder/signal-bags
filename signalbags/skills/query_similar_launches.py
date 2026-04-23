"""
Skill: bags__query_similar_launches

Given a user's narrative / product pitch, return the top-K semantically
closest past Bags launches, with their ticker, name, status, and score.

This is Signal's anchor tool: every strategy judgement is grounded in
"here are comparable past launches on Bags and how they fared," not
LLM priors.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from adapters.skills.base import Skill, SkillResult  # evancore
from signalbags.adapters.embedder import Embedder
from signalbags.core.narrative import SearchHit, load_index, search


DEFAULT_K = 8
MAX_K = 30


class QuerySimilarLaunchesSkill(Skill):
    tool_id = "bags__query_similar_launches"
    description = (
        "在已索引的 Bags launch 历史里做语义检索，返回与输入描述/叙事最相近的 K 个代币。"
        "每条结果包含 symbol / name / feed 状态 / 相似度分数 / 截断的 description。"
        "用途：判断 idea 是否已有雷同先例；给出 narrative 风险与定位差异。"
    )

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder
        self._matrix: np.ndarray | None = None
        self._mints: list[str] | None = None

    def _ensure_embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    def _ensure_index(self, embedder: Embedder) -> tuple[np.ndarray, list[str]]:
        if self._matrix is None or self._mints is None:
            self._matrix, self._mints = load_index(embedder.model_name)
        return self._matrix, self._mints

    def execute(self, query: str, config: dict[str, Any] | None = None) -> SkillResult:
        cfg = config or {}
        k_raw = cfg.get("k", DEFAULT_K)
        try:
            k = max(1, min(int(k_raw), MAX_K))
        except (TypeError, ValueError):
            k = DEFAULT_K

        if not query or not query.strip():
            return SkillResult(
                tool_id=self.tool_id,
                success=False,
                output="",
                error="query is empty",
            )

        embedder = self._ensure_embedder()
        matrix, mints = self._ensure_index(embedder)
        if matrix.size == 0:
            return SkillResult(
                tool_id=self.tool_id,
                success=False,
                output="",
                error="no embeddings indexed — run `scripts/build_embeddings.py` first",
            )

        hits: list[SearchHit] = search(embedder, query, k=k, matrix=matrix, mints=mints)
        return SkillResult(
            tool_id=self.tool_id,
            success=True,
            output=_format_hits(query, hits),
            metadata={
                "k": k,
                "count": len(hits),
                "model": embedder.model_name,
                "hits": [
                    {
                        "token_mint": h.token_mint,
                        "symbol": h.symbol,
                        "name": h.name,
                        "score": h.score,
                        "feed_status": h.feed_status,
                    }
                    for h in hits
                ],
            },
        )

    def to_anthropic_tool(self) -> dict:
        return {
            "name": self.tool_id,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户的叙事 / 产品概念描述；越具体越好（多长没关系）。",
                    },
                    "k": {
                        "type": "integer",
                        "description": f"返回条数，默认 {DEFAULT_K}，最大 {MAX_K}。",
                        "minimum": 1,
                        "maximum": MAX_K,
                    },
                },
                "required": ["query"],
            },
        }


def _format_hits(query: str, hits: list[SearchHit]) -> str:
    if not hits:
        return f"没有找到与 {query!r} 相近的历史 Bags launch。"
    lines = [f"Top {len(hits)} similar Bags launches for: {query!r}", ""]
    for rank, h in enumerate(hits, 1):
        status = f" [{h.feed_status}]" if h.feed_status else ""
        desc = h.description.replace("\n", " ").strip()
        lines.append(
            f"{rank}. [{h.symbol}] {h.name} (score={h.score:.3f}){status}\n"
            f"   mint: {h.token_mint}\n"
            f"   desc: {desc[:160]}"
        )
    return "\n".join(lines)
