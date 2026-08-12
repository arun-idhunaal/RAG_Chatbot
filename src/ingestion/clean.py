"""HTML cleaning and fact tagging (Architecture §4.3; EC-ING-05, EC-ING-06)."""

from __future__ import annotations

import hashlib
import re
from bs4 import BeautifulSoup, NavigableString, Tag

from src.config.fact_types import (
    FACT_TYPE_PATTERNS,
    OUT_OF_SCOPE_FACT_TYPE,
    PERFORMANCE_KEYWORDS,
)
from src.config.schemes import SCHEMES, get_scheme_by_id
from src.ingestion.models import CleanedDocument, ScrapedPage

# Chrome / contamination selectors (EC-ING-06 related-fund carousels).
_REMOVE_TAGS = ("script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header")
_REMOVE_SELECTORS = (
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".cookie",
    "#cookie",
    ".advertisement",
    ".ads",
    ".related-funds",
    ".relatedFunds",
    ".similar-funds",
    ".similarFunds",
    ".recommended-funds",
    ".other-funds",
    "[data-testid*='related']",
    "[class*='RelatedFund']",
    "[class*='related-fund']",
    "[class*='SimilarFund']",
    "[class*='Carousel']",
    "[class*='carousel']",
)

_RELATED_HEADING_RE = re.compile(
    r"^\s*(related\s+funds?|similar\s+funds?|people\s+also\s+(view|invest)|"
    r"recommended\s+funds?|other\s+funds?|explore\s+more|you\s+may\s+also\s+like|"
    r".*ranking\s+and\s+peer\s+comparison.*|.*peer\s+comparison.*|"
    r".*returns?\s+calculator.*|.*historical\s+returns?.*|"
    r".*\bfund\s+performance\b.*|.*nav\s+chart.*)\s*$",
    re.I,
)

# Section headings to drop entirely after extraction (EC-ING-05 / EC-ING-06).
_DROP_SECTION_HEADING_RE = re.compile(
    r"(peer\s+comparison|ranking\s+and\s+peer|returns?\s+calculator|"
    r"historical\s+returns?|fund\s+performance|nav\s+chart|"
    r"related\s+funds?|similar\s+funds?|holdings?\s+comparison|"
    r"top\s+holdings|holdings?\s+details|sector\s+allocation|asset\s+allocation|"
    r"sector\s+changes|portfolio|aum\s+change|"
    r"how\s+do\s+i\s+invest)",
    re.I,
)

_WHITESPACE_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def clean_page(page: ScrapedPage) -> CleanedDocument | None:
    """Extract main content; strip nav/ads/related-fund chrome; quarantine performance."""
    if page.status != "ok" or not page.html.strip():
        return None

    soup = BeautifulSoup(page.html, "lxml")
    for tag_name in _REMOVE_TAGS:
        for node in soup.find_all(tag_name):
            node.decompose()
    for selector in _REMOVE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    _strip_related_fund_sections(soup)
    if page.corpus == "scheme" and page.scheme_id:
        _strip_cross_scheme_links(soup, page.scheme_id)

    root = _main_content_root(soup)
    sections = _extract_sections(root)
    if not sections:
        plain = _normalize_text(root.get_text("\n", strip=True))
        if plain:
            sections = [(None, plain)]

    kept: list[tuple[str | None, str]] = []
    out_of_scope: list[str] = []
    for heading, body in sections:
        combined = f"{heading or ''}\n{body}".strip()
        if heading and _DROP_SECTION_HEADING_RE.search(heading):
            out_of_scope.append(combined[:500])
            continue
        if _is_performance_only(combined):
            out_of_scope.append(combined[:500])
            continue
        if page.corpus == "scheme" and page.scheme_id:
            body = _filter_peer_rows(body, page.scheme_id)
            if not body.strip():
                continue
        # Drop tiny chrome leftovers
        if len(body.split()) < 8 and not _looks_like_fact_row(body):
            continue
        kept.append((heading, body))

    if not kept:
        return None

    full_text = "\n\n".join(
        (f"## {h}\n{b}" if h else b) for h, b in kept
    ).strip()
    content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

    return CleanedDocument(
        url=page.url,
        title=page.title or _guess_title(soup) or page.url,
        corpus=page.corpus,
        scheme_id=page.scheme_id,
        text=full_text,
        sections=kept,
        content_hash=content_hash,
        scraped_at=page.scraped_at,
        out_of_scope_sections=out_of_scope,
    )


