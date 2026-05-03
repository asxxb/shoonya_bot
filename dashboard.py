import os
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import subprocess
from datetime import datetime

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------

st.set_page_config(
    page_title="Shoonya Trading Dashboard",
    layout="wide"
)

# ---------------------------------------------------
# FILE PATHS
# ---------------------------------------------------

DATA_DIR = "data"

STATUS_FILE = os.path.join(DATA_DIR, "status.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.csv")
EQUITY_FILE = os.path.join(DATA_DIR, "equity.csv")

# ---------------------------------------------------
# AUTO REFRESH
# ---------------------------------------------------

st_autorefresh(
    interval=5000,
    key="dashboard_refresh"
)

# ---------------------------------------------------
# TITLE
# ---------------------------------------------------

st.title("📈 Shoonya Algo Trading Dashboard")

# ---------------------------------------------------
# LOAD STATUS
# ---------------------------------------------------

if os.path.exists(STATUS_FILE):

    with open(STATUS_FILE, "r") as f:
        status = json.load(f)

else:

    status = {
        "bot_status": "OFFLINE",
        "capital": 0,
        "daily_pnl": 0,
        "active_trade": "NONE",
        "last_update": ""
    }

# ---------------------------------------------------
# TOP METRICS
# ---------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Bot Status", status["bot_status"])

with col2:
    st.metric("Capital", f"₹{status['capital']:.2f}")

with col3:
    st.metric("Daily PnL", f"₹{status['daily_pnl']:.2f}")

with col4:
    st.metric("Active Trade", status["active_trade"])

st.divider()

# ---------------------------------------------------
# EQUITY CURVE
# ---------------------------------------------------

st.subheader("📊 Equity Curve")

if os.path.exists(EQUITY_FILE):

    equity_df = pd.read_csv(EQUITY_FILE)

    if not equity_df.empty:

        fig = px.line(
            equity_df,
            x="time",
            y="capital",
            title="Capital Growth"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

else:

    st.warning("No equity data found")

st.divider()

# ---------------------------------------------------
# TRADE HISTORY
# ---------------------------------------------------

st.subheader("📝 Trade History")

if os.path.exists(TRADES_FILE):

    trades_df = pd.read_csv(TRADES_FILE)

    if not trades_df.empty:

        st.dataframe(
            trades_df.sort_values(
                by="date",
                ascending=False
            ),
            use_container_width=True
        )

        wins = trades_df[trades_df["pnl"] > 0]

        losses = trades_df[trades_df["pnl"] <= 0]

        total_trades = len(trades_df)

        win_rate = (
            len(wins) / total_trades * 100
            if total_trades > 0
            else 0
        )

        profit_factor = (
            wins["pnl"].sum() / abs(losses["pnl"].sum())
            if not losses.empty and losses["pnl"].sum() != 0
            else 0
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Trades", total_trades)

        with col2:
            st.metric("Win Rate", f"{win_rate:.1f}%")

        with col3:
            st.metric("Profit Factor", f"{profit_factor:.2f}")

else:

    st.warning("No trade history found")

st.divider()

# ---------------------------------------------------
# LAST UPDATE
# ---------------------------------------------------

st.caption(f"Last Updated: {datetime.now()}")

# ---------------------------------------------------
# STOCK FETCHER
# ---------------------------------------------------

st.subheader("📥 Fetch Stock Data")

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
    "IRFC"
]


stock_input = st.selectbox(
    "Select Stock",
    WATCHLIST
)

fetch_button = st.button("Fetch Data")

if fetch_button:

    import yfinance as yf

    try:

        symbol = f"{stock_input.upper()}.NS"

        with st.spinner(f"Fetching {symbol}..."):

            df = yf.download(
                symbol,
                interval="5m",
                period="1mo",
                progress=False
            )

        # -----------------------------------------
        # Flatten MultiIndex
        # -----------------------------------------

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.reset_index(inplace=True)

        # -----------------------------------------
        # Rename Columns
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
        # Keep Required Columns
        # -----------------------------------------

        df = df[[
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]]

        # -----------------------------------------
        # Numeric Conversion
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
        # Save File
        # -----------------------------------------

        os.makedirs("data", exist_ok=True)

        filename = (
            f"data/candles_"
            f"{stock_input.upper()}_EQ.csv"
        )

        df.to_csv(filename, index=False)

        st.success(
            f"Saved {len(df)} candles to {filename}"
        )

        st.dataframe(df.tail(10))

    except Exception as e:

        st.error(f"Error: {e}")

# ---------------------------------------------------
# RUN BACKTEST
# ---------------------------------------------------

st.subheader("⚡ Run Backtest")

backtest_stock = st.selectbox(
    "Select Stock For Backtest",
    [
        "SBIN",
        "NHPC",
        "SUZLON",
        "YESBANK",
        "IDFCFIRSTB",
        "UCOBANK",
        "IREDA",
        "RVNL",
        "NBCC",
        "IRFC"
    ]
)

run_backtest = st.button("Run Backtest")

if run_backtest:

    try:

        with st.spinner(
            f"Running backtest for {backtest_stock}..."
        ):

            result = subprocess.run(
                [
                    "python3",
                    "backtest.py",
                    "--symbol",
                    f"{backtest_stock}-EQ",
                    "--use-cached"
                ],
                capture_output=True,
                text=True
            )

        st.success("Backtest completed")

        st.code(result.stdout)

        if result.stderr:
            st.error(result.stderr)

    except Exception as e:

        st.error(f"Error running backtest: {e}")