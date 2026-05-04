"""
core/scanner.py
Unified scanner with quality + momentum filtering.
Used by: scanner.py, scanner_worker.py, live_scanner.py
"""
import json
import os
import pandas as pd

from config import settings
from utils.logger import get_logger

log = get_logger()


# ---------------------------------------------------
# PERFORMANCE DATA (CACHED)
# ---------------------------------------------------

def load_performance_data():
    """Load backtest performance data for stock quality filtering."""
    path = "data/backtest_results.json"
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


PERFORMANCE_DATA = load_performance_data()


# ---------------------------------------------------
# STOCK SCORING (SHARED LOGIC)
# ---------------------------------------------------

def compute_score(row, rel_volume, change_pct, trend_strength):
    """Compute momentum score for a stock."""
    score = 0
    
    # EMA Trend
    if row.get("ema20") and row.get("ema50") and row["ema20"] > row["ema50"]:
        score += 2
    
    # Above VWAP
    if row.get("vwap") and row["close"] > row["vwap"]:
        score += 2
    
    # RSI Strength
    if row.get("rsi") and row["rsi"] > 50:
        score += 2
    
    # Relative Volume
    if rel_volume > 1:
        score += 2
    
    # Momentum Score
    if change_pct > 2:
        score += 4
    elif change_pct > 1:
        score += 3
    elif change_pct > 0.5:
        score += 2
    elif change_pct > 0:
        score += 1
    else:
        score -= 3
    
    # Strong Trend
    if trend_strength > 0.001:
        score += 1
    
    # Volatility
    atr_pct = row.get("atr", 0) / row["close"] if row["close"] else 0
    if atr_pct > 0.0005:
        score += 1
    
    return score


# ---------------------------------------------------
# STOCK FILTERING (SHARED LOGIC)
# ---------------------------------------------------

def should_include_stock(symbol, perf=None):
    """
    STEP 1: Quality Filter
    Returns: (should_include: bool, reason: str)
    """
    # If no performance data, allow (for exploration)
    if not perf:
        return True, "no_perf_data"
    
    # Require minimum trades for reliability
    if perf.get("trades", 0) < settings.MIN_BACKTEST_TRADES:
        return False, f"insufficient_trades({perf.get('trades', 0)})"
    
    # Skip stocks with negative expectancy
    if perf.get("expectancy", 0) <= settings.MIN_EXPECTANCY:
        return False, f"negative_expectancy({perf.get('expectancy', 0):.2f})"
    
    return True, "passed"


def passes_momentum_filter(change_pct, score):
    """
    STEP 2: Momentum Filter
    Returns: (should_include: bool)
    """
    return (
        score >= settings.SCORE_THRESHOLD
        and change_pct >= settings.MIN_MOMENTUM_PCT
    )


# ---------------------------------------------------
# EXPORTED FUNCTIONS
# ---------------------------------------------------

__all__ = [
    "PERFORMANCE_DATA",
    "load_performance_data",
    "compute_score",
    "should_include_stock",
    "passes_momentum_filter"
]