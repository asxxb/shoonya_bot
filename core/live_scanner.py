import pandas as pd

from strategies.ema_rsi_scalper import EmaRsiScalper
from core.broker import ShoonyaBroker
from config import settings
from core.scanner import (
    PERFORMANCE_DATA,
    should_include_stock,
    passes_momentum_filter,
    compute_score
)
from utils.logger import get_logger

log = get_logger()


class LiveScanner:

    def __init__(self):
        self.broker = ShoonyaBroker()
        self.strategy = EmaRsiScalper()

    # ---------------------------------------------------
    # Scan Stocks
    # ---------------------------------------------------

    def scan(self):

        results = []

        for symbol in settings.WATCHLIST:

            try:

                df = self.broker.get_candles(
                    symbol=symbol
                )

                if df.empty or len(df) < 60:
                    continue

                df = self.strategy.compute_indicators(df)

                row = df.iloc[-2]

                # -----------------------------------------
                # Relative Volume
                # -----------------------------------------

                rel_volume = (

                    row["volume"]

                    /

                    row["vol_ma"]

                )

                # -----------------------------------------
                # Momentum %
                # -----------------------------------------

                old_close = df.iloc[-10]["close"]

                change_pct = (

                    (
                        row["close"]
                        -
                        old_close
                    )

                    /

                    old_close

                ) * 100

                # -----------------------------------------
                # Trend Strength
                # -----------------------------------------

                trend_strength = (

                    abs(
                        row["ema20"]
                        -
                        row["ema50"]
                    )

                    /

                    row["close"]

                )

                # -----------------------------------------
                # STEP 1: QUALITY FILTER (Performance)
                # -----------------------------------------
                
                # Use -EQ suffix to match backtest_results.json keys
                perf = PERFORMANCE_DATA.get(f"{symbol}-EQ", {})
                include, reason = should_include_stock(symbol, perf)
                
                if not include:
                    log.debug(f"{symbol}: Skipping - {reason}")
                    continue

                # -----------------------------------------
                # Score (using shared function)
                # -----------------------------------------

                score = compute_score(row, rel_volume, change_pct, trend_strength)

                # -----------------------------------------
                # STEP 2: MOMENTUM FILTER
                # -----------------------------------------

                if (
                    score >= settings.SCORE_THRESHOLD
                    and change_pct >= settings.MIN_MOMENTUM_PCT
                ):

                    results.append({

                        "symbol": symbol,

                        "score": score,

                        "change_pct": round(
                            change_pct,
                            2
                        ),

                        "close": round(
                            row["close"],
                            2
                        ),

                        "rsi": round(
                            row["rsi"],
                            2
                        )

                    })

            except Exception as e:

                log.error(
                    f"Scanner error "
                    f"{symbol}: {e}"
                )

        # ---------------------------------------------------
        # Sort
        # ---------------------------------------------------

        results = sorted(

            results,

            key=lambda x: x["score"],

            reverse=True

        )

        return results

    # ---------------------------------------------------
    # Best Stock
    # ---------------------------------------------------

    def best_stock(self):

        results = self.scan()

        if not results:

            return None

        best = results[0]

        log.info(

            f"🔥 BEST STOCK: "

            f"{best['symbol']} | "

            f"Score={best['score']} | "

            f"Move={best['change_pct']}%"

        )

        return best