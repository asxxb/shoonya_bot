import os
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from config import settings
from core.sentiment import SentimentAnalyzer
from streamlit_autorefresh import st_autorefresh
import subprocess
from datetime import datetime
from scanner import scan_stock
# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------

st.set_page_config(
    page_title="Shoonya Trading Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
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

    [data-testid="stToolbar"] {
        display: none !important;
    }

    [data-testid="stDecoration"] {
        display: none !important;
    }

    .main-content {
        margin-top: 0 !important;
        padding-top: 0.3rem !important;
    }

    header {
        display: none !important;
    }

    .st-emotion-cache-1y4p8pa {
        padding-top: 2rem !important;
    }

    [data-testid="stAppViewContainer"] {
        padding-top: 0.8rem !important;
    }

    .stTabs {
        margin-top: 0.5rem !important;
    }

    html, body, [class*="css"] {
        --spacing: 0.25rem;
    }

    .title-block {
        padding: 2px 4px;
        border-radius: 2px;
        background: linear-gradient(120deg, #16243b, #101a2d);
        border: 1px solid var(--border);
        margin-bottom: 0.3rem;
    }
    
    .title-block h3 {
        font-size: 0.95rem;
        margin: 0;
        color: #e5edf8;
        font-weight: 600;
    }

    .section-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 3px;
        padding: 2px 3px;
        margin-bottom: 0.2rem;
    }
    
    .section-card h3 {
        font-size: 0.75rem;
        margin: 2px 0;
        font-weight: 600;
    }

    div[data-testid="stMetric"] {
        border: 1px solid var(--border);
        border-radius: 2px;
        padding: 1px 2px !important;
        background: #0f1728;
        min-height: auto !important;
        gap: 0 !important;
    }
    
    div[data-testid="stMetric"] > div:first-child {
        font-size: 0.5rem !important;
        margin-bottom: 1px !important;
        line-height: 1 !important;
        font-weight: 500 !important;
    }
    
    div[data-testid="stMetric"] > div:nth-child(2) {
        font-size: 0.6rem !important;
        margin-bottom: 1px !important;
        line-height: 1 !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stMetric"] > div:nth-child(3) {
        font-size: 0.45rem !important;
        line-height: 1 !important;
    }

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricDelta"] {
        color: var(--ink) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 3px;
        background: rgba(17, 26, 43, 0.7);
        border: 1px solid var(--border);
        padding: 4px;
        border-radius: 6px;
        margin-bottom: 0.3rem;
    }

    .stTabs [data-baseweb="tab"] {
        color: var(--muted);
        background: transparent;
        border-radius: 4px;
        font-size: 0.8rem;
        padding: 4px 10px !important;
        margin: 0 !important;
    }

    .stTabs [aria-selected="true"] {
        color: var(--ink) !important;
        background: #1a2a42 !important;
        border-bottom: 2px solid var(--accent) !important;
    }

    .stSelectbox label,
    .stSubheader,
    .stMarkdown,
    .stCaption,
    label {
        color: var(--ink) !important;
        font-size: 0.7rem;
    }

    div[data-baseweb="select"] > div,
    .stTextInput input,
    .stNumberInput input {
        background: #0f1728 !important;
        color: var(--ink) !important;
        border: 1px solid var(--border) !important;
        font-size: 0.75rem !important;
        padding: 3px !important;
    }

    .stButton button {
        background: linear-gradient(135deg, #1b2c48, #1f365a);
        color: #e9f1ff;
        border: 1px solid #35527a;
        font-size: 0.7rem;
        padding: 2px 6px;
        height: auto !important;
        min-height: 24px;
    }

    .stButton button:hover {
        border-color: #4f79ad;
        color: #ffffff;
    }

    .stDataFrame {
        border: 1px solid var(--border);
        border-radius: 3px;
    }

    .stAlert {
        border-radius: 3px;
        border: 1px solid var(--border);
        padding: 3px 6px !important;
        margin-bottom: 0.2rem !important;
        font-size: 0.7rem;
    }

    .stPlotlyChart {
        border: 1px solid var(--border);
        border-radius: 3px;
        background: #0f1728;
        padding: 2px;
    }
    
    .block-container {
        padding-top: 0.25rem !important;
        padding-bottom: 0.15rem !important;
        max-width: 100% !important;
    }
    
    [data-testid="stVerticalBlock"] {
        gap: 0.15rem !important;
    }
    
    [data-testid="stHorizontalBlock"] {
        gap: 0.2rem !important;
    }
    
    .stPlotlyChart > div {
        height: 90px !important;
    }
    
    div[data-testid="stDataFrame"] {
        font-size: 0.7rem;
        max-height: 100px;
    }

    .compact-section {
        margin-bottom: 0.2rem !important;
    }

    [role="tabpanel"] {
        outline: none !important;
        padding-top: 0.2rem !important;
    }

    .stTabs > div {
        display: flex !important;
        flex-direction: column !important;
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



# ---------------------------------------------------
# TITLE
# ---------------------------------------------------

st.markdown(
    """
    <div class="title-block">
        <span style="font-size:0.95rem;color:#e5edf8;font-weight:600;">🚀 Shoonya Dashboard</span>
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

tab_overview, tab_scanner, tab_data, tab_backtest = st.tabs([

    "Overview",
    "Momentum Scanner",
    "Fetch Data",
    "Run Backtest"

])

with tab_overview:
    st_autorefresh(interval=5000, key="overview_refresh")
    
    pnl_value = float(status["daily_pnl"]) if pd.notna(status["daily_pnl"]) else 0
    mode_text = "🟡 PAPER" if settings.PAPER_TRADE else "🔴 LIVE"
    
    # === TOP STATUS BAR (COMPACT) ===
    c1, c2, c3, c4, c5 = st.columns(5, gap="xxsmall")
    with c1: st.metric("Bot", status["bot_status"])
    with c2: st.metric("Mode", mode_text)
    with c3: st.metric("₹Cap", format_inr(status["capital"]))
    with c4: st.metric("₹PnL", format_inr(pnl_value), delta=f"{pnl_value:+,.2f}")
    with c5: st.metric("Active", status["active_trade"])
    
    st.markdown(
        """
        <style>
        div[data-testid="stMetric"]:has(> div:first-child:contains("Bot")),
        div[data-testid="stMetric"]:has(> div:first-child:contains("Mode")),
        div[data-testid="stMetric"]:has(> div:first-child:contains("₹Cap")),
        div[data-testid="stMetric"]:has(> div:first-child:contains("₹PnL")),
        div[data-testid="stMetric"]:has(> div:first-child:contains("Active")) {
            font-size: 0.95rem !important;
            color: #e5edf8 !important;
            font-weight: 600 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # === 4-COLUMN LAYOUT FOR SINGLE SCREEN ===
    col1, col2, col3, col4 = st.columns(4, gap="xxsmall")
    
    # === COLUMN 1: EQUITY CHART ===
    with col1:
        st.markdown('<div class="section-card"><h3>Equity Curve</h3>', unsafe_allow_html=True)
        if os.path.exists(EQUITY_FILE):
            equity_df = safe_read_csv(EQUITY_FILE)
            if not equity_df.empty and {"time", "capital"}.issubset(equity_df.columns):
                equity_df["time"] = pd.to_datetime(equity_df["time"], errors="coerce")
                equity_df = equity_df.dropna(subset=["time", "capital"])
                fig = px.line(equity_df, x="time", y="capital")
                fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=100, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#d7e2f3", size=6), showlegend=False)
                fig.update_traces(line=dict(color="#34d399", width=1.5))
                st.plotly_chart(fig, use_container_width=True)
            else: st.caption("No equity data", help="Equity curve will appear here")
        else: st.caption("No equity file")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # === COLUMN 2: PERFORMANCE METRICS ===
    with col2:
        st.markdown('<div class="section-card"><h3>Performance</h3>', unsafe_allow_html=True)
        if os.path.exists(TRADES_FILE):
            trades_df = safe_read_csv(TRADES_FILE)
            if not trades_df.empty and "pnl" in trades_df.columns:
                trades_df["pnl"] = pd.to_numeric(trades_df["pnl"], errors="coerce").fillna(0)
                wins = trades_df[trades_df["pnl"] > 0]
                losses = trades_df[trades_df["pnl"] <= 0]
                total_trades = len(trades_df)
                win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
                total_pnl = trades_df["pnl"].sum()
                avg_win = wins["pnl"].mean() if not wins.empty else 0
                avg_loss = losses["pnl"].mean() if not losses.empty else 0
                expectancy = (win_rate / 100) * avg_win + ((100 - win_rate) / 100) * avg_loss
                pf = f"{(wins['pnl'].sum() / abs(losses['pnl'].sum())):.2f}" if not losses.empty and losses['pnl'].sum() != 0 else "0"
                rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0
                
                equity = 0
                peak = 0
                max_dd = 0
                for _, row in trades_df.iterrows():
                    equity += row["pnl"]
                    peak = max(peak, equity)
                    max_dd = max(max_dd, peak - equity)
                
                m1, m2 = st.columns(2, gap="xxsmall")
                with m1: st.metric("Trades", total_trades)
                with m2: st.metric("Win%", f"{win_rate:.0f}%")
                
                m3, m4 = st.columns(2, gap="xxsmall")
                with m3: st.metric("P&L", f"₹{total_pnl:.0f}")
                with m4: st.metric("PF", pf)
                
                m5, m6 = st.columns(2, gap="xxsmall")
                with m5: st.metric("R:R", f"{rr:.1f}")
                with m6: st.metric("MaxDD", f"₹{max_dd:.0f}")
                
                m7, m8 = st.columns(2, gap="xxsmall")
                with m7: st.metric("Exp", f"₹{expectancy:.1f}")
                with m8: st.metric("Avg", f"₹{trades_df['pnl'].mean():.1f}")
            else: st.caption("No trades yet")
        else: st.caption("No trades file")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # === COLUMN 3: RECENT TRADES ===
    with col3:
        st.markdown('<div class="section-card"><h3>Recent Trades</h3>', unsafe_allow_html=True)
        if os.path.exists(TRADES_FILE):
            trades_df = safe_read_csv(TRADES_FILE)
            if not trades_df.empty:
                if "date" in trades_df.columns:
                    trades_df = trades_df.sort_values("date", ascending=False).head(8)
                st.dataframe(trades_df, use_container_width=True, hide_index=True)
            else: st.caption("No trades")
        else: st.caption("No file")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # === COLUMN 4: CONTROLS & INFO ===
    with col4:
        st.markdown('<div class="section-card"><h3>Trade Mode</h3>', unsafe_allow_html=True)
        current_mode = settings.get_trade_mode()
        mode_label = "🟡 PAPER" if current_mode else "🔴 LIVE"
        
        cols_info = st.columns(1)
        st.info(f"**Mode:** {mode_label}", icon="⚙️")
        
        toggle = st.toggle("Paper Trade", value=current_mode, key="mode_toggle")
        if toggle != current_mode:
            settings.set_paper_trade_mode(toggle)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown('<div class="section-card"><h3>Stats</h3>', unsafe_allow_html=True)
        if os.path.exists(TRADES_FILE):
            trades_df = safe_read_csv(TRADES_FILE)
            if not trades_df.empty:
                st.metric("Total Trades", len(trades_df))
                if "pnl" in trades_df.columns:
                    trades_df["pnl"] = pd.to_numeric(trades_df["pnl"], errors="coerce")
                    st.metric("Total P&L", f"₹{trades_df['pnl'].sum():.0f}")
            else:
                st.caption("No data available")
        else:
            st.caption("No file")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------
    # MOMENTUM SCANNER TAB
    # ---------------------------------------------------

# with tab_scanner:

#         st.markdown(
#             '<div class="section-card">',
#             unsafe_allow_html=True
#         )

#         st.subheader("Live Momentum Scanner")

#         # -----------------------------------------
#         # AUTO REFRESH OPTION
#         # -----------------------------------------

#         scanner_refresh = st.checkbox(
#             "Auto Refresh Scanner",
#             value=False
#         )

#         # -----------------------------------------
#         # BUTTON
#         # -----------------------------------------

#         scan_button = st.button(
#             "Run Scanner",
#             width='stretch'
#         )

#         # -----------------------------------------
#         # RUN SCANNER ONLY ON CLICK
#         # -----------------------------------------

#         should_scan = False

#         if scan_button:
#             should_scan = True

#         elif (
#             scanner_refresh
#             and "last_scan_time"
#             not in st.session_state
#         ):
#             should_scan = True

#         # -----------------------------------------
#         # AUTO REFRESH TIMER
#         # -----------------------------------------

#         if scanner_refresh:

#             st_autorefresh(
#                 interval=60000,
#                 key="scanner_refresh"
#             )

#         # -----------------------------------------
#         # RUN SCANNER
#         # -----------------------------------------

#         if should_scan:

#             scanner_results = []

#             sentiment_analyzer = (
#                 SentimentAnalyzer()
#             )

#             progress = st.progress(0)

#             for i, stock in enumerate(WATCHLIST):

#                 result = scan_stock(stock)

#                 if result:

#                     # -----------------------------
#                     # SENTIMENT
#                     # -----------------------------

#                     sentiment = (

#                         sentiment_analyzer
#                         .get_sentiment(stock)

#                     )

#                     result["sentiment"] = round(
#                         sentiment,
#                         2
#                     )

#                     # -----------------------------
#                     # FILTER
#                     # -----------------------------

#                     if (

#                         result["score"] >= 7

#                         and

#                         result["change_pct"] > -0.3

#                     ):

#                         scanner_results.append(
#                             result
#                         )

#                 progress.progress(
#                     (i + 1) / len(WATCHLIST)
#                 )

#             # -------------------------------------
#             # SORT
#             # -------------------------------------

#             scanner_results = sorted(

#                 scanner_results,

#                 key=lambda x: x["score"],

#                 reverse=True

#             )

#             # -------------------------------------
#             # SAVE TO SESSION
#             # -------------------------------------

#             st.session_state[
#                 "scanner_results"
#             ] = scanner_results

#             st.session_state[
#                 "last_scan_time"
#             ] = datetime.now().strftime(
#                 "%H:%M:%S"
#             )

#         # -----------------------------------------
#         # DISPLAY CACHED RESULTS
#         # -----------------------------------------

#         if "scanner_results" in st.session_state:

#             scanner_results = (
#                 st.session_state[
#                     "scanner_results"
#                 ]
#             )

#             if scanner_results:

#                 scanner_df = pd.DataFrame(
#                     scanner_results
#                 )

#                 st.success(

#                     f"Found "
#                     f"{len(scanner_df)} "
#                     f"momentum stocks"

#                 )

#                 st.dataframe(

#                     scanner_df,

#                     use_container_width=True

#                 )

#                 # ---------------------------------
#                 # TOP STOCK
#                 # ---------------------------------

#                 top_stock = (
#                     scanner_df.iloc[0]
#                 )

#                 st.metric(

#                     "Top Momentum Stock",

#                     top_stock["symbol"],

#                     delta=f"{top_stock['change_pct']}%"

#                 )

#                 # ---------------------------------
#                 # LAST SCAN
#                 # ---------------------------------

#                 st.caption(

#                     f"Last Scan: "
#                     f"{st.session_state['last_scan_time']}"

#                 )

#             else:

#                 st.warning(
#                     "No strong momentum stocks found."
#                 )

#         st.markdown(
#             "</div>",
#             unsafe_allow_html=True
#         )


with tab_scanner:

    st.markdown(
        '<div class="section-card">',
        unsafe_allow_html=True
    )

    st.subheader(
        "Live Momentum Scanner"
    )

    scanner_file = os.path.join(
        DATA_DIR,
        "scanner_results.json"
    )

    if os.path.exists(scanner_file):

        with open(scanner_file, "r") as f:

            data = json.load(f)

        scanner_results = data.get(
            "results",
            []
        )

        last_scan = data.get(
            "last_scan",
            "Unknown"
        )

        if scanner_results:

            scanner_df = pd.DataFrame(
                scanner_results
            )

            st.success(

                f"Found "
                f"{len(scanner_df)} "
                f"momentum stocks"

            )

            st.dataframe(

                scanner_df,

                width='stretch'

            )

            top_stock = (
                scanner_df.iloc[0]
            )

            st.metric(

                "Top Momentum Stock",

                top_stock["symbol"],

                delta=f"{top_stock['change_pct']}%"

            )

        else:

            st.warning(
                "No strong momentum stocks found."
            )

        st.caption(
            f"Last Scan: {last_scan}"
        )

    else:

        st.info(
            "Scanner results not available yet."
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )
    
with tab_data:

    st.markdown(
        '<div class="section-card">',
        unsafe_allow_html=True
    )

    st.subheader("Fetch Stock Data")

    stock_input = st.selectbox(
        "Select Stock",
        WATCHLIST,
        key="fetch_stock"
    )

    fetch_button = st.button(
        "Fetch Data",
        width='stretch'
    )

    if fetch_button:

        import yfinance as yf

        try:

            symbol = f"{stock_input.upper()}.NS"

            with st.spinner(
                f"Fetching {symbol}..."
            ):

                df = yf.download(
                    symbol,
                    interval="5m",
                    period="1mo",
                    progress=False
                )

            # -----------------------------------------
            # FIX MULTIINDEX
            # -----------------------------------------

            if isinstance(df.columns, pd.MultiIndex):

                df.columns = (
                    df.columns.get_level_values(0)
                )

            # -----------------------------------------
            # FORMAT DATA
            # -----------------------------------------

            df.reset_index(inplace=True)

            df.rename(columns={

                "Datetime": "datetime",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"

            }, inplace=True)

            required_columns = [

                "datetime",
                "open",
                "high",
                "low",
                "close",
                "volume"

            ]

            if not set(required_columns).issubset(df.columns):

                st.error(
                    "Downloaded data missing OHLCV columns."
                )

            else:

                df = df[required_columns]

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
                # SAVE SESSION STATE
                # -----------------------------------------

                st.session_state["fetched_df"] = df

                st.session_state[
                    "fetched_stock"
                ] = stock_input

                # -----------------------------------------
                # SAVE CSV
                # -----------------------------------------

                os.makedirs(
                    DATA_DIR,
                    exist_ok=True
                )

                filename = os.path.join(

                    DATA_DIR,
                    f"candles_{stock_input.upper()}_EQ.csv"

                )

                df.to_csv(
                    filename,
                    index=False
                )

                st.success(
                    f"Saved {len(df)} candles "
                    f"to {filename}"
                )

        except Exception as e:

            st.error(f"Error: {e}")

    # ---------------------------------------------------
    # SHOW FETCHED DATA PERSISTENTLY
    # ---------------------------------------------------

    if "fetched_df" in st.session_state:

        st.success(
            f"Showing cached data for "
            f"{st.session_state['fetched_stock']}"
        )

        st.dataframe(

            st.session_state[
                "fetched_df"
            ].tail(10),

            width='stretch'

        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


with tab_backtest:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Run Backtest")

    backtest_stock = st.selectbox(
        "Select Stock For Backtest",
        WATCHLIST,
        key="backtest_stock"
    )

    run_backtest = st.button("Run Backtest", width='stretch')

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

st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
