"""Fuzzy scheme matching against canonical names + aliases (FR-2)."""

from __future__ import annotations

from rapidfuzz import fuzz

from src.config.schemes import SCHEMES, SchemeConfig
from src.config.settings import Settings, get_settings
from src.pipeline.models import SchemeMatchResult

# Tokens too generic to match a scheme alone (EC-SCH-06).
_GENERIC_TOKENS = frozenset(
    {
        "icici",
        "prudential",
        "icici prudential",
        "mutual fund",
        "fund",
        "direct",
        "growth",
        "plan",
    }
)

# Unsupported AMC / competitor cues (handled at intent layer too).
_UNSUPPORTED_AMC_TOKENS = (
    "hdfc",
    "sbi",
    "axis",
    "kotak",
    "nippon",
    "uti ",
    "uti-",
    "franklin",
    "dsp",
    "mirae",
    "parag parikh",
    "ppfas",
    "tata mutual",
    "aditya birla",
    "birla sun",
)


def _build_candidates() -> list[tuple[str, str, str]]:
    """Return (scheme_id, label, match_text) for all names and aliases."""
    out: list[tuple[str, str, str]] = []
    for scheme in SCHEMES:
        out.append((scheme.scheme_id, scheme.canonical_name, scheme.canonical_name.lower()))
        for alias in scheme.aliases:
            out.append((scheme.scheme_id, scheme.canonical_name, alias.lower()))
    return out


_CANDIDATES = _build_candidates()


def mentions_unsupported_amc(query: str) -> bool:
    q = query.lower()
    return any(tok in q for tok in _UNSUPPORTED_AMC_TOKENS)


def resolve_scheme(
    query: str,
    *,
    settings: Settings | None = None,
) -> SchemeMatchResult:
    """Conservative fuzzy match; ambiguity or low score → no match (FR-9 path)."""
    settings = settings or get_settings()
    threshold = settings.scheme_match_threshold
    min_gap = settings.scheme_match_gap

    q = query.strip().lower()
    if not q:
        return SchemeMatchResult(
            scheme_id=None,
            scheme_name=None,
            confidence=0.0,
            matched=False,
        )

    if mentions_unsupported_amc(q):
        return SchemeMatchResult(
            scheme_id=None,
            scheme_name=None,
            confidence=0.0,
            matched=False,
        )

    # EC-SCH-06: bare AMC name without scheme cue → no default scheme.
    if _is_generic_only(q):
        return SchemeMatchResult(
            scheme_id=None,
            scheme_name=None,
            confidence=0.0,
            matched=False,
        )

    scores: dict[str, float] = {}
    name_by_id: dict[str, str] = {}
    for scheme_id, canonical, match_text in _CANDIDATES:
        score = max(
            fuzz.partial_ratio(q, match_text),
            fuzz.token_set_ratio(q, match_text),
        )
        if score > scores.get(scheme_id, 0):
            scores[scheme_id] = float(score)
            name_by_id[scheme_id] = canonical

    if not scores:
        return SchemeMatchResult(
            scheme_id=None,
            scheme_name=None,
            confidence=0.0,
            matched=False,
        )

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_id, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    ambiguous = (best_score - second_score) < min_gap and second_score >= threshold - 10
    if ambiguous:
        return SchemeMatchResult(
            scheme_id=None,
            scheme_name=None,
            confidence=best_score,
            matched=False,
            ambiguous=True,
            candidates=[(sid, sc) for sid, sc in ranked[:3]],
        )

    if best_score < threshold:
        return SchemeMatchResult(
            scheme_id=None,
            scheme_name=None,
            confidence=best_score,
            matched=False,
            candidates=[(sid, sc) for sid, sc in ranked[:3]],
        )

    return SchemeMatchResult(
        scheme_id=best_id,
        scheme_name=name_by_id[best_id],
        confidence=best_score,
        matched=True,
        candidates=[(sid, sc) for sid, sc in ranked[:3]],
    )


def get_scheme_config(scheme_id: str) -> SchemeConfig | None:
    for s in SCHEMES:
        if s.scheme_id == scheme_id:
            return s
    return None


def _is_generic_only(q: str) -> bool:
    normalized = " ".join(q.split())
    if normalized in _GENERIC_TOKENS:
        return True
    # "icici prudential" with no fund-type cue
    if normalized in ("icici", "prudential", "icici prudential"):
        return True
    has_scheme_cue = any(
        cue in q
        for cue in (
            "nasdaq",
            "midcap",
            "mid cap",
            "flexicap",
            "flexi cap",
            "large cap",
            "largecap",
            "elss",
            "tax saver",
        )
    )
    if not has_scheme_cue and normalized in _GENERIC_TOKENS:
        return True
    return False
