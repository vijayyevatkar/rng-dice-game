from __future__ import annotations

import re
from typing import Optional

from .catalog import SPEC_BY_MPN, TRACKED_SPECS, TrackedSpec
from .config import Settings
from .models import AlertTier, Condition, DealListing, EvaluatedDeal

# Exclude non-target products & accessories
_EXCLUDE_PRODUCT_RE = re.compile(
    r"\b(macbook\s+air|macbook\s+neo|mac\s+mini|mac\s+studio|imac|ipad|"
    r"16[\s.\-]*(?:inch|in|\")|16\.2|15[\s.\-]*(?:inch|in|\")|13[\s.\-]*(?:inch|in|\")|"
    r"charger|adapter|cable|sleeve|case|shell|hub|dock|stand|screen\s+protector|"
    r"privacy\s+screen|keyboard\s+cover|bag|backpack|skin|mount|applecare\s+only)\b",
    re.IGNORECASE,
)

# Strictly reject older Apple Silicon chips unless M5/M6 is also explicitly the product
_OLDER_CHIP_RE = re.compile(r"\bM[1-4](?:\s+(?:Pro|Max|Ultra))?\b", re.IGNORECASE)
_TARGET_CHIP_RE = re.compile(r"\b(M5\s+Max|M5\s+Pro|M5|M6\s+Pro|M6\s+Max|M6)\b", re.IGNORECASE)
_MBP_RE = re.compile(r"\b(macbook\s*pro|mbp)\b", re.IGNORECASE)
_SCREEN_14_RE = re.compile(r"\b14(?:\.2)?[\s\-]*(?:inch|in|\"|”)?\b", re.IGNORECASE)
_RAM_RE = re.compile(r"\b(16|24|32|36|48|64)\s*GB\b", re.IGNORECASE)
_STORAGE_TB_RE = re.compile(r"\b([1248])\s*TB\b", re.IGNORECASE)
_STORAGE_512_RE = re.compile(r"\b512\s*GB\b", re.IGNORECASE)
_MPN_RE = re.compile(r"\b(M[A-Z0-9]{4}LL/A|Z1[A-Z0-9]{6}|G1[A-Z0-9]{3}LL/A|F[A-Z0-9]{4}LL/A)\b", re.IGNORECASE)
_PRICE_RE = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]{3,4}(?:\.[0-9]{1,2})?)")


def extract_price_from_text(text: str) -> Optional[float]:
    """Extract plausible laptop price ($750–$4500) from feed/title text."""
    candidates: list[float] = []
    for m in _PRICE_RE.finditer(text):
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 750.0 <= val <= 4500.0:
            candidates.append(val)
    if not candidates:
        return None
    # If text says "Save $300" or "$300 off", those are <750 so already filtered;
    # prefer the lowest plausible laptop price if multiple (e.g. "$1499 (was $1999)").
    return min(candidates)


def parse_specs_from_text(text: str) -> tuple[str, Optional[int], Optional[int], str]:
    """Infer (chip, ram_gb, storage_gb, mpn) from a listing title/body."""
    chip = ""
    m_chip = _TARGET_CHIP_RE.search(text)
    if m_chip:
        raw = re.sub(r"\s+", " ", m_chip.group(1)).strip().upper()
        chip = raw.replace("M5 PRO", "M5 Pro").replace("M5 MAX", "M5 Max").replace("M6 PRO", "M6 Pro").replace("M6 MAX", "M6 Max")

    ram_gb: Optional[int] = None
    for m in _RAM_RE.finditer(text):
        ram_gb = int(m.group(1))
        break

    storage_gb: Optional[int] = None
    m_tb = _STORAGE_TB_RE.search(text)
    if m_tb:
        storage_gb = int(m_tb.group(1)) * 1024
    elif _STORAGE_512_RE.search(text):
        storage_gb = 512

    mpn = ""
    m_mpn = _MPN_RE.search(text)
    if m_mpn:
        mpn = m_mpn.group(1).upper()

    return chip, ram_gb, storage_gb, mpn


