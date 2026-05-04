"""
config/settings.py
Loads and validates all environment variables.
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

RUNTIME_CONFIG = "data/runtime_config.json"

paper_trade_runtime = True

if os.path.exists(RUNTIME_CONFIG):

    try:

        with open(RUNTIME_CONFIG, "r") as f:

            runtime_data = json.load(f)

            paper_trade_runtime = runtime_data.get(
                "paper_trade",
                True
            )

    except Exception:

        pass

def _get(key, default=None, required=False, cast=str):
    val = os.getenv(key, default)
    if required and val is None:
        raise EnvironmentError(f"Required env var '{key}' is not set. Check your .env file.")
    if val is not None:
        try:
            return cast(val)
        except Exception:
            raise ValueError(f"Env var '{key}' has invalid value: {val}")
    return val

# ── Credentials ────────────────────────────────────────────────────────────────
SHOONYA_USER        = _get("SHOONYA_USER",        required=True)
SHOONYA_PASSWORD    = _get("SHOONYA_PASSWORD",    required=True)
SHOONYA_TOTP_SECRET = _get("SHOONYA_TOTP_SECRET", required=True)
SHOONYA_VENDOR_CODE = _get("SHOONYA_VENDOR_CODE", required=True)
SHOONYA_API_SECRET  = _get("SHOONYA_API_SECRET",  required=True)
SHOONYA_IMEI        = _get("SHOONYA_IMEI",        default="abc1234")

# ── Trading Parameters ─────────────────────────────────────────────────────────
CAPITAL             = _get("CAPITAL",             default="1000",  cast=float)
RISK_PER_TRADE_PCT  = _get("RISK_PER_TRADE_PCT",  default="1.0",   cast=float)
MAX_TRADES_PER_DAY  = _get("MAX_TRADES_PER_DAY",  default="5",     cast=int)
MAX_LOSS_PER_DAY_PCT= _get("MAX_LOSS_PER_DAY_PCT",default="2.0",   cast=float)

SYMBOL              = _get("SYMBOL",              default="SBIN-EQ")
EXCHANGE            = _get("EXCHANGE",            default="NSE")

# ── Strategy Settings ──────────────────────────────────────────────────────────
EMA_FAST            = _get("EMA_FAST",            default="9",     cast=int)
EMA_SLOW            = _get("EMA_SLOW",            default="21",    cast=int)
EMA_SIGNAL          = _get("EMA_SIGNAL",          default="9",     cast=int)
RSI_PERIOD          = _get("RSI_PERIOD",          default="14",    cast=int)
RSI_OVERBOUGHT      = _get("RSI_OVERBOUGHT",      default="70",    cast=float)
RSI_OVERSOLD        = _get("RSI_OVERSOLD",        default="30",    cast=float)
ATR_PERIOD          = _get("ATR_PERIOD",          default="14",    cast=int)
ATR_MULTIPLIER      = _get("ATR_MULTIPLIER",      default="1.5",   cast=float)
TRAIL_ATR_MULT      = _get("TRAIL_ATR_MULT",     default="1.0",   cast=float)  # ATR distance for trailing SL
TRAIL_ACTIVATE_PCT = _get("TRAIL_ACTIVATE_PCT",default="0.3",   cast=float)  # Profit % to activate trailing
CANDLE_INTERVAL     = _get("CANDLE_INTERVAL",     default="5",     cast=int)

# ── Mode ───────────────────────────────────────────────────────────────────────
# PAPER_TRADE         = _get("PAPER_TRADE",         default="true").lower() == "true"
PAPER_TRADE = paper_trade_runtime
LOG_LEVEL           = _get("LOG_LEVEL",           default="INFO")

# ── Derived ────────────────────────────────────────────────────────────────────
RISK_AMOUNT         = CAPITAL * RISK_PER_TRADE_PCT / 100
MAX_DAILY_LOSS      = CAPITAL * MAX_LOSS_PER_DAY_PCT / 100

# ── Market Timing (IST) ────────────────────────────────────────────────────────
MARKET_OPEN_H, MARKET_OPEN_M     = 9, 15
MARKET_CLOSE_H, MARKET_CLOSE_M   = 15, 30
TRADING_START_H, TRADING_START_M = 9, 20   # Wait a few mins after open
SQUARE_OFF_H, SQUARE_OFF_M       = 15, 15  # Square off before close

def summary():
    mode = "🟡 PAPER TRADE" if PAPER_TRADE else "🔴 LIVE TRADE"
    return (
        f"\n{'='*50}\n"
        f"  Mode     : {mode}\n"
        f"  Symbol   : {SYMBOL} ({EXCHANGE})\n"
        f"  Capital  : ₹{CAPITAL:,.0f}\n"
        f"  Risk/Trade: ₹{RISK_AMOUNT:.1f} ({RISK_PER_TRADE_PCT}%)\n"
        f"  Max Loss : ₹{MAX_DAILY_LOSS:.1f}/day\n"
        f"  Max Trades: {MAX_TRADES_PER_DAY}/day\n"
        f"  Interval : {CANDLE_INTERVAL}m candles\n"
        f"  Trail ATR: {TRAIL_ATR_MULT}\n"
        f"  Trail %  : {TRAIL_ACTIVATE_PCT}%\n"
        f"{'='*50}\n"
    )


TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


WATCHLIST = [

    "SBIN-EQ",
    "NHPC-EQ",
    "SUZLON-EQ",
    "YESBANK-EQ",
    "IDFCFIRSTB-EQ",
    "UCOBANK-EQ",
    "IREDA-EQ",
    "RVNL-EQ",
    "NBCC-EQ",
    "IRFC-EQ",
    "PNB-EQ",
    "BANKBARODA-EQ",
    "SAIL-EQ",
    "JIOFIN-EQ"

]

FINNHUB_API_KEY = os.getenv(
    "FINNHUB_API_KEY"
)

# ---------------------------------------------------
# Runtime Mode Helpers
# ---------------------------------------------------

def set_paper_trade_mode(enabled: bool):

    global PAPER_TRADE

    PAPER_TRADE = enabled

    data = {
        "paper_trade": enabled
    }

    with open(RUNTIME_CONFIG, "w") as f:
        json.dump(data, f, indent=2)


def get_trade_mode():

    return PAPER_TRADE