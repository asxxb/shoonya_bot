import pandas as pd

from strategies.ema_rsi_scalper import (
    EmaRsiScalper
)

from core.broker import ShoonyaBroker

from config import settings

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
                # Score
                # -----------------------------------------

                score = 0

                if row["ema20"] > row["ema50"]:
                    score += 2

                if row["close"] > row["vwap"]:
                    score += 2

                if row["rsi"] > 50:
                    score += 2

                if rel_volume > 1:
                    score += 2

                if change_pct > 0:
                    score += 2

                if trend_strength > 0.001:
                    score += 1

                # -----------------------------------------
                # Strong Bullish Momentum Only
                # -----------------------------------------

                if (
                    score >= 7
                    and change_pct > 0
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