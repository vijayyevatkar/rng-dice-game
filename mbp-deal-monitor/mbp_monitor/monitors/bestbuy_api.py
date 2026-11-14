from __future__ import annotations

import logging
import httpx

from ..catalog import TRACKED_SPECS, TrackedSpec
from ..models import Condition, DealListing

logger = logging.getLogger(__name__)


async def fetch_bestbuy_api(api_key: str, zip_code: str = "78759") -> list[DealListing]:
    """Query Best Buy's official Products + Buying Options (Open Box) API."""
    if not api_key:
        return []

    specs = [s for s in TRACKED_SPECS if s.bestbuy_sku]
    if not specs:
        return []

    spec_by_sku: dict[str, TrackedSpec] = {s.bestbuy_sku: s for s in specs if s.bestbuy_sku}
    sku_csv = ",".join(spec_by_sku.keys())
    listings: list[DealListing] = []

    async with httpx.AsyncClient() as client:
        # 1. Official New/Sale Product Pricing
        try:
            r = await client.get(
                f"https://api.bestbuy.com/v1/products(sku in({sku_csv}))",
                params={
                    "apiKey": api_key,
                    "format": "json",
                    "show": "sku,name,salePrice,regularPrice,onSale,onlineAvailability,inStoreAvailability,url,modelNumber",
                    "pageSize": 100,
                },
                timeout=15.0,
            )
            r.raise_for_status()
            for p in r.json().get("products", []):
                sku = str(p.get("sku", ""))
                spec = spec_by_sku.get(sku)
                if not spec:
                    continue
                price = p.get("salePrice") or p.get("regularPrice")
                if not price:
                    continue
                in_stock = bool(p.get("onlineAvailability") or p.get("inStoreAvailability"))
                listings.append(
                    DealListing(
                        source="bestbuy_api",
                        retailer="Best Buy",
                        title=p.get("name") or f"MacBook Pro 14 {spec.chip} {spec.ram_gb}GB",
                        url=p.get("url") or spec.bestbuy_url or f"https://www.bestbuy.com/site/{sku}.p?skuId={sku}",
                        price=float(price),
                        condition=Condition.NEW,
                        chip=spec.chip,
                        ram_gb=spec.ram_gb,
                        storage_gb=spec.storage_gb,
                        color=spec.color,
                        sku=spec.mpn,
                        msrp=spec.msrp,
                        location="Best Buy Online / Austin",
                        in_stock=in_stock,
                        raw_id=f"{sku}:new",
                    )
                )
        except Exception as exc:
            logger.warning("Best Buy Products API failed: %s", exc)

        # 2. Official Open-Box Offers API
        try:
            r_ob = await client.get(
                f"https://api.bestbuy.com/beta/products/openBox(sku in({sku_csv}))",
                params={"apiKey": api_key, "pageSize": 100},
                timeout=15.0,
            )
            r_ob.raise_for_status()
            for item in r_ob.json().get("results", []):
                sku = str(item.get("sku", ""))
                spec = spec_by_sku.get(sku)
                if not spec:
                    continue
                item_url = (item.get("links") or {}).get("web") or spec.bestbuy_url or f"https://www.bestbuy.com/site/{sku}.p?skuId={sku}"
                title = (item.get("names") or {}).get("title") or f"MacBook Pro 14 {spec.chip} {spec.ram_gb}GB"
                for offer in item.get("offers", []):
                    cond_str = (offer.get("condition") or "").lower()
                    cur_price = (offer.get("prices") or {}).get("current")
                    if not cur_price:
                        continue
                    cond = Condition.OPEN_BOX
                    if "excellent" in cond_str:
                        cond = Condition.OPEN_BOX_EXCELLENT
                    elif "good" in cond_str:
                        cond = Condition.OPEN_BOX_GOOD
                    elif "fair" in cond_str:
                        cond = Condition.OPEN_BOX_FAIR
                    listings.append(
                        DealListing(
                            source="bestbuy_openbox_api",
                            retailer="Best Buy Open Box",
                            title=f"[Open Box - {cond_str.title()}] {title}",
                            url=item_url,
                            price=float(cur_price),
                            condition=cond,
                            chip=spec.chip,
                            ram_gb=spec.ram_gb,
                            storage_gb=spec.storage_gb,
                            color=spec.color,
                            sku=spec.mpn,
                            msrp=spec.msrp,
                            location="Best Buy (Ship / Austin)",
                            in_stock=True,
                            raw_id=f"{sku}:ob:{cond_str}",
                        )
                    )
        except Exception as exc:
            logger.warning("Best Buy Open Box API failed: %s", exc)

    return listings
