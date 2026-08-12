"""Post-ingest / cold-start health check (Architecture §12, EC-X-04)."""

from __future__ import annotations

from dataclasses import dataclass

from src.config.schemes import all_scheme_ids
from src.config.settings import Settings, get_settings
from src.ingestion.store import VectorStore

# EC-X-04 — UI / pipeline fail-closed copy when Chroma is empty.
CORPUS_UNAVAILABLE_MESSAGE = (
    "The knowledge base is currently unavailable. "
    "Please try again after the next data refresh. "
    "I cannot answer from memory or invent fund facts."
)


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    scheme_count: int
    general_count: int
    schemes_present: list[str]
    sample_query_ok: bool
    reason: str | None = None

    def summary(self) -> str:
        status = "OK" if self.ok else "FAIL"
        lines = [
            f"=== Index Health: {status} ===",
            f"scheme chunks: {self.scheme_count}",
            f"general chunks: {self.general_count}",
            f"schemes present: {', '.join(self.schemes_present) or '(none)'}",
            f"sample query: {'ok' if self.sample_query_ok else 'fail'}",
        ]
        if self.reason:
            lines.append(f"reason: {self.reason}")
        return "\n".join(lines)


def check_index_health(
    *,
    settings: Settings | None = None,
    store: VectorStore | None = None,
    require_all_schemes: bool = True,
    run_sample_query: bool = True,
) -> HealthStatus:
    """
    Collections non-empty + optional sample metadata query.

    Cold start / empty Chroma → ok=False (EC-X-04 fail closed).
    """
    settings = settings or get_settings()
    store = store or VectorStore(settings)
    counts = store.counts()
    scheme_n = int(counts.get("scheme") or 0)
    general_n = int(counts.get("general") or 0)
    by_scheme = store.counts_by_scheme()
    present = sorted(sid for sid, n in by_scheme.items() if n > 0)

    if scheme_n <= 0 or general_n <= 0:
        return HealthStatus(
            ok=False,
            scheme_count=scheme_n,
            general_count=general_n,
            schemes_present=present,
            sample_query_ok=False,
            reason="empty_collections",
        )

    expected = set(all_scheme_ids())
    if require_all_schemes and not expected.issubset(set(present)):
        missing = sorted(expected - set(present))
        return HealthStatus(
            ok=False,
            scheme_count=scheme_n,
            general_count=general_n,
            schemes_present=present,
            sample_query_ok=False,
            reason=f"missing_schemes:{','.join(missing)}",
        )

    sample_ok = True
    if run_sample_query:
        sample_ok = _sample_query_ok(store)

    if not sample_ok:
        return HealthStatus(
            ok=False,
            scheme_count=scheme_n,
            general_count=general_n,
            schemes_present=present,
            sample_query_ok=False,
            reason="sample_query_failed",
        )

    return HealthStatus(
        ok=True,
        scheme_count=scheme_n,
        general_count=general_n,
        schemes_present=present,
        sample_query_ok=True,
        reason=None,
    )


def _sample_query_ok(store: VectorStore) -> bool:
    """Cheap metadata peek — avoids loading the embedding model for health."""
    try:
        result = store.scheme.get(
            where={"scheme_id": "icici_flexicap_dg"},
            include=["metadatas"],
            limit=1,
        )
        ids = result.get("ids") or []
        if not ids:
            return False
        metas = result.get("metadatas") or []
        if metas and metas[0].get("corpus") != "scheme":
            return False
        gen = store.general.get(include=["metadatas"], limit=1)
        return bool(gen.get("ids"))
    except Exception:  # noqa: BLE001 — health must never crash callers
        return False
