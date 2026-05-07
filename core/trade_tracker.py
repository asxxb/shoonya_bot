"""
core/trade_tracker.py
Tracks open positions and writes a trade journal CSV.
"""
import csv
import os
from datetime import datetime
import pytz
import json
from utils.logger import get_logger
from utils.telegram import telegram

log = get_logger()
IST = pytz.timezone("Asia/Kolkata")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)


class TradeTracker:
    """
    Tracks the lifecycle of a single trade:
      ENTRY → monitor SL/TP → EXIT → log to CSV
    """

    ACTIVE_TRADE_FILE = os.path.join(DATA_DIR, "active_trade.json")

    def __init__(self):
        self.active_trade: dict | None = None
        self._journal_path = os.path.join(
            DATA_DIR, f"journal_{datetime.now(IST).strftime('%Y-%m-%d')}.csv"
        )
        self._ensure_journal_header()
        
        # Try to restore active trade from crash recovery
        self._restore_active_trade()

    # ── Crash Recovery ─────────────────────────────────────────────────────────

    def _save_active_trade(self):
        """Save active trade to disk for crash recovery."""
        if self.active_trade:
            try:
                with open(self.ACTIVE_TRADE_FILE, "w") as f:
                    json.dump(self.active_trade, f, indent=2)
                log.debug(f"Saved active trade: {self.active_trade.get('symbol')}")
            except Exception as e:
                log.error(f"Failed to save active trade: {e}")

    def _restore_active_trade(self):
        """Restore active trade from disk on startup."""
        if os.path.exists(self.ACTIVE_TRADE_FILE):
            try:
                with open(self.ACTIVE_TRADE_FILE, "r") as f:
                    self.active_trade = json.load(f)
                log.info(f"Restored active trade: {self.active_trade.get('symbol')}")
            except Exception as e:
                log.error(f"Failed to restore active trade: {e}")

    def _clear_active_trade(self):
        """Clear saved active trade."""
        try:
            if os.path.exists(self.ACTIVE_TRADE_FILE):
                os.remove(self.ACTIVE_TRADE_FILE)
        except Exception as e:
            log.error(f"Failed to clear active trade: {e}")

    # ── Trade Lifecycle ─────────────────────────────────────────────────────────

    def open_trade(
        self,
        side: str,           # "BUY" or "SELL"
        symbol: str,
        qty: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        order_id: str,
        atr: float = 0.0,
    ):
        from config import settings
        partial_exit_rr = getattr(settings, 'PARTIAL_EXIT_RR', 1.0)
        
        self.active_trade = {
            "side":        side,
            "symbol":      symbol,
            "qty":         qty,
            "original_qty": qty,
            "entry_price": entry_price,
            "stop_loss":   stop_loss,
            "target":      target,
            "order_id":    order_id,
            "atr":         atr,
            "sl_order_id": None,
            "tp_order_id": None,
            "trail_count": 0,
            "entry_time":  datetime.now(IST).isoformat(),
            "exit_price":  None,
            "exit_time":   None,
            "exit_reason": None,
            "pnl":         None,
            "partial_exited": False,
            "partial_exit_price": None,
            "partial_exit_qty": 0,
            "partial_rr": partial_exit_rr,
            "moved_to_breakeven": False,
        }
        
        # Save for crash recovery
        self._save_active_trade()
        
        log.info(
            f"📂 Trade OPENED | {side} {qty}×{symbol} @ ₹{entry_price:.2f} | "
            f"SL=₹{stop_loss:.2f} TP=₹{target:.2f}"
        )

        telegram.send(
            f"🚀 *TRADE OPENED*\n\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Qty: {qty}\n"
            f"Entry: ₹{entry_price:.2f}\n"
            f"SL: ₹{stop_loss:.2f}\n"
            f"TP: ₹{target:.2f}"
        )

    def close_trade(self, exit_price: float, reason: str) -> float:
        """Close active trade, log it, return PnL."""
        if not self.active_trade:
            return 0.0

        t = self.active_trade
        qty = t["qty"]

        if t["side"] == "BUY":
            pnl = (exit_price - t["entry_price"]) * qty
        else:
            pnl = (t["entry_price"] - exit_price) * qty

        t["exit_price"]  = exit_price
        t["exit_time"]   = datetime.now(IST).isoformat()
        t["exit_reason"] = reason
        t["pnl"]         = round(pnl, 2)

        # Clear crash recovery file
        self._clear_active_trade()

        emoji = "✅" if pnl >= 0 else "❌"
        log.info(
            f"{emoji} Trade CLOSED | {t['side']} {qty}×{t['symbol']} | "
            f"Entry=₹{t['entry_price']:.2f} Exit=₹{exit_price:.2f} | "
            f"PnL=₹{pnl:+.2f} | Reason={reason}"
        )

        telegram.send(
            f"📕 *TRADE CLOSED*\n\n"
            f"Symbol: {t['symbol']}\n"
            f"Side: {t['side']}\n"
            f"Exit: ₹{exit_price:.2f}\n"
            f"PnL: ₹{pnl:+.2f}\n"
            f"Reason: {reason}"
        )

        self._write_journal(t)
        self.active_trade = None
        return pnl

    def has_open_trade(self) -> bool:
        return self.active_trade is not None

    def calculate_trailing_sl(self, ltp: float, atr: float, vwap: float = None) -> float | None:
        """
        3-Phase Professional Trailing System with VWAP anchor:
        Phase 1: Risk protection (break-even)
        Phase 2: VWAP-based trailing (institutional support/resistance)
        Phase 3: Let winners run
        
        Args:
            ltp: Current market price
            atr: ATR value for volatility-based trailing
            vwap: Optional VWAP for stronger trailing anchor
        """
        from config import settings

        if not self.active_trade:
            return None

        t = self.active_trade
        side = t["side"]
        entry = t["entry_price"]
        current_sl = t["stop_loss"]

        if side == "BUY":
            profit_pct = ((ltp - entry) / entry) * 100
        else:
            profit_pct = ((entry - ltp) / entry) * 100

        # ── Phase 1: Move to breakeven ──
        if profit_pct >= settings.BREAKEVEN_PCT:
            if current_sl == entry:
                pass
            elif side == "BUY" and current_sl < entry:
                log.info(f"🟢 BE MOVE → {entry:.2f}")
                return entry
            elif side == "SELL" and current_sl > entry:
                log.info(f"🟢 BE MOVE → {entry:.2f}")
                return entry
        else:
            return None

        # ── Phase 2: Trailing with VWAP anchor ──
        if profit_pct >= settings.TRAIL_TIGHTEN_PCT:
            trail_mult = settings.TRAIL_FAST_MULT
        else:
            trail_mult = settings.TRAIL_SLOW_MULT

        trail_distance = atr * trail_mult
        min_move = atr * 0.3

        if side == "BUY":
            # ATR-based trailing
            atr_trailing = ltp - trail_distance
            
            # VWAP anchor (if available, use higher of ATR trail or VWAP)
            if vwap and vwap > atr_trailing:
                vwap_anchor = vwap
            else:
                vwap_anchor = None
            
            # Use the better of ATR trail or VWAP
            if vwap_anchor:
                new_sl = max(atr_trailing, vwap_anchor, entry)
            else:
                new_sl = max(atr_trailing, entry)
                
            if new_sl <= current_sl + min_move:
                return None
            t["trail_count"] = t.get("trail_count", 0) + 1
            log.info(
                f"🔄 TRAIL BUY → {current_sl:.2f} → {new_sl:.2f} | "
                f"PCT={profit_pct:.2f}% | VWAP={vwap_anchor if vwap_anchor else 'N/A'}"
            )
            return new_sl
        else:  # SELL
            atr_trailing = ltp + trail_distance
            
            if vwap and vwap < atr_trailing:
                vwap_anchor = vwap
            else:
                vwap_anchor = None
            
            if vwap_anchor:
                new_sl = min(atr_trailing, vwap_anchor, entry)
            else:
                new_sl = min(atr_trailing, entry)
                
            if new_sl >= current_sl - min_move:
                return None
            t["trail_count"] = t.get("trail_count", 0) + 1
            log.info(
                f"🔄 TRAIL SELL → {current_sl:.2f} → {new_sl:.2f} | "
                f"PCT={profit_pct:.2f}% | VWAP={vwap_anchor if vwap_anchor else 'N/A'}"
            )
            return new_sl

    def check_sl_tp(self, ltp: float) -> str | None:
        """
        Check if LTP has hit SL or TP.
        Returns 'SL', 'TP', or None.
        """
        if not self.active_trade:
            return None
        t = self.active_trade
        if t["side"] == "BUY":
            if ltp <= t["stop_loss"]:
                return "SL"
            if ltp >= t["target"]:
                return "TP"
        else:  # SELL/SHORT
            if ltp >= t["stop_loss"]:
                return "SL"
            if ltp <= t["target"]:
                return "TP"
        return None

    def should_partial_exit(self, ltp: float) -> bool:
        """
        Check if we should trigger partial exit at 1:1 RR.
        Returns True if partial exit should be executed.
        """
        if not self.active_trade:
            return False
        
        t = self.active_trade
        
        if t.get("partial_exited", False):
            return False
        
        side = t["side"]
        entry = t["entry_price"]
        rr_target = t.get("partial_rr", 1.0)
        
        if side == "BUY":
            risk = entry - t["stop_loss"]
            reward = ltp - entry
            rr = reward / risk if risk > 0 else 0
            return rr >= rr_target
        else:
            risk = t["stop_loss"] - entry
            reward = entry - ltp
            rr = reward / risk if risk > 0 else 0
            return rr >= rr_target

    def execute_partial_exit(self, exit_price: float) -> dict:
        """
        Execute partial exit (50% of position).
        Returns info about the partial exit.
        """
        if not self.active_trade:
            return {"success": False, "message": "No active trade"}
        
        t = self.active_trade
        original_qty = t["original_qty"]
        partial_qty = original_qty // 2
        remaining_qty = original_qty - partial_qty
        
        if t["side"] == "BUY":
            pnl = (exit_price - t["entry_price"]) * partial_qty
        else:
            pnl = (t["entry_price"] - exit_price) * partial_qty
        
        t["partial_exited"] = True
        t["partial_exit_price"] = exit_price
        t["partial_exit_qty"] = partial_qty
        t["qty"] = remaining_qty
        t["moved_to_breakeven"] = True
        t["stop_loss"] = t["entry_price"]
        
        self._save_active_trade()
        
        log.info(
            f"✂️ PARTIAL EXIT | {t['side']} {partial_qty}×{t['symbol']} @ ₹{exit_price:.2f} | "
            f"Locked ₹{pnl:.2f} | Remaining: {remaining_qty}"
        )
        
        telegram.send(
            f"✂️ *PARTIAL EXIT*\n\n"
            f"Symbol: {t['symbol']}\n"
            f"Exited: {partial_qty} @ ₹{exit_price:.2f}\n"
            f"Locked PnL: ₹{pnl:+.2f}\n"
            f"Remaining: {remaining_qty} @ BE"
        )
        
        return {
            "success": True,
            "partial_qty": partial_qty,
            "exit_price": exit_price,
            "pnl": pnl,
            "remaining_qty": remaining_qty
        }

    def current_trade_info(self) -> str:
        if not self.active_trade:
            return "No open trade"
        t = self.active_trade
        return (
            f"{t['side']} {t['qty']}×{t['symbol']} @ ₹{t['entry_price']:.2f} | "
            f"SL=₹{t['stop_loss']:.2f} TP=₹{t['target']:.2f}"
        )

    # ── CSV Journal ─────────────────────────────────────────────────────────────

    def _ensure_journal_header(self):
        if not os.path.exists(self._journal_path):
            with open(self._journal_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self._fields())
                writer.writeheader()

    def _write_journal(self, trade: dict):
        with open(self._journal_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._fields())
            writer.writerow({k: trade.get(k, "") for k in self._fields()})
        log.debug(f"Trade logged to {self._journal_path}")

    @staticmethod
    def _fields():
        return [
            "entry_time", "exit_time", "symbol", "side", "qty",
            "entry_price", "exit_price", "stop_loss", "target",
            "pnl", "exit_reason", "order_id",
        ]

    def journal_path(self) -> str:
        return self._journal_path
