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

st.markdown(
    """
    <style>
    :root {
        --bg-soft: #0b1220;
        --bg-deep: #070d18;
        --card: #111a2b;
        --ink: #e5edf8;
        --muted: #9aabc3;
        --accent: #34d399;
        --accent-soft: #122538;
        --border: #22324a;
    }

    .stApp {
        background: radial-gradient(circle at 15% 10%, #162038 0%, var(--bg-soft) 45%, var(--bg-deep) 100%);
        color: var(--ink);
    }

    .title-block {
        padding: 16px 20px;
        border-radius: 16px;
        background: linear-gradient(120deg, #16243b, #101a2d);
        border: 1px solid var(--border);
        margin-bottom: 12px;
    }

    .subtitle {
        color: var(--muted);
        margin-top: 6px;
        font-size: 0.95rem;
    }

    .section-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 14px 16px 8px 16px;
        margin-bottom: 14px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    }

    div[data-testid="stMetric"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 10px 12px;
        background: #0f1728;
    }

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricDelta"] {
        color: var(--ink) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(17, 26, 43, 0.7);
        border: 1px solid var(--border);
        padding: 4px;
        border-radius: 12px;
    }

    .stTabs [data-baseweb="tab"] {
        color: var(--muted);
        background: transparent;
        border-radius: 8px;
    }

    .stTabs [aria-selected="true"] {
        color: var(--ink) !important;
        background: #1a2a42 !important;
    }

    .stSelectbox label,
    .stSubheader,
    .stMarkdown,
    .stCaption,
    label {
        color: var(--ink) !important;
    }

    div[data-baseweb="select"] > div,
    .stTextInput input,
    .stNumberInput input {
        background: #0f1728 !important;
        color: var(--ink) !important;
        border: 1px solid var(--border) !important;
    }

    .stButton button {
        background: linear-gradient(135deg, #1b2c48, #1f365a);
        color: #e9f1ff;
        border: 1px solid #35527a;
    }

    .stButton button:hover {
        border-color: #4f79ad;
        color: #ffffff;
    }

    .stDataFrame {
        border: 1px solid var(--border);
        border-radius: 10px;
    }

    .stAlert {
        border-radius: 10px;
        border: 1px solid var(--border);
    }

    .stPlotlyChart {
        border: 1px solid var(--border);
        border-radius: 10px;
        background: #0f1728;
        padding: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------
# FILE PATHS
# ---------------------------------------------------

DATA_DIR = "data"

STATUS_FILE = os.path.join(DATA_DIR, "status.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.csv")
EQUITY_FILE = os.path.join(DATA_DIR, "equity.csv")

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


def format_inr(value):
    try:
        return f"Rs {float(value):,.2f}"
    except (TypeError, ValueError):
        return "Rs 0.00"


def safe_read_csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

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

st.markdown(
    """
    <div class="title-block">
        <h2 style="margin:0; color:#e5edf8;">Shoonya Algo Trading Dashboard</h2>
        <div class="subtitle">Live overview, data preparation, and backtesting in one place.</div>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------
# LOAD STATUS
# ---------------------------------------------------

if os.path.exists(STATUS_FILE):
    try:
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)
    except json.JSONDecodeError:
        status = {}
else:
    status = {}

status = {
    "bot_status": status.get("bot_status", "OFFLINE"),
    "capital": status.get("capital", 0),
    "daily_pnl": status.get("daily_pnl", 0),
    "active_trade": status.get("active_trade", "NONE"),
    "last_update": status.get("last_update", "")
}

# ---------------------------------------------------
# TOP METRICS
# ---------------------------------------------------

tab_overview, tab_data, tab_backtest = st.tabs([
    "Overview",
    "Fetch Data",
    "Run Backtest"
])

