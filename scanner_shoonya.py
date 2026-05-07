"""
scanner_shoonya.py - Scanner using Shoonya API instead of yfinance
"""
import pandas as pd

from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

from config import settings
from core.scanner import (
    get_performance_data,
    to_internal,
    should_include_stock,
    passes_momentum_filter,
    compute_score,
    safe_divide
)
from core.broker import ShoonyaBroker
from utils.logger import get_logger

log = get_logger()

WATCHLIST = settings.WATCHLIST

def get_performance(stock):
    return get_performance_data().get(to_internal(stock))

def scan_stock(symbol, broker):
    try:
        df = broker.get_candles(
            symbol=symbol,
            lookback_days=5
        )

        if df is None or df.empty or len(df) < 60:
            log.debug(f"{symbol}: No data")
            return None

        required_columns = ["datetime", "open", "high", "low", "close", "volume"]
        if not set(required_columns).issubset(df.columns):
            log.debug(f"{symbol}: Missing OHLCV")
            return None

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df.dropna(inplace=True)

        if len(df) < 60:
            return None

        df["ema20"] = EMAIndicator(close=df["close"], window=20).ema_indicator()
        df["ema50"] = EMAIndicator(close=df["close"], window=50).ema_indicator()
        df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()

        atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["atr"] = atr.average_true_range()

        df["datetime"] = pd.to_datetime(df["datetime"])
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["date"] = df["datetime"].dt.date
        df["tpv"] = typical_price * df["volume"]
        df["vwap"] = df.groupby("date")["tpv"].cumsum() / df.groupby("date")["volume"].cumsum()

        df["vol_ma"] = df["volume"].rolling(20).mean()

        row = df.iloc[-1]

        rel_volume = safe_divide(row["volume"], row["vol_ma"])
        old_close = df.iloc[-10]["close"] if len(df) > 10 else df.iloc[0]["close"]
        change_pct = safe_divide(row["close"] - old_close, old_close) * 100
        trend_strength = safe_divide(abs(row["ema20"] - row["ema50"]), row["close"])
        atr_pct = safe_divide(row["atr"], row["close"])

        score = compute_score(row, rel_volume, change_pct, trend_strength)

        return {
            "symbol": symbol,
            "close": round(row["close"], 2),
            "rsi": round(row["rsi"], 2),
            "rel_volume": round(rel_volume, 2),
            "change_pct": round(change_pct, 2),
            "trend_strength": round(trend_strength, 4),
            "score": round(score, 2)
        }

    except Exception as e:
        log.debug(f"{symbol} error: {e}")

    return None


def run_scan():
    broker = ShoonyaBroker()
    
    if not broker.login():
        log.error("Failed to login to Shoonya")
        return []
    
    results = []
    
    for stock in WATCHLIST:
        perf = get_performance(stock)
        
        if perf is None:
            if not settings.ALLOW_UNKNOWN_STOCKS:
                log.debug(f"{stock}: Skipping - no performance data")
                continue
        else:
            include, reason = should_include_stock(stock, perf)
            if not include:
                log.debug(f"{stock}: Skipping - {reason}")
                continue

        result = scan_stock(stock, broker)

        if result and passes_momentum_filter(result["change_pct"], result["score"]):
            results.append(result)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    print("\n🔥 TOP MOMENTUM STOCKS (Shoonya) 🔥\n")

    if not results:
        print("No strong momentum stocks found.")
    else:
        for r in results:
            print(f"{r['symbol']} | ₹{r['close']} | RSI={r['rsi']} | RVOL={r['rel_volume']} | Move={r['change_pct']}% | Trend={r['trend_strength']} | Score={r['score']}")

    return results


if __name__ == "__main__":
    run_scan()