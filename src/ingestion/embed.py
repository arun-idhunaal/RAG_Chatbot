"""bge-m3 embeddings only (EC-ING-08)."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from src.config.settings import Settings, get_settings

# Confirmed model — never mix models in the same Chroma collection.
ALLOWED_EMBEDDING_MODEL = "BAAI/bge-m3"


class EmbeddingError(RuntimeError):
    """Raised when embedding fails; callers must abort upsert (EC-ING-03)."""


@lru_cache
def _load_model(model_name: str):
    if model_name != ALLOWED_EMBEDDING_MODEL:
        raise EmbeddingError(
            f"Forbidden embedding model '{model_name}'. Only {ALLOWED_EMBEDDING_MODEL} is allowed (EC-ING-08)."
        )
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def get_embedder(settings: Settings | None = None):
    settings = settings or get_settings()
    return _load_model(settings.embedding_model)


def embed_texts(
    texts: Sequence[str],
    *,
    settings: Settings | None = None,
) -> list[list[float]]:
    """Embed texts with BAAI/bge-m3. Raises EmbeddingError on failure."""
    settings = settings or get_settings()
    if settings.embedding_model != ALLOWED_EMBEDDING_MODEL:
        raise EmbeddingError(
            f"Forbidden embedding model '{settings.embedding_model}' (EC-ING-08)."
        )
    if not texts:
        return []
    try:
        model = get_embedder(settings)
        vectors = model.encode(
            list(texts),
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]
    except EmbeddingError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingError(f"Embedding failed: {exc}") from exc
