# Signal — Bags Launch Intelligence Copilot

> A pre-launch strategy engine for Bags.fm creators. Not a content
> generator, not a token launcher — the judgment layer that sits
> *before* you click launch.

Built for the [Bags Hackathon](https://bags.fm/hackathon). Signal reads
**live Bags on-chain data** and grounds every strategy judgment in
real comparable launches. No LLM hallucination, no hype copywriting,
just decisions you can defend.

---

## What Signal does

Given a user's launch idea, Signal will:

1. **Judge** — is the narrative launch-ready? Which risks matter?
2. **Route** — 2–3 comparable launch paths, each referencing a named
   Bags token as comp.
3. **Act** — convert the chosen path into next concrete steps
   (launch-tx generation is designed but not yet wired).
4. **Audit** — take an existing draft description and surface if it's
   already an on-chain clone.

Every number Signal cites (similarity scores, status counts,
comparable tokens) traces back to its local index of **2,000+ real
Bags launches** pulled from the Bags API + Helius DAS API.

---

## Architecture

```
  ┌───────────────┐            ┌──────────────────────────────┐
  │ user prompt   │ ─► MiniMax │ signal.yaml harness (EvanCore)│
  └───────────────┘    ModelM2 │  role: bags_launch_strategist │
                               │  tool: bags__query_similar_   │
                               │        launches               │
                               └──────────┬───────────────────┘
                                          │ tool call
                                          ▼
                              ┌──────────────────────────┐
                              │ BagsToolBackend          │
                              │  (scheme: bags)          │
                              └──────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────────┐
                              │ narrative.search()       │
                              │ sentence-transformers    │
                              │ all-MiniLM-L6-v2  (MPS)  │
                              └──────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────────┐
                              │ SQLite (2119 launches,   │
                              │ 2079 embeddings)         │
                              │                          │
                              │ fed by:                  │
                              │ • Bags /token-launch/feed│
                              │ • Bags /solana/bags/pools│
                              │ • Helius getAssetBatch   │
                              └──────────────────────────┘
```

Signal is built on top of [EvanCore](https://github.com/evanyuan-builder/evancore),
a harness-engineering platform with a v2 pluggable backend model
(Role / Skill / Memory / Tool). Signal adds two backends — `signal://`
for roles and `bags://` for tools — without touching EvanCore core.

---

## Quickstart

```bash
# 1. Install EvanCore (sibling clone required) + Signal
git clone https://github.com/evanyuan-builder/evancore ../evancore
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ../evancore
pip install -e ".[test]"
pip install sentence-transformers   # pulls torch + 80MB model on first run

# 2. Configure
cp .env.example .env
# edit .env:
#   MINIMAX_API_KEY=sk-cp-...         (domestic key)
#   MINIMAX_BASE_URL=https://api.minimaxi.com/v1
#   BAGS_API_KEY=bags_prod_...
#   HELIUS_API_KEY=<uuid>

# 3. Build local index (one-time, ~30 seconds + first-run model download)
python -m scripts.index_bags --limit 2000   # ~17s: feed + pools + helius enrich
python -m scripts.build_embeddings          # ~4s after model cache is warm

# 4a. Run Signal via CLI
python -m scripts.run_signal "我想为我的直播社区发一个 AI 助手币"

# 4b. Or launch the web UI (opens http://127.0.0.1:8000 automatically)
python -m scripts.serve
```

---

## Demo

See [`docs/demo_script.md`](docs/demo_script.md) for the three-scenario
recording plan:

1. **Strong match** — AI-assistant streaming token pitch; Signal
   cites 4 comparable tokens in 0.40–0.51 range and gives 3 paths.
2. **Honest "I don't know"** — niche code-review token; Signal names
   TURINGMIND as the closest comp but flags it as inactive and
   refuses to commit to a path.
3. **Clone detection** — generic community-token draft; Signal
   surfaces **two identical existing launches** and calls the draft
   "一字不差" (word-for-word identical).

---

## Tests

```bash
pytest -v
```

Current: **12 tests, all green** (`tests/test_bags_tool_backend.py`
covers ToolBackend contract + real semantic search;
`tests/test_model_patches.py` covers MiniMax `<think>`-stripping).

---

## Acknowledgments

- **Bags.fm** — public API + 174k-pool universe
- **Helius** — free-tier DAS API for Metaplex metadata enrichment
- **MiniMax (M2.7)** — OpenAI-compatible endpoint with tool calling
- **EvanCore** — harness platform Signal extends
- **sentence-transformers** — `all-MiniLM-L6-v2` for embeddings
