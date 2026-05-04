
"""
core/broker.py
Thin wrapper around NorenRestApiPy for Shoonya (Finvasia).
Handles login, websocket, order placement,
position management, and market data.
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

    log.error(
        "NorenRestApiPy not installed. "
        "Run: pip install NorenRestApiPy"
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

    BASE_URL = "https://api.shoonya.com/NorenWClientTP/"

    # -----------------------------------------------------------------------
    # INIT
    # -----------------------------------------------------------------------

    def __init__(self):

        self.api = NorenApi(

            host=self.BASE_URL,

            websocket="wss://api.shoonya.com/NorenWSTP/",

        )

        self.logged_in = False

        self._paper_orders = []

        self._paper_order_id = 1000

        # Live ticks store
        self.live_ticks = {}

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

            pwd_hash = hashlib.sha256(

                settings.SHOONYA_PASSWORD.encode()

            ).hexdigest()

            log.info(

                f"Logging into Shoonya as "
                f"{settings.SHOONYA_USER} ..."

            )

            ret = self.api.login(

                userid=settings.SHOONYA_USER,

                password=pwd_hash,

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
                time.sleep(2)
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

                        log.info(
                            f"Subscribed: {symbol}"
                        )

                return True

            # ---------------------------------------------------------------
            # LOGIN FAILED
            # ---------------------------------------------------------------

            else:

                log.error(
                    f"❌ Login failed: {ret}"
                )

                return False

        except Exception as e:

            log.error(
                f"Login error: {e}"
            )

            return False

    # -----------------------------------------------------------------------
    # SOCKET OPEN CALLBACK
    # -----------------------------------------------------------------------

    def on_socket_open(self):

        log.info(
            "✅ Shoonya WebSocket connected"
        )

    # -----------------------------------------------------------------------
    # SOCKET CLOSE CALLBACK
    # -----------------------------------------------------------------------

    def on_socket_close(self):

        log.warning(
            "⚠️ Shoonya WebSocket disconnected"
        )

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

            # fallback to token
            symbol_key = symbol or token

            self.live_ticks[symbol_key] = {

                "ltp": float(ltp),

                "time": datetime.now(IST)

            }

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

            log.info(
                f"[PAPER] {side} {qty} {symbol}"
            )

            return {

                "success": True,

                "order_id": f"PAPER_{int(time.time())}",

                "message": "Paper trade executed"

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

    def _get_token(

        self,

        symbol: str,

        exchange: str

    ) -> str:

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

