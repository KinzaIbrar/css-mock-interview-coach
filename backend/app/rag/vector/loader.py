"""Loads and validates the RAG evidence index (FAISS vectors + aligned metadata + its own recorded
config) from the approved baseline directory. Never accepts inconsistent artifacts: every count/shape
is cross-checked before a bundle is handed back.

Caching mirrors `app.agents.runtime`'s singleton pattern (one shared object per worker process), plus a
short failure cooldown -- borrowed from `GeminiProvider`'s cooldown -- so a persistently broken index
doesn't re-read disk and re-log on every single request.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.rag.vector.errors import (
    RagConfigInvalid,
    RagDimensionMismatch,
    RagError,
    RagIndexCorrupted,
    RagIndexMissing,
    RagMetadataMismatch,
)

logger = logging.getLogger("app.rag.vector")

REQUIRED_METADATA_FIELDS = ("chunk_id", "subject", "topic", "source_type", "source_title", "content")
FAILURE_COOLDOWN_SECONDS = 60.0


@dataclass(frozen=True)
class IndexBundle:
    index: "faiss.Index"  # noqa: F821 - faiss imported lazily inside load_bundle, type checked loosely here
    records: list[dict]
    model_name: str
    embedding_dim: int
    chunk_count: int


def load_bundle(index_dir: Path) -> IndexBundle:
    """Pure load + validate (no caching). Raises a `RagError` subclass on any inconsistency."""
    import faiss  # imported here, not at module scope, so importing this module never pulls in faiss/torch

    index_path = index_dir / "css_knowledge_base.faiss"
    metadata_path = index_dir / "css_knowledge_base_metadata.jsonl"
    config_path = index_dir / "index_config.json"

    missing = [p.name for p in (index_path, metadata_path, config_path) if not p.exists()]
    if missing:
        raise RagIndexMissing(f"missing RAG artifact file(s): {', '.join(missing)}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RagIndexCorrupted(f"index_config.json could not be parsed: {exc}") from None

    model_name = config.get("model_name")
    if not model_name or not isinstance(model_name, str):
        raise RagConfigInvalid("index_config.json is missing a non-empty 'model_name'")
    if config.get("normalize_embeddings") is not True:
        # This loader's cosine-via-inner-product retrieval assumes both index and query vectors are
        # L2-normalized; an index built without that would silently return meaningless scores.
        raise RagConfigInvalid("index_config.json does not declare normalize_embeddings: true")
    embedding_dim = config.get("embedding_dim")
    chunk_count = config.get("chunk_count")
    if not isinstance(embedding_dim, int) or embedding_dim <= 0:
        raise RagConfigInvalid("index_config.json has an invalid 'embedding_dim'")
    if not isinstance(chunk_count, int) or chunk_count <= 0:
        raise RagConfigInvalid("index_config.json has an invalid 'chunk_count'")

    try:
        records = []
        with open(metadata_path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise RagIndexCorrupted(f"metadata line {line_no} is not valid JSON: {exc}") from None
    except OSError as exc:
        raise RagIndexCorrupted(f"metadata file could not be read: {exc}") from None

    try:
        index = faiss.read_index(str(index_path))
    except Exception as exc:  # noqa: BLE001 - faiss raises its own untyped RuntimeError on a bad file
        raise RagIndexCorrupted(f"FAISS index could not be read: {exc}") from None

    # --- cross-checks: never silently accept inconsistent artifacts ---
    if index.ntotal != len(records) or index.ntotal != chunk_count:
        raise RagMetadataMismatch(
            f"count mismatch: FAISS ntotal={index.ntotal}, metadata rows={len(records)}, "
            f"config chunk_count={chunk_count}"
        )
    if index.d != embedding_dim:
        raise RagDimensionMismatch(f"FAISS dimension={index.d} != config embedding_dim={embedding_dim}")

    seen_ids: set[str] = set()
    for i, r in enumerate(records):
        missing_fields = [f for f in REQUIRED_METADATA_FIELDS if not r.get(f)]
        if missing_fields:
            raise RagMetadataMismatch(f"metadata row {i} is missing required field(s): {missing_fields}")
        cid = r["chunk_id"]
        if cid in seen_ids:
            raise RagMetadataMismatch(f"duplicate chunk_id in metadata: {cid!r}")
        seen_ids.add(cid)

    return IndexBundle(index=index, records=records, model_name=model_name, embedding_dim=embedding_dim, chunk_count=chunk_count)


_lock = threading.Lock()
_cached_bundle: IndexBundle | None = None
_cached_bundle_path: Path | None = None
_last_failure: RagError | None = None
_last_failure_at: float = 0.0


def get_cached_bundle(index_dir: Path) -> IndexBundle:
    """Thread-safe singleton accessor. Re-raises a cached failure (without re-reading disk or re-logging)
    for FAILURE_COOLDOWN_SECONDS after a failed load, then tries again."""
    global _cached_bundle, _cached_bundle_path, _last_failure, _last_failure_at
    index_dir = Path(index_dir).resolve()
    with _lock:
        if _cached_bundle is not None and _cached_bundle_path == index_dir:
            return _cached_bundle
        if _last_failure is not None and (time.monotonic() - _last_failure_at) < FAILURE_COOLDOWN_SECONDS:
            raise _last_failure
        try:
            bundle = load_bundle(index_dir)
        except RagError as exc:
            logger.warning("RAG index unavailable (%s): %s", exc.code, exc)
            _last_failure, _last_failure_at = exc, time.monotonic()
            raise
        _cached_bundle, _cached_bundle_path = bundle, index_dir
        _last_failure = None
        logger.info("RAG index loaded: %d chunks, dim=%d, model=%s", bundle.chunk_count, bundle.embedding_dim, bundle.model_name)
        return bundle


def _reset_cache_for_tests() -> None:
    """Test-only: clears the module-level singleton so each test starts clean."""
    global _cached_bundle, _cached_bundle_path, _last_failure, _last_failure_at
    with _lock:
        _cached_bundle, _cached_bundle_path, _last_failure, _last_failure_at = None, None, None, 0.0
