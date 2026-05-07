
"""
core/broker.py
Thin wrapper around NorenRestApiPy for Shoonya (Finvasia).
Handles login, websocket, order placement,
position management, and market data.
"""

import pyotp
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

    class ShoonyaApiPy(NorenApi):
        def __init__(self):
            super().__init__(
                host='https://api.shoonya.com/NorenWClientAPI',
                websocket='wss://api.shoonya.com/NorenWSTP'
            )

except ImportError:

    log.error(
        "NorenRestApiPy not found. "
        "Install with: pip install NorenRestApiPy"
    )

    raise


class ShoonyaBroker:

    """
    Wraps Shoonya API with:

    - Paper trade support
    - WebSocket support
    - Order placement
    - Historical candles
    - Position management
    """

    BASE_URL = "https://api.shoonya.com/NorenWClientAPI/"

    # -----------------------------------------------------------------------
    # INIT
    # -----------------------------------------------------------------------

    def __init__(self):

        self.api = ShoonyaApiPy()

        self.api._NorenApi__service_config['host'] = "https://api.shoonya.com/NorenWClientAPI/"
        self.api._NorenApi__service_config['websocket_endpoint'] = "wss://api.shoonya.com/NorenWSTP/"

        self.logged_in = False

        self._paper_orders = []

        self._paper_order_id = 1000

        # Live ticks store
        self.live_ticks = {}

        # Heartbeat tracking
        self.last_tick_time = datetime.now(IST)

        # Reconnection lock
        self.reconnecting = False

        # WebSocket connection state
        self.websocket_connected = False

        # Token to symbol mapping
        self.token_symbol_map = {}

    # -----------------------------------------------------------------------
    # LOGIN
    # -----------------------------------------------------------------------

    def login(self) -> bool:

        """
        Login with TOTP 2FA.
        """

        try:

            totp = pyotp.TOTP(

                settings.SHOONYA_TOTP_SECRET

            ).now()

            log.info(

                f"Logging into Shoonya as "
                f"{settings.SHOONYA_USER} ..."

            )

            ret = self.api.login(

                userid=settings.SHOONYA_USER,

                password=settings.SHOONYA_PASSWORD,

                twoFA=totp,

                vendor_code=settings.SHOONYA_VENDOR_CODE,

                api_secret=settings.SHOONYA_API_SECRET,

                imei=settings.SHOONYA_IMEI,

            )

            # ---------------------------------------------------------------
            # LOGIN SUCCESS
            # ---------------------------------------------------------------

            if ret and ret.get("stat") == "Ok":

                self.logged_in = True

                log.info("✅ Login successful")

                # -----------------------------------------------------------
                # START WEBSOCKET
                # -----------------------------------------------------------

                self.api.start_websocket(

                    subscribe_callback=self.on_tick_update,

                    socket_open_callback=self.on_socket_open,

                    socket_close_callback=self.on_socket_close

                )

                log.info("✅ WebSocket started")
                time.sleep(3)

                if not self.websocket_connected:
                    log.error(
                        "WebSocket failed to connect"
                    )
                    return False

                # -----------------------------------------------------------
                # SUBSCRIBE WATCHLIST
                # -----------------------------------------------------------

                for symbol in settings.WATCHLIST:

                    token = self._get_token(

                        symbol,

                        settings.EXCHANGE
                    )

                    if token != "0":

                        self.api.subscribe(
                            f"{settings.EXCHANGE}|{token}"
                        )

                        self.token_symbol_map[token] = symbol

                        log.info(
                            f"Subscribed: {symbol}"
                        )

                return True

            # ---------------------------------------------------------------
            # LOGIN FAILED
            # ---------------------------------------------------------------

            else:

                emsg = ret.get("emsg", "Unknown error") if ret else "No response"

                if "User Not enabled" in emsg:
                    log.error(
                        f"❌ API Access not enabled. "
                        f"Enable in Shoonya portal: Profile → API Access"
                    )
                else:
                    log.error(
                        f"❌ Login failed: {emsg}"
                    )

                return False

        except Exception as e:

            log.error(
                f"Login error: {type(e).__name__}: {e}"
            )

            return False

    # -----------------------------------------------------------------------
    # SOCKET OPEN CALLBACK
    # -----------------------------------------------------------------------

    def on_socket_open(self):

        log.info(
            "✅ Shoonya WebSocket connected"
        )

        self.websocket_connected = True

    # -----------------------------------------------------------------------
    # SOCKET CLOSE CALLBACK
    # -----------------------------------------------------------------------

    def on_socket_close(self):

        log.warning(
            "⚠️ Shoonya WebSocket disconnected"
        )

        self.websocket_connected = False

        # Auto reconnect
        self.reconnect_websocket()

    # -----------------------------------------------------------------------
    # WEBSOCKET TICK HANDLER
    # -----------------------------------------------------------------------

    def on_tick_update(self, tick_data):

        """
        Handles incoming live ticks.
        """

        try:

            symbol = tick_data.get("ts")

            token = tick_data.get("tk")

            ltp = tick_data.get("lp")

            if not ltp:
                return

            # Resolve symbol from token mapping
            symbol_key = (
                symbol
                or
                self.token_symbol_map.get(token)
            )

            if not symbol_key:
                log.warning(
                    f"Could not resolve symbol for tick: {token}"
                )
                return

            self.live_ticks[symbol_key] = {

                "ltp": float(ltp),

                "time": datetime.now(IST)

            }

            # Update heartbeat
            self.last_tick_time = datetime.now(IST)

            log.debug(
                f"TICK: {symbol_key} -> {ltp}"
            )

        except Exception as e:

            log.error(
                f"Tick update error: {e}"
            )

    # -----------------------------------------------------------------------
    # GET LIVE TICK
    # -----------------------------------------------------------------------

    def get_live_tick(self, symbol):

        tick = self.live_ticks.get(symbol)

        if not tick:
            return None

        return tick.get("ltp")

    # -----------------------------------------------------------------------
    # HEARTBEAT CHECK
    # -----------------------------------------------------------------------

    def websocket_alive(self):

        diff = (
            datetime.now(IST)
            -
            self.last_tick_time
        ).seconds

        return diff < 30

    # -----------------------------------------------------------------------
    # RECONNECT WEBSOCKET
    # -----------------------------------------------------------------------

    def reconnect_websocket(self):

        from utils.telegram import telegram

        # Check if already reconnecting
        if self.reconnecting:
            log.warning(
                "Reconnection already in progress"
            )
            return False

        self.reconnecting = True

        log.warning(
            "Attempting WebSocket reconnection..."
        )

        telegram.send(
            "🔄 Reconnecting WebSocket..."
        )

        # Retry loop - 5 attempts
        for attempt in range(1, 6):

            try:

                log.info(
                    f"Reconnect attempt {attempt}/5"
                )

                # Prevent recursive reconnect
                self.websocket_connected = False

                # Stop existing websocket safely
                try:
                    if hasattr(self.api, "close_websocket"):
                        self.api.close_websocket()
                except Exception as e:
                    log.warning(
                        f"close_websocket failed: {e}"
                    )

                time.sleep(2)

                # Restart websocket
                self.api.start_websocket(
                    subscribe_callback=self.on_tick_update,
                    socket_open_callback=self.on_socket_open,
                    socket_close_callback=self.on_socket_close
                )

                # Wait for connection
                time.sleep(3)

                # Verify connection
                if not self.websocket_connected:
                    raise Exception(
                        "WebSocket did not reconnect"
                    )

                # Resubscribe to watchlist
                for symbol in settings.WATCHLIST:

                    token = self._get_token(
                        symbol,
                        settings.EXCHANGE
                    )

                    if token != "0":
                        self.api.subscribe(
                            f"{settings.EXCHANGE}|{token}"
                        )
                        self.token_symbol_map[token] = symbol
                        log.info(
                            f"Resubscribed: {symbol}"
                        )

                # Reset heartbeat
                self.last_tick_time = datetime.now(IST)

                log.info(
                    "✅ WebSocket reconnected successfully"
                )

                telegram.send(
                    "✅ WebSocket Reconnected"
                )

                self.reconnecting = False
                return True

            except Exception as e:

                log.error(
                    f"Reconnect attempt {attempt} failed: {e}"
                )

                if attempt < 5:
                    time.sleep(5)

        # All attempts failed
        log.error(
            "WebSocket reconnection failed after 5 attempts"
        )

        telegram.send(
            "❌ WebSocket reconnect failed"
        )

        self.reconnecting = False
        return False

    # -----------------------------------------------------------------------
    # GET QUOTE
    # -----------------------------------------------------------------------

    def get_quote(

        self,

        symbol: str = None,

        exchange: str = None

    ) -> dict | None:

        sym = symbol or settings.SYMBOL

        exch = exchange or settings.EXCHANGE

        ret = self.api.get_quotes(

            exchange=exch,

            token=self._get_token(sym, exch)

        )

        if ret and ret.get("stat") == "Ok":

            return {

                "ltp": float(ret.get("lp", 0)),

                "open": float(ret.get("o", 0)),

                "high": float(ret.get("h", 0)),

                "low": float(ret.get("l", 0)),

                "close": float(ret.get("c", 0)),

                "volume": int(ret.get("v", 0)),

            }

        log.warning(
            f"get_quote failed: {ret}"
        )

        return None

    # -----------------------------------------------------------------------
    # GET LTP
    # -----------------------------------------------------------------------

    def get_ltp(

        self,

        symbol: str = None,

        exchange: str = None

    ) -> float | None:

        # Try websocket first
        tick_ltp = self.get_live_tick(symbol)

        if tick_ltp:
            return tick_ltp

        # Fallback to REST API
        q = self.get_quote(symbol, exchange)

        return q["ltp"] if q else None

    # -----------------------------------------------------------------------
    # GET NIFTY VWAP FOR MARKET DIRECTION FILTER
    # -----------------------------------------------------------------------

    def get_nifty_vwap(self) -> float | None:
        """
        Get Nifty 50 VWAP for market direction filtering.
        Returns None if unavailable.
        """
        try:
            df = self.get_candles(
                symbol="NIFTY 50-EQ",
                lookback_days=1
            )
            
            if df.empty or "close" not in df.columns:
                return None
            
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            tpv = typical_price * df["volume"]
            
            vwap = tpv.cumsum() / df["volume"].cumsum()
            
            if len(vwap) > 0:
                return round(vwap.iloc[-1], 2)
            
            return None
            
        except Exception as e:
            log.warning(f"Failed to get Nifty VWAP: {e}")
            return None

    # -----------------------------------------------------------------------
    # GET NIFTY LTP
    # -----------------------------------------------------------------------

    def get_nifty_ltp(self) -> float | None:
        """Get Nifty 50 current price."""
        return self.get_ltp("NIFTY 50-EQ")

    # -----------------------------------------------------------------------
    # GET INDIA VIX
    # -----------------------------------------------------------------------

    def get_india_vix(self) -> float | None:
        """
        Get India VIX value for adaptive position sizing.
        Returns None if unavailable.
        """
        try:
            df = self.get_candles(
                symbol="INDIA VIX-EQ",
                lookback_days=1
            )
            
            if df.empty or "close" not in df.columns:
                return None
            
            # Return latest close as VIX value
            vix = df["close"].iloc[-1]
            return round(float(vix), 2)
            
        except Exception as e:
            log.debug(f"Failed to get India VIX: {e}")
            return None

    # -----------------------------------------------------------------------
    # GET HISTORICAL CANDLES
    # -----------------------------------------------------------------------

    def get_candles(

        self,

        symbol: str = None,

        exchange: str = None,

        interval: int = None,

        lookback_days: int = 5,

    ) -> pd.DataFrame:

        sym = symbol or settings.SYMBOL

        exch = exchange or settings.EXCHANGE

        ivl = interval or settings.CANDLE_INTERVAL

        token = self._get_token(sym, exch)

        end_dt = datetime.now(IST)

        start_dt = end_dt - timedelta(days=lookback_days)

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

            log.warning(
                f"get_candles returned nothing for {sym}"
            )

            return pd.DataFrame()

        rows = []

        for r in ret:

            try:

                rows.append({

                    "datetime": datetime.fromtimestamp(
                        int(r["ssboe"]),
                        tz=IST
                    ),

                    "open": float(r["into"]),

                    "high": float(r["inth"]),

                    "low": float(r["intl"]),

                    "close": float(r["intc"]),

                    "volume": int(r["intv"]),

                })

            except Exception:

                continue

        df = pd.DataFrame(rows)

        df = df.sort_values("datetime")

        df = df.reset_index(drop=True)

        log.debug(
            f"Fetched {len(df)} candles for {sym}"
        )

        return df

    # -----------------------------------------------------------------------
    # PLACE ORDER
    # -----------------------------------------------------------------------

    def place_order(

        self,

        symbol,

        side,

        qty,

        order_type="MKT",

        tag=""

    ):

        # ---------------------------------------------------------------
        # PAPER TRADE
        # ---------------------------------------------------------------

        if settings.PAPER_TRADE:

            paper_order_id = f"PAPER_{int(time.time())}"

            # Get current price for paper fill
            fill_price = self.get_ltp(symbol) or 0.0

            log.info(
                f"[PAPER] {side} {qty} {symbol} @ ₹{fill_price}"
            )

            self._paper_orders.append({
                "order_id": paper_order_id,
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "fill_price": fill_price,
                "tag": tag,
                "time": datetime.now(IST).isoformat(),
            })

            return {

                "success": True,

                "order_id": paper_order_id,

                "message": "Paper trade executed",

                "fill_price": fill_price
            }

        # ---------------------------------------------------------------
        # LIVE TRADE
        # ---------------------------------------------------------------

        try:

            order = self.api.place_order(

                buy_or_sell=side[0],

                product_type="I",

                exchange=settings.EXCHANGE,

                tradingsymbol=symbol,

                quantity=qty,

                discloseqty=0,

                price_type=order_type,

                retention="DAY",

                remarks=tag

            )

            if order and order.get("stat") == "Ok":

                log.info(
                    f"✅ LIVE ORDER: "
                    f"{side} {qty} {symbol}"
                )

                return {

                    "success": True,

                    "order_id": order.get("norenordno"),

                    "message": "Live order placed"

                }

            return {

                "success": False,

                "message": str(order)

            }

        except Exception as e:

            return {

                "success": False,

                "message": str(e)

            }

    # -----------------------------------------------------------------------
    # PLACE STOP LOSS ORDER
    # -----------------------------------------------------------------------

    def place_sl_order(

        self,

        symbol,

        side,

        qty,

        trigger_price,

        tag="SL_ORDER"

    ):

        # ---------------------------------------------------------------
        # PAPER MODE
        # ---------------------------------------------------------------

        if settings.PAPER_TRADE:

            return {

                "success": True,

                "order_id": f"PAPER_SL_{int(time.time())}",

                "message": "Paper SL order"

            }

        # ---------------------------------------------------------------
        # LIVE MODE
        # ---------------------------------------------------------------

        try:

            order = self.api.place_order(

                buy_or_sell=side[0],

                product_type="I",

                exchange=settings.EXCHANGE,

                tradingsymbol=symbol,

                quantity=qty,

                discloseqty=0,

                price_type="SL-M",

                trigger_price=trigger_price,

                retention="DAY",

                remarks=tag

            )

            if order and order.get("stat") == "Ok":

                log.info(
                    f"✅ SL ORDER PLACED: {symbol} @ {trigger_price}"
                )

                return {

                    "success": True,

                    "order_id": order.get("norenordno"),

                    "message": "SL order placed"

                }

            return {

                "success": False,

                "message": str(order)

            }

        except Exception as e:

            return {

                "success": False,

                "message": str(e)

            }

    # -----------------------------------------------------------------------
    # CANCEL ORDER
    # -----------------------------------------------------------------------

    def cancel_order(self, order_id: str) -> bool:

        if settings.PAPER_TRADE:

            log.info(
                f"[PAPER] Cancel order {order_id}"
            )

            return True

        ret = self.api.cancel_order(

            orderno=order_id

        )

        return ret and ret.get("stat") == "Ok"

    # -----------------------------------------------------------------------
    # GET ORDER STATUS
    # -----------------------------------------------------------------------

    def get_order_status(self, order_id):

        try:

            ret = self.api.single_order_history(
                orderno=order_id
            )

            if ret:

                return ret[0].get("status")

        except Exception as e:

            log.error(
                f"Order status error: {e}"
            )

        return None

    # -----------------------------------------------------------------------
    # GET ORDER FILL PRICE
    # -----------------------------------------------------------------------

    def get_order_fill_price(self, order_id):

        try:

            ret = self.api.single_order_history(
                orderno=order_id
            )

            if ret:

                avg_price = ret[0].get("avgprc")

                if avg_price:

                    return float(avg_price)

        except Exception as e:

            log.error(
                f"Fill price error: {e}"
            )

        return None

    # -----------------------------------------------------------------------
    # POSITIONS
    # -----------------------------------------------------------------------

    def get_positions(self) -> list[dict]:

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

                "symbol": p.get("tsym", ""),

                "qty": qty,

                "avg_price": float(
                    p.get("netavgprc", 0)
                ),

                "side": (
                    "BUY"
                    if qty > 0
                    else "SELL"
                ),

                "pnl": float(
                    p.get("urmtom", 0)
                ),

            })

        return positions

    # -----------------------------------------------------------------------
    # ORDER BOOK
    # -----------------------------------------------------------------------

    def get_order_book(self) -> list[dict]:

        if settings.PAPER_TRADE:

            return self._paper_orders.copy()

        ret = self.api.get_order_book()

        return ret if ret else []

    # -----------------------------------------------------------------------
    # SQUARE OFF
    # -----------------------------------------------------------------------

    def square_off_all(self):

        positions = self.get_positions()

        if not positions:

            log.info(
                "No open positions to square off."
            )

            return

        for pos in positions:

            side = (

                "SELL"

                if pos["side"] == "BUY"

                else "BUY"

            )

            self.place_order(

                side=side,

                qty=abs(pos["qty"]),

                symbol=pos["symbol"],

                tag="SQUARE_OFF",

            )

