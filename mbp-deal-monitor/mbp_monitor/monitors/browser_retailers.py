from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from bs4 import BeautifulSoup

from ..catalog import TRACKED_SPECS, TrackedSpec, WAREHOUSERUNNER_URLS
from ..config import Settings
from ..evaluator import extract_price_from_text, is_target_macbook_pro, parse_specs_from_text
from ..models import Condition, DealListing

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")


def _extract_dollars(text: str) -> list[float]:
    vals: list[float] = []
    for m in _PRICE_RE.finditer(text or ""):
        try:
            v = float(m.group(1).replace(",", ""))
            if 750.0 <= v <= 4500.0:
                vals.append(v)
        except ValueError:
            continue
    return vals


def parse_appleinsider_table(html: str, page_url: str, default_chip: str) -> list[DealListing]:
    """Parse AppleInsider's live multi-retailer comparison table (B&H, Adorama, Amazon, Expercom, etc.)."""
    soup = BeautifulSoup(html, "html.parser")
    listings: list[DealListing] = []
    retailer_cols = ["Apple", "Adorama", "Amazon", "B&H Photo", "Expercom", "Best Buy"]

    for tr in soup.select("table tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.select("th, td")]
        if len(cells) < 4:
            continue
        config_text = cells[0]
        if "M5" not in config_text and "M6" not in config_text:
            continue
        # Only track 14-inch & <=2TB reasonable specs unless huge discount
        chip, ram_gb, storage_gb, _ = parse_specs_from_text(config_text)
        if not chip:
            chip = default_chip
        if ram_gb is not None and ram_gb > 36:
            continue
        if storage_gb is not None and storage_gb > 2048:
            continue

        best_prices = _extract_dollars(cells[1])
        if not best_prices:
            continue
        best_price = best_prices[0]

        # Try to identify which retailer holds the best price from cell links/text
        best_retailer = "Authorized Reseller (AppleInsider)"
        best_link = page_url
        cell_links = tr.select("a[href]")
        for idx, td in enumerate(tr.select("td")[2:], start=0):
            td_prices = _extract_dollars(td.get_text(" ", strip=True))
            if td_prices and abs(td_prices[0] - best_price) < 1.0:
                if idx < len(retailer_cols):
                    best_retailer = retailer_cols[idx]
                a = td.select_one("a[href]")
                if a:
                    href = a.get("href", "")
                    best_link = f"https://prices.appleinsider.com{href}" if href.startswith("/") else href
                break
        if best_link == page_url and cell_links:
            href = cell_links[0].get("href", "")
            best_link = f"https://prices.appleinsider.com{href}" if href.startswith("/") else href

        listings.append(
            DealListing(
                source="appleinsider_guide",
                retailer=best_retailer,
                title=f"MacBook Pro 14\" {config_text}",
                url=best_link,
                price=best_price,
                condition=Condition.NEW,
                chip=chip,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                location=f"Online ({best_retailer})",
                in_stock=True,
                raw_id=f"ai:{config_text}",
            )
        )
    return listings


def parse_microcenter_pdp(html: str, spec: TrackedSpec, url: str) -> list[DealListing]:
    """Parse Micro Center Austin (storeid=215) PDP for New & Open-Box prices/stock."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "NOT CARRIED at Austin Store" in text:
        return []

    listings: list[DealListing] = []
    out_of_stock = "0 NEW IN STOCK" in text and "In-Store Pickup Only" not in text
    in_stock = ("IN STOCK" in text or "Available for In-Store Pickup" in text) and not out_of_stock

    price_el = soup.select_one("#pricing, [data-price], .price")
    price: Optional[float] = None
    if price_el:
        if price_el.has_attr("data-price"):
            try:
                price = float(price_el["data-price"])
            except ValueError:
                price = None
        if price is None:
            pts = _extract_dollars(price_el.get_text(" ", strip=True))
            price = pts[0] if pts else None

    if price is None:
        m = re.search(r'"price"\s*:\s*"?([0-9]+\.[0-9]{2})"?', html)
        if m:
            price = float(m.group(1))

    if price is not None and 750.0 <= price <= 4500.0:
        listings.append(
            DealListing(
                source="microcenter_austin",
                retailer="Micro Center Austin",
                title=f"MacBook Pro 14\" {spec.chip} {spec.ram_gb}GB/{spec.storage_gb // 1024}TB {spec.color} ({spec.mpn})",
                url=url,
                price=price,
                condition=Condition.NEW,
                chip=spec.chip,
                ram_gb=spec.ram_gb,
                storage_gb=spec.storage_gb,
                color=spec.color,
                sku=spec.mpn,
                msrp=spec.msrp,
                location="Austin #215 (12707 N MoPac)",
                in_stock=in_stock,
                raw_id=f"mc215:{spec.mpn}:new",
            )
        )

    # Check if Micro Center Austin lists an Open Box offer on the PDP
    m_ob = re.search(r"Open\s*Box[^$]{0,80}\$([0-9,]+\.[0-9]{2})", text, re.IGNORECASE)
    if m_ob:
        ob_price = float(m_ob.group(1).replace(",", ""))
        if 750.0 <= ob_price <= 4500.0:
            listings.append(
                DealListing(
                    source="microcenter_austin_openbox",
                    retailer="Micro Center Austin Open Box",
                    title=f"[Open Box] MacBook Pro 14\" {spec.chip} {spec.ram_gb}GB/{spec.storage_gb // 1024}TB ({spec.mpn})",
                    url=url,
                    price=ob_price,
                    condition=Condition.OPEN_BOX,
                    chip=spec.chip,
                    ram_gb=spec.ram_gb,
                    storage_gb=spec.storage_gb,
                    color=spec.color,
                    sku=spec.mpn,
                    msrp=spec.msrp,
                    location="Austin #215 (12707 N MoPac)",
                    in_stock=True,
                    raw_id=f"mc215:{spec.mpn}:openbox",
                )
            )
    return listings


def parse_bestbuy_pdp(html: str, spec: TrackedSpec, url: str) -> list[DealListing]:
    """Parse Best Buy PDP rendered HTML (with Austin ZIP 78759) for New & Open-Box offers."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    listings: list[DealListing] = []

    # New price from JSON-LD or price block
    new_price: Optional[float] = None
    for sel in (
        '[data-testid="customer-price"] span',
        '.priceView-customer-price span[aria-hidden="true"]',
        '.priceView-hero-price span[aria-hidden="true"]',
    ):
        el = soup.select_one(sel)
        if el:
            pts = _extract_dollars(el.get_text(strip=True))
            if pts:
                new_price = pts[0]
                break

    if new_price is None:
        m = re.search(r'"priceCurrency"\s*:\s*"USD"\s*,\s*"price"\s*:\s*([0-9]+(?:\.[0-9]{2})?)', html)
        if m:
            new_price = float(m.group(1))

    unavailable = "sold out" in text.lower()[:3000] or "currently unavailable" in text.lower()[:3000]
    if new_price is not None and 750.0 <= new_price <= 4500.0:
        listings.append(
            DealListing(
                source="bestbuy_web",
                retailer="Best Buy",
                title=f"MacBook Pro 14\" {spec.chip} {spec.ram_gb}GB/{spec.storage_gb // 1024}TB {spec.color} ({spec.mpn})",
                url=url,
                price=new_price,
                condition=Condition.NEW,
                chip=spec.chip,
                ram_gb=spec.ram_gb,
                storage_gb=spec.storage_gb,
                color=spec.color,
                sku=spec.mpn,
                msrp=spec.msrp,
                location="Best Buy Austin (ZIP 78759)",
                in_stock=not unavailable,
                raw_id=f"bbyweb:{spec.mpn}:new",
            )
        )

    # Open-Box Excellent / Good / Fair mentions in rendered page
    for grade, cond_enum in (
        ("Excellent", Condition.OPEN_BOX_EXCELLENT),
        ("Good", Condition.OPEN_BOX_GOOD),
        ("Fair", Condition.OPEN_BOX_FAIR),
        ("Open-Box", Condition.OPEN_BOX),
    ):
        pat = re.compile(rf"Open-Box\s*{grade}[^$]{{0,80}}\$([0-9,]+\.[0-9]{{2}})", re.IGNORECASE) if grade != "Open-Box" else re.compile(r"Open-Box\s+from\s+\$([0-9,]+\.[0-9]{2})", re.IGNORECASE)
        m_ob = pat.search(text)
        if m_ob:
            ob_price = float(m_ob.group(1).replace(",", ""))
            if 750.0 <= ob_price <= 4500.0:
                listings.append(
                    DealListing(
                        source="bestbuy_web_openbox",
                        retailer="Best Buy Open Box",
                        title=f"[Open Box - {grade}] MacBook Pro 14\" {spec.chip} {spec.ram_gb}GB/{spec.storage_gb // 1024}TB {spec.color}",
                        url=url,
                        price=ob_price,
                        condition=cond_enum,
                        chip=spec.chip,
                        ram_gb=spec.ram_gb,
                        storage_gb=spec.storage_gb,
                        color=spec.color,
                        sku=spec.mpn,
                        msrp=spec.msrp,
                        location="Best Buy Austin (ZIP 78759)",
                        in_stock=True,
                        raw_id=f"bbyweb:{spec.mpn}:ob:{grade.lower()}",
                    )
                )
    return listings


def parse_warehouserunner(html: str, item_meta: dict[str, str]) -> list[DealListing]:
    """Parse WarehouseRunner Costco warehouse pricing & Austin TX stock status."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    listings: list[DealListing] = []

    austin_keywords = ("Austin", "Cedar Park", "Pflugerville", "Georgetown", "Liberty Hill")
    # Look for local Texas warehouse rows in table
    found_local = False
    for tr in soup.select("table tr"):
        row_txt = tr.get_text(" ", strip=True)
        if any(k.lower() in row_txt.lower() for k in austin_keywords):
            pts = _extract_dollars(row_txt)
            if not pts:
                continue
            in_stock = "out of stock" not in row_txt.lower()
            found_local = True
            listings.append(
                DealListing(
                    source="costco_warehouserunner",
                    retailer="Costco Warehouse",
                    title=item_meta["label"],
                    url=item_meta["url"],
                    price=pts[0],
                    condition=Condition.NEW,
                    sku=item_meta["mpn"],
                    location=row_txt.split("$")[0].strip()[:60],
                    in_stock=in_stock,
                    notes="Verify by calling warehouse desk before driving!",
                    raw_id=f"wr:{item_meta['item']}:{row_txt[:25]}",
                )
            )

    # Also capture the national lowest verified warehouse price snapshot if low enough
    if not found_local:
        m_low = re.search(r"Lowest\s+verified\s+warehouse\s+price[^$]{0,40}\$([0-9,]+\.[0-9]{2})", text, re.IGNORECASE)
        if not m_low:
            pts = _extract_dollars(text[:1200])
            lowest = pts[0] if pts else None
        else:
            lowest = float(m_low.group(1).replace(",", ""))
        if lowest is not None and 750.0 <= lowest <= 2500.0:
            listings.append(
                DealListing(
                    source="costco_warehouserunner",
                    retailer="Costco Warehouse (National Snapshot)",
                    title=item_meta["label"],
                    url=item_meta["url"],
                    price=lowest,
                    condition=Condition.NEW,
                    sku=item_meta["mpn"],
                    location="Check Austin/Cedar Park/Pflugerville Costco app",
                    in_stock=True,
                    notes="Warehouse clearance snapshot — check local TX stock in Costco app",
                    raw_id=f"wr:{item_meta['item']}:national",
                )
            )
    return listings


def parse_deal_grid_links(html: str, source: str, retailer: str, base_url: str) -> list[DealListing]:
    """Generic parser for B&H Deal Zone, Woot Computers, and eBay Certified Refurbished cards."""
    soup = BeautifulSoup(html, "html.parser")
    listings: list[DealListing] = []
    seen_urls: set[str] = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        full_url = f"{base_url.rstrip('/')}{href}" if href.startswith("/") else href
        if full_url in seen_urls:
            continue

        # Grab enclosing card text for title + price
        card = a.parent
        for _ in range(3):
            if card and len(card.get_text(" ", strip=True)) < 260 and card.parent:
                card = card.parent
        card_text = card.get_text(" ", strip=True) if card else a.get_text(" ", strip=True)
        link_text = a.get_text(" ", strip=True)

        candidate_title = link_text if len(link_text) > 20 else card_text[:180]
        if not is_target_macbook_pro(candidate_title, allow_missing_size=False):
            continue

        price = extract_price_from_text(card_text)
        if price is None:
            continue

        seen_urls.add(full_url)
        chip, ram_gb, storage_gb, mpn = parse_specs_from_text(card_text)
        cond = Condition.CERTIFIED_REFURB if ("refurb" in card_text.lower() or source in {"woot", "ebay_refurb"}) else Condition.NEW
        listings.append(
            DealListing(
                source=source,
                retailer=retailer,
                title=candidate_title[:180],
                url=full_url,
                price=price,
                condition=cond,
                chip=chip,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                sku=mpn,
                location=f"Online ({retailer})",
                in_stock=True,
                raw_id=full_url.split("?")[0],
            )
        )
    return listings


async def _fetch_page_html(context: Any, url: str, wait_ms: int = 2500) -> str:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(wait_ms)
        return await page.content()
    except Exception as exc:
        logger.debug("Playwright failed loading %s: %s", url, exc)
        return ""
    finally:
        await page.close()


async def fetch_browser_retailers(settings: Settings) -> list[DealListing]:
    """Run residential-IP Playwright checks across Micro Center Austin, Best Buy, AppleInsider, Costco/WR, B&H, Woot."""
    if not settings.enable_browser_monitors:
        return []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright not installed; skipping browser tier.")
        return []

    all_listings: list[DealListing] = []
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(settings.browser_profile_dir),
            headless=settings.browser_headless,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1366, "height": 900},
            locale="en-US",
            timezone_id="America/Chicago",
        )
        try:
            # Set Austin ZIP 78759 cookie for Best Buy
            await context.add_cookies(
                [
                    {
                        "name": "locDestZip",
                        "value": settings.zip_code,
                        "domain": ".bestbuy.com",
                        "path": "/",
                    },
                    {
                        "name": "locStoreId",
                        "value": "203",
                        "domain": ".bestbuy.com",
                        "path": "/",
                    },
                ]
            )

            # 1. AppleInsider Price Guides (covers B&H, Adorama, Expercom, Amazon, CDW)
            ai_pages = [
                ("https://prices.appleinsider.com/macbook-pro-14-inch-m5", "M5"),
                ("https://prices.appleinsider.com/macbook-pro-14-inch-m6", "M6"),
                ("https://prices.appleinsider.com/macbook-pro-14-inch-m5-pro", "M5 Pro"),
            ]
            for url, chip in ai_pages:
                html = await _fetch_page_html(context, url, wait_ms=2000)
                if html:
                    all_listings.extend(parse_appleinsider_table(html, url, chip))

            # 2. Micro Center Austin (storeid=215)
            for spec in TRACKED_SPECS:
                if spec.microcenter_url:
                    html = await _fetch_page_html(context, spec.microcenter_url, wait_ms=2500)
                    if html:
                        all_listings.extend(parse_microcenter_pdp(html, spec, spec.microcenter_url))

            # 3. Best Buy Austin Local + Open-Box (check all tracked URLs when no API key is set)
            bby_specs = [s for s in TRACKED_SPECS if s.bestbuy_url]
            if settings.bestbuy_api_key:
                bby_specs = bby_specs[:6]
            for spec in bby_specs:
                html = await _fetch_page_html(context, spec.bestbuy_url, wait_ms=3000)
                if html:
                    all_listings.extend(parse_bestbuy_pdp(html, spec, spec.bestbuy_url))

            # 4. WarehouseRunner (Costco warehouse .97 / .00 tracker)
            for item_meta in WAREHOUSERUNNER_URLS:
                html = await _fetch_page_html(context, item_meta["url"], wait_ms=2500)
                if html:
                    all_listings.extend(parse_warehouserunner(html, item_meta))

            # 5. B&H Deal Zone, Woot Computers, eBay Certified Refurbished
            grid_targets = [
                ("bh_dealzone", "B&H Deal Zone", "https://www.bhphotovideo.com/c/buy/Deal-Zone/ci/25620", "https://www.bhphotovideo.com"),
                ("woot", "Woot Computers", "https://computers.woot.com", "https://computers.woot.com"),
                (
                    "ebay_refurb",
                    "eBay Certified Refurbished",
                    "https://www.ebay.com/sch/i.html?_nkw=MacBook+Pro+14+(M5,M6)&_sacat=111422&LH_ItemCondition=2000&_sop=15",
                    "https://www.ebay.com",
                ),
            ]
            for src, retailer, url, base_url in grid_targets:
                html = await _fetch_page_html(context, url, wait_ms=2500)
                if html:
                    all_listings.extend(parse_deal_grid_links(html, src, retailer, base_url))

        finally:
            await context.close()

    return all_listings
