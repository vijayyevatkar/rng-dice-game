from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import httpx

from mbp_monitor.catalog import TRACKED_SPECS
from mbp_monitor.config import Settings
from mbp_monitor.db import DealDatabase
from mbp_monitor.evaluator import evaluate_deal, is_target_macbook_pro
from mbp_monitor.models import AlertTier, Condition, DealListing
from mbp_monitor.monitors.amazon import parse_amazon_dp_html
from mbp_monitor.monitors.apple_refurb import parse_apple_refurb_html
from mbp_monitor.monitors.feeds import FEED_SOURCES, parse_feed_xml
from mbp_monitor.notifiers import send_ntfy


def _test_settings(tmp_dir: Path, **overrides) -> Settings:
    base = Settings(
        base_dir=tmp_dir,
        db_path=tmp_dir / "deals.db",
        browser_profile_dir=tmp_dir / "profile",
        ntfy_topic="",
        ntfy_server="https://ntfy.sh",
        discord_webhook_url="",
        telegram_bot_token="",
        telegram_chat_id="",
        macos_notify=False,
        macos_sound="Hero",
        bestbuy_api_key="",
        keepa_api_key="",
        zip_code="78759",
        has_bh_payboo=False,
        has_costco_4pct=False,
        tax_rate=0.0825,
        fast_interval_sec=60,
        browser_interval_sec=180,
        realert_drop_dollars=15.0,
        alert_cooldown_hours=12.0,
        enable_browser_monitors=False,
        browser_headless=True,
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


class FilterAndEvaluatorTests(unittest.TestCase):
    def test_target_filter_accepts_m5_m6_14_and_rejects_m4_16_air_accessories(self) -> None:
        self.assertTrue(is_target_macbook_pro('Apple MacBook Pro 14" M5 24GB RAM 1TB SSD Space Black $1599'))
        self.assertTrue(is_target_macbook_pro('Apple MacBook Pro 14.2-inch M6 chip 16GB 1TB $1749'))
        self.assertTrue(is_target_macbook_pro('Open Box Apple MacBook Pro 14" M5 Pro 24GB 1TB $1899'))

        # Reject older chips, 16-inch, MacBook Air, accessories
        self.assertFalse(is_target_macbook_pro('Apple MacBook Pro 14" M4 Pro 24GB 1TB $1599'))
        self.assertFalse(is_target_macbook_pro('Apple MacBook Pro 14" M3 Max 36GB 1TB $1799'))
        self.assertFalse(is_target_macbook_pro('Apple MacBook Pro 16" M5 Pro 24GB 1TB $2299'))
        self.assertFalse(is_target_macbook_pro('Apple MacBook Air 14" M5 24GB 1TB $1299'))
        self.assertFalse(is_target_macbook_pro('65W USB-C Charger for MacBook Pro 14 M5 $19'))

    def test_evaluator_tiers_and_payboo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            s = _test_settings(Path(td), has_bh_payboo=True)
            # B&H M5 24GB/1TB at $1749 -> Payboo saves ~$144 tax -> eff ~$1604.71 -> URGENT
            listing = DealListing(
                source="appleinsider_guide",
                retailer="B&H Photo",
                title='Apple 14" MacBook Pro (M5, Silver) 24GB 1TB MDE64LL/A',
                url="https://www.bhphotovideo.com/example",
                price=1749.0,
                condition=Condition.NEW,
                chip="M5",
                ram_gb=24,
                storage_gb=1024,
                sku="MDE64LL/A",
            )
            ev = evaluate_deal(listing, s)
            self.assertIsNotNone(ev)
            assert ev is not None
            self.assertEqual(ev.tier, AlertTier.URGENT)
            self.assertLess(ev.effective_price, 1620.0)

    def test_costco_97_clearance_is_urgent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            s = _test_settings(Path(td))
            listing = DealListing(
                source="costco_warehouserunner",
                retailer="Costco Warehouse",
                title="Costco M5 16GB/1TB Space Black (#1945139)",
                url="https://app.warehouserunner.com/example",
                price=1349.97,
                condition=Condition.NEW,
                chip="M5",
                ram_gb=16,
                storage_gb=1024,
                sku="MDE14LL/A",
                location="Austin #681",
            )
            ev = evaluate_deal(listing, s)
            self.assertIsNotNone(ev)
            assert ev is not None
            self.assertEqual(ev.tier, AlertTier.URGENT)
            self.assertTrue(any(".97" in r for r in ev.reasons))


class DatabaseDeduplicationTests(unittest.TestCase):
    def test_dedup_price_drop_and_restock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            s = _test_settings(tmp)
            db = DealDatabase(s.db_path)
            try:
                base_listing = DealListing(
                    source="apple_refurb",
                    retailer="Apple Certified Refurbished",
                    title="Refurbished 14-inch MacBook Pro M5 24GB 1TB",
                    url="https://www.apple.com/shop/product/fde34ll/a",
                    price=1729.0,
                    condition=Condition.APPLE_REFURB,
                    chip="M5",
                    ram_gb=24,
                    storage_gb=1024,
                    sku="MDE34LL/A",
                    raw_id="FDE34LL/A",
                )
                ev1 = evaluate_deal(base_listing, s)
                assert ev1 is not None
                alert1, r1 = db.record_and_should_alert(ev1)
                self.assertTrue(alert1)
                self.assertEqual(r1, "new_deal")

                # Same price -> suppressed
                ev2 = evaluate_deal(base_listing, s)
                assert ev2 is not None
                alert2, _ = db.record_and_should_alert(ev2)
                self.assertFalse(alert2)

                # Drop by $30 -> re-alert
                dropped = replace(base_listing, price=1699.0)
                ev3 = evaluate_deal(dropped, s)
                assert ev3 is not None
                alert3, r3 = db.record_and_should_alert(ev3)
                self.assertTrue(alert3)
                self.assertIn("price_dropped", r3)

                # Goes OOS then back in stock at same price -> re-alert
                oos = replace(dropped, in_stock=False)
                ev4 = evaluate_deal(oos, s)
                assert ev4 is not None
                alert4, _ = db.record_and_should_alert(ev4)
                self.assertFalse(alert4)

                back = replace(dropped, in_stock=True)
                ev5 = evaluate_deal(back, s)
                assert ev5 is not None
                alert5, r5 = db.record_and_should_alert(ev5)
                self.assertTrue(alert5)
                self.assertEqual(r5, "back_in_stock")
            finally:
                db.close()


class ParserTests(unittest.TestCase):
    def test_apple_refurb_parser(self) -> None:
        sample_html = '''
        <script>
        window.REFURB_GRID_BOOTSTRAP = {
          "tiles": [
            {
              "title": "Refurbished 14-inch MacBook Pro Apple M5 chip - Space Black",
              "partNumber": "FDE34LL/A",
              "productDetailsUrl": "/shop/product/fde34ll/a/test",
              "price": {"currentPrice": {"raw_amount": "1779.00"}, "previousPrice": {"raw_amount": "2099.00"}},
              "filters": {"dimensions": {"dimensionScreensize": "14inch", "tsMemorySize": "24gb", "dimensionCapacity": "1tb", "dimensionColor": "spaceblack"}}
            },
            {
              "title": "Refurbished 14-inch MacBook Pro Apple M4 Pro Chip - Silver",
              "partNumber": "FX2H3LL/A",
              "productDetailsUrl": "/shop/product/fx2h3ll/a/test",
              "price": {"currentPrice": {"raw_amount": "1699.00"}},
              "filters": {"dimensions": {"dimensionScreensize": "14inch", "tsMemorySize": "24gb", "dimensionCapacity": "512gb"}}
            }
          ]
        };
        </script>
        '''
        res = parse_apple_refurb_html(sample_html)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].chip, "M5")
        self.assertEqual(res[0].ram_gb, 24)
        self.assertEqual(res[0].storage_gb, 1024)
        self.assertEqual(res[0].price, 1779.0)

    def test_amazon_dp_parser_new_and_resale(self) -> None:
        spec = next(s for s in TRACKED_SPECS if s.mpn == "MDE64LL/A")
        sample_html = '''
        <html><body>
          <span id="productTitle">Apple 2025 MacBook Pro 14.2-inch M5 24GB 1TB Silver</span>
          <div id="corePrice_feature_div"><span class="a-price"><span class="a-offscreen">$1,899.00</span></span></div>
          <div id="usedAccordionRow">
            Used - Like New <span class="a-price"><span class="a-offscreen">$1,700.00</span></span>
            Sold by: Amazon Resale Save 20% at checkout
          </div>
        </body></html>
        '''
        res = parse_amazon_dp_html(sample_html, spec)
        self.assertEqual(len(res), 2)
        new_l = next(r for r in res if r.condition == Condition.NEW)
        resale_l = next(r for r in res if r.source == "amazon_resale")
        self.assertEqual(new_l.price, 1899.0)
        self.assertEqual(resale_l.price, 1360.0)  # 1700 * 0.80

    def test_slickdeals_rss_parser(self) -> None:
        src = next(s for s in FEED_SOURCES if s.name == "slickdeals_mbp")
        rss = '''<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item>
            <title>Apple MacBook Pro 14" M5 24GB RAM 1TB SSD $1,549.99</title>
            <link>https://slickdeals.net/f/12345</link>
            <guid>sd-12345</guid>
            <description>Great Black Friday deal at B&amp;H</description>
          </item>
          <item>
            <title>Apple MacBook Pro 14" M4 16GB RAM 512GB $1,199</title>
            <link>https://slickdeals.net/f/99999</link>
            <guid>sd-99999</guid>
            <description>M4 model</description>
          </item>
        </channel></rss>'''
        res = parse_feed_xml(rss, src)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].price, 1549.99)
        self.assertEqual(res[0].ram_gb, 24)


class NotifierTests(unittest.TestCase):
    def test_ntfy_headers_are_ascii_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            s = _test_settings(Path(td), ntfy_topic="test-topic-123")
            listing = DealListing(
                source="test",
                retailer="Test — Retailer ‑ Austin",
                title="Apple 14\u201d MacBook Pro M5 \u2014 24GB",
                url="https://example.com/deal?q=14\u201d",
                price=1499.0,
                condition=Condition.NEW,
                chip="M5",
                ram_gb=24,
                storage_gb=1024,
                sku="MDE34LL/A",
            )
            ev = evaluate_deal(listing, s)
            assert ev is not None

            captured_headers: dict[str, str] = {}

            def handler(request: httpx.Request) -> httpx.Response:
                captured_headers.update(dict(request.headers))
                return httpx.Response(200, text="ok")

            async def _run() -> None:
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    await send_ntfy(client, s, ev, "test")

            asyncio.run(_run())
            self.assertIn("title", captured_headers)
            captured_headers["title"].encode("ascii")


if __name__ == "__main__":
    unittest.main()
