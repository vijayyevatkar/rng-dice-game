from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class TrackedSpec:
    mpn: str                    # Apple US part number, e.g. MDE34LL/A
    chip: str                   # "M5", "M5 Pro", "M6"
    ram_gb: int
    storage_gb: int
    color: str
    msrp: float
    street_baseline: float      # Typical mid-Nov 2026 street price (not a deal!)
    urgent_price: float         # Instant Priority-5 alarm threshold
    deal_price: float           # Priority-4 deal threshold
    nano_texture: bool = False
    amazon_asin: Optional[str] = None
    bestbuy_sku: Optional[str] = None
    bestbuy_url: Optional[str] = None
    costco_item: Optional[str] = None
    costco_url: Optional[str] = None
    microcenter_url: Optional[str] = None
    apple_refurb_mpn: Optional[str] = None


# Verified Nov 2026 catalog of 14-inch MacBook Pro M5 & M6 configurations.
# Note: Apple raised MacBook Pro prices by $300-$500 in June 2026 and
# discontinued base M5 on Nov 6, 2026 when M6 shipped.
TRACKED_SPECS: list[TrackedSpec] = [
    # --- M5 14" (10C CPU / 10C GPU) — 24GB RAM (Preferred) ---
    TrackedSpec(
        mpn="MDE34LL/A",
        chip="M5",
        ram_gb=24,
        storage_gb=1024,
        color="Space Black",
        msrp=2199.0,
        street_baseline=1899.0,
        urgent_price=1649.0,
        deal_price=1779.0,
        amazon_asin="B0FWD726XF",
        bestbuy_sku="6565873",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m5-chip-with-10-core-cpu-and-10-core-gpu-24gb-memory-1tb-ssd-space-black/JJGCQL8L5Y/sku/6565873",
        microcenter_url="https://www.microcenter.com/product/702784/apple-macbook-pro-14-mde34ll-a-(late-2025)-142-laptop-computer-space-black?storeid=215",
        apple_refurb_mpn="FDE34LL/A",
    ),
    TrackedSpec(
        mpn="MDE64LL/A",
        chip="M5",
        ram_gb=24,
        storage_gb=1024,
        color="Silver",
        msrp=2199.0,
        street_baseline=1849.0,
        urgent_price=1649.0,
        deal_price=1740.0,
        amazon_asin="B0FWD7QF6M",
        bestbuy_sku="6565877",
        bestbuy_url="https://www.bestbuy.com/product/14-inch-macbook-pro-apple-m5-chip-with-10-core-cpu-and-10-core-gpu-24gb-memory-1tb-ssd-silver/JJGCQL8S2Q/sku/6565877",
        apple_refurb_mpn="FDE64LL/A",
    ),
    TrackedSpec(
        mpn="Z1KH000BZ",
        chip="M5",
        ram_gb=24,
        storage_gb=512,
        color="Space Black",
        msrp=1799.0,
        street_baseline=1649.0,
        urgent_price=1499.0,
        deal_price=1560.0,
        amazon_asin="B0FZXZ942V",
        microcenter_url="https://www.microcenter.com/product/703290/apple-macbook-pro-14-z1kh000bz-(late-2025)-142-laptop-computer-space-black?storeid=215",
        apple_refurb_mpn="G1KL0LL/A",
    ),
    TrackedSpec(
        mpn="Z1KJ000S2",
        chip="M5",
        ram_gb=24,
        storage_gb=1024,
        color="Space Black",
        nano_texture=True,
        msrp=2349.0,
        street_baseline=1899.0,
        urgent_price=1649.0,
        deal_price=1749.0,
        microcenter_url="https://www.microcenter.com/product/711644/apple-macbook-pro-nano-texture-14-z1kj000s2-(late-2025)-142-laptop-computer-space-black?storeid=215",
        apple_refurb_mpn="G1KK5LL/A",
    ),

    # --- M5 14" (10C CPU / 10C GPU) — 16GB RAM (Acceptable if strong deal) ---
    TrackedSpec(
        mpn="MDE14LL/A",
        chip="M5",
        ram_gb=16,
        storage_gb=1024,
        color="Space Black",
        msrp=1999.0,
        street_baseline=1797.0,
        urgent_price=1449.0,
        deal_price=1599.0,
        amazon_asin="B0FWD623D1",
        bestbuy_sku="11619265",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m5-chip-with-10-core-cpu-and-10-core-gpu-16gb-memory-1tb-ssd-space-black/JJGCQL8L2P/sku/11619265",
        costco_item="1945139",
        costco_url="https://www.costco.com/p/-/macbook-pro-laptop-14-inch-apple-m5-chip-built-for-apple-intelligence-10-core-cpu-10-core-gpu-16gb-memory-1tb-ssd-storage/4000370739",
    ),
    TrackedSpec(
        mpn="MDE54LL/A",
        chip="M5",
        ram_gb=16,
        storage_gb=1024,
        color="Silver",
        msrp=1999.0,
        street_baseline=1799.0,
        urgent_price=1449.0,
        deal_price=1599.0,
        amazon_asin="B0FWD8WBSW",
        bestbuy_sku="6565875",
        costco_item="1945139",
    ),
    TrackedSpec(
        mpn="MDE04LL/A",
        chip="M5",
        ram_gb=16,
        storage_gb=512,
        color="Space Black",
        msrp=1599.0,
        street_baseline=1499.0,
        urgent_price=1249.0,
        deal_price=1349.0,
        bestbuy_sku="12062373",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m5-chip-with-10-core-cpu-and-10-core-gpu-16gb-memory-512gb-ssd-space-black/JJGCQL8GYV/sku/12062373",
        costco_item="1945134",
    ),

    # --- M5 Pro 14" (15C CPU / 16C GPU) — 24GB RAM ---
    TrackedSpec(
        mpn="MGDR4LL/A",
        chip="M5 Pro",
        ram_gb=24,
        storage_gb=1024,
        color="Space Black",
        msrp=2499.0,
        street_baseline=2239.0,
        urgent_price=1899.0,
        deal_price=2049.0,
        amazon_asin="B0GR1JK9W3",
        bestbuy_sku="6615860",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m5-pro-chip-with-15-core-cpu-and-16-core-gpu-24gb-memory-1tb-ssd-space-black/JJGCQLZV5J/sku/6615860",
        costco_item="2042887",
        costco_url="https://www.costco.com/p/-/macbook-pro-laptop-14-inch-apple-m5-pro-chip-built-for-apple-intelligence-15-core-cpu-16-core-gpu-24gb-memory-1tb-ssd-storage/4000444264",
    ),
    TrackedSpec(
        mpn="MGDN4LL/A",
        chip="M5 Pro",
        ram_gb=24,
        storage_gb=1024,
        color="Silver",
        msrp=2499.0,
        street_baseline=2249.0,
        urgent_price=1899.0,
        deal_price=2049.0,
        amazon_asin="B0GR17YNHL",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m5-pro-chip-with-15-core-cpu-and-16-core-gpu-24gb-memory-1tb-ssd-silver/JJGCQLZ5QH",
        costco_item="2042887",
    ),

    # --- M6 14" (12C CPU / 12C GPU, Wi-Fi 7, BT 6) — Nov 2026 Launch ---
    TrackedSpec(
        mpn="MHWT4LL/A",
        chip="M6",
        ram_gb=16,
        storage_gb=1024,
        color="Space Black",
        msrp=1999.0,
        street_baseline=1999.0,
        urgent_price=1699.0,
        deal_price=1799.0,
        amazon_asin="B0HPGSTXXX",
        bestbuy_sku="6565882",
        bestbuy_url="https://www.bestbuy.com/product/6565882/6565882",
        costco_url="https://www.costco.com/p/-/macbook-pro-laptop-14-inch-apple-m6-chip-built-for-apple-intelligence-12-core-cpu-12-core-gpu-16gb-memory-1tb-ssd-storage-1-year-applecare-included/4201023417",
    ),
    TrackedSpec(
        mpn="MHWW4LL/A",
        chip="M6",
        ram_gb=16,
        storage_gb=1024,
        color="Silver",
        msrp=1999.0,
        street_baseline=1999.0,
        urgent_price=1699.0,
        deal_price=1799.0,
        amazon_asin="B0HPGSSRNZ",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m6-chip-with-12-core-cpu-and-12-core-gpu-16gb-memory-1tb-ssd-silver/JJGCQYK3W7",
    ),
    TrackedSpec(
        mpn="MHWT4-24",
        chip="M6",
        ram_gb=24,
        storage_gb=1024,
        color="Space Black",
        msrp=2199.0,
        street_baseline=2199.0,
        urgent_price=1849.0,
        deal_price=1999.0,
        amazon_asin="B0HPGLLVR8",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m6-chip-with-12-core-cpu-and-12-core-gpu-24gb-memory-1tb-ssd-space-black/JJGCQYKX3Q",
    ),
    TrackedSpec(
        mpn="MHWW4-24",
        chip="M6",
        ram_gb=24,
        storage_gb=1024,
        color="Silver",
        msrp=2199.0,
        street_baseline=2199.0,
        urgent_price=1849.0,
        deal_price=1999.0,
        amazon_asin="B0HPGQYZYC",
        bestbuy_url="https://www.bestbuy.com/product/apple-macbook-pro-14-inch-laptop-m6-chip-with-12-core-cpu-and-12-core-gpu-24gb-memory-1tb-ssd-silver/JJGCQYK8S5",
    ),
]