def is_target_macbook_pro(title: str, allow_missing_size: bool = False) -> bool:
    """Return True iff text describes a 14-inch MacBook Pro with M5 or M6 (no M1-M4)."""
    if not title:
        return False
    if _EXCLUDE_PRODUCT_RE.search(title):
        return False
    if not _MBP_RE.search(title):
        return False
    if not _TARGET_CHIP_RE.search(title):
        return False
    # Reject listings whose chip is M1-M4 (e.g. "M4 vs M5" or "M4 MacBook Pro")
    # Only reject if an older chip appears AND isn't merely a comparison footnote.
    if _OLDER_CHIP_RE.search(title):
        # Check whether the primary chip before "vs" / "instead of" is M5/M6 or M4
        m_old = _OLDER_CHIP_RE.search(title)
        m_new = _TARGET_CHIP_RE.search(title)
        if m_old and m_new and m_old.start() < m_new.start():
            return False
        if m_old and not m_new:
            return False
    if not allow_missing_size and not _SCREEN_14_RE.search(title):
        return False
    return True


def _find_matching_spec(listing: DealListing) -> Optional[TrackedSpec]:
    if listing.sku:
        sku_up = listing.sku.upper()
        if sku_up in SPEC_BY_MPN:
            return SPEC_BY_MPN[sku_up]
        for s in TRACKED_SPECS:
            if s.amazon_asin == listing.sku or s.bestbuy_sku == listing.sku or s.apple_refurb_mpn == sku_up or s.costco_item == listing.sku:
                return s

    # Match by chip + RAM + storage + color
    chip = listing.chip
    ram = listing.ram_gb
    storage = listing.storage_gb
    if chip:
        candidates = [
            s for s in TRACKED_SPECS
            if s.chip.lower() == chip.lower()
            and (ram is None or s.ram_gb == ram)
            and (storage is None or s.storage_gb == storage)
        ]
        if candidates:
            if listing.color:
                for c in candidates:
                    if c.color.lower() in listing.color.lower():
                        return c
            return candidates[0]
    return None


def _default_baseline(chip: str, ram_gb: Optional[int], storage_gb: Optional[int]) -> tuple[float, float, float, float]:
    """Fallback (msrp, street_baseline, deal_price, urgent_price) when no exact SKU matched."""
    chip_u = (chip or "M5").upper()
    ram = ram_gb or 16
    storage = storage_gb or 1024

    if "M5 MAX" in chip_u:
        return (4099.0, 3599.0, 3199.0, 2799.0)
    if "M5 PRO" in chip_u:
        if storage >= 2048:
            return (2899.0, 2634.0, 2249.0, 1999.0)
        return (2499.0, 2239.0, 2049.0, 1899.0)
    if "M6" in chip_u:
        if ram >= 24:
            return (2199.0, 2199.0, 1999.0, 1849.0)
        return (1999.0, 1999.0, 1799.0, 1699.0)
    # Base M5
    if ram >= 32:
        return (2399.0, 2099.0, 1849.0, 1699.0)
    if ram >= 24:
        if storage <= 512:
            return (1799.0, 1649.0, 1560.0, 1499.0)
        return (2199.0, 1879.0, 1769.0, 1649.0)
    if storage <= 512:
        return (1599.0, 1499.0, 1349.0, 1249.0)
    return (1999.0, 1797.0, 1599.0, 1449.0)


