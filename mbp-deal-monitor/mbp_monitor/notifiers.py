from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from typing import Iterable

import httpx

from .config import Settings
from .models import AlertTier, EvaluatedDeal

logger = logging.getLogger(__name__)


def format_deal_headline(deal: EvaluatedDeal, reason: str = "") -> str:
    l = deal.listing
    ram = f"{l.ram_gb}GB" if l.ram_gb else "?GB"
    ssd = f"{l.storage_gb // 1024}TB" if l.storage_gb and l.storage_gb >= 1024 else (f"{l.storage_gb}GB" if l.storage_gb else "")
    spec_str = " / ".join(p for p in [l.chip, ram, ssd, l.condition.value.replace("_", " ")] if p)
    prefix = "URGENT DEAL" if deal.tier == AlertTier.URGENT else "DEAL"
    return f"[{prefix}] ${l.price:,.0f} — {l.retailer} ({spec_str})"


def format_deal_body(deal: EvaluatedDeal, reason: str = "") -> str:
    l = deal.listing
    lines = [
        l.title,
        f"Price: ${l.price:,.2f} (Eff: ${deal.effective_price:,.2f}) | MSRP: ${deal.msrp:,.0f} | Save: ${deal.savings_vs_msrp:,.0f} ({deal.savings_pct_msrp:.0f}%)",
        f"Retailer: {l.retailer} | Location: {l.location}",
    ]
    if l.sku:
        lines.append(f"SKU/MPN: {l.sku}")
    if deal.reasons:
        lines.append("Highlights: " + ", ".join(deal.reasons))
    if l.notes:
        lines.append(f"Notes: {l.notes}")
    if reason:
        lines.append(f"Trigger: {reason}")
    lines.append(f"Link: {l.url}")
    return "\n".join(lines)


async def send_ntfy(client: httpx.AsyncClient, settings: Settings, deal: EvaluatedDeal, reason: str) -> None:
    if not settings.ntfy_topic:
        return
    title = format_deal_headline(deal, reason)
    body = format_deal_body(deal, reason)
    priority = "5" if deal.tier == AlertTier.URGENT else "4"
    tags = "rotating_light,laptop" if deal.tier == AlertTier.URGENT else "moneybag,laptop"
    headers = {
        "Title": title[:250],
        "Priority": priority,
        "Tags": tags,
        "Click": deal.listing.url,
        "Actions": f"view, Open Deal, {deal.listing.url}",
    }
    url = f"{settings.ntfy_server}/{settings.ntfy_topic}"
    r = await client.post(url, content=body.encode("utf-8"), headers=headers, timeout=10.0)
    r.raise_for_status()


async def send_discord(client: httpx.AsyncClient, settings: Settings, deal: EvaluatedDeal, reason: str) -> None:
    if not settings.discord_webhook_url:
        return
    l = deal.listing
    color = 0xE11D48 if deal.tier == AlertTier.URGENT else 0x10B981
    payload = {
        "embeds": [
            {
                "title": format_deal_headline(deal, reason)[:256],
                "url": l.url,
                "description": format_deal_body(deal, reason)[:4000],
                "color": color,
            }
        ]
    }
    r = await client.post(settings.discord_webhook_url, json=payload, timeout=10.0)
    r.raise_for_status()


async def send_telegram(client: httpx.AsyncClient, settings: Settings, deal: EvaluatedDeal, reason: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    text = f"{format_deal_headline(deal, reason)}\n\n{format_deal_body(deal, reason)}"
    api_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    r = await client.post(
        api_url,
        json={
            "chat_id": settings.telegram_chat_id,
            "text": text[:4096],
            "disable_web_page_preview": False,
        },
        timeout=10.0,
    )
    r.raise_for_status()


def send_macos_local(settings: Settings, deal: EvaluatedDeal, reason: str) -> None:
    if not settings.macos_notify or platform.system() != "Darwin":
        return
    title = format_deal_headline(deal, reason).replace('"', "'")
    subtitle = f"{deal.listing.retailer} — {deal.listing.location}".replace('"', "'")
    body = f"Eff: ${deal.effective_price:,.0f} | Save ${deal.savings_vs_msrp:,.0f}".replace('"', "'")
    script = f'display notification "{body}" with title "{title}" subtitle "{subtitle}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        if settings.macos_sound and deal.tier == AlertTier.URGENT:
            sound_path = f"/System/Library/Sounds/{settings.macos_sound}.aiff"
            subprocess.Popen(["afplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        logger.debug("macOS notification failed: %s", exc)


async def dispatch_alerts(settings: Settings, deals_with_reasons: Iterable[tuple[EvaluatedDeal, str]]) -> None:
    items = list(deals_with_reasons)
    if not items:
        return

    async with httpx.AsyncClient() as client:
        tasks = []
        for deal, reason in items:
            send_macos_local(settings, deal, reason)
            if settings.ntfy_topic:
                tasks.append(send_ntfy(client, settings, deal, reason))
            if settings.discord_webhook_url:
                tasks.append(send_discord(client, settings, deal, reason))
            if settings.telegram_bot_token and settings.telegram_chat_id:
                tasks.append(send_telegram(client, settings, deal, reason))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.warning("Notification delivery error: %s", res)
