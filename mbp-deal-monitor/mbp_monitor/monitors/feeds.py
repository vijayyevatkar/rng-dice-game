from __future__ import annotations

import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from curl_cffi.requests import AsyncSession

from ..evaluator import extract_price_from_text, is_target_macbook_pro, parse_specs_from_text
from ..models import Condition, DealListing

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeedSource:
    name: str
    retailer: str
    url: str
    kind: str  # "rss" or "atom"
    allow_missing_size: bool = False


FEED_SOURCES: list[FeedSource] = [
    FeedSource(
        name="slickdeals_mbp",
        retailer="Slickdeals",
        url="https://slickdeals.net/newsearch.php?q=macbook+pro&searcharea=deals&searchin=first&rss=1",
        kind="rss",
    ),
    FeedSource(
        name="slickdeals_frontpage",
        retailer="Slickdeals Frontpage",
        url="https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
        kind="rss",
    ),
    FeedSource(
        name="reddit_buildapcsales",
        retailer="r/buildapcsales",
        url="https://www.reddit.com/r/buildapcsales/new/.rss",
        kind="atom",
    ),
    FeedSource(
        name="reddit_macoffer",
        retailer="r/macoffer",
        url="https://www.reddit.com/r/macoffer/new/.rss",
        kind="atom",
        allow_missing_size=True,
    ),
    FeedSource(
        name="reddit_costcodeals",
        retailer="r/CostcoDeals",
        url="https://www.reddit.com/r/CostcoDeals/new/.rss",
        kind="atom",
    ),
    FeedSource(
        name="reddit_appleswap",
        retailer="r/appleswap",
        url="https://www.reddit.com/r/appleswap/new/.rss",
        kind="atom",
        allow_missing_size=True,
    ),
    FeedSource(
        name="reddit_blackfriday",
        retailer="r/blackfriday",
        url="https://www.reddit.com/r/blackfriday/new/.rss",
        kind="atom",
    ),
    FeedSource(
        name="9to5toys",
        retailer="9to5Toys",
        url="https://9to5toys.com/feed/",
        kind="rss",
    ),
    FeedSource(
        name="9to5mac",
        retailer="9to5Mac",
        url="https://9to5mac.com/feed/",
        kind="rss",
    ),
    FeedSource(
        name="appleinsider_news",
        retailer="AppleInsider",
        url="https://appleinsider.com/rss/news/",
        kind="rss",
    ),
    FeedSource(
        name="macrumors",
        retailer="MacRumors",
        url="https://feeds.macrumors.com/MacRumors-All",
        kind="rss",
    ),
]


def _strip_tags(raw: str) -> str:
    txt = html.unescape(raw or "")
    return re.sub(r"<[^>]+>", " ", txt)


def _infer_condition(text: str, source_name: str) -> Condition:
    low = text.lower()
    if "open-box" in low or "open box" in low:
        if "excellent" in low:
            return Condition.OPEN_BOX_EXCELLENT
        if "good" in low:
            return Condition.OPEN_BOX_GOOD
        if "fair" in low:
            return Condition.OPEN_BOX_FAIR
        return Condition.OPEN_BOX
    if "apple refurbished" in low or "certified refurbished" in low:
        return Condition.CERTIFIED_REFURB
    if "refurb" in low or "renewed" in low:
        return Condition.CERTIFIED_REFURB
    if source_name == "reddit_appleswap" or "[h]" in low:
        return Condition.USED
    return Condition.NEW


def parse_feed_xml(xml_text: str, src: FeedSource) -> list[DealListing]:
    listings: list[DealListing] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.debug("XML parse failed for %s: %s", src.name, exc)
        return []

    entries: list[tuple[str, str, str, str]] = []
    if src.kind == "atom":
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            title = entry.findtext("a:title", default="", namespaces=ns).strip()
            link_el = entry.find("a:link", ns)
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            entry_id = entry.findtext("a:id", default=link, namespaces=ns).strip()
            content = entry.findtext("a:content", default="", namespaces=ns)
            entries.append((title, link, entry_id, content))
    else:
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link).strip()
            desc = item.findtext("description") or ""
            entries.append((title, link, guid, desc))

    for title, link, guid, body in entries:
        clean_title = _strip_tags(title)
        clean_body = _strip_tags(body)[:800]
        combined = f"{clean_title} {clean_body}"

        # Require title itself (or title+body for short Reddit posts) to match target MacBook Pro
        if not is_target_macbook_pro(clean_title, allow_missing_size=src.allow_missing_size):
            continue

        # For appleswap, ignore [W] (buying) posts where user is wanting rather than selling
        if src.name == "reddit_appleswap" and "[h]" not in clean_title.lower():
            continue

        price = extract_price_from_text(clean_title) or extract_price_from_text(clean_body)
        if price is None:
            continue

        chip, ram_gb, storage_gb, mpn = parse_specs_from_text(combined)
        cond = _infer_condition(combined, src.name)
        listings.append(
            DealListing(
                source=src.name,
                retailer=src.retailer,
                title=clean_title,
                url=link,
                price=price,
                condition=cond,
                chip=chip,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                sku=mpn,
                location="Community / Feed",
                in_stock=True,
                raw_id=guid or link or clean_title,
            )
        )
    return listings


async def _fetch_one(session: AsyncSession, src: FeedSource) -> list[DealListing]:
    headers = {
        "User-Agent": "macos:mbp-deal-monitor:v1.0 (personal deal tracker)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9",
    }
    try:
        resp = await session.get(src.url, headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.debug("Feed %s returned HTTP %s", src.name, resp.status_code)
            return []
        return parse_feed_xml(resp.text, src)
    except Exception as exc:
        logger.debug("Feed %s failed: %s", src.name, exc)
        return []


async def fetch_all_feeds() -> list[DealListing]:
    async with AsyncSession(impersonate="chrome131") as session:
        results = await asyncio.gather(*(_fetch_one(session, s) for s in FEED_SOURCES))
    merged: list[DealListing] = []
    for r in results:
        merged.extend(r)
    return merged
