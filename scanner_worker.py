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

from core.sentiment import (
    SentimentAnalyzer
)

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

            result = scan_stock(stock)

            if result:

                # ---------------------------------
                # SENTIMENT
                # ---------------------------------

                sentiment = (

                    sentiment_analyzer
                    .get_sentiment(stock)

                )

                result["sentiment"] = round(
                    sentiment,
                    2
                )

                # ---------------------------------
                # FILTER
                # ---------------------------------

                if (

                    result["score"] >= 7

                    and

                    result["change_pct"] > -0.3

                ):

                    scanner_results.append(
                        result
                    )

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