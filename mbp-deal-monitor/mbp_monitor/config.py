from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


def _as_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    base_dir: Path
    db_path: Path
    browser_profile_dir: Path

    ntfy_topic: str
    ntfy_server: str
    discord_webhook_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    macos_notify: bool
    macos_sound: str

    bestbuy_api_key: str
    keepa_api_key: str

    zip_code: str
    has_bh_payboo: bool
    has_costco_4pct: bool
    tax_rate: float

    fast_interval_sec: int
    browser_interval_sec: int
    realert_drop_dollars: float
    alert_cooldown_hours: float

    enable_browser_monitors: bool
    browser_headless: bool

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        base_dir = Path(__file__).resolve().parent.parent
        dotenv_path = env_file or (base_dir / ".env")
        if dotenv_path.exists():
            load_dotenv(dotenv_path)

        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        profile_dir = data_dir / "chromium_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            base_dir=base_dir,
            db_path=data_dir / "deals.db",
            browser_profile_dir=profile_dir,
            ntfy_topic=os.getenv("NTFY_TOPIC", "").strip(),
            ntfy_server=os.getenv("NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/"),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            macos_notify=_as_bool(os.getenv("MACOS_NOTIFY"), default=True),
            macos_sound=os.getenv("MACOS_SOUND", "Hero").strip(),
            bestbuy_api_key=os.getenv("BESTBUY_API_KEY", "").strip(),
            keepa_api_key=os.getenv("KEEPA_API_KEY", "").strip(),
            zip_code=os.getenv("ZIP_CODE", "78759").strip(),
            has_bh_payboo=_as_bool(os.getenv("HAS_BH_PAYBOO"), default=False),
            has_costco_4pct=_as_bool(os.getenv("HAS_COSTCO_4PCT"), default=False),
            tax_rate=float(os.getenv("TAX_RATE", "0.0825")),
            fast_interval_sec=int(os.getenv("FAST_INTERVAL_SEC", "60")),
            browser_interval_sec=int(os.getenv("BROWSER_INTERVAL_SEC", "180")),
            realert_drop_dollars=float(os.getenv("REALERT_DROP_DOLLARS", "15")),
            alert_cooldown_hours=float(os.getenv("ALERT_COOLDOWN_HOURS", "12")),
            enable_browser_monitors=_as_bool(os.getenv("ENABLE_BROWSER_MONITORS"), default=True),
            browser_headless=_as_bool(os.getenv("BROWSER_HEADLESS"), default=True),
        )
