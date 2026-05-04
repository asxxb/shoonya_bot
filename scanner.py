import yfinance as yf
import pandas as pd

from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# ---------------------------------------------------
# WATCHLIST
# ---------------------------------------------------

WATCHLIST = [

    "SBIN",
    "NHPC",
    "SUZLON",
    "YESBANK",
    "IDFCFIRSTB",
    "UCOBANK",
    "IREDA",
    "RVNL",
    "NBCC",
    "IRFC",
    "PNB",
    "BANKBARODA",
    "SAIL",
    "JIOFIN"

]

# ---------------------------------------------------
# SCAN SINGLE STOCK
# ---------------------------------------------------

def scan_stock(symbol):

    try:

        yahoo_symbol = f"{symbol}.NS"

        # -----------------------------------------
        # FETCH DATA
        # -----------------------------------------

        df = yf.download(

            yahoo_symbol,
            interval="5m",
            period="5d",
            progress=False,
            auto_adjust=False

        )

        # -----------------------------------------
        # EMPTY CHECK
        # -----------------------------------------

        if df.empty or len(df) < 60:

            print(f"{symbol}: No data")

            return None

        # -----------------------------------------
        # FIX MULTIINDEX
        # -----------------------------------------

        if isinstance(df.columns, pd.MultiIndex):

            df.columns = (
                df.columns.get_level_values(0)
            )

        # -----------------------------------------
        # RESET INDEX
        # -----------------------------------------

        df.reset_index(inplace=True)

        # -----------------------------------------
        # RENAME COLUMNS
        # -----------------------------------------

        df.rename(columns={

            "Datetime": "datetime",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"

        }, inplace=True)

        # -----------------------------------------
        # KEEP REQUIRED COLUMNS
        # -----------------------------------------

        required_columns = [

            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume"

        ]

        if not set(required_columns).issubset(df.columns):

            print(f"{symbol}: Missing OHLCV")

            return None

        df = df[required_columns]

        # -----------------------------------------
        # NUMERIC CONVERSION
        # -----------------------------------------

        for col in [

            "open",
            "high",
            "low",
            "close",
            "volume"

        ]:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df.dropna(inplace=True)

        # -----------------------------------------
        # NEED ENOUGH DATA
        # -----------------------------------------

        if len(df) < 60:

            return None

        # -----------------------------------------
        # EMA
        # -----------------------------------------

        df["ema20"] = EMAIndicator(

            close=df["close"],
            window=20

        ).ema_indicator()

        df["ema50"] = EMAIndicator(

            close=df["close"],
            window=50

        ).ema_indicator()

        # -----------------------------------------
        # RSI
        # -----------------------------------------

        df["rsi"] = RSIIndicator(

            close=df["close"],
            window=14

        ).rsi()

        # -----------------------------------------
        # ATR
        # -----------------------------------------

        atr = AverageTrueRange(

            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14

        )

        df["atr"] = atr.average_true_range()

        # -----------------------------------------
        # VWAP
        # -----------------------------------------

        df["datetime"] = pd.to_datetime(
            df["datetime"]
        )

        typical_price = (

            df["high"] +
            df["low"] +
            df["close"]

        ) / 3

        df["date"] = (
            df["datetime"].dt.date
        )

        df["tpv"] = (
            typical_price *
            df["volume"]
        )

        df["vwap"] = (

            df.groupby("date")["tpv"].cumsum()

            /

            df.groupby("date")["volume"].cumsum()

        )

        # -----------------------------------------
        # VOLUME MA
        # -----------------------------------------

        df["vol_ma"] = (

            df["volume"]
            .rolling(20)
            .mean()

        )

        # -----------------------------------------
        # USE PREVIOUS CLOSED CANDLE
        # -----------------------------------------

        row = df.iloc[-2]

        # -----------------------------------------
        # RELATIVE VOLUME
        # -----------------------------------------

        rel_volume = (

            row["volume"]

            /

            row["vol_ma"]

        )

        # -----------------------------------------
        # PRICE CHANGE %
        # -----------------------------------------

        old_close = df.iloc[-10]["close"]

        change_pct = (

            (
                row["close"] -
                old_close
            )

            /

            old_close

        ) * 100

        # -----------------------------------------
        # TREND STRENGTH
        # -----------------------------------------

        trend_strength = (

            abs(
                row["ema20"] -
                row["ema50"]
            )

            /

            row["close"]

        )

        # -----------------------------------------
        # ATR %
        # -----------------------------------------

        atr_pct = (

            row["atr"]

            /

            row["close"]

        )

        # -----------------------------------------
        # SCORE SYSTEM
        # -----------------------------------------

        score = 0

        # EMA Trend
        if row["ema20"] > row["ema50"]:
            score += 2

        # Above VWAP
        if row["close"] > row["vwap"]:
            score += 2

        # RSI Strength
        if row["rsi"] > 50:
            score += 2

        # Relative Volume
        if rel_volume > 1:
            score += 2

        # -----------------------------------------
        # MOMENTUM SCORE
        # -----------------------------------------

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
        if atr_pct > 0.0005:
            score += 1

        # -----------------------------------------
        # RETURN RESULT
        # -----------------------------------------

        return {

            "symbol": symbol,

            "close": round(
                row["close"],
                2
            ),

            "rsi": round(
                row["rsi"],
                2
            ),

            "rel_volume": round(
                rel_volume,
                2
            ),

            "change_pct": round(
                change_pct,
                2
            ),

            "trend_strength": round(
                trend_strength,
                4
            ),

            "score": round(
                score,
                2
            )

        }

    except Exception as e:

        print(f"{symbol} error: {e}")

    return None


# ---------------------------------------------------
# RUN SCANNER
# ---------------------------------------------------

if __name__ == "__main__":

    results = []

    for stock in WATCHLIST:

        result = scan_stock(stock)

        # ONLY GOOD SCORES
        if (

            result
            and result["score"] >= 7
            and result["change_pct"] > 0

        ):

            results.append(result)

    # -----------------------------------------
    # SORT BY SCORE
    # -----------------------------------------

    results = sorted(

        results,

        key=lambda x: x["score"],

        reverse=True

    )

    # -----------------------------------------
    # OUTPUT
    # -----------------------------------------

    print("\n🔥 TOP MOMENTUM STOCKS 🔥\n")

    if not results:

        print(
            "No strong momentum stocks found."
        )

    else:

        for r in results:

            print(

                f"{r['symbol']} | "

                f"₹{r['close']} | "

                f"RSI={r['rsi']} | "

                f"RVOL={r['rel_volume']} | "

                f"Move={r['change_pct']}% | "

                f"Trend={r['trend_strength']} | "

                f"Score={r['score']}"

            )