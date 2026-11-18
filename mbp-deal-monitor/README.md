# MacBook Pro 14" (M5 & M6) 24/7 Deal Monitor — North Austin Edition

Low-latency 24/7 deal monitor built for your Mac Studio (Austin residential IP) covering:

- **Fast HTTP Tier (every 60s, 30s burst at midnight/Deal Zone reset):**
  - **Apple Certified Refurbished** (`apple.com/shop/refurbished/mac/14-inch-macbook-pro`) — parses `REFURB_GRID_BOOTSTRAP` directly
  - **Amazon New & Amazon Resale** (11 tracked M5, M5 Pro, and M6 ASINs + checkout promo % + optional Keepa API)
  - **Slickdeals RSS** (MacBook Pro search + Frontpage)
  - **Reddit Atom RSS** (`r/buildapcsales`, `r/macoffer`, `r/CostcoDeals`, `r/appleswap`, `r/blackfriday`)
  - **Apple Deal Blogs** (`9to5Toys`, `9to5Mac`, `AppleInsider`, `MacRumors`)
  - **Best Buy Official API** (optional free key — instant New + Open Box Excellent/Good/Fair)
- **Residential Browser Tier via Playwright (every 180s):**
  - **Micro Center Austin (`storeid=215`, 12707 N MoPac Expy)** — New & Open Box
  - **Best Buy Austin Local (`ZIP 78759`)** — New & Open Box without needing an API key
  - **AppleInsider Price Guide** — live matrix for B&H Photo, Adorama, Expercom, Amazon, CDW
  - **WarehouseRunner / Costco** — `.97` & `.00` warehouse clearance across Austin `#681`, Cedar Park `#1152`, Pflugerville `#1322`, Georgetown `#1385`
  - **B&H Photo Deal Zone**, **Woot Computers**, and **eBay Certified Refurbished**

## Quickstart on Mac Studio

```bash
cd mbp-deal-monitor
chmod +x setup_macos.sh
./setup_macos.sh
```

1. **Set up instant push notifications (15 seconds, zero signup):**
   - Install **ntfy** on your iPhone/Android (App Store / Play Store) and subscribe to a private random topic name (e.g., `mbp-atx-84k2m`).
   - Put `NTFY_TOPIC=mbp-atx-84k2m` into `.env`.
   - Optionally add `DISCORD_WEBHOOK_URL` or `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
   - `MACOS_NOTIFY=true` also triggers native Mac Studio banners + `Hero.aiff` alarm sound on `URGENT` deals.

2. **Test notifications & run a live check:**

```bash
.venv/bin/python -m mbp_monitor.monitor --test-notify
.venv/bin/python -m mbp_monitor.monitor --once --fast-only
.venv/bin/python -m mbp_monitor.monitor --once
```

3. **Run 24/7 in background with `launchd`:**

```bash
sed "s|__INSTALL_DIR__|$PWD|g" com.user.mbp-deal-monitor.plist.template > ~/Library/LaunchAgents/com.user.mbp-deal-monitor.plist
launchctl load -w ~/Library/LaunchAgents/com.user.mbp-deal-monitor.plist
tail -f data/monitor.log
```

Stop later with:

```bash
launchctl unload -w ~/Library/LaunchAgents/com.user.mbp-deal-monitor.plist
```

## Optional API Keys (Recommended for Maximum Speed)

- **Best Buy Developer API (Free):** Register at `https://developer.bestbuy.com/` and set `BESTBUY_API_KEY=...` in `.env` for instant official `openBox` + `products` queries.
- **Keepa API (Optional):** Set `KEEPA_API_KEY=...` in `.env` for sub-minute Amazon New & Amazon Resale price drops without relying on HTML parsing.
