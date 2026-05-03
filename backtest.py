#!/usr/bin/env python3
"""
backtest.py
Simple event-driven backtest using saved candle data.

Usage:
    python backtest.py --symbol SBIN-EQ --days 10

Reads from: data/candles_<symbol>.csv  OR fetches live and saves.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import pandas as pd
from datetime import datetime

from utils.logger import get_logger
from config import settings
from strategies.ema_rsi_scalper import EmaRsiScalper, SIGNAL_LONG, SIGNAL_SHORT
from core.risk_manager import RiskManager

log = get_logger()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_and_save(symbol, exchange, days):
    """Fetch candles from Shoonya and save to CSV."""
    from core.broker import ShoonyaBroker
    broker = ShoonyaBroker()
    if not broker.login():
        log.error("Login failed — cannot fetch data for backtest.")
        sys.exit(1)
    df = broker.get_candles(symbol=symbol, exchange=exchange, lookback_days=days)
    path = os.path.join(DATA_DIR, f"candles_{symbol.replace('-','_')}.csv")
    df.to_csv(path, index=False)
    log.info(f"Saved {len(df)} candles to {path}")
    return df


def run_backtest(df: pd.DataFrame, initial_capital: float = 1000.0):
    strategy = EmaRsiScalper()
    risk = RiskManager()

    capital = initial_capital
    trades = []
    in_trade = False
    entry = sl = tp = side = qty_bt = 0

    # Walk forward through candles
    for i in range(settings.EMA_SLOW + 5, len(df)):
        window = df.iloc[:i+1].copy()
        signal, info = strategy.get_signal(window)

        ltp = df.iloc[i]["close"]

        # ── Exit logic ─────────────────────────────────────────────────────────
        if in_trade:
            hit = None
            if side == "BUY":
                if ltp <= sl: hit = "SL"
                elif ltp >= tp: hit = "TP"
            else:
                if ltp >= sl: hit = "SL"
                elif ltp <= tp: hit = "TP"

            if hit:
                pnl = (ltp - entry) * qty_bt if side == "BUY" else (entry - ltp) * qty_bt
                capital += pnl
                trades.append({
                    "date":  df.iloc[i]["datetime"],
                    "side":  side,
                    "entry": entry,
                    "exit":  ltp,
                    "qty":   qty_bt,
                    "pnl":   round(pnl, 2),
                    "hit":   hit,
                    "cap":   round(capital, 2),
                })
                in_trade = False

        # ── Entry logic ────────────────────────────────────────────────────────
        if not in_trade and info:
            atr = info.get("atr", ltp * 0.01)
            if atr <= 0:
                atr = ltp * 0.01

            if signal == SIGNAL_LONG:
                qty_bt, sl, tp = risk.calculate_qty(ltp, atr)
                entry = ltp
                side  = "BUY"
                in_trade = True
            elif signal == SIGNAL_SHORT:
                qty_bt, sl, tp = risk.calculate_short_qty(ltp, atr)
                entry = ltp
                side  = "SELL"
                in_trade = True

    # ── Results ────────────────────────────────────────────────────────────────
    results = pd.DataFrame(trades)
    if results.empty:
        log.info("No trades generated in backtest.")
        return

    wins   = results[results["pnl"] > 0]
    losses = results[results["pnl"] <= 0]

    print("\n" + "="*55)
    print(f"  BACKTEST RESULTS — {settings.SYMBOL}")
    print("="*55)
    print(f"  Candles    : {len(df)}")
    print(f"  Trades     : {len(results)}")
    print(f"  Win Rate   : {len(wins)/len(results)*100:.1f}%")
    print(f"  Avg Win    : ₹{wins['pnl'].mean():.2f}" if not wins.empty else "  Avg Win    : N/A")
    print(f"  Avg Loss   : ₹{losses['pnl'].mean():.2f}" if not losses.empty else "  Avg Loss   : N/A")
    print(f"  Total PnL  : ₹{results['pnl'].sum():.2f}")
    print(f"  Start Cap  : ₹{initial_capital:.2f}")
    print(f"  End Cap    : ₹{capital:.2f}")
    print(f"  Return     : {((capital-initial_capital)/initial_capital*100):.1f}%")
    print("="*55)
    print("\nLast 10 trades:")
    print(results.tail(10).to_string(index=False))

    # Save results
    out_path = os.path.join(DATA_DIR, f"backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    results.to_csv(out_path, index=False)
    log.info(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",   default=settings.SYMBOL)
    parser.add_argument("--exchange", default=settings.EXCHANGE)
    parser.add_argument("--days",     default=10, type=int)
    parser.add_argument("--use-cached", action="store_true",
                        help="Load from local CSV instead of fetching live")
    args = parser.parse_args()

    cached_path = os.path.join(DATA_DIR, f"candles_{args.symbol.replace('-','_')}.csv")

    if args.use_cached and os.path.exists(cached_path):
        log.info(f"Loading cached data from {cached_path}")
        df = pd.read_csv(cached_path, parse_dates=["datetime"])
    else:
        df = fetch_and_save(args.symbol, args.exchange, args.days)

    run_backtest(df, initial_capital=settings.CAPITAL)
