"""
scanner_worker.py
Runs scanner continuously
and saves results to JSON
"""

import os
import json
import time
from datetime import datetime

import pandas as pd

from scanner import scan_stock
from core.scanner import (
    PERFORMANCE_DATA,
    should_include_stock,
    passes_momentum_filter
)

from core.sentiment import SentimentAnalyzer

from config import settings

from utils.logger import get_logger

log = get_logger()

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

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

DATA_DIR = "data"

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

RESULT_FILE = os.path.join(
    DATA_DIR,
    "scanner_results.json"
)

# ---------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------

sentiment_analyzer = (
    SentimentAnalyzer()
)

while True:

    try:

        log.info(
            "Running scanner..."
        )

        scanner_results = []

        # -----------------------------------------
        # SCAN STOCKS
        # -----------------------------------------

        for stock in WATCHLIST:

            # ---------------------------------
            # STEP 1: QUALITY FILTER (Performance)
            # ---------------------------------
            
            # Use -EQ suffix to match backtest_results.json keys
            perf = PERFORMANCE_DATA.get(f"{stock}-EQ", {})
            include, reason = should_include_stock(stock, perf)
            
            if not include:
                log.debug(f"{stock}: Skipping - {reason}")
                continue

            result = scan_stock(stock)

            if result:

                # ---------------------------------
                # SENTIMENT
                # ---------------------------------

                sentiment = sentiment_analyzer.get_sentiment(stock)

                result["sentiment"] = round(sentiment, 2)

                # ---------------------------------
                # STEP 2: MOMENTUM FILTER
                # ---------------------------------

                if passes_momentum_filter(result["change_pct"], result["score"]):
                    scanner_results.append(result)

        # -----------------------------------------
        # SORT
        # -----------------------------------------

        scanner_results = sorted(

            scanner_results,

            key=lambda x: x["score"],

            reverse=True

        )

        # -----------------------------------------
        # SAVE JSON
        # -----------------------------------------

        output = {

            "last_scan": datetime.now()
            .strftime("%Y-%m-%d %H:%M:%S"),

            "results": scanner_results

        }

        with open(
            RESULT_FILE,
            "w"
        ) as f:

            json.dump(
                output,
                f,
                indent=2
            )

        log.info(

            f"Scanner complete | "
            f"{len(scanner_results)} stocks"

        )

    except Exception as e:

        log.error(
            f"Scanner worker error: {e}"
        )

    # ---------------------------------------------
    # WAIT
    # ---------------------------------------------

    time.sleep(300)