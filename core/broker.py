"""
core/broker.py
Thin wrapper around NorenRestApiPy for Shoonya (Finvasia).
Handles login, order placement, position management, and market data.
"""
import pyotp
import hashlib
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz

from config import settings
from utils.logger import get_logger

log = get_logger()
IST = pytz.timezone("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Try importing Shoonya SDK
# ---------------------------------------------------------------------------
try:
    from NorenRestApiPy.NorenApi import NorenApi
except ImportError:
    log.error("NorenRestApiPy not installed. Run: pip install NorenRestApiPy")
    raise


class ShoonyaBroker:
    """
    Wraps Shoonya API with paper-trade support and helper methods.
    All order methods return a unified dict:
      { success: bool, order_id: str|None, message: str }
    """

    BASE_URL = "https://api.shoonya.com/NorenWClientTP/"

    def __init__(self):
        self.api = NorenApi(
            host=self.BASE_URL,
            websocket="wss://api.shoonya.com/NorenWSTP/",
        )
        self.logged_in = False
        self._paper_orders: list[dict] = []
        self._paper_order_id = 1000

    # ── Auth ────────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        """Login with TOTP 2FA. Returns True on success."""
        totp = pyotp.TOTP(settings.SHOONYA_TOTP_SECRET).now()
        pwd_hash = hashlib.sha256(settings.SHOONYA_PASSWORD.encode()).hexdigest()

        log.info(f"Logging into Shoonya as {settings.SHOONYA_USER} ...")
        ret = self.api.login(
            userid=settings.SHOONYA_USER,
            password=pwd_hash,
            twoFA=totp,
            vendor_code=settings.SHOONYA_VENDOR_CODE,
            api_secret=settings.SHOONYA_API_SECRET,
            imei=settings.SHOONYA_IMEI,
        )

        if ret and ret.get("stat") == "Ok":
            self.logged_in = True
            log.info("✅ Login successful")
            return True
        else:
            log.error(f"❌ Login failed: {ret}")
            return False

    # ── Market Data ─────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str = None, exchange: str = None) -> dict | None:
        """Fetch live LTP quote for a symbol."""
        sym = symbol or settings.SYMBOL
        exch = exchange or settings.EXCHANGE
        ret = self.api.get_quotes(exchange=exch, token=self._get_token(sym, exch))
        if ret and ret.get("stat") == "Ok":
            return {
                "ltp": float(ret.get("lp", 0)),
                "open": float(ret.get("o", 0)),
                "high": float(ret.get("h", 0)),
                "low":  float(ret.get("l", 0)),
                "close": float(ret.get("c", 0)),
                "volume": int(ret.get("v", 0)),
            }
        log.warning(f"get_quote failed: {ret}")
        return None

    def get_candles(
        self,
        symbol: str = None,
        exchange: str = None,
        interval: int = None,
        lookback_days: int = 5,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV candles.
        Returns DataFrame with columns: [datetime, open, high, low, close, volume]
        """
        sym = symbol or settings.SYMBOL
        exch = exchange or settings.EXCHANGE
        ivl = interval or settings.CANDLE_INTERVAL
        token = self._get_token(sym, exch)

        end_dt = datetime.now(IST)
        start_dt = end_dt - timedelta(days=lookback_days)

        # Shoonya expects epoch timestamps
        start_epoch = int(start_dt.timestamp())
        end_epoch = int(end_dt.timestamp())

        ret = self.api.get_time_price_series(
            exchange=exch,
            token=token,
            starttime=start_epoch,
            endtime=end_epoch,
            interval=ivl,
        )

        if not ret or not isinstance(ret, list):
            log.warning(f"get_candles returned nothing for {sym}")
            return pd.DataFrame()

        rows = []
        for r in ret:
            try:
                rows.append({
                    "datetime": datetime.fromtimestamp(int(r["ssboe"]), tz=IST),
                    "open":   float(r["into"]),
                    "high":   float(r["inth"]),
                    "low":    float(r["intl"]),
                    "close":  float(r["intc"]),
                    "volume": int(r["intv"]),
                })
            except (KeyError, ValueError):
                continue

        df = pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)
        log.debug(f"Fetched {len(df)} candles for {sym}")
        return df

    def get_ltp(self, symbol: str = None, exchange: str = None) -> float | None:
        """Shortcut: return only Last Traded Price."""
        q = self.get_quote(symbol, exchange)
        return q["ltp"] if q else None

    # ── Order Management ────────────────────────────────────────────────────────

    def place_order(
        self,
        side: str,          # "BUY" or "SELL"
        qty: int,
        price: float = 0,   # 0 = market order
        order_type: str = "MKT",  # MKT | LMT | SL-MKT | SL-LMT
        symbol: str = None,
        exchange: str = None,
        tag: str = "",
    ) -> dict:
        sym = symbol or settings.SYMBOL
        exch = exchange or settings.EXCHANGE

        if settings.PAPER_TRADE:
            return self._paper_order(side, qty, price, order_type, sym, exch, tag)

        ret = self.api.place_order(
            buy_or_sell=side[0],           # "B" or "S"
            product_type="I",              # I=Intraday
            exchange=exch,
            tradingsymbol=sym,
            quantity=qty,
            discloseqty=0,
            price_type=order_type,
            price=price if order_type != "MKT" else 0,
            trigger_price=None,
            retention="DAY",
            remarks=tag,
        )

        if ret and ret.get("stat") == "Ok":
            oid = ret.get("norenordno", "N/A")
            log.info(f"✅ ORDER {side} {qty}x{sym} @ {price or 'MKT'} | ID:{oid} | {tag}")
            return {"success": True, "order_id": oid, "message": "Order placed"}
        else:
            log.error(f"❌ Order failed: {ret}")
            return {"success": False, "order_id": None, "message": str(ret)}

    def cancel_order(self, order_id: str) -> bool:
        if settings.PAPER_TRADE:
            log.info(f"[PAPER] Cancel order {order_id}")
            return True
        ret = self.api.cancel_order(orderno=order_id)
        return ret and ret.get("stat") == "Ok"

    def get_positions(self) -> list[dict]:
        """Return list of current intraday positions."""
        if settings.PAPER_TRADE:
            return self._paper_positions()
        ret = self.api.get_positions()
        if not ret:
            return []
        positions = []
        for p in ret:
            qty = int(p.get("netqty", 0))
            if qty == 0:
                continue
            positions.append({
                "symbol":    p.get("tsym", ""),
                "qty":       qty,
                "avg_price": float(p.get("netavgprc", 0)),
                "side":      "BUY" if qty > 0 else "SELL",
                "pnl":       float(p.get("urmtom", 0)),
            })
        return positions

    def get_order_book(self) -> list[dict]:
        if settings.PAPER_TRADE:
            return self._paper_orders.copy()
        ret = self.api.get_order_book()
        return ret if ret else []

    def square_off_all(self):
        """Close all open intraday positions."""
        positions = self.get_positions()
        if not positions:
            log.info("No open positions to square off.")
            return
        for pos in positions:
            side = "SELL" if pos["side"] == "BUY" else "BUY"
            log.info(f"Squaring off: {side} {abs(pos['qty'])} {pos['symbol']}")
            self.place_order(
                side=side,
                qty=abs(pos["qty"]),
                symbol=pos["symbol"],
                tag="SQUARE_OFF",
            )

    # ── Token Lookup ────────────────────────────────────────────────────────────

    def _get_token(self, symbol: str, exchange: str) -> str:
        """
        Look up instrument token for a symbol.
        Shoonya uses numeric tokens for API calls.
        """
        ret = self.api.searchscrip(exchange=exchange, searchtext=symbol.split("-")[0])
        if ret and ret.get("stat") == "Ok":
            values = ret.get("values", [])
            for v in values:
                if v.get("tsym") == symbol:
                    return v.get("token", "")
            if values:
                return values[0].get("token", "")
        log.warning(f"Token not found for {symbol}, using '0'")
        return "0"

    # ── Paper Trade Simulation ──────────────────────────────────────────────────

    def _paper_order(self, side, qty, price, order_type, symbol, exchange, tag):
        ltp = self.get_ltp(symbol, exchange) or price or 100.0
        fill_price = price if (price and order_type != "MKT") else ltp
        oid = str(self._paper_order_id)
        self._paper_order_id += 1
        order = {
            "order_id":   oid,
            "side":       side,
            "qty":        qty,
            "fill_price": fill_price,
            "symbol":     symbol,
            "tag":        tag,
            "time":       datetime.now(IST).isoformat(),
            "status":     "COMPLETE",
        }
        self._paper_orders.append(order)
        log.info(
            f"[PAPER] {side} {qty}x{symbol} @ ₹{fill_price:.2f} | ID:{oid} | {tag}"
        )
        return {"success": True, "order_id": oid, "message": "Paper order"}

    def _paper_positions(self) -> list[dict]:
        """Calculate net positions from paper order book."""
        net: dict[str, dict] = {}
        for o in self._paper_orders:
            sym = o["symbol"]
            qty = o["qty"] if o["side"] == "BUY" else -o["qty"]
            if sym not in net:
                net[sym] = {"qty": 0, "cost": 0.0}
            net[sym]["qty"] += qty
            net[sym]["cost"] += qty * o["fill_price"]

        result = []
        for sym, data in net.items():
            if data["qty"] == 0:
                continue
            avg = abs(data["cost"] / data["qty"]) if data["qty"] else 0
            result.append({
                "symbol":    sym,
                "qty":       data["qty"],
                "avg_price": avg,
                "side":      "BUY" if data["qty"] > 0 else "SELL",
                "pnl":       0.0,  # would need LTP to compute
            })
        return result
