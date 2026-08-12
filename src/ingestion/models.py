"""Chunk and scrape result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


Corpus = Literal["scheme", "general"]


@dataclass
class ScrapedPage:
    url: str
    title: str
    corpus: Corpus
    scheme_id: str | None
    html: str
    scraped_at: datetime
    status: Literal["ok", "empty", "error"]
    error: str | None = None


@dataclass
class CleanedDocument:
    url: str
    title: str
    corpus: Corpus
    scheme_id: str | None
    text: str
    sections: list[tuple[str | None, str]]  # (heading, body)
    content_hash: str
    scraped_at: datetime
    out_of_scope_sections: list[str] = field(default_factory=list)


@dataclass
class ChunkRecord:
    chunk_id: str
    corpus: Corpus
    scheme_id: str | None
    fact_types: list[str]
    source_url: str
    source_title: str
    page_ref: str | None
    scraped_at: str  # ISO-8601
    content_hash: str
    text: str
    out_of_scope: bool = False


@dataclass
class UrlAuditEntry:
    url: str
    status: Literal["ok", "unchanged", "empty", "error", "stale_kept"]
    chunk_count: int
    scraped_at: str
    error: str | None = None
    content_hash: str | None = None
    scheme_id: str | None = None
    corpus: str | None = None
