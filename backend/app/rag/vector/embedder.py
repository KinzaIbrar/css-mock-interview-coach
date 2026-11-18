"""Wraps `SentenceTransformer`, loaded lazily (only when RAG is enabled and a retrieval is actually
requested) and cached as a process-wide singleton, mirroring `app.agents.runtime`'s provider-caching
pattern. Importing this module does not import `sentence_transformers`/`torch` -- that import happens
inside `_load_model`, so a RAG-disabled process never pays for it.
"""

import logging
import threading

import numpy as np

from app.rag.vector.errors import RagDimensionMismatch, RagModelLoadFailed

logger = logging.getLogger("app.rag.vector")

_lock = threading.Lock()
_model = None  # type: ignore[var-annotated]  -- SentenceTransformer, imported lazily
_model_name: str | None = None


def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # noqa: BLE001
        raise RagModelLoadFailed(f"sentence-transformers is not importable: {exc}") from None
    try:
        return SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001 - any model-download/load failure
        raise RagModelLoadFailed(f"could not load embedding model {model_name!r}: {exc}") from None


def get_model(model_name: str):
    """Returns the cached model if it matches `model_name`; otherwise loads (and replaces) it once."""
    global _model, _model_name
    with _lock:
        if _model is not None and _model_name == model_name:
            return _model
        try:
            model = _load_model(model_name)
        except RagModelLoadFailed:
            raise
        except Exception as exc:  # noqa: BLE001 - never let an unwrapped exception leave this layer
            raise RagModelLoadFailed(f"could not load embedding model {model_name!r}: {exc}") from None
        _model, _model_name = model, model_name
        logger.info("RAG embedding model loaded: %s", model_name)
        return model


def encode_query(text: str, *, model_name: str, expected_dim: int) -> np.ndarray:
    """Encodes one query string into a single L2-normalized float32 vector of `expected_dim`, matching
    the normalization the index itself was built with."""
    model = get_model(model_name)
    vec = model.encode([text], normalize_embeddings=True)
    vec = np.asarray(vec, dtype="float32")
    if vec.shape != (1, expected_dim):
        raise RagDimensionMismatch(f"query embedding shape {vec.shape} != expected (1, {expected_dim})")
    return vec


def _reset_for_tests() -> None:
    global _model, _model_name
    with _lock:
        _model, _model_name = None, None
