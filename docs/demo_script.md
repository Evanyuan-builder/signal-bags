# Signal — Demo Recording Script

Target length: **3 minutes total**. Three live queries, ~45-60s each.

---

## Setup checklist (do NOT record)

- Browser: use a **clean Incognito/Private window** (no extensions)
- Browser zoom to 125% (`⌘+`) so text is legible in the video
- `cd /Users/m2ultra/Desktop/signal-bags && source .venv/bin/activate`
- Pre-warm in a separate terminal: `python -m scripts.serve` — wait
  for the browser to auto-open and the top-right meta to read
  `model: MiniMax-M2.7 · indexed: 2,119 launches` before recording
- Do a practice click on preset 1 and cancel halfway (warms tool path)
- `.env` has `MINIMAX_API_KEY` and `MINIMAX_BASE_URL=https://api.minimaxi.com/v1`
- DB has embeddings (check by seeing `indexed: 2,119` in the header)

---

## Opening (0:00 – 0:30)

**Hook (spoken)**:

> "Signal is a pre-launch strategy copilot for Bags.fm creators.
> Not a content generator. Not a token launcher.
> It's the judgment engine that sits *before* you click launch —
> reading live Bags on-chain data and grounding every recommendation
> in actual past launches, not model priors."

**On screen**: the web UI is already open. Point out briefly:
- The header shows the model in use and the **2,119 launches indexed
  locally** — "every number you're about to see comes from this corpus."
- The three preset buttons ("strong-match / honest-uncertainty /
  clone-detection") represent the three scenarios we'll run.

---

## Query 1 — Strong-match scenario (0:30 – 1:30)

**Narration before running**:
> "First query — a pitch for an AI trading-agent token that shares PnL
> with holders."

**In the web UI**: click the **`01 strong-match scenario`** preset →
hit `Ask Signal →`.

**What to highlight while Signal responds** (~10s tool, ~15s reasoning):

1. **Live agent trace on the left** — viewers see `tool.called` fire
   with the query MiniMax auto-reformulated from the user's pitch,
   followed by `tool.result` with a preview of the top hits. No faked
   progress bar — these are real EvanCore events over SSE.
2. **Real tokens cited** once the response renders: GTA, RAI,
   SENDITAI, AXONAI, MEMESCORE, CROD — all with concrete scores.
3. **Four-section output** (`Verdict → Evidence → Paths → Next Steps`)
   enforced by the role persona.
4. **No flattery in the Verdict**: expect lines like "the concept
   collapses to 'AI agent meme coin' which is already well-trodden"
   if the differentiation is thin.

**Single-sentence voiceover for this demo**:
> "Every number you just saw — the token names, the scores, the
> crowded-vs-empty assessment — came from a live semantic search
> across 2,000+ indexed Bags launches. Nothing is made up."

---

## Query 2 — Honest-uncertainty scenario (1:30 – 2:15)

**Narration before running**:
> "Second query tests whether Signal fabricates when the data is thin."

**In the web UI**: click **`02 honest-uncertainty scenario`** → `Ask Signal →`.

**What to highlight**:

1. The agent trace shows a much more sparse tool result — the top
   comparable (typically TURINGMIND around 0.58) has no feed status.
2. Signal's **Verdict** opens by flagging the data as thin, not by
   pretending there's a strong comp.
3. **Next Steps** does not commit to a single path. Expect language
   like "verify the status of the closest comparable first" — the
   exact opposite of a content generator that would cheerfully
   pattern-match.

**Single-sentence voiceover**:
> "This is the difference — Signal would rather say 'I don't know,
> here's what to verify' than fabricate confidence."

---

## Query 3 — Clone detection scenario (2:15 – 3:00)

**Narration before running**:
> "Third query — I'll hand Signal a draft description I wrote and
> ask it to audit before I launch."

**In the web UI**: click **`03 clone-detection scenario`** → `Ask Signal →`.

**What to highlight** (this is the visually strongest scenario):

1. Watch the agent trace — MiniMax extracts *only the quoted draft*
   and passes that exact string to the tool. Smart query
   reformulation in action.
2. `tool.result` returns **two existing Bags tokens at score ~0.70**,
   both literally named "Community Token" with a description that is
   word-for-word identical to the draft.
3. Signal's **Verdict** opens with a high-duplicate-risk call-out and
   names both tokens explicitly.
4. **Paths** offers three de-cloning moves (narrow the narrative,
   change the dimension, rename the ticker), and **Next Steps** ends
   with an explicit offer to rescan a revised draft — turns a one-shot
   response into a multi-turn copilot loop.

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
| Header shows `model: offline` | Server isn't running — restart `python -m scripts.serve` |
| `401 invalid api key (2049)` | Base URL wrong: should be `https://api.minimaxi.com/v1` for `sk-cp-` keys |
| Timeline shows `⟳ retrying` + `✗ recovery.failed` | MiniMax overloaded (free-tier 529). Wait 30s, try again, or switch to a different `MINIMAX_MODEL` in `.env` and restart |
| Output is in Chinese | Role YAML reverted — confirm `specs/roles/bags_launch_strategist.yaml` is the English version (should say "You are Signal, a cold, professional…") |
| Long boot on first load | Sentence-transformers cold-loading — top-right meta will fill once ready; just wait |

---

## Post-production notes

- The agent trace (left panel) is the star of the visual — don't
  crop it out in the edit
- If MiniMax tool-call takes > 15s, the pulsing "model forming
  judgment…" placeholder fills the gap on screen, so no cutaway needed
- Final output is best cut cleanly — don't truncate the **Next Steps**
  block; that's where the role's "the signature is yours" line shows
- If you need B-roll, `cat specs/roles/bags_launch_strategist.yaml` in
  a terminal shows the cold-persona rules viewers can read at a glance
- Fallback recording path (if the web UI misbehaves live):
  `python -m scripts.demo_runner` runs the same three scenarios in
  the terminal with the rich-formatted output the CLI already produced
