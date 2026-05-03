"""
core/engine.py
Main trading engine — the brain of the bot.
Orchestrates: broker → strategy → risk → orders → tracking.
"""
import time
from datetime import datetime
import pytz
import schedule

from config import settings
from core.broker import ShoonyaBroker
from core.risk_manager import RiskManager
from core.trade_tracker import TradeTracker
from strategies.ema_rsi_scalper import EmaRsiScalper, SIGNAL_LONG, SIGNAL_SHORT, SIGNAL_NONE
from utils.logger import get_logger

log = get_logger(level=settings.LOG_LEVEL)
IST = pytz.timezone("Asia/Kolkata")


class TradingEngine:
    """
    Main loop:
      Every N minutes (= candle interval):
        1. Check if market is open + risk is OK
        2. Fetch candles → run strategy → get signal
        3. If signal and no open trade → size position → enter
        4. If open trade → check SL/TP → exit if triggered
        5. At SQUARE_OFF time → close everything
    """

    def __init__(self):
        self.broker  = ShoonyaBroker()
        self.risk    = RiskManager()
        self.tracker = TradeTracker()
        self.strategy = EmaRsiScalper()
        self.running = False

    # ── Startup ─────────────────────────────────────────────────────────────────

    def start(self):
        """Main entry point."""
        log.info(settings.summary())
        log.info(f"Strategy: {self.strategy.description()}")

        if not self.broker.login():
            log.error("Cannot start bot — login failed.")
            return

        mode = "PAPER TRADE 🟡" if settings.PAPER_TRADE else "⚠️  LIVE TRADE 🔴"
        log.info(f"\n{'='*40}\n  BOT STARTING — {mode}\n{'='*40}\n")

        self.running = True

        # Schedule candle checks
        interval = settings.CANDLE_INTERVAL
        schedule.every(interval).minutes.do(self._tick)

        # Schedule daily reset at 9:00 IST
        schedule.every().day.at("09:00").do(self._daily_reset)

        # Schedule square-off
        sq_time = f"{settings.SQUARE_OFF_H:02d}:{settings.SQUARE_OFF_M:02d}"
        schedule.every().day.at(sq_time).do(self._square_off_and_stop)

        log.info(f"Scheduler active. Checking every {interval} minute(s). Square-off at {sq_time} IST.")
        log.info("Press Ctrl+C to stop.\n")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            log.info("\nKeyboard interrupt — shutting down gracefully...")
            self._shutdown()

    # ── Core Tick ───────────────────────────────────────────────────────────────

    def _tick(self):
        """Called every candle interval."""
        now = datetime.now(IST)

        # ── Time gate ──────────────────────────────────────────────────────────
        if not self._is_trading_time(now):
            log.debug(f"Outside trading hours ({now.strftime('%H:%M')}) — skip")
            return

        log.info(f"── Tick {now.strftime('%H:%M:%S')} | {self.risk.summary()} ──")

        # ── Fetch market data ──────────────────────────────────────────────────
        ltp = self.broker.get_ltp()
        if ltp is None:
            log.warning("LTP fetch failed — skipping tick")
            return

        # ── Manage open trade ──────────────────────────────────────────────────
        if self.tracker.has_open_trade():
            self._manage_open_trade(ltp)
            return   # Don't look for new signals while in a trade

        # ── Look for new entry ─────────────────────────────────────────────────
        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            log.info(f"No trade allowed: {reason}")
            return

        df = self.broker.get_candles()
        if df.empty or len(df) < 30:
            log.warning(f"Not enough candle data ({len(df)} rows) — skip")
            return

        signal, info = self.strategy.get_signal(df)

        if signal == SIGNAL_LONG:
            self._enter_trade("BUY", info["close"], info["atr"])
        elif signal == SIGNAL_SHORT:
            self._enter_trade("SELL", info["close"], info["atr"])
        else:
            log.info(f"No signal | close={info.get('close','?')} rsi={info.get('rsi','?')}")

    # ── Trade Entry ─────────────────────────────────────────────────────────────

    def _enter_trade(self, side: str, price: float, atr: float):
        """Size and place an entry order."""
        if side == "BUY":
            qty, sl, tp = self.risk.calculate_qty(price, atr)
        else:
            qty, sl, tp = self.risk.calculate_short_qty(price, atr)

        if qty < 1:
            log.warning(f"Qty too small ({qty}) — skipping entry")
            return

        result = self.broker.place_order(
            side=side,
            qty=qty,
            order_type="MKT",
            tag=f"ENTRY_{side}",
        )

        if result["success"]:
            fill_price = price  # approximate; real fills differ slightly
            self.tracker.open_trade(
                side=side,
                symbol=settings.SYMBOL,
                qty=qty,
                entry_price=fill_price,
                stop_loss=sl,
                target=tp,
                order_id=result["order_id"],
            )
        else:
            log.error(f"Entry order failed: {result['message']}")

    # ── Trade Management ────────────────────────────────────────────────────────

    def _manage_open_trade(self, ltp: float):
        """Check SL/TP on open trade and exit if triggered."""
        trigger = self.tracker.check_sl_tp(ltp)
        log.info(f"Managing trade | LTP=₹{ltp:.2f} | {self.tracker.current_trade_info()}")

        if trigger in ("SL", "TP"):
            t = self.tracker.active_trade
            close_side = "SELL" if t["side"] == "BUY" else "BUY"

            result = self.broker.place_order(
                side=close_side,
                qty=t["qty"],
                order_type="MKT",
                tag=f"EXIT_{trigger}",
            )

            if result["success"]:
                pnl = self.tracker.close_trade(ltp, reason=trigger)
                self.risk.record_trade(pnl)
            else:
                log.error(f"Exit order failed: {result['message']}")

    # ── Square-off & Shutdown ───────────────────────────────────────────────────

    def _square_off_and_stop(self):
        log.info("⏰ Square-off time reached — closing all positions.")
        if self.tracker.has_open_trade():
            ltp = self.broker.get_ltp() or self.tracker.active_trade["entry_price"]
            pnl = self.tracker.close_trade(ltp, reason="SQUARE_OFF")
            self.risk.record_trade(pnl)
        self.broker.square_off_all()
        self.running = False
        log.info("✅ Square-off complete. Bot stopped for today.")

    def _shutdown(self):
        log.info("Shutting down — squaring off all positions...")
        self._square_off_and_stop()

    def _daily_reset(self):
        self.risk.reset_daily()

    # ── Time Checks ─────────────────────────────────────────────────────────────

    def _is_trading_time(self, now: datetime) -> bool:
        h, m = now.hour, now.minute
        start = (settings.TRADING_START_H, settings.TRADING_START_M)
        stop  = (settings.SQUARE_OFF_H,    settings.SQUARE_OFF_M)
        current = (h, m)
        return start <= current < stop
