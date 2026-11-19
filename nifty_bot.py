
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

STOP_LOSS = 10
TARGET = 15
MAX_TRADES = 2
DAILY_LOSS_LIMIT = 20

STATE_FILE = "state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)

    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_bot():
    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")

    if now.weekday() >= 5:
        print("Weekend: market closed")
        return

    if now.hour < 9 or (now.hour == 9 and now.minute < 15):
        print("Market not open")
        return

    if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
        print("Market closed")
        return

    state = load_state()

    if state.get("date") != today:
        state = {
            "date": today,
            "trades": 0,
            "daily_loss": 0,
            "position": None,
            "last_candle": ""
        }

    data = yf.download(
        "^NSEI",
        period="5d",
        interval="5m",
        progress=False
    )

    if data.empty:
        print("No market data available")
        return

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data["EMA9"] = data["Close"].ewm(span=9).mean()
    data["EMA21"] = data["Close"].ewm(span=21).mean()

    if len(data) < 3:
        print("Insufficient data")
        return

    previous = data.iloc[-3]
    candle = data.iloc[-2]

    candle_id = str(data.index[-2])

    if candle_id == state["last_candle"]:
        print("Already processed this candle")
        return

    state["last_candle"] = candle_id

    price = float(candle["Close"])
    high = float(candle["High"])
    low = float(candle["Low"])

    bullish = (
        previous["EMA9"] <= previous["EMA21"]
        and candle["EMA9"] > candle["EMA21"]
    )

    bearish = (
        previous["EMA9"] >= previous["EMA21"]
        and candle["EMA9"] < candle["EMA21"]
    )

    position = state["position"]

    if position:
        entry = position["entry"]
        direction = position["direction"]

        if direction == "BUY":
            exit_price = (
                entry - STOP_LOSS if low <= entry - STOP_LOSS
                else entry + TARGET if high >= entry + TARGET
                else None
            )
        else:
            exit_price = (
                entry + STOP_LOSS if high >= entry + STOP_LOSS
                else entry - TARGET if low <= entry - TARGET
                else None
            )

        if exit_price is not None:
            pnl = (
                exit_price - entry
                if direction == "BUY"
                else entry - exit_price
            )

            state["daily_loss"] += max(0, -pnl)
            state["position"] = None

            print("CLOSED:", direction, "P&L:", pnl)

    if (
        state["position"] is None
        and state["trades"] < MAX_TRADES
        and state["daily_loss"] < DAILY_LOSS_LIMIT
    ):
        if bullish:
            state["position"] = {
                "direction": "BUY",
                "entry": price
            }
            state["trades"] += 1
            print("PAPER BUY:", price)

        elif bearish:
            state["position"] = {
                "direction": "SELL",
                "entry": price
            }
            state["trades"] += 1
            print("PAPER SELL:", price)

    save_state(state)
    print("Trades:", state["trades"])
    print("Daily loss:", state["daily_loss"])


if __name__ == "__main__":
    run_bot()
          
