import os
import glob
from datetime import datetime
from collections import defaultdict


def get_latest_journal():
    journal_files = glob.glob("data/journal_*.csv")
    if not journal_files:
        return None
    return max(journal_files, key=os.path.getmtime)


def load_journal(path: str) -> list[dict]:
    trades = []
    with open(path, "r") as f:
        header = f.readline().strip().split(",")
        for line in f:
            if not line.strip():
                continue
            values = line.strip().split(",")
            trade = dict(zip(header, values))
            trade["pnl"] = float(trade.get("pnl", 0) or 0)
            trade["qty"] = int(trade.get("qty", 0) or 0)
            trade["entry_price"] = float(trade.get("entry_price", 0) or 0)
            trade["exit_price"] = float(trade.get("exit_price", 0) or 0)
            trade["stop_loss"] = float(trade.get("stop_loss", 0) or 0)
            trades.append(trade)
    return trades


def calculate_stats(trades: list[dict]) -> dict:
    if not trades:
        return {"error": "No trades found"}

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    total_trades = len(trades)

    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    avg_win = sum(t["pnl"] for t in wins) / win_count if win_count > 0 else 0
    avg_loss = sum(t["pnl"] for t in losses) / loss_count if loss_count > 0 else 0
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    biggest_win = max((t["pnl"] for t in trades), default=0)
    biggest_loss = min((t["pnl"] for t in trades), default=0)

    consecutive_wins = 0
    consecutive_losses = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    for t in trades:
        if t["pnl"] > 0:
            consecutive_wins += 1
            consecutive_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
        else:
            consecutive_losses += 1
            consecutive_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)

    exit_reasons = defaultdict(int)
    for t in trades:
        exit_reasons[t.get("exit_reason", "UNKNOWN")] += 1

    symbols = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0})
    for t in trades:
        sym = t.get("symbol", "UNKNOWN")
        symbols[sym]["pnl"] += t["pnl"]
        if t["pnl"] > 0:
            symbols[sym]["wins"] += 1
        else:
            symbols[sym]["losses"] += 1

    return {
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(avg_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "rr_ratio": round(rr_ratio, 2),
        "biggest_win": round(biggest_win, 2),
        "biggest_loss": round(biggest_loss, 2),
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
        "exit_reasons": dict(exit_reasons),
        "symbols": dict(symbols),
    }


def print_report(trades: list[dict], stats: dict):
    if "error" in stats:
        print(f"\n  ⚠️ {stats['error']}")
        print("=" * 50)
        return

    print("\n" + "=" * 50)
    print("  📊 TRADING PERFORMANCE REPORT")
    print("=" * 50)

    print(f"\n  Trades: {stats['total_trades']} | Wins: {stats['win_count']} | Losses: {stats['loss_count']}")
    print(f"  Win Rate: {stats['win_rate']}%")

    print(f"\n  💰 Total P&L: ₹{stats['total_pnl']:,.2f}")
    print(f"  📈 Avg P&L/Trade: ₹{stats['avg_pnl']:,.2f}")

    print(f"\n  Avg Win: ₹{stats['avg_win']:,.2f} | Avg Loss: ₹{stats['avg_loss']:,.2f}")
    print(f"  R:R Ratio: {stats['rr_ratio']}:1")

    print(f"\n  🏆 Biggest Win: ₹{stats['biggest_win']:,.2f}")
    print(f"  💔 Biggest Loss: ₹{stats['biggest_loss']:,.2f}")

    print(f"\n  🔥 Max Consecutive Wins: {stats['max_consecutive_wins']}")
    print(f"  ❄️ Max Consecutive Losses: {stats['max_consecutive_losses']}")

    print(f"\n  📋 Exit Reasons:")
    for reason, count in stats["exit_reasons"].items():
        print(f"      {reason}: {count}")

    print(f"\n  📌 Symbol Performance:")
    for sym, data in stats["symbols"].items():
        pnl_str = f"₹{data['pnl']:,.2f}"
        print(f"      {sym}: W{data['wins']} L{data['losses']} | {pnl_str}")

    print("\n" + "=" * 50)


def run():
    path = get_latest_journal()
    if not path:
        print("No journal files found")
        return

    print(f"Loading: {path}")
    trades = load_journal(path)
    stats = calculate_stats(trades)
    print_report(trades, stats)


if __name__ == "__main__":
    run()