with tab_overview:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)

    pnl_value = float(status["daily_pnl"]) if pd.notna(status["daily_pnl"]) else 0

    with col1:
        st.metric("Bot Status", status["bot_status"])
    with col2:
        st.metric("Capital", format_inr(status["capital"]))
    with col3:
        st.metric("Daily PnL", format_inr(pnl_value), delta=f"{pnl_value:+,.2f}")
    with col4:
        st.metric("Active Trade", status["active_trade"])

    last_update = status.get("last_update") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"Status Last Update: {last_update}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Equity Curve")
    if os.path.exists(EQUITY_FILE):
        equity_df = safe_read_csv(EQUITY_FILE)
        if not equity_df.empty and {"time", "capital"}.issubset(equity_df.columns):
            equity_df["time"] = pd.to_datetime(equity_df["time"], errors="coerce")
            equity_df = equity_df.dropna(subset=["time", "capital"])

            fig = px.line(
                equity_df,
                x="time",
                y="capital",
                title="Capital Growth"
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#d7e2f3"),
                title_font=dict(color="#d7e2f3"),
                margin=dict(l=20, r=20, t=40, b=20)
            )
            fig.update_traces(line=dict(color="#34d399", width=2.2))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Equity file exists but has no usable records yet.")
    else:
        st.info("No equity data found.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Trade History")
    if os.path.exists(TRADES_FILE):
        trades_df = safe_read_csv(TRADES_FILE)

        if not trades_df.empty:
            if "date" in trades_df.columns:
                trades_view = trades_df.sort_values(by="date", ascending=False)
            else:
                trades_view = trades_df.copy()

            st.dataframe(trades_view, use_container_width=True, height=320)

            if "pnl" in trades_df.columns:
                trades_df["pnl"] = pd.to_numeric(trades_df["pnl"], errors="coerce").fillna(0)
                wins = trades_df[trades_df["pnl"] > 0]
                losses = trades_df[trades_df["pnl"] <= 0]
                total_trades = len(trades_df)

                win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
                losses_sum = losses["pnl"].sum()

                if losses.empty or losses_sum == 0:
                    profit_factor = "INF" if wins["pnl"].sum() > 0 else "0.00"
                else:
                    profit_factor = f"{(wins['pnl'].sum() / abs(losses_sum)):.2f}"

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Trades", total_trades)
                with col2:
                    st.metric("Win Rate", f"{win_rate:.1f}%")
                with col3:
                    st.metric("Profit Factor", profit_factor)
            else:
                st.info("Trade records loaded, but 'pnl' column is missing.")
        else:
            st.info("Trade history file is empty.")
    else:
        st.info("No trade history found.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_data:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Fetch Stock Data")
    stock_input = st.selectbox(
        "Select Stock",
        WATCHLIST,
        key="fetch_stock"
    )

    fetch_button = st.button("Fetch Data", use_container_width=True)

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

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df.reset_index(inplace=True)
            df.rename(columns={
                "Datetime": "datetime",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            }, inplace=True)

            required_columns = ["datetime", "open", "high", "low", "close", "volume"]
            if not set(required_columns).issubset(df.columns):
                st.error("Downloaded data did not contain expected OHLCV columns.")
            else:
                df = df[required_columns]

                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

                df.dropna(inplace=True)

                os.makedirs(DATA_DIR, exist_ok=True)
                filename = os.path.join(DATA_DIR, f"candles_{stock_input.upper()}_EQ.csv")
                df.to_csv(filename, index=False)

                st.success(f"Saved {len(df)} candles to {filename}")
                st.dataframe(df.tail(10), use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_backtest:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Run Backtest")

    backtest_stock = st.selectbox(
        "Select Stock For Backtest",
        WATCHLIST,
        key="backtest_stock"
    )

    run_backtest = st.button("Run Backtest", use_container_width=True)

    if run_backtest:
        try:
            with st.spinner(f"Running backtest for {backtest_stock}..."):
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

            if result.returncode == 0:
                st.success("Backtest completed")
                st.code(result.stdout if result.stdout else "No output returned.")
            else:
                st.error("Backtest failed.")
                if result.stdout:
                    st.code(result.stdout)
                if result.stderr:
                    st.code(result.stderr)

        except Exception as e:
            st.error(f"Error running backtest: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

st.caption(f"Dashboard Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")