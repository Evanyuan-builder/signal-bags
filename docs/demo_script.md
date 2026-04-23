# Signal — Demo Recording Script

Target length: **3 minutes total**. Three live queries, ~45-60s each.

---

## Setup checklist (do NOT record)

- Terminal in a clean iTerm/Warp window, font size ≥ 18pt
- `cd /Users/m2ultra/Desktop/signal-bags && source .venv/bin/activate`
- One pre-warm: `python -m scripts.run_signal --dry-run` so the 60s
  sentence-transformers boot doesn't happen on camera
- Camera covers terminal + small "Signal" banner in corner (optional)
- `.env` loaded with MINIMAX_API_KEY
- DB has embeddings: `python -m scripts.build_embeddings` has been run once

---

## Opening (0:00 – 0:30)

**Hook (spoken)**:

> "Signal is a pre-launch strategy copilot for Bags creators.
> Not a content generator. Not a token launcher.
> It's the judgment engine that sits *before* you click launch —
> reading 2000+ real Bags launches live, and grounding every
> recommendation in actual on-chain data."

**Show on screen**: the project tree
```bash
tree -L 2 signalbags scripts specs
```

Call out in 5 seconds:
- `signalbags/skills/query_similar_launches.py` — the anchor tool
- `specs/signal.yaml` — harness spec
- `specs/roles/bags_launch_strategist.yaml` — the "cold, restrained"
  role persona that forbids hype

---

## Query 1 — Strong-match scenario (0:30 – 1:30)

**Narration before running**:
> "First query — I'm pitching a token for my streaming community."

**Command to type** (paste):
```bash
python -m scripts.run_signal "我想为我的直播社区发一个 AI 助手币，主打帮主播自动回复粉丝、分析观众情绪、维护会员福利"
```

**What to highlight while Signal responds** (~20s tool call, ~20s LLM reasoning):

1. **Tool call is visible** — MiniMax decides to call
   `bags__query_similar_launches` on its own. No prompt engineering
   trick — the role persona makes it a rule.
2. **Real tokens cited**: NUORY, HONCHO, BIGI, LGAI — these are
   actual Bags launches with actual similarity scores (0.40–0.51).
3. **3 paths offered** — each with a named comparison token.
4. **Clarifying questions at the end** — Signal refuses to recommend
   blindly until it knows community size, feature priority, prototype
   readiness. This is the "no hype" role rule enforced.

**Single-sentence voiceover for this demo**:
> "Every one of those numbers came from a live search across 2000+
> indexed Bags launches — nothing is made up by the model."

---

## Query 2 — Honest-uncertainty scenario (1:30 – 2:15)

**Narration before running**:
> "Second query tests whether Signal fabricates when data is thin."

**Command to type**:
```bash
python -m scripts.run_signal "我想发一个面向独立开发者的 AI 代码审查工具代币，让订阅用户能用代币换取 PR 审查积分"
```

**What to highlight**:

1. Signal finds **TURINGMIND** (score 0.586) as the closest comparable.
2. **But then**: Signal notices TURINGMIND isn't in the active feed
   window — `feed_status = None` — and flags "may have failed, need
   verification before relying on it as a comp."
3. **The recommended-action block doesn't commit to a path**.
   Instead Signal tells the user: *confirm TURINGMIND's state first,
   because if it's dead, copying a failed narrative is a losing move.*

**Single-sentence voiceover**:
> "This is the difference — Signal would rather say 'I don't know,
> here's what to verify' than invent confidence."

---

## Query 3 — Clone detection scenario (2:15 – 3:00)

**Narration before running**:
> "Third query — I'll give Signal a draft description I wrote
> and ask it to audit before I launch."

**Command to type**:
```bash
python -m scripts.run_signal "这是我打算给我的 Bags 代币写的描述：'A token inspired by community content.' 帮我在发射前审视一下这段描述。"
```

**What to highlight**:

1. MiniMax extracts the quoted draft string and feeds *only that*
   into the tool — demonstrates smart query reformulation.
2. **Two existing Bags tokens return at score 0.703** — both literally
   named "Community Token" with a description that, in Signal's own
   words, is **"一字不差"** (word-for-word identical).
3. Signal's output opens with "**判断：描述重复风险极高**", names
   both duplicates with partial mint addresses, and gives 3 explicit
   paths (narrow the narrative / change the dimension / rename ticker).
4. Ends by **offering to re-check the revised description** — multi-turn
   loop invitation, not a dead-end response.

**Single-sentence voiceover**:
> "Signal catches when your idea is already on-chain twice — a
> launch-blocking mistake that no content-gen tool would flag."

---

## Closing (3:00 – 3:15)

**Spoken**:
> "Signal is built on EvanCore — an open harness platform I maintain.
> The Bags tool backend, role definition, and data layer are all
> project-local. Anyone can plug a different data source in the same
> way. Full code, tests, and indexer are linked in the README."

**Show on screen**:
- pytest output: `12 passed`
- link to GitHub repo

---

## If something goes wrong on camera

| Symptom | One-line fix |
|---|---|
| `MINIMAX_API_KEY missing` | `cat .env \| grep MINIMAX_API_KEY` — confirm it's set |
| `401 invalid api key (2049)` | Base URL wrong: should be `https://api.minimaxi.com/v1` for `sk-cp-` keys |
| Long boot on first run | You forgot the pre-warm `--dry-run` step. Cut, re-warm, re-shoot |
| `<think>` tag in output | `model_patches.apply_minimax_patches()` didn't fire — check `scripts/run_signal.py` imports |

---

## Post-production notes

- Keep cursor visible in terminal; judges will want to see typing
- If MiniMax tool-call takes > 15s, speed up the dead air with an
  insert shot of the `specs/signal.yaml` file
- Final output is best cut cleanly — don't truncate Signal's
  "推荐行动" block; that's where the persona strength shows
