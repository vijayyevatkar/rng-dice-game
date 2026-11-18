from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.table import Table

from .config import Settings
from .db import DealDatabase
from .evaluator import evaluate_deal
from .models import AlertTier, Condition, DealListing, EvaluatedDeal
from .monitors.amazon import fetch_amazon_direct, fetch_keepa_offers
from .monitors.apple_refurb import fetch_apple_refurb
from .monitors.bestbuy_api import fetch_bestbuy_api
from .monitors.browser_retailers import fetch_browser_retailers
from .monitors.feeds import fetch_all_feeds
from .notifiers import dispatch_alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mbp_monitor")
console = Console()
AUSTIN_TZ = ZoneInfo("America/Chicago")


async def run_fast_cycle(settings: Settings) -> list[DealListing]:
    tasks = [
        fetch_apple_refurb(),
        fetch_all_feeds(),
        fetch_amazon_direct(),
    ]
    if settings.bestbuy_api_key:
        tasks.append(fetch_bestbuy_api(settings.bestbuy_api_key, settings.zip_code))
    if settings.keepa_api_key:
        tasks.append(fetch_keepa_offers(settings.keepa_api_key))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    listings: list[DealListing] = []
    for res in results:
        if isinstance(res, Exception):
            logger.warning("Fast monitor task failed: %s", res)
        else:
            listings.extend(res)
    return listings


async def process_listings(settings: Settings, db: DealDatabase, raw_listings: list[DealListing]) -> list[EvaluatedDeal]:
    evaluated: list[EvaluatedDeal] = []
    to_notify: list[tuple[EvaluatedDeal, str]] = []

    for listing in raw_listings:
        ev = evaluate_deal(listing, settings)
        if ev is None:
            continue
        evaluated.append(ev)
        should_alert, reason = db.record_and_should_alert(
            ev,
            realert_drop_dollars=settings.realert_drop_dollars,
            cooldown_hours=settings.alert_cooldown_hours,
        )
        if should_alert:
            to_notify.append((ev, reason))

    if to_notify:
        to_notify.sort(key=lambda pair: (pair[0].tier != AlertTier.URGENT, -pair[0].score))
        logger.info("Sending %d alert(s)...", len(to_notify))
        await dispatch_alerts(settings, to_notify)

    return evaluated


