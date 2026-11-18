"""Errors raised by the RAG evidence layer. `code` is a short, safe identifier (never contains secrets
or local file paths) -- mirrors `app.agents.errors`'s LLMError taxonomy so logs/tests follow one
convention across both AI-adjacent subsystems."""


class RagError(Exception):
    code = "rag_error"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message or self.code)
        if code:
            self.code = code


class RagDisabled(RagError):
    """RAG_EVIDENCE_ENABLED is False. Not a failure -- the normal, default state."""

    code = "disabled"


class RagIndexMissing(RagError):
    """One or more of the FAISS index / metadata / config files does not exist on disk."""

    code = "index_missing"


class RagIndexCorrupted(RagError):
    """A file exists but could not be parsed (bad FAISS file, invalid JSON/JSONL)."""

    code = "index_corrupted"


class RagMetadataMismatch(RagError):
    """FAISS vector count, metadata row count and config chunk_count disagree, or chunk IDs are not unique,
    or a metadata row is missing a required field."""

    code = "metadata_mismatch"


class RagDimensionMismatch(RagError):
    """The FAISS index dimension does not match index_config.json's embedding_dim, or an embedding call
    returned an unexpected shape."""

    code = "dimension_mismatch"


class RagConfigInvalid(RagError):
    """index_config.json is missing model_name, or normalize_embeddings is not True (this retriever's
    cosine-via-inner-product math assumes normalized vectors on both sides)."""

    code = "config_invalid"


class RagModelLoadFailed(RagError):
    """The configured SentenceTransformer model could not be loaded."""

    code = "model_load_failed"


class RagRetrievalFailed(RagError):
    """FAISS search() itself raised (corrupt in-memory index, etc.) after a successful load."""

    code = "retrieval_failed"