def tag_fact_types(text: str) -> list[str]:
    """Return in-scope fact_type tags present in text; mark performance as out_of_scope."""
    lower = text.lower()
    tags: list[str] = []
    if any(k in lower for k in PERFORMANCE_KEYWORDS):
        # If the chunk is dominated by performance language, tag out_of_scope.
        if _is_performance_only(text):
            return [OUT_OF_SCOPE_FACT_TYPE]
        tags.append(OUT_OF_SCOPE_FACT_TYPE)

    for fact_type, patterns in FACT_TYPE_PATTERNS.items():
        if any(p in lower for p in patterns):
            tags.append(fact_type)
    # Deduplicate preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _strip_related_fund_sections(soup: BeautifulSoup) -> None:
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        title = heading.get_text(" ", strip=True)
        if not _RELATED_HEADING_RE.match(title):
            continue
        # Remove heading and following siblings until next heading of same/higher level.
        level = int(heading.name[1])
        sibling = heading.next_sibling
        heading.decompose()
        while sibling is not None:
            nxt = sibling.next_sibling
            if isinstance(sibling, Tag) and sibling.name and re.match(r"^h[1-6]$", sibling.name):
                if int(sibling.name[1]) <= level:
                    break
            if isinstance(sibling, Tag):
                sibling.decompose()
            elif isinstance(sibling, NavigableString):
                sibling.extract()
            sibling = nxt


def _strip_cross_scheme_links(soup: BeautifulSoup, scheme_id: str) -> None:
    """Remove blocks that primarily advertise other supported schemes (EC-ING-06)."""
    own = get_scheme_by_id(scheme_id)
    if not own:
        return
    own_slug = own.source_url.rstrip("/").split("/")[-1]
    other_slugs = {
        s.source_url.rstrip("/").split("/")[-1]
        for s in SCHEMES
        if s.scheme_id != scheme_id
    }
    other_names = [s.canonical_name.lower() for s in SCHEMES if s.scheme_id != scheme_id]

    for a in list(soup.find_all("a", href=True)):
        href = a["href"]
        if not isinstance(href, str):
            continue
        slug = href.rstrip("/").split("/")[-1]
        if slug in other_slugs and slug != own_slug:
            # Prefer removing a small parent card rather than the whole page.
            parent = a.find_parent(["li", "article", "div", "section"])
            target = parent if parent and _is_small_card(parent) else a
            target.decompose()

    # Also drop short paragraphs that only name another scheme.
    for p in list(soup.find_all(["p", "li", "span"])):
        text = p.get_text(" ", strip=True).lower()
        if not text or len(text) > 160:
            continue
        if any(name in text for name in other_names) and own.canonical_name.lower() not in text:
            if any(k in text for k in ("invest", "explore", "view", "similar", "related")):
                p.decompose()


def _is_small_card(node: Tag) -> bool:
    text = node.get_text(" ", strip=True)
    return 0 < len(text) < 400


def _main_content_root(soup: BeautifulSoup) -> Tag:
    for selector in ("main", "article", "[role='main']", "#content", ".content"):
        found = soup.select_one(selector)
        if found:
            return found
    body = soup.body
    return body if body else soup