SPEC_BY_MPN: dict[str, TrackedSpec] = {s.mpn.upper(): s for s in TRACKED_SPECS}
SPEC_BY_ASIN: dict[str, TrackedSpec] = {s.amazon_asin: s for s in TRACKED_SPECS if s.amazon_asin}
SPEC_BY_BBY_SKU: dict[str, TrackedSpec] = {s.bestbuy_sku: s for s in TRACKED_SPECS if s.bestbuy_sku}

# WarehouseRunner Costco clearance URLs (North Austin / TX warehouse stock tracker)
WAREHOUSERUNNER_URLS: list[dict[str, str]] = [
    {
        "item": "1945139",
        "mpn": "MDE14LL/A",
        "label": "Costco M5 16GB/1TB Space Black (#1945139)",
        "url": "https://app.warehouserunner.com/costco/1945139-macbook-pro-14-m5-16gb-1tb-space-black-mde14ll-a",
    },
    {
        "item": "1945134",
        "mpn": "MDE04LL/A",
        "label": "Costco M5 16GB/512GB Space Black (#1945134)",
        "url": "https://app.warehouserunner.com/costco/1945134-macbook-pro-14-m5-16gb-512gb-space-black-mde04ll-a",
    },
    {
        "item": "2042887",
        "mpn": "MGDR4LL/A",
        "label": "Costco M5 Pro 24GB/1TB Space Black (#2042887)",
        "url": "https://app.warehouserunner.com/costco/2042887-macbook-pro-14-m5-pro-24gb-1tb-space-black-mgdr4ll-a",
    },
]

