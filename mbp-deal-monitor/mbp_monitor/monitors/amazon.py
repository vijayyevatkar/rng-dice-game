from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import httpx

from ..catalog import TRACKED_SPECS, TrackedSpec
from ..models import Condition, DealListing

logger = logging.getLogger(__name__)

_DOLLAR_RE = re.compile(r"\$([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})")
_RESALE_PCT_RE = re.compile(r"Save\s+(\d+)%\s+(?:at\s+checkout|on\s+Amazon\s+Resale)", re.IGNORECASE)


def _parse_dollar(text: str) -> Optional[float]:
    if not text:
        return None
    m = _DOLLAR_RE.search(text.replace(" ", ""))
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
        return val if 750.0 <= val <= 4500.0 else None
    except ValueError:
        return None


def parse_amazon_dp_html(html: str, spec: TrackedSpec) -> list[DealListing]:
    """Parse both New BuyBox and Amazon Resale / Used BuyBox from an Amazon /dp/ page."""
    if "captcha" in html.lower() and "productTitle" not in html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("#productTitle")
    title = title_el.get_text(" ", strip=True) if title_el else (
        f"Apple MacBook Pro 14\" {spec.chip} {spec.ram_gb}GB {spec.storage_gb // 1024}TB {spec.color}"
    )
    dp_url = f"https://www.amazon.com/dp/{spec.amazon_asin}"
    listings: list[DealListing] = []

    # 1. Check primary buybox to see if Used / Amazon Resale took over the main box
    buybox_text = ""
    buybox_el = soup.select_one("#desktop_buybox, #buybox")
    if buybox_el:
        buybox_text = buybox_el.get_text(" ", strip=True)

    is_used_primary = "buy used" in buybox_text.lower() or "used: " in buybox_text.lower()

    # Check New price selectors
    if not is_used_primary:
        new_price: Optional[float] = None
        for sel in (
            "#corePrice_feature_div .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#newAccordionRow .a-price .a-offscreen",
        ):
            for el in soup.select(sel):
                p = _parse_dollar(el.get_text(strip=True))
                if p is not None:
                    new_price = p
                    break
            if new_price is not None:
                break

        if new_price is not None:
            listings.append(
                DealListing(
                    source="amazon",
                    retailer="Amazon",
                    title=title,
                    url=dp_url,
                    price=new_price,
                    condition=Condition.NEW,
                    chip=spec.chip,
                    ram_gb=spec.ram_gb,
                    storage_gb=spec.storage_gb,
                    color=spec.color,
                    sku=spec.mpn,
                    msrp=spec.msrp,
                    location="Online (Amazon.com)",
                    in_stock=True,
                    raw_id=f"{spec.amazon_asin}:new",
                )
            )
    else:
        used_primary_price = _parse_dollar(buybox_text)
        if used_primary_price is not None:
            promo_m = _RESALE_PCT_RE.search(html)
            notes = f"Checkout promo: Save {promo_m.group(1)}%" if promo_m else "Amazon Resale (Primary BuyBox)"
            final_price = used_primary_price
            if promo_m:
                pct = int(promo_m.group(1))
                final_price = round(used_primary_price * (1.0 - pct / 100.0), 2)
                notes += f" (${used_primary_price:,.2f} -> ${final_price:,.2f})"
            listings.append(
                DealListing(
                    source="amazon_resale",
                    retailer="Amazon Resale",
                    title=f"[Amazon Resale] {title}",
                    url=dp_url,
                    price=final_price,
                    condition=Condition.OPEN_BOX,
                    chip=spec.chip,
                    ram_gb=spec.ram_gb,
                    storage_gb=spec.storage_gb,
                    color=spec.color,
                    sku=spec.mpn,
                    msrp=spec.msrp,
                    location="Online (Amazon Resale)",
                    in_stock=True,
                    notes=notes,
                    raw_id=f"{spec.amazon_asin}:resale_primary",
                )
            )

    # 2. Check #usedAccordionRow (secondary Amazon Resale / Used offer)
    used_row = soup.select_one("#usedAccordionRow")
    if used_row:
        used_txt = used_row.get_text(" ", strip=True)
        used_price = _parse_dollar(used_txt)
        if used_price is not None:
            is_resale = "amazon resale" in used_txt.lower() or "amazon warehouse" in used_txt.lower()
            cond = Condition.OPEN_BOX if is_resale else Condition.USED
            if "like new" in used_txt.lower():
                cond = Condition.OPEN_BOX_EXCELLENT
            elif "very good" in used_txt.lower() or "good" in used_txt.lower():
                cond = Condition.OPEN_BOX_GOOD

            promo_m = _RESALE_PCT_RE.search(used_txt) or _RESALE_PCT_RE.search(html)
            final_used = used_price
            notes = "Sold by Amazon Resale" if is_resale else "Amazon Used offer"
            if is_resale and promo_m:
                pct = int(promo_m.group(1))
                final_used = round(used_price * (1.0 - pct / 100.0), 2)
                notes = f"Amazon Resale {pct}% checkout promo (${used_price:,.2f} -> ${final_used:,.2f})"

            listings.append(
                DealListing(
                    source="amazon_resale" if is_resale else "amazon_used",
                    retailer="Amazon Resale" if is_resale else "Amazon Used",
                    title=f"[{'Amazon Resale' if is_resale else 'Amazon Used'}] {title}",
                    url=dp_url,
                    price=final_used,
                    condition=cond,
                    chip=spec.chip,
                    ram_gb=spec.ram_gb,
                    storage_gb=spec.storage_gb,
                    color=spec.color,
                    sku=spec.mpn,
                    msrp=spec.msrp,
                    location="Online (Amazon.com)",
                    in_stock=True,
                    notes=notes,
                    raw_id=f"{spec.amazon_asin}:used_accordion",
                )
            )

    return listings