def _extract_sections(root: Tag) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_heading
        body = _normalize_text("\n".join(buffer))
        if body:
            sections.append((current_heading, body))
        buffer = []

    # Prefer walking block-level children when possible.
    blocks = list(root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr", "table"], recursive=True))
    if not blocks:
        text = _normalize_text(root.get_text("\n", strip=True))
        return [(None, text)] if text else []

    seen_tables: set[int] = set()
    for el in blocks:
        if el.name and re.match(r"^h[1-6]$", el.name):
            flush()
            current_heading = el.get_text(" ", strip=True) or None
            continue
        if el.name == "table":
            tid = id(el)
            if tid in seen_tables:
                continue
            seen_tables.add(tid)
            table_text = _table_to_text(el)
            if table_text:
                buffer.append(table_text)
            continue
        if el.name == "tr":
            # Handled via table walker
            continue
        # Skip nested list items already covered? Keep simple: take direct text.
        if el.find_parent("table"):
            continue
        text = el.get_text(" ", strip=True)
        if text:
            buffer.append(text)
    flush()
    return sections


def _table_to_text(table: Tag) -> str:
    rows: list[str] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def _is_performance_only(text: str) -> bool:
    """True when text is returns/performance content without answerable in-scope facts.

    Mentions of 'benchmark' alone do not rescue a returns block (EC-ING-05) —
    only strong in-scope fact types (ER, exit load, SIP, lock-in, etc.) do.
    """
    lower = text.lower()
    hits = sum(1 for k in PERFORMANCE_KEYWORDS if k in lower)
    if hits == 0:
        return False
    strong_types = (
        "expense_ratio",
        "exit_load",
        "min_sip",
        "lock_in",
        "riskometer",
        "statement_download",
    )
    in_scope_hit = any(
        any(p in lower for p in FACT_TYPE_PATTERNS[ft]) for ft in strong_types
    )
    return not in_scope_hit


def _looks_like_fact_row(text: str) -> bool:
    lower = text.lower()
    return any(
        any(p in lower for p in patterns) for patterns in FACT_TYPE_PATTERNS.values()
    ) or ("%" in text and any(k in lower for k in ("expense", "exit", "load", "sip")))


def _filter_peer_rows(body: str, scheme_id: str) -> str:
    """Drop other-fund / return-scorecard lines from scheme pages (EC-ING-06 / EC-ING-05)."""
    own = get_scheme_by_id(scheme_id)
    if not own:
        return body

    distinctive = _distinctive_tokens(own.canonical_name)
    other_names = [s.canonical_name.lower() for s in SCHEMES if s.scheme_id != scheme_id]
    other_amc_markers = (
        "hdfc ",
        "sbi ",
        "axis ",
        "kotak ",
        "nippon ",
        "uti ",
        "aditya birla",
        "bank of india",
        "mirae ",
        "parag parikh",
        "quant ",
        "dsp ",
        "tata ",
        "franklin ",
        "motilal ",
        "canara ",
        "hsbc ",
        "edelweiss ",
        "invesco ",
        "pgim ",
        "mahindra ",
    )

    kept_lines: list[str] = []
    for line in body.split("\n"):
        low = line.lower().strip()
        if not low:
            continue

        # Competing AMC rows never belong under our scheme_id.
        if any(m in low for m in other_amc_markers):
            continue

        # Other supported ICICI schemes (without our distinctive token).
        if any(n in low for n in other_names):
            if not any(t in low for t in distinctive):
                continue

        # Peer scorecard header / multi-metric ranking rows.
        if "fund name" in low and "expense ratio" in low:
            continue
        if re.search(r"\b\d+/\d+\b", low) and low.count("%") >= 2:
            continue
        if "|" in line and low.count("%") >= 3 and "expense" not in low:
            # Dense return comparison table rows
            if any(
                x in low
                for x in (
                    "this fund",
                    "nifty",
                    "avg",
                    "best in",
                    "worst in",
                    "category rank",
                    "period",
                )
            ):
                continue
        if "outperformed the benchmark" in low or "underperformed the benchmark" in low:
            continue
        if low.startswith("period |") or low.startswith("category rank"):
            continue
        if "since inception" in low and "%" in low:
            continue
        if re.match(r"^₹?[\d,.]+\s*%?\s*/?per year", low):
            continue

        # Pure performance prose without in-scope facts.
        if _is_performance_only(low):
            continue

        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def _distinctive_tokens(canonical_name: str) -> set[str]:
    low = canonical_name.lower()
    tokens: set[str] = set()
    mapping = {
        "nasdaq": ("nasdaq", "nasdaq 100"),
        "midcap": ("midcap", "mid cap"),
        "flexicap": ("flexicap", "flexi cap"),
        "large cap": ("large cap", "largecap"),
        "elss": ("elss", "tax saver"),
    }
    for key, vals in mapping.items():
        if key in low:
            tokens.update(vals)
    return tokens


def _guess_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)
    return None