# -----------------------------------------------------------------------
    # TOKEN LOOKUP
    # -----------------------------------------------------------------------

    TOKEN_FALLBACK = {
        # High liquidity stocks
        ("RELIANCE-EQ", "NSE"): "2885",
        ("HDFCBANK-EQ", "NSE"): "4963",
        ("ICICIBANK-EQ", "NSE"): "3087",
        ("SBIN-EQ", "NSE"): "3045",
        ("TCS-EQ", "NSE"): "11536",
        ("INFY-EQ", "NSE"): "1594",
        ("AXISBANK-EQ", "NSE"): "3110",
        ("KOTAKBANK-EQ", "NSE"): "3472",
        ("LT-EQ", "NSE"): "2993",
        ("BAJFINANCE-EQ", "NSE"): "8113",
        # Indices
        ("NIFTY 50-EQ", "NSE"): "26009",
        ("NIFTY BANK-EQ", "NSE"): "26017",
    }

    def _get_token(

        self,

        symbol: str,

        exchange: str

    ) -> str:

        # Try fallback first
        fallback_key = (symbol, exchange)
        if fallback_key in self.TOKEN_FALLBACK:
            return self.TOKEN_FALLBACK[fallback_key]

        ret = self.api.searchscrip(

            exchange=exchange,

            searchtext=symbol.split("-")[0]

        )

        if ret and ret.get("stat") == "Ok":

            values = ret.get("values", [])

            for v in values:

                if v.get("tsym") == symbol:

                    return v.get("token", "")

            if values:

                return values[0].get("token", "")

        log.warning(

            f"Token not found for {symbol}"

        )

        return "0"

    # -----------------------------------------------------------------------
    # PAPER POSITIONS
    # -----------------------------------------------------------------------

    def _paper_positions(self):

        net = {}

        for o in self._paper_orders:

            sym = o["symbol"]

            qty = (

                o["qty"]

                if o["side"] == "BUY"

                else -o["qty"]

            )

            if sym not in net:

                net[sym] = {

                    "qty": 0,

                    "cost": 0.0

                }

            net[sym]["qty"] += qty

            net[sym]["cost"] += (

                qty * o["fill_price"]

            )

        result = []

        for sym, data in net.items():

            if data["qty"] == 0:
                continue

            avg = abs(

                data["cost"] / data["qty"]

            )

            result.append({

                "symbol": sym,

                "qty": data["qty"],

                "avg_price": avg,

                "side": (
                    "BUY"
                    if data["qty"] > 0
                    else "SELL"
                ),

                "pnl": 0.0,

            })

        return result

