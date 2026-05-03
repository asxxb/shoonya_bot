"""
strategies/ema_rsi_scalper.py

Strategy: EMA Crossover + RSI Filter + ATR Stop Loss

Logic:
  LONG  → Fast EMA crosses ABOVE Slow EMA + RSI > 50 + RSI < overbought
  SHORT → Fast EMA crosses BELOW Slow EMA + RSI < 50 + RSI > oversold
  SL    → ATR-based (configurable multiplier)
  TP    → 2:1 Risk:Reward
"""
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

from config import settings
from utils.logger import get_logger

log = get_logger()

# Signal constants
SIGNAL_LONG  =  1
SIGNAL_SHORT = -1
SIGNAL_NONE  =  0


class EmaRsiScalper:

    def __init__(self):
        self.ema_fast = settings.EMA_FAST
        self.ema_slow = settings.EMA_SLOW
        self.rsi_period = settings.RSI_PERIOD
        self.rsi_ob = settings.RSI_OVERBOUGHT
        self.rsi_os = settings.RSI_OVERSOLD
        self.atr_period = settings.ATR_PERIOD

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add indicator columns to the candle DataFrame.
        Requires columns: open, high, low, close, volume
        Returns enriched DataFrame (may have NaN rows at start).
        """
        if len(df) < self.ema_slow + 5:
            log.warning(f"Not enough candles ({len(df)}) to compute indicators.")
            return df

        df = df.copy()

        # EMAs
        df["ema_fast"] = EMAIndicator(df["close"], window=self.ema_fast).ema_indicator()
        df["ema_slow"] = EMAIndicator(df["close"], window=self.ema_slow).ema_indicator()

        # RSI
        df["rsi"] = RSIIndicator(df["close"], window=self.rsi_period).rsi()

        # ATR
        atr_ind = AverageTrueRange(df["high"], df["low"], df["close"], window=self.atr_period)
        df["atr"] = atr_ind.average_true_range()

        # EMA cross direction (+1 fast>slow, -1 fast<slow)
        df["ema_cross"] = np.where(df["ema_fast"] > df["ema_slow"], 1, -1)

        # Crossover detection (change in ema_cross)
        df["crossover"] = df["ema_cross"].diff().fillna(0)
        # +2 = bullish cross, -2 = bearish cross

        return df

    def get_signal(self, df: pd.DataFrame) -> tuple[int, dict]:
        """
        Analyse the latest complete candle and return a trade signal.

        Returns:
            signal : SIGNAL_LONG | SIGNAL_SHORT | SIGNAL_NONE
            info   : dict with indicator values for logging
        """
        df = self.compute_indicators(df)

        if df.empty or df.iloc[-1].isnull().any():
            return SIGNAL_NONE, {}

        # Use last COMPLETE candle (index -2 is safer than -1 which may be forming)
        row = df.iloc[-2]

        info = {
            "close":    round(row["close"], 2),
            "ema_fast": round(row["ema_fast"], 2),
            "ema_slow": round(row["ema_slow"], 2),
            "rsi":      round(row["rsi"], 1),
            "atr":      round(row["atr"], 2),
            "crossover": row["crossover"],
        }

        signal = SIGNAL_NONE

        # ── LONG signal ────────────────────────────────────────────────────────
        if (
            row["crossover"] >= 2               # fresh bullish EMA cross
            and row["rsi"] > 50                 # momentum confirms up
            and row["rsi"] < self.rsi_ob        # not overbought
        ):
            signal = SIGNAL_LONG

        # ── SHORT signal ───────────────────────────────────────────────────────
        elif (
            row["crossover"] <= -2              # fresh bearish EMA cross
            and row["rsi"] < 50                 # momentum confirms down
            and row["rsi"] > self.rsi_os        # not oversold
        ):
            signal = SIGNAL_SHORT

        label = {1: "LONG 📈", -1: "SHORT 📉", 0: "HOLD ⏸"}.get(signal, "HOLD")
        log.debug(
            f"Signal: {label} | close={info['close']} "
            f"ema9={info['ema_fast']} ema21={info['ema_slow']} "
            f"rsi={info['rsi']} atr={info['atr']}"
        )

        return signal, info

    def description(self) -> str:
        return (
            f"EMA({self.ema_fast}/{self.ema_slow}) + RSI({self.rsi_period}) Scalper | "
            f"OB={self.rsi_ob} OS={self.rsi_os} | ATR-SL×{settings.ATR_MULTIPLIER}"
        )
