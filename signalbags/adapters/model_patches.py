"""
Signal-local patches for EvanCore's OpenAIModelClient.

Reason: MiniMax-M2.7 returns its chain-of-thought inline in
`message.content` wrapped in `<think>…</think>` tags. Claude, GPT-4.x,
and o1 don't do this (o1 keeps reasoning in a separate field entirely),
so EvanCore's generic OpenAIModelClient never had to strip them.

Without stripping, the thinking leaks two places:
  1. Final user-visible output (cosmetic but unprofessional).
  2. `make_assistant_message` packs `msg.content` back into the message
     history of subsequent turns — the model sees its own reasoning
     and can get confused or waste tokens.

We patch in place rather than forking EvanCore because the fix is
strictly MiniMax-specific; if/when EvanCore lands native reasoning-tag
support upstream we delete this module.

Usage:
    from signalbags.adapters.model_patches import apply_minimax_patches
    apply_minimax_patches()
"""
from __future__ import annotations

import re

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

_applied = False


def strip_think(text: str | None) -> str:
    if not text:
        return text or ""
    return _THINK_RE.sub("", text).lstrip()


def apply_minimax_patches() -> None:
    """Idempotent. Safe to call multiple times in one process."""
    global _applied
    if _applied:
        return

    from adapters import model_client  # evancore

    _orig_chat = model_client.OpenAIModelClient.chat

    def _patched_chat(self, *args, **kwargs):
        resp = _orig_chat(self, *args, **kwargs)
        resp.text = strip_think(resp.text)
        # Scrub the raw message too so make_assistant_message (which reads
        # response.raw.content) doesn't seed the next turn with think tags.
        if resp.raw is not None:
            try:
                resp.raw.content = strip_think(getattr(resp.raw, "content", None))
            except AttributeError:
                pass
        return resp

    model_client.OpenAIModelClient.chat = _patched_chat
    _applied = True