async def _fetch_asin(session: AsyncSession, spec: TrackedSpec) -> list[DealListing]:
    if not spec.amazon_asin:
        return []
    url = f"https://www.amazon.com/dp/{spec.amazon_asin}"
    try:
        resp = await session.get(url, timeout=15)
        if resp.status_code != 200:
            logger.debug("Amazon %s returned HTTP %s", spec.amazon_asin, resp.status_code)
            return []
        return parse_amazon_dp_html(resp.text, spec)
    except Exception as exc:
        logger.debug("Amazon %s fetch error: %s", spec.amazon_asin, exc)
        return []


async def fetch_amazon_direct() -> list[DealListing]:
    specs = [s for s in TRACKED_SPECS if s.amazon_asin]
    async with AsyncSession(impersonate="chrome131") as session:
        # Limit concurrency slightly to avoid triggering Amazon rate limits
        sem = asyncio.Semaphore(4)

        async def _guarded(s: TrackedSpec) -> list[DealListing]:
            async with sem:
                await asyncio.sleep(0.25)
                return await _fetch_asin(session, s)

        results = await asyncio.gather(*(_guarded(s) for s in specs))
    merged: list[DealListing] = []
    for r in results:
        merged.extend(r)
    return merged


async def fetch_keepa_offers(keepa_api_key: str) -> list[DealListing]:
    """Optional Keepa API check for ultra-fast Amazon New + Amazon Warehouse/Resale tracking."""
    if not keepa_api_key:
        return []
    asins = [s.amazon_asin for s in TRACKED_SPECS if s.amazon_asin]
    if not asins:
        return []

    spec_map = {s.amazon_asin: s for s in TRACKED_SPECS if s.amazon_asin}
    listings: list[DealListing] = []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.keepa.com/product",
                params={"key": keepa_api_key, "domain": 1, "asin": ",".join(asins), "stats": 1},
                timeout=20.0,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("Keepa API failed: %s", exc)
        return []

    for prod in data.get("products", []):
        asin = prod.get("asin")
        spec = spec_map.get(asin)
        if not spec:
            continue
        current = (prod.get("stats") or {}).get("current") or []
        # Keepa current[] indices: 0=Amazon New, 1=New 3P, 9=Amazon Warehouse/Resale (in cents)
        checks = [
            (0, "amazon_keepa", "Amazon (Keepa)", Condition.NEW),
            (9, "amazon_resale_keepa", "Amazon Resale (Keepa)", Condition.OPEN_BOX),
        ]
        for idx, src, retailer, cond in checks:
            if idx < len(current) and isinstance(current[idx], int) and current[idx] > 0:
                price = round(current[idx] / 100.0, 2)
                if 750.0 <= price <= 4500.0:
                    listings.append(
                        DealListing(
                            source=src,
                            retailer=retailer,
                            title=prod.get("title") or f"MacBook Pro 14 {spec.chip} {spec.ram_gb}GB",
                            url=f"https://www.amazon.com/dp/{asin}",
                            price=price,
                            condition=cond,
                            chip=spec.chip,
                            ram_gb=spec.ram_gb,
                            storage_gb=spec.storage_gb,
                            color=spec.color,
                            sku=spec.mpn,
                            msrp=spec.msrp,
                            location="Online (Amazon.com)",
                            in_stock=True,
                            raw_id=f"{asin}:keepa:{idx}",
                        )
                    )
    return listings
