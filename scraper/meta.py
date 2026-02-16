"""
Meta Ad Library Scraper
Fetches active ads by scraping the public Meta Ad Library web UI.
Uses Playwright to load the page, then extracts ad data from embedded
JSON (data-sjs script tags) and GraphQL pagination responses.
No API key required.
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import nest_asyncio
from playwright.async_api import async_playwright, Page, Response

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

# Allow asyncio.run() inside Streamlit's existing event loop
nest_asyncio.apply()

logger = logging.getLogger(__name__)

# ── URL construction ────────────────────────────────────────────────


def _build_search_url(brand_name: str, country_code: str) -> str:
    """Build a Meta Ad Library search URL."""
    return (
        f"https://www.facebook.com/ads/library/"
        f"?active_status=active"
        f"&ad_type=all"
        f"&country={country_code.upper()}"
        f"&q={quote(brand_name)}"
        f"&search_type=keyword_unordered"
        f"&media_type=all"
    )


# ── Normalization ───────────────────────────────────────────────────


def _safe_str(val, default: str = "") -> str:
    """Safely convert a value to string, handling None and dicts."""
    if val is None:
        return default
    if isinstance(val, dict):
        return val.get("text", default)
    return str(val)


def _unix_to_iso(ts) -> str:
    """Convert a Unix timestamp (seconds) to ISO 8601 string."""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return str(ts)


def _detect_media_type(snapshot: dict) -> str:
    """Determine media type from snapshot object."""
    display_format = _safe_str(snapshot.get("display_format")).lower()
    if display_format:
        if "video" in display_format:
            return "video"
        if "carousel" in display_format or "dco" in display_format:
            return "carousel"
        if "image" in display_format:
            return "image"

    if snapshot.get("videos"):
        return "video"
    cards = snapshot.get("cards") or []
    if len(cards) > 1:
        return "carousel"
    if snapshot.get("images"):
        return "image"
    return "unknown"


def _normalize_ad(raw: dict) -> Optional[dict]:
    """
    Map a raw ad object (from embedded JSON or GraphQL) to the
    normalized structure expected by the analysis engine.

    Handles both snake_case (data-sjs) and camelCase (GraphQL) keys.
    """
    # Ad ID: try snake_case first (data-sjs), then camelCase (GraphQL)
    ad_id = str(
        raw.get("ad_archive_id")
        or raw.get("adArchiveID")
        or ""
    )
    if not ad_id:
        return None

    snapshot = raw.get("snapshot") or {}

    # Body text: snapshot.body can be {"text": "..."} or a plain string
    body_text = _safe_str(snapshot.get("body"))
    if not body_text:
        cards = snapshot.get("cards") or []
        if cards and isinstance(cards[0], dict):
            body_text = _safe_str(cards[0].get("body"))

    title = _safe_str(snapshot.get("title"))
    description = _safe_str(snapshot.get("link_description"))
    caption = _safe_str(snapshot.get("caption"))

    # Page info: try both snake_case and camelCase at top level,
    # then fall back to snapshot
    page_name = str(
        raw.get("page_name")
        or raw.get("pageName")
        or snapshot.get("page_name")
        or "Unknown"
    )
    page_id = str(
        raw.get("page_id")
        or raw.get("pageID")
        or snapshot.get("page_id")
        or ""
    )

    # Start date — Unix timestamp
    start_date = _unix_to_iso(
        raw.get("start_date") or raw.get("startDate")
    )

    # Publisher platforms
    platforms = (
        raw.get("publisher_platform")
        or raw.get("publisherPlatform")
        or []
    )
    if isinstance(platforms, str):
        platforms = [p.strip() for p in platforms.split(",")]
    # Normalize to lowercase
    if isinstance(platforms, list):
        platforms = [p.lower() if isinstance(p, str) else p for p in platforms]

    media_type = _detect_media_type(snapshot)
    snapshot_url = f"https://www.facebook.com/ads/library/?id={ad_id}"

    return {
        "id": ad_id,
        "platform": "meta",
        "page_name": page_name,
        "page_id": page_id,
        "body_text": body_text[:2000],
        "title": title,
        "description": description,
        "caption": caption,
        "start_date": start_date,
        "snapshot_url": snapshot_url,
        "publisher_platforms": platforms if isinstance(platforms, list) else [],
        "media_type": media_type,
        "impressions": {},   # Not available from web scraping
        "spend": {},         # Not available from web scraping
        "languages": [],     # Not available from web scraping
    }


# ── Data extraction ─────────────────────────────────────────────────


def _find_collated_results(obj, depth: int = 0) -> list[dict]:
    """Recursively find all 'collated_results' arrays in nested JSON."""
    if depth > 20:
        return []
    results = []
    if isinstance(obj, dict):
        if "collated_results" in obj and isinstance(obj["collated_results"], list):
            results.extend(obj["collated_results"])
        for v in obj.values():
            results.extend(_find_collated_results(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_collated_results(item, depth + 1))
    return results


def _extract_ads_from_html(html: str) -> list[dict]:
    """
    Extract ads from the data-sjs script tags embedded in the
    initial server-rendered HTML. This is where the first batch
    of ad results lives.
    """
    raw_ads = []
    # Facebook embeds JSON data in script tags with the data-sjs attribute
    for script_text in re.findall(
        r'<script[^>]*data-sjs[^>]*>(.*?)</script>', html, re.DOTALL
    ):
        if "collated_results" not in script_text:
            continue
        try:
            data = json.loads(script_text)
        except (json.JSONDecodeError, ValueError):
            continue
        raw_ads.extend(_find_collated_results(data))
    return raw_ads


def _extract_ads_from_graphql(text: str) -> list[dict]:
    """
    Extract ads from a GraphQL response body.
    Facebook sometimes returns multiple JSON objects per line.
    """
    raw_ads = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            raw_ads.extend(_find_collated_results(data))
        except (json.JSONDecodeError, ValueError):
            continue
    return raw_ads


# ── Ad collector ────────────────────────────────────────────────────


class _AdCollector:
    """Collects and deduplicates ads from multiple sources."""

    def __init__(self):
        self._seen_ids: set[str] = set()
        self._ads: list[dict] = []
        self._graphql_ad_count: int = 0

    def add_raw_ads(self, raw_ads: list[dict]) -> int:
        """Normalize and deduplicate a batch of raw ad objects.
        Returns the number of new ads added."""
        added = 0
        for raw in raw_ads:
            normalized = _normalize_ad(raw)
            if normalized is None:
                continue
            ad_id = normalized["id"]
            if ad_id in self._seen_ids:
                continue
            self._seen_ids.add(ad_id)
            self._ads.append(normalized)
            added += 1
        return added

    def get_ads(self, limit: int = 50) -> list[dict]:
        return self._ads[:limit]

    @property
    def count(self) -> int:
        return len(self._ads)

    async def on_response(self, response: Response) -> None:
        """Callback for page.on('response') — intercepts GraphQL ad data."""
        if "/api/graphql/" not in response.url:
            return
        try:
            text = await response.text()
            if "collated_results" not in text and "ad_archive_id" not in text:
                return
            raw_ads = _extract_ads_from_graphql(text)
            new_count = self.add_raw_ads(raw_ads)
            self._graphql_ad_count += new_count
            if new_count > 0:
                logger.info(
                    f"GraphQL pagination: +{new_count} ads "
                    f"(total: {self.count})"
                )
        except Exception:
            pass


# ── Browser automation ──────────────────────────────────────────────


async def _dismiss_popups(page: Page) -> None:
    """Dismiss cookie banners and login modals if they appear."""
    dismiss_selectors = [
        'button[data-testid="cookie-policy-manage-dialog-decline-button"]',
        'button:has-text("Decline optional cookies")',
        'button:has-text("Only allow essential cookies")',
        '[aria-label="Close"]',
        '[aria-label="Dismiss"]',
    ]
    for sel in dismiss_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            continue

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def _fetch_brand_async(
    brand_name: str,
    country_code: str,
    max_ads: int = 50,
) -> list[dict]:
    """Scrape ads for a single brand using Playwright."""
    collector = _AdCollector()
    pw = await async_playwright().start()

    try:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        width = random.randint(1280, 1920)
        height = random.randint(800, 1080)

        context = await browser.new_context(
            viewport={"width": width, "height": height},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()

        if stealth_async:
            await stealth_async(page)

        # Attach GraphQL listener BEFORE navigation (for pagination)
        page.on("response", collector.on_response)

        url = _build_search_url(brand_name, country_code)
        logger.info(f"Scraping: {url}")

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            logger.warning(f"Page load timeout/error for {brand_name}: {e}")

        # Wait for page to settle
        await asyncio.sleep(random.uniform(3.0, 5.0))
        await _dismiss_popups(page)
        await asyncio.sleep(random.uniform(1.0, 2.0))

        # STEP 1: Extract ads from the initial server-rendered HTML
        html = await page.content()
        initial_raw = _extract_ads_from_html(html)
        initial_count = collector.add_raw_ads(initial_raw)
        logger.info(
            f"Initial HTML extraction: {initial_count} ads for '{brand_name}'"
        )

        # STEP 2: Scroll to trigger GraphQL pagination for more ads
        if collector.count < max_ads:
            no_new_rounds = 0
            prev_count = collector.count

            for _ in range(20):
                if collector.count >= max_ads:
                    break

                scroll_px = random.randint(600, 1200)
                await page.evaluate(f"window.scrollBy(0, {scroll_px})")
                await asyncio.sleep(random.uniform(2.0, 4.0))

                if collector.count == prev_count:
                    no_new_rounds += 1
                    if no_new_rounds >= 3:
                        break
                else:
                    no_new_rounds = 0
                prev_count = collector.count

        ads = collector.get_ads(limit=max_ads)
        logger.info(
            f"Scraped {len(ads)} total ads for '{brand_name}' in {country_code}"
        )
        return ads

    except Exception as e:
        logger.error(f"Scraper error for {brand_name}: {e}")
        return []

    finally:
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass


# ── Public API (sync wrappers) ──────────────────────────────────────


def fetch_ads_for_brand(
    brand_name: str,
    country_code: str,
    limit: int = 50,
) -> list[dict]:
    """
    Fetch active ads for a brand in a specific country.
    No API key required — scrapes the public Ad Library web UI.
    """
    return asyncio.run(
        _fetch_brand_async(brand_name, country_code, max_ads=limit)
    )


def fetch_landscape(
    brands: list[str],
    country_code: str,
    ads_per_brand: int = 50,
) -> dict[str, list[dict]]:
    """
    Fetch ads for multiple brands in a single market.
    Returns {brand_name: [normalized_ads]}.
    """
    landscape = {}
    for brand in brands:
        ads = fetch_ads_for_brand(
            brand_name=brand,
            country_code=country_code,
            limit=ads_per_brand,
        )
        landscape[brand] = ads
    return landscape
