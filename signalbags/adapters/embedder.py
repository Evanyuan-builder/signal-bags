"""
Local sentence embedding via sentence-transformers.

Default model: `all-MiniLM-L6-v2` — 80MB, 384-dim, English-first but
robust on short noisy text (meme-coin descriptions are exactly this).
Apple-Silicon MPS is auto-detected when available.

First call downloads the model (~80MB) to ~/.cache/huggingface; subsequent
imports are instant.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None) -> None:
        # Lazy import so `import adapters.embedder` doesn't pay the 2s torch boot
        # when only the class name is referenced.
        from sentence_transformers import SentenceTransformer
        import torch

        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self._model = SentenceTransformer(model_name, device=device)
        self.model_name = model_name
        self.device = device
        # New API on sentence-transformers ≥5; fall back to old name for older releases.
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def encode(self, texts: Iterable[str], batch_size: int = 64, normalize: bool = True) -> np.ndarray:
        return self._model.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

    def encode_one(self, text: str, normalize: bool = True) -> np.ndarray:
        return self.encode([text], normalize=normalize)[0]
