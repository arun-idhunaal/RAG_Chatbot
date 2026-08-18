"""Remote bge-m3 embedding path (Render Free — no local torch)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.config.settings import Settings
from src.ingestion.embed import EmbeddingError, _as_sentence_vector, _l2_normalize, embed_texts


def test_hf_backend_requires_token(tmp_path):
    settings = Settings(
        chroma_persist_dir=tmp_path / "chroma",
        embedding_backend="huggingface",
        hf_token="",
    )
    with pytest.raises(EmbeddingError, match="HF_TOKEN"):
        embed_texts(["expense ratio"], settings=settings)


def test_hf_backend_normalizes_vector(tmp_path, monkeypatch):
    settings = Settings(
        chroma_persist_dir=tmp_path / "chroma",
        embedding_backend="huggingface",
        hf_token="hf_test",
        embedding_batch_size=1,
    )

    def _fake_post(url, headers=None, json=None, timeout=None):
        del url, headers, json, timeout
        resp = MagicMock()
        resp.status_code = 200
        resp.is_success = True
        resp.json.return_value = [3.0, 4.0, 0.0]
        return resp

    monkeypatch.setattr("src.ingestion.embed.httpx.post", _fake_post)
    vectors = embed_texts(["hello"], settings=settings)
    assert len(vectors) == 1
    assert vectors[0] == pytest.approx([0.6, 0.8, 0.0])


def test_as_sentence_vector_mean_pools_tokens():
    raw = [[1.0, 0.0], [3.0, 0.0]]
    assert _as_sentence_vector(raw) == [2.0, 0.0]


def test_l2_normalize_zero_vector():
    assert _l2_normalize([0.0, 0.0]) == [0.0, 0.0]
