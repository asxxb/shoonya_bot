"""
strategies/orb_vwap_strategy.py

ORB + VWAP + Volume Confirmation Strategy for Intraday Trading

Entry Logic:
- Long: 15min ORB high breaks + price above VWAP + volume spike + RSI > 55 + EMA20 > EMA50
- Short: 15min ORB low breaks + price below VWAP + volume spike + RSI < 45 + EMA20 < EMA50

Time Window: 9:20 AM - 11:30 AM only
Exit: 50% at 1:1 RR, trail remaining with VWAP/ATR
"""

import pandas as pd
import numpy as np

from datetime import datetime
import pytz

from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

from config import settings
from utils.logger import get_logger

log = get_logger()

IST = pytz.timezone("Asia/Kolkata")

SIGNAL_LONG = 1
SIGNAL_SHORT = -1
SIGNAL_NONE = 0


class OrbVwapStrategy:
    
    def __init__(self):
        self.orb_minutes = getattr(settings, 'ORB_MINUTES', 15)
        self.rsi_period = getattr(settings, 'RSI_PERIOD', 14)
        self.volume_mult = getattr(settings, 'VOLUME_MULTIPLIER', 1.5)
        self.atr_period = getattr(settings, 'ATR_PERIOD', 14)
        self.atr_sl_mult = getattr(settings, 'ATR_MULTIPLIER', 1.2)
        self.partial_exit_rr = 1.0
        
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all required indicators to the dataframe."""
        df = df.copy()
        
        df["datetime"] = pd.to_datetime(df["datetime"])
        
        df["ema20"] = EMAIndicator(close=df["close"], window=20).ema_indicator()
        df["ema50"] = EMAIndicator(close=df["close"], window=50).ema_indicator()
        
        df["rsi"] = RSIIndicator(close=df["close"], window=self.rsi_period).rsi()
        
        atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=self.atr_period)
        df["atr"] = atr.average_true_range()
        
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["date"] = df["datetime"].dt.date
        df["tpv"] = typical_price * df["volume"]
        df["vwap"] = df.groupby("date")["tpv"].cumsum() / df.groupby("date")["volume"].cumsum()
        
        df["vol_ma"] = df["volume"].rolling(20).mean()
        
        return df
    
    def get_opening_range(self, df: pd.DataFrame) -> tuple:
        """Get opening range high/low from first N candles."""
        orb_candles = df[df["datetime"] < df["datetime"].iloc[0] + pd.Timedelta(minutes=self.orb_minutes)]
        
        if len(orb_candles) < 3:
            return None, None
        
        orb_high = orb_candles["high"].max()
        orb_low = orb_candles["low"].min()
        
        return orb_high, orb_low
    
    def is_within_trading_hours(self, dt: datetime) -> bool:
        """Check if time is within 9:20 AM - 11:30 AM."""
        hour, minute = dt.hour, dt.minute
        
        start_hour = getattr(settings, 'TRADING_START_H', 9)
        start_min = getattr(settings, 'TRADING_START_M', 20)
        end_hour = getattr(settings, 'TRADING_END_H', 11)
        end_min = getattr(settings, 'TRADING_END_M', 30)
        
        start_time = start_hour * 60 + start_min
        end_time = end_hour * 60 + end_min
        current_time = hour * 60 + minute
        
        return start_time <= current_time <= end_time
    
    def is_no_trade_zone(self, price: float, vwap: float) -> bool:
        """Avoid trades when price is too close to VWAP (chop zone)."""
        if vwap is None or vwap == 0:
            return False
        pct_diff = abs(price - vwap) / vwap * 100
        return pct_diff < 0.1
    
    def get_signal(self, df: pd.DataFrame, nifty_vwap: float = None) -> tuple:
        """
        Generate trading signal based on ORB + VWAP + Volume + RSI + EMA.
        
        Args:
            df: Candle data
            nifty_vwap: Optional Nifty VWAP for market direction filter
            
        Returns:
            (signal, info_dict)
        """
        if df is None or len(df) < 60:
            return SIGNAL_NONE, {}
        
        df = self.compute_indicators(df)
        
        dt = df["datetime"].iloc[-1]
        
        if not self.is_within_trading_hours(dt):
            return SIGNAL_NONE, {"reason": "outside_trading_hours"}
        
        row = df.iloc[-2]
        prev_row = df.iloc[-3] if len(df) > 2 else row
        
        orb_high, orb_low = self.get_opening_range(df)
        
        if orb_high is None:
            return SIGNAL_NONE, {"reason": "no_orb_data"}
        
        vwap = row["vwap"]
        close = row["close"]
        volume = row["volume"]
        vol_ma = row["vol_ma"]
        
        if self.is_no_trade_zone(close, vwap):
            return SIGNAL_NONE, {"reason": "no_trade_zone"}
        
        volume_spike = volume > vol_ma * self.volume_mult
        
        atr_pct = row["atr"] / close
        
        signal = SIGNAL_NONE
        
        long_conditions = (
            close > orb_high and
            close > vwap and
            row["ema20"] > row["ema50"] and
            row["rsi"] > 55 and
            volume_spike and
            atr_pct > 0.001
        )
        
        short_conditions = (
            close < orb_low and
            close < vwap and
            row["ema20"] < row["ema50"] and
            row["rsi"] < 45 and
            volume_spike and
            atr_pct > 0.001
        )
        
        if nifty_vwap is not None:
            if long_conditions and close > nifty_vwap:
                signal = SIGNAL_LONG
            elif short_conditions and close < nifty_vwap:
                signal = SIGNAL_SHORT
        else:
            if long_conditions:
                signal = SIGNAL_LONG
            elif short_conditions:
                signal = SIGNAL_SHORT
        
        info = {
            "close": round(close, 2),
            "vwap": round(vwap, 2),
            "orb_high": round(orb_high, 2),
            "orb_low": round(orb_low, 2),
            "rsi": round(row["rsi"], 2),
            "atr": round(row["atr"], 2),
            "ema20": round(row["ema20"], 2),
            "ema50": round(row["ema50"], 2),
            "volume": int(volume),
            "vol_ma": int(vol_ma) if pd.notna(vol_ma) else 0,
            "volume_spike": volume_spike,
            "signal": signal,
            "orb_high_broken": close > orb_high,
            "orb_low_broken": close < orb_low,
            "above_vwap": close > vwap,
            "below_vwap": close < vwap,
        }
        
        log.debug(
            f"ORB VWAP Signal | close={close:.2f} | "
            f"orb_h={orb_high:.2f} orb_l={orb_low:.2f} | "
            f"vwap={vwap:.2f} | rsi={row['rsi']:.1f} | "
            f"vol_spike={volume_spike} | signal={signal}"
        )
        
        return signal, info
    
    def calculate_sl(self, side: str, entry: float, atr: float, df: pd.DataFrame) -> float:
        """Calculate dynamic stop loss."""
        atr_sl = entry - (atr * self.atr_sl_mult) if side == "BUY" else entry + (atr * self.atr_sl_mult)
        
        swing_low = df["low"].iloc[-10:-2].min() if side == "BUY" else df["high"].iloc[-10:-2].max()
        
        if side == "BUY":
            sl = max(atr_sl, swing_low) if swing_low else atr_sl
        else:
            sl = min(atr_sl, swing_low) if swing_low else atr_sl
        
        return round(sl, 2)
    
    def calculate_target(self, side: str, entry: float, sl: float) -> float:
        """Calculate 2:1 risk reward target."""
        risk = abs(entry - sl)
        target = entry + (risk * 2) if side == "BUY" else entry - (risk * 2)
        return round(target, 2)
    
    def description(self) -> str:
        return (
            f"ORB({self.orb_minutes}m) + VWAP + Volume | "
            f"RSI | EMA20/50 | Time: 9:20-11:30 | "
            f"SL: ATR×{self.atr_sl_mult}"
        )