from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .models import AlertTier, EvaluatedDeal


class DealDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stable_key TEXT NOT NULL,
                source TEXT NOT NULL,
                retailer TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                sku TEXT,
                chip TEXT,
                ram_gb INTEGER,
                storage_gb INTEGER,
                condition TEXT,
                location TEXT,
                price REAL NOT NULL,
                effective_price REAL NOT NULL,
                msrp REAL,
                score REAL,
                tier TEXT NOT NULL,
                in_stock INTEGER NOT NULL,
                observed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_obs_key_time ON observations(stable_key, observed_at);

            CREATE TABLE IF NOT EXISTS best_prices (
                stable_key TEXT PRIMARY KEY,
                lowest_price REAL NOT NULL,
                last_price REAL NOT NULL,
                last_in_stock INTEGER NOT NULL,
                last_alerted_price REAL,
                last_alerted_at TEXT,
                last_tier TEXT,
                retailer TEXT,
                title TEXT,
                url TEXT,
                chip TEXT,
                ram_gb INTEGER,
                storage_gb INTEGER,
                condition TEXT,
                location TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def record_and_should_alert(
        self,
        deal: EvaluatedDeal,
        realert_drop_dollars: float = 15.0,
        cooldown_hours: float = 12.0,
    ) -> tuple[bool, str]:
        """Store observation and decide if this warrants an immediate push notification.

        Returns (should_alert, reason).
        """
        l = deal.listing
        key = l.stable_key()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        self.conn.execute(
            """
            INSERT INTO observations (
                stable_key, source, retailer, title, url, sku, chip, ram_gb, storage_gb,
                condition, location, price, effective_price, msrp, score, tier, in_stock, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                l.source,
                l.retailer,
                l.title,
                l.url,
                l.sku,
                l.chip,
                l.ram_gb,
                l.storage_gb,
                l.condition.value,
                l.location,
                l.price,
                deal.effective_price,
                deal.msrp,
                deal.score,
                deal.tier.value,
                1 if l.in_stock else 0,
                now_iso,
            ),
        )

        row = self.conn.execute("SELECT * FROM best_prices WHERE stable_key = ?", (key,)).fetchone()

        should_alert = False
        alert_reason = ""

        if not l.in_stock:
            # Update state even if out of stock so future restocks trigger an alert
            if row:
                self.conn.execute(
                    "UPDATE best_prices SET last_price=?, last_in_stock=0, updated_at=? WHERE stable_key=?",
                    (l.price, now_iso, key),
                )
            self.conn.commit()
            return False, "out_of_stock"

        if deal.tier == AlertTier.INFO:
            # Update baseline tracking without alerting
            if row is None:
                self.conn.execute(
                    """
                    INSERT INTO best_prices (
                        stable_key, lowest_price, last_price, last_in_stock,
                        last_alerted_price, last_alerted_at, last_tier,
                        retailer, title, url, chip, ram_gb, storage_gb, condition, location, updated_at
                    ) VALUES (?, ?, ?, 1, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key, l.price, l.price, deal.tier.value,
                        l.retailer, l.title, l.url, l.chip, l.ram_gb, l.storage_gb,
                        l.condition.value, l.location, now_iso,
                    ),
                )
            else:
                self.conn.execute(
                    "UPDATE best_prices SET lowest_price=MIN(lowest_price, ?), last_price=?, last_in_stock=1, url=?, updated_at=? WHERE stable_key=?",
                    (l.price, l.price, l.url, now_iso, key),
                )
            self.conn.commit()
            return False, "info_only"

        # DEAL or URGENT tier
        if row is None:
            should_alert = True
            alert_reason = "new_deal"
        else:
            prev_in_stock = bool(row["last_in_stock"])
            last_alerted_price: Optional[float] = row["last_alerted_price"]
            last_alerted_at_str: Optional[str] = row["last_alerted_at"]

            if last_alerted_price is None:
                should_alert = True
                alert_reason = "crossed_deal_threshold"
            elif not prev_in_stock:
                should_alert = True
                alert_reason = "back_in_stock"
            elif l.price <= last_alerted_price - realert_drop_dollars:
                should_alert = True
                alert_reason = f"price_dropped_${last_alerted_price - l.price:.0f}"
            elif last_alerted_at_str:
                last_dt = datetime.fromisoformat(last_alerted_at_str)
                if now - last_dt >= timedelta(hours=cooldown_hours) and deal.tier == AlertTier.URGENT:
                    should_alert = True
                    alert_reason = "urgent_reminder"

        if row is None:
            self.conn.execute(
                """
                INSERT INTO best_prices (
                    stable_key, lowest_price, last_price, last_in_stock,
                    last_alerted_price, last_alerted_at, last_tier,
                    retailer, title, url, chip, ram_gb, storage_gb, condition, location, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key, l.price, l.price,
                    l.price if should_alert else None,
                    now_iso if should_alert else None,
                    deal.tier.value,
                    l.retailer, l.title, l.url, l.chip, l.ram_gb, l.storage_gb,
                    l.condition.value, l.location, now_iso,
                ),
            )
        else:
            self.conn.execute(
                """
                UPDATE best_prices
                SET lowest_price = MIN(lowest_price, ?),
                    last_price = ?,
                    last_in_stock = 1,
                    last_alerted_price = COALESCE(?, last_alerted_price),
                    last_alerted_at = COALESCE(?, last_alerted_at),
                    last_tier = ?,
                    url = ?,
                    updated_at = ?
                WHERE stable_key = ?
                """,
                (
                    l.price,
                    l.price,
                    l.price if should_alert else None,
                    now_iso if should_alert else None,
                    deal.tier.value,
                    l.url,
                    now_iso,
                    key,
                ),
            )
        self.conn.commit()
        return should_alert, alert_reason

    def top_recent_deals(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM best_prices
            WHERE last_in_stock = 1
            ORDER BY last_price ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
