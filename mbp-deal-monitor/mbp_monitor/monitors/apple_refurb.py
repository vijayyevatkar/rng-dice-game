from __future__ import annotations

import json
import logging
import re
from typing import Optional

from curl_cffi.requests import AsyncSession

from ..models import Condition, DealListing

logger = logging.getLogger(__name__)

APPLE_REFURB_URL = "https://www.apple.com/shop/refurbished/mac/14-inch-macbook-pro"


def _parse_capacity_gb(val: str) -> Optional[int]:
    if not val:
        return None
    v = val.lower().strip()
    m_tb = re.match(r"(\d+)\s*tb", v)
    if m_tb:
        return int(m_tb.group(1)) * 1024
    m_gb = re.match(r"(\d+)\s*gb", v)
    if m_gb:
        return int(m_gb.group(1))
    return None


def parse_apple_refurb_html(html: str) -> list[DealListing]:
    m = re.search(r"window\.REFURB_GRID_BOOTSTRAP\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not m:
        return []

    data = json.loads(m.group(1))
    listings: list[DealListing] = []
    for tile in data.get("tiles", []):
        title = (tile.get("title") or "").strip()
        if "14-inch MacBook Pro" not in title:
            continue
        if "M5" not in title and "M6" not in title:
            continue

        dims = (tile.get("filters") or {}).get("dimensions") or {}
        if dims.get("dimensionScreensize") and dims.get("dimensionScreensize") != "14inch":
            continue

        price_obj = tile.get("price") or {}
        cur = price_obj.get("currentPrice") or {}
        raw_amount = cur.get("raw_amount")
        if not raw_amount:
            continue
        try:
            price = float(str(raw_amount).replace(",", ""))
        except ValueError:
            continue

        prev_obj = price_obj.get("previousPrice") or {}
        msrp: Optional[float] = None
        if prev_obj.get("raw_amount"):
            try:
                msrp = float(str(prev_obj["raw_amount"]).replace(",", ""))
            except ValueError:
                msrp = None

        chip = "M6" if "M6" in title else ("M5 Max" if "M5 Max" in title else ("M5 Pro" if "M5 Pro" in title else "M5"))
        ram_gb = _parse_capacity_gb(dims.get("tsMemorySize", ""))
        storage_gb = _parse_capacity_gb(dims.get("dimensionCapacity", ""))
        color = dims.get("dimensionColor", "").title()
        mpn = (tile.get("partNumber") or "").upper()
        rel_url = tile.get("productDetailsUrl") or ""
        full_url = f"https://www.apple.com{rel_url}" if rel_url.startswith("/") else (rel_url or APPLE_REFURB_URL)

        notes = "Nano-texture display" if "nano-texture" in title.lower() else ""
        listings.append(
            DealListing(
                source="apple_refurb",
                retailer="Apple Certified Refurbished",
                title=title,
                url=full_url.split("?")[0],
                price=price,
                condition=Condition.APPLE_REFURB,
                chip=chip,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                color=color,
                sku=mpn,
                msrp=msrp,
                location="Online (Apple.com)",
                in_stock=True,
                notes=notes,
                raw_id=mpn or title,
            )
        )
    return listings


async def fetch_apple_refurb() -> list[DealListing]:
    try:
        async with AsyncSession(impersonate="chrome131") as session:
            resp = await session.get(APPLE_REFURB_URL, timeout=15)
            resp.raise_for_status()
            return parse_apple_refurb_html(resp.text)
    except Exception as exc:
        logger.warning("Apple Refurb monitor failed: %s", exc)
        return []
