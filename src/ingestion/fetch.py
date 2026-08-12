"""HTTP fetch with retries + Playwright fallback (Architecture §4.2 / §4.6)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from src.config.settings import Settings, get_settings
from src.config.sources import SourceConfig
from src.ingestion.models import ScrapedPage

IST = ZoneInfo("Asia/Kolkata")

_CLOUDFLARE_MARKERS = (
    "just a moment...",
    "cf-browser-verification",
    "challenge-platform",
    "attention required",
)


def _now_ist() -> datetime:
    return datetime.now(tz=IST)


def fetch_url(
    source: SourceConfig,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    save_raw: bool = True,
    allow_playwright: bool | None = None,
) -> ScrapedPage:
    """Fetch HTML for a SOURCE_LIST URL.

    On soft 403 / Cloudflare / thin HTML, try Playwright once.
    On hard failure return status=error so callers keep last-good (EC-ING-01).
    """
    settings = settings or get_settings()
    if allow_playwright is None:
        allow_playwright = settings.allow_playwright
    scraped_at = _now_ist()
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )

    assert client is not None
    last_error: str | None = None
    last_html = ""
    try:
        for attempt in range(settings.http_max_retries + 1):
            try:
                response = client.get(source.url)
                html = response.text or ""
                last_html = html
                if response.status_code >= 400:
                    last_error = f"HTTP {response.status_code}"
                    if _should_try_playwright(response.status_code, html) and allow_playwright:
                        break
                    if attempt < settings.http_max_retries:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    break

                if not html.strip():
                    last_error = "empty_html"
                    break

                if _looks_blocked(html):
                    last_error = "soft_block_or_challenge"
                    break

                if save_raw:
                    _save_raw_html(settings.raw_html_dir, source.url, html)
                return ScrapedPage(
                    url=source.url,
                    title=source.title,
                    corpus=source.corpus,
                    scheme_id=source.scheme_id,
                    html=html,
                    scraped_at=scraped_at,
                    status="ok",
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < settings.http_max_retries:
                    time.sleep(0.5 * (2**attempt))

        # Playwright fallback once (Architecture §4.6)
        if allow_playwright and (
            last_error
            or _looks_blocked(last_html)
            or _should_try_playwright(0, last_html)
        ):
            try:
                html = _fetch_with_playwright(source.url, settings)
                if html and html.strip() and not _looks_blocked(html):
                    if save_raw:
                        _save_raw_html(settings.raw_html_dir, source.url, html)
                    return ScrapedPage(
                        url=source.url,
                        title=source.title,
                        corpus=source.corpus,
                        scheme_id=source.scheme_id,
                        html=html,
                        scraped_at=scraped_at,
                        status="ok",
                    )
                last_error = last_error or "playwright_empty_or_blocked"
            except Exception as exc:  # noqa: BLE001
                last_error = f"PlaywrightFallback: {type(exc).__name__}: {exc}"

        if last_error == "empty_html" or (last_html == "" and last_error is None):
            return ScrapedPage(
                url=source.url,
                title=source.title,
                corpus=source.corpus,
                scheme_id=source.scheme_id,
                html="",
                scraped_at=scraped_at,
                status="empty",
                error="empty_html",
            )

        return ScrapedPage(
            url=source.url,
            title=source.title,
            corpus=source.corpus,
            scheme_id=source.scheme_id,
            html="",
            scraped_at=scraped_at,
            status="error",
            error=last_error or "fetch_failed",
        )
    finally:
        if owns_client:
            client.close()


def _should_try_playwright(status_code: int, html: str) -> bool:
    if status_code in {403, 429, 503}:
        return True
    return _looks_blocked(html)


def _looks_blocked(html: str) -> bool:
    if not html:
        return False
    low = html.lower()
    return any(m in low for m in _CLOUDFLARE_MARKERS)


def _fetch_with_playwright(url: str, settings: Settings) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed; pip install -e '.[playwright]' "
            "and run playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=settings.user_agent)
            page.goto(url, wait_until="domcontentloaded", timeout=int(settings.http_timeout_seconds * 1000))
            # Allow client-rendered content to settle
            page.wait_for_timeout(settings.playwright_wait_ms)
            return page.content()
        finally:
            browser.close()


def _save_raw_html(raw_dir: Path, url: str, html: str) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe = (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "_")
    )
    path = raw_dir / f"{safe[:180]}.html"
    path.write_text(html, encoding="utf-8", errors="replace")


def utc_iso(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
