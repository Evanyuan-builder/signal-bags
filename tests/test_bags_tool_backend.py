"""
Smoke tests for BagsToolBackend — the EvanCore integration layer.

These cover the contract surface (list_tool_ids / get_tool_def / execute
shapes) and one real dispatch through to narrative search. The search
test requires the DB already seeded by scripts/index_bags.py +
scripts/build_embeddings.py; we skip when the index is empty so CI
without data doesn't fail opaquely.
"""
from __future__ import annotations

import pytest

from adapters.skills.base import SkillResult

from signalbags.backends.bags_tool_backend import BagsToolBackend
from signalbags.core.narrative import load_index
from signalbags.adapters.embedder import DEFAULT_MODEL


def test_backend_scheme():
    b = BagsToolBackend()
    assert b.scheme == "bags"


def test_backend_lists_query_tool():
    b = BagsToolBackend()
    assert "bags__query_similar_launches" in b.list_tool_ids()


def test_tool_def_shape():
    b = BagsToolBackend()
    td = b.get_tool_def("bags__query_similar_launches")
    assert td is not None
    assert td["name"] == "bags__query_similar_launches"
    assert "query" in td["input_schema"]["properties"]
    assert "k" in td["input_schema"]["properties"]
    assert td["input_schema"]["required"] == ["query"]


def test_unknown_tool_id_returns_failure_not_raise():
    b = BagsToolBackend()
    res = b.execute("bags__nonexistent", "hi")
    assert isinstance(res, SkillResult)
    assert res.success is False
    assert "unknown tool_id" in (res.error or "")


def test_mock_mode_returns_deterministic_success():
    b = BagsToolBackend()
    res = b.execute("bags__query_similar_launches", "any query", use_mock=True)
    assert res.success is True
    assert res.tool_id == "bags__query_similar_launches"


def test_empty_query_returns_explicit_failure():
    b = BagsToolBackend()
    res = b.execute("bags__query_similar_launches", "   ")
    assert res.success is False
    assert "empty" in (res.error or "")


@pytest.mark.skipif(
    load_index(DEFAULT_MODEL)[0].size == 0,
    reason="no embeddings in DB — run scripts/build_embeddings.py first",
)
def test_real_search_returns_hits_with_expected_fields():
    b = BagsToolBackend()
    res = b.execute("bags__query_similar_launches", "AI agent that trades crypto", {"k": 3})
    assert res.success is True
    assert res.tool_id == "bags__query_similar_launches"
    assert "Top" in res.output
    assert res.metadata["count"] >= 1
    first = res.metadata["hits"][0]
    for field in ("token_mint", "symbol", "name", "score"):
        assert field in first
