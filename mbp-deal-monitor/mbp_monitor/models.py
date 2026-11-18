from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Condition(str, Enum):
    NEW = "new"
    OPEN_BOX_EXCELLENT = "open_box_excellent"
    OPEN_BOX_GOOD = "open_box_good"
    OPEN_BOX_FAIR = "open_box_fair"
    OPEN_BOX = "open_box"
    APPLE_REFURB = "apple_refurbished"
    CERTIFIED_REFURB = "certified_refurbished"
    USED = "used"
    UNKNOWN = "unknown"


class AlertTier(str, Enum):
    URGENT = "URGENT"   # Priority 5: exceptional clearance / record-low deal
    DEAL = "DEAL"       # Priority 4: solid discount >= threshold below baseline
    INFO = "INFO"       # Logged & tracked; normal street price or minor dip


@dataclass(slots=True)
class DealListing:
    source: str                 # e.g. "apple_refurb", "amazon", "bestbuy_api", "microcenter_austin"
    retailer: str               # Display retailer name, e.g. "Micro Center Austin"
    title: str
    url: str
    price: float
    condition: Condition = Condition.NEW
    chip: str = ""              # "M5", "M5 Pro", "M5 Max", "M6"
    ram_gb: Optional[int] = None
    storage_gb: Optional[int] = None
    color: str = ""
    sku: str = ""               # Apple MPN (MDE34LL/A) or ASIN / retailer ID
    msrp: Optional[float] = None
    location: str = "Online"    # e.g. "Austin #215", "North Austin #203", "Online"
    in_stock: bool = True
    notes: str = ""
    raw_id: str = ""            # Stable ID for deduplication across polls
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def stable_key(self) -> str:
        if self.raw_id:
            return f"{self.source}:{self.raw_id}"
        sku_part = self.sku or self.title[:60]
        return f"{self.source}:{sku_part}:{self.condition.value}:{self.location}".lower()


@dataclass(slots=True)
class EvaluatedDeal:
    listing: DealListing
    effective_price: float
    street_baseline: float
    msrp: float
    savings_vs_msrp: float
    savings_pct_msrp: float
    savings_vs_street: float
    score: float
    tier: AlertTier
    reasons: list[str] = field(default_factory=list)