# North Austin / North Metro physical store locations
AUSTIN_STORES = {
    "microcenter": [
        {"id": "215", "name": "Micro Center Austin", "address": "12707 N Mopac Expy, Austin, TX 78727"},
    ],
    "bestbuy": [
        {"id": "203", "name": "Best Buy North Austin", "address": "9607 Research Blvd Ste 500, Austin, TX 78759"},
        {"id": "178", "name": "Best Buy Cedar Park", "address": "11066 Pecan Park Blvd, Cedar Park, TX 78613"},
        {"id": "859", "name": "Best Buy Round Rock", "address": "3201 S I-35 Ste 600, Round Rock, TX 78664"},
        {"id": "1153", "name": "Best Buy Mueller", "address": "1201 Barbara Jordan Blvd, Austin, TX 78723"},
        {"id": "pflugerville", "name": "Best Buy Pflugerville", "address": "19000 Limestone Commercial Dr, Pflugerville, TX 78660"},
    ],
    "costco": [
        {"id": "681", "name": "Costco North Austin", "address": "10401 Research Blvd, Austin, TX 78759", "phone": "(512) 634-2253"},
        {"id": "1152", "name": "Costco Cedar Park", "address": "4601 183A Toll Rd, Cedar Park, TX 78613", "phone": "(512) 690-9059"},
        {"id": "1322", "name": "Costco Pflugerville", "address": "1901 Kelly Ln, Pflugerville, TX 78660", "phone": "(737) 888-6037"},
        {"id": "1385", "name": "Costco Georgetown", "address": "2201A N I-35, Georgetown, TX 78628"},
    ],
}
