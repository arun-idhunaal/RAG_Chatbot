"""Runtime settings loaded from environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = parents[2] from src/config/settings.py
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    chroma_persist_dir: Path = Field(default=_REPO_ROOT / "data" / "chroma")
    raw_html_dir: Path = Field(default=_REPO_ROOT / "data" / "raw")
    audit_log_dir: Path = Field(default=_REPO_ROOT / "data" / "audit")
    metrics_log_dir: Path = Field(default=_REPO_ROOT / "data" / "metrics")
    eval_report_dir: Path = Field(default=_REPO_ROOT / "data" / "eval")

    # EC-ING-08: bge-m3 only — do not change collection embedding model.
    embedding_model: str = Field(default="BAAI/bge-m3")
    embedding_batch_size: int = Field(default=8)

    http_timeout_seconds: float = Field(default=30.0)
    http_max_retries: int = Field(default=2)
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    allow_playwright: bool = Field(default=True)
    playwright_wait_ms: int = Field(default=4000)

    # Chunking (Architecture §4.4)
    chunk_target_tokens: int = Field(default=550)
    chunk_min_tokens: int = Field(default=400)
    chunk_max_tokens: int = Field(default=700)
    chunk_overlap_tokens: int = Field(default=65)

    scheme_collection: str = Field(default="mf_scheme_chunks")
    general_collection: str = Field(default="mf_general_chunks")

    # Phase 2 — retrieval & matching
    retrieval_top_k: int = Field(default=5)
    retrieval_min_similarity: float = Field(default=0.55)
    scheme_match_threshold: int = Field(default=82)
    scheme_match_gap: int = Field(default=5)

    # LLM — Groq (hybrid intent classifier + later generation stages)
    groq_api_key: str = Field(default="")
    llm_model: str = Field(default="llama-3.3-70b-versatile")
    llm_temperature: float = Field(default=0.0)
    use_llm_classifier: bool = Field(default=True)

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT


@lru_cache
def get_settings() -> Settings:
    return Settings()
