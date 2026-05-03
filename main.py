#!/usr/bin/env python3
"""
main.py — Entry point for the Shoonya Intraday Trading Bot

Usage:
    python main.py            # Start the bot
    python main.py --backtest # Run backtest on historical data (coming soon)
    python main.py --check    # Just test credentials and market data
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import get_logger
from config import settings

log = get_logger(level=settings.LOG_LEVEL)


def check_mode():
    """Quick sanity check: login + fetch one quote."""
    log.info("Running connection check...")
    from core.broker import ShoonyaBroker
    broker = ShoonyaBroker()
    if not broker.login():
        log.error("❌ Login failed. Check .env credentials.")
        sys.exit(1)
    ltp = broker.get_ltp()
    if ltp:
        log.info(f"✅ Market data OK | {settings.SYMBOL} LTP = ₹{ltp:.2f}")
    else:
        log.warning("⚠️  LTP returned None — market may be closed.")
    candles = broker.get_candles(lookback_days=2)
    log.info(f"✅ Candles fetched: {len(candles)} rows")
    log.info("Check complete.")


def run_bot():
    from core.engine import TradingEngine
    engine = TradingEngine()
    engine.start()


def main():
    args = sys.argv[1:]

    if "--check" in args:
        check_mode()
    elif "--backtest" in args:
        log.info("Backtest mode coming soon. Run the strategy on historical CSV data.")
    else:
        run_bot()


if __name__ == "__main__":
    main()
