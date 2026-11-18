#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.11+ (e.g. brew install python)." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit .env to set your NTFY_TOPIC / Discord / Telegram!"
fi

echo ""
echo "Setup complete! Next steps:"
echo "  1. Edit .env and set NTFY_TOPIC (e.g. mbp-austin-$(openssl rand -hex 3))"
echo "  2. Test notifications:  .venv/bin/python -m mbp_monitor.monitor --test-notify"
echo "  3. Run one live check:  .venv/bin/python -m mbp_monitor.monitor --once"
echo "  4. Run 24/7 foreground: .venv/bin/python -m mbp_monitor.monitor"