def print_summary_table(evaluated: list[EvaluatedDeal]) -> None:
    if not evaluated:
        console.print("[yellow]No matching M5/M6 14-inch MacBook Pro deals observed in this cycle.[/yellow]")
        return

    table = Table(title="14-inch MacBook Pro (M5 / M6) Live Observations")
    table.add_column("Tier", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Eff.", justify="right")
    table.add_column("Save vs MSRP", justify="right")
    table.add_column("Chip / RAM / SSD")
    table.add_column("Cond.")
    table.add_column("Retailer")
    table.add_column("Location")

    for ev in sorted(evaluated, key=lambda d: (-d.score, d.effective_price))[:25]:
        l = ev.listing
        tier_style = "bold red" if ev.tier == AlertTier.URGENT else ("bold green" if ev.tier == AlertTier.DEAL else "dim")
        ram = f"{l.ram_gb}GB" if l.ram_gb else "?GB"
        ssd = f"{l.storage_gb // 1024}TB" if l.storage_gb and l.storage_gb >= 1024 else (f"{l.storage_gb}GB" if l.storage_gb else "?")
        table.add_row(
            f"[{tier_style}]{ev.tier.value}[/{tier_style}]",
            f"${l.price:,.0f}",
            f"${ev.effective_price:,.0f}",
            f"-${ev.savings_vs_msrp:,.0f} ({ev.savings_pct_msrp:.0f}%)",
            f"{l.chip} {ram}/{ssd}",
            l.condition.value.replace("open_box_", "OB:"),
            l.retailer,
            l.location[:28],
        )
    console.print(table)


async def fast_loop(settings: Settings, db: DealDatabase) -> None:
    while True:
        now_ct = datetime.now(AUSTIN_TZ)
        # Burst to 30s polling around B&H Deal Zone reset (23:00 CT) & Best Buy reset (00:00 CT)
        is_reset_burst = (now_ct.hour == 23 and now_ct.minute <= 10) or (now_ct.hour == 0 and now_ct.minute <= 10)
        interval = min(30, settings.fast_interval_sec) if is_reset_burst else settings.fast_interval_sec

        try:
            listings = await run_fast_cycle(settings)
            evaluated = await process_listings(settings, db, listings)
            deals_count = sum(1 for e in evaluated if e.tier != AlertTier.INFO)
            logger.info("Fast cycle complete: %d M5/M6 listings (%d deals/urgent).", len(evaluated), deals_count)
        except Exception as exc:
            logger.exception("Fast loop error: %s", exc)

        await asyncio.sleep(interval)


async def browser_loop(settings: Settings, db: DealDatabase) -> None:
    if not settings.enable_browser_monitors:
        return
    while True:
        try:
            listings = await fetch_browser_retailers(settings)
            evaluated = await process_listings(settings, db, listings)
            deals_count = sum(1 for e in evaluated if e.tier != AlertTier.INFO)
            logger.info("Browser cycle complete: %d M5/M6 listings (%d deals/urgent).", len(evaluated), deals_count)
        except Exception as exc:
            logger.exception("Browser loop error: %s", exc)

        await asyncio.sleep(settings.browser_interval_sec)


async def run_once(settings: Settings, db: DealDatabase, fast_only: bool) -> None:
    listings = await run_fast_cycle(settings)
    if not fast_only and settings.enable_browser_monitors:
        listings.extend(await fetch_browser_retailers(settings))
    evaluated = await process_listings(settings, db, listings)
    print_summary_table(evaluated)


async def send_test_alert(settings: Settings) -> None:
    sample = DealListing(
        source="test",
        retailer="Test Alert (Micro Center Austin)",
        title="TEST: Apple MacBook Pro 14\" M5 24GB/1TB Space Black (MDE34LL/A)",
        url="https://www.apple.com/shop/refurbished/mac/14-inch-macbook-pro",
        price=1499.00,
        condition=Condition.NEW,
        chip="M5",
        ram_gb=24,
        storage_gb=1024,
        sku="MDE34LL/A",
        msrp=2199.0,
        location="Austin #215 (12707 N MoPac)",
        notes="End-to-end notification pipeline verification",
    )
    ev = evaluate_deal(sample, settings)
    assert ev is not None
    await dispatch_alerts(settings, [(ev, "test_notification")])
    console.print("[green]Test notification dispatched to configured channels.[/green]")


def show_db_summary(db: DealDatabase) -> None:
    rows = db.top_recent_deals(limit=25)
    if not rows:
        console.print("[yellow]Database has no recorded deals yet.[/yellow]")
        return
    table = Table(title="Lowest Recorded In-Stock M5/M6 14\" MacBook Pro Prices")
    table.add_column("Tier")
    table.add_column("Last $", justify="right")
    table.add_column("Low $", justify="right")
    table.add_column("Chip/RAM/SSD")
    table.add_column("Cond.")
    table.add_column("Retailer")
    table.add_column("URL")
    for r in rows:
        ssd = f"{r['storage_gb'] // 1024}TB" if r["storage_gb"] and r["storage_gb"] >= 1024 else f"{r['storage_gb']}GB"
        table.add_row(
            r["last_tier"] or "?",
            f"${r['last_price']:,.0f}",
            f"${r['lowest_price']:,.0f}",
            f"{r['chip']} {r['ram_gb']}GB/{ssd}",
            r["condition"],
            r["retailer"],
            r["url"][:65],
        )
    console.print(table)


async def async_main() -> None:
    parser = argparse.ArgumentParser(description="MacBook Pro 14 (M5 / M6) 24/7 Deal Monitor")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--fast-only", action="store_true", help="Skip Playwright browser checks")
    parser.add_argument("--test-notify", action="store_true", help="Send a test alert and exit")
    parser.add_argument("--summary", action="store_true", help="Print best prices stored in SQLite and exit")
    args = parser.parse_args()

    settings = Settings.load()
    db = DealDatabase(settings.db_path)
    try:
        if args.test_notify:
            await send_test_alert(settings)
        elif args.summary:
            show_db_summary(db)
        elif args.once:
            await run_once(settings, db, fast_only=args.fast_only)
        else:
            logger.info(
                "Starting 24/7 MBP 14\" (M5/M6) Monitor — fast=%ds, browser=%ds (enabled=%s)",
                settings.fast_interval_sec,
                settings.browser_interval_sec,
                settings.enable_browser_monitors and not args.fast_only,
            )
            tasks = [fast_loop(settings, db)]
            if not args.fast_only and settings.enable_browser_monitors:
                tasks.append(browser_loop(settings, db))
            await asyncio.gather(*tasks)
    finally:
        db.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