def evaluate_deal(listing: DealListing, settings: Settings) -> Optional[EvaluatedDeal]:
    """Filter, enrich, score, and classify a DealListing."""
    # Reject obviously bogus prices (accessories, monthly payments, typos)
    if listing.price < 750.0 or listing.price > 4500.0:
        return None

    # Fill missing parsed fields from title
    inferred_chip, inferred_ram, inferred_storage, inferred_mpn = parse_specs_from_text(listing.title)
    if not listing.chip and inferred_chip:
        listing.chip = inferred_chip
    if listing.ram_gb is None and inferred_ram is not None:
        listing.ram_gb = inferred_ram
    if listing.storage_gb is None and inferred_storage is not None:
        listing.storage_gb = inferred_storage
    if not listing.sku and inferred_mpn:
        listing.sku = inferred_mpn

    # Must be M5 or M6 (never M4 or older)
    if not listing.chip or not listing.chip.upper().startswith(("M5", "M6")):
        return None
    # Reject 16-inch or other excluded products if somehow present
    if _EXCLUDE_PRODUCT_RE.search(listing.title):
        return None

    spec = _find_matching_spec(listing)
    if spec:
        msrp = listing.msrp or spec.msrp
        street = spec.street_baseline
        deal_threshold = spec.deal_price
        urgent_threshold = spec.urgent_price
        if listing.ram_gb is None:
            listing.ram_gb = spec.ram_gb
        if listing.storage_gb is None:
            listing.storage_gb = spec.storage_gb
    else:
        d_msrp, d_street, d_deal, d_urgent = _default_baseline(listing.chip, listing.ram_gb, listing.storage_gb)
        msrp = listing.msrp or d_msrp
        street = d_street
        deal_threshold = d_deal
        urgent_threshold = d_urgent

    # Effective price adjustment for Payboo (B&H) or Costco 4% cashback
    effective_price = listing.price
    reasons: list[str] = []
    retailer_low = listing.retailer.lower()
    if settings.has_bh_payboo and ("b&h" in retailer_low or "bhphotovideo" in listing.url.lower()):
        tax_saved = round(listing.price * settings.tax_rate, 2)
        effective_price = round(listing.price - tax_saved, 2)
        reasons.append(f"Payboo saves ~${tax_saved:.0f} TX tax")
    elif settings.has_costco_4pct and "costco" in retailer_low:
        cb = round(listing.price * 0.04, 2)
        effective_price = round(listing.price - cb, 2)
        reasons.append(f"Costco 4% back (-${cb:.0f})")

    savings_vs_msrp = round(msrp - effective_price, 2)
    savings_pct_msrp = round((savings_vs_msrp / msrp) * 100.0, 1) if msrp > 0 else 0.0
    savings_vs_street = round(street - effective_price, 2)

    # Check Costco .97 / .00 clearance price signature
    cents = round((listing.price % 1) * 100)
    is_costco_clearance = ("costco" in retailer_low) and cents in (97, 0) and listing.price < street - 100
    if is_costco_clearance:
        reasons.append(f"Costco .{cents:02d} clearance!")

    # Determine alert tier (price & deal prioritized, 24GB RAM gets a value bonus)
    is_open_or_used = listing.condition != Condition.NEW
    min_street_drop = 150.0 if is_open_or_used else 75.0

    if (
        effective_price <= urgent_threshold
        or savings_pct_msrp >= 22.0
        or is_costco_clearance
        or (is_open_or_used and savings_vs_street >= 250.0)
    ):
        tier = AlertTier.URGENT
    elif (
        effective_price <= deal_threshold
        or savings_vs_street >= min_street_drop
        or savings_pct_msrp >= 14.0
        or (listing.source in {"reddit", "slickdeals", "bh_dealzone", "woot"} and savings_vs_msrp >= 150.0)
    ):
        tier = AlertTier.DEAL
    else:
        tier = AlertTier.INFO

    if savings_vs_msrp >= 150:
        reasons.append(f"${savings_vs_msrp:.0f} ({savings_pct_msrp:.0f}%) off MSRP")
    if savings_vs_street >= 50:
        reasons.append(f"${savings_vs_street:.0f} below street")
    if (listing.ram_gb or 0) >= 24:
        reasons.append("24GB+ RAM")
    if listing.condition == Condition.APPLE_REFURB:
        reasons.append("Apple Certified Refurb (1yr warranty)")
    elif listing.condition in {Condition.OPEN_BOX, Condition.OPEN_BOX_EXCELLENT, Condition.OPEN_BOX_GOOD, Condition.OPEN_BOX_FAIR}:
        reasons.append(f"Open Box ({listing.condition.value.replace('open_box_', '').title()})")

    # Composite value score (higher = better deal)
    ram_bonus = 8.0 if (listing.ram_gb or 16) >= 24 else 0.0
    chip_bonus = 6.0 if "M6" in listing.chip.upper() or "PRO" in listing.chip.upper() else 0.0
    score = round(savings_pct_msrp * 2.0 + (savings_vs_street / 25.0) + ram_bonus + chip_bonus, 1)

    return EvaluatedDeal(
        listing=listing,
        effective_price=effective_price,
        street_baseline=street,
        msrp=msrp,
        savings_vs_msrp=savings_vs_msrp,
        savings_pct_msrp=savings_pct_msrp,
        savings_vs_street=savings_vs_street,
        score=score,
        tier=tier,
        reasons=reasons,
    )
