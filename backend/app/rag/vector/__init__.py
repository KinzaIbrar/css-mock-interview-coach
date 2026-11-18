"""Optional, feature-flagged vector retrieval of supplementary evaluation evidence.

Importing this package never imports faiss/torch/sentence-transformers -- those happen lazily inside
`loader.load_bundle` / `embedder.get_model`, only when `evidence.get_evidence()` is actually called
with `settings.rag_evidence_enabled = True`.

Public entry point for the rest of the app: `app.rag.vector.evidence.get_evidence` /
`format_for_prompt`. Everything else here is an internal implementation detail of this package.
"""
