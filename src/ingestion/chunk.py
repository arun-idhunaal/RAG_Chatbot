"""Structure-aware chunking (Architecture §4.4)."""

from __future__ import annotations

import uuid
from datetime import datetime

import tiktoken

from src.config.fact_types import OUT_OF_SCOPE_FACT_TYPE
from src.config.settings import Settings, get_settings
from src.ingestion.clean import tag_fact_types
from src.ingestion.models import ChunkRecord, CleanedDocument

_ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def chunk_document(
    doc: CleanedDocument,
    *,
    settings: Settings | None = None,
) -> list[ChunkRecord]:
    """Split cleaned document into ~400–700 token chunks with overlap."""
    settings = settings or get_settings()
    scraped_at = _iso(doc.scraped_at)
    chunks: list[ChunkRecord] = []

    for heading, body in doc.sections:
        section_chunks = _chunk_section(
            heading=heading,
            body=body,
            target=settings.chunk_target_tokens,
            max_tokens=settings.chunk_max_tokens,
            overlap=settings.chunk_overlap_tokens,
        )
        for page_ref, text in section_chunks:
            fact_types = tag_fact_types(text)
            out_of_scope = OUT_OF_SCOPE_FACT_TYPE in fact_types and len(fact_types) == 1
            # Drop pure out-of-scope chunks from the answerable index (EC-ING-05).
            if out_of_scope:
                continue
            # Strip out_of_scope tag from mixed chunks but keep in-scope tags.
            fact_types = [t for t in fact_types if t != OUT_OF_SCOPE_FACT_TYPE]
            chunks.append(
                ChunkRecord(
                    chunk_id=str(uuid.uuid4()),
                    corpus=doc.corpus,
                    scheme_id=doc.scheme_id,
                    fact_types=fact_types,
                    source_url=doc.url,
                    source_title=doc.title,
                    page_ref=page_ref,
                    scraped_at=scraped_at,
                    content_hash=doc.content_hash,
                    text=text,
                    out_of_scope=False,
                )
            )
    return chunks


def _chunk_section(
    *,
    heading: str | None,
    body: str,
    target: int,
    max_tokens: int,
    overlap: int,
) -> list[tuple[str | None, str]]:
    prefix = f"{heading}\n\n" if heading else ""
    # Keep tables / short sections intact when under max.
    if count_tokens(prefix + body) <= max_tokens:
        return [(heading, (prefix + body).strip())]

    # Split on paragraphs / table rows first.
    parts = [p.strip() for p in body.split("\n") if p.strip()]
    windows: list[str] = []
    current: list[str] = []
    current_tokens = count_tokens(prefix) if prefix else 0

    for part in parts:
        part_tokens = count_tokens(part)
        if current and current_tokens + part_tokens + 1 > target:
            windows.append("\n".join(current))
            # Overlap: keep last ~overlap tokens worth of trailing parts
            current = _overlap_tail(current, overlap)
            current_tokens = count_tokens("\n".join(current)) if current else 0
        current.append(part)
        current_tokens += part_tokens + 1
        # Hard cap: if a single part exceeds max, hard-split by tokens
        if part_tokens > max_tokens:
            windows.extend(_hard_split(part, max_tokens, overlap))
            current = []
            current_tokens = 0

    if current:
        windows.append("\n".join(current))

    results: list[tuple[str | None, str]] = []
    for w in windows:
        text = (prefix + w).strip() if prefix else w.strip()
        if text:
            results.append((heading, text))
    return results


def _overlap_tail(parts: list[str], overlap_tokens: int) -> list[str]:
    if not parts or overlap_tokens <= 0:
        return []
    acc: list[str] = []
    tokens = 0
    for part in reversed(parts):
        t = count_tokens(part)
        if tokens + t > overlap_tokens and acc:
            break
        acc.insert(0, part)
        tokens += t
    return acc


def _hard_split(text: str, max_tokens: int, overlap: int) -> list[str]:
    tokens = _ENC.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    out: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        out.append(_ENC.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start = max(end - overlap, start + 1)
    return out


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat()
    return dt.isoformat()
