
import os
import time
import requests
import pandas as pd

# ==============================
# BINANCE FUTURES DEMO - CE BOT
# ==============================

BASE_URL = "https://demo-fapi.binance.com"

SYMBOL = "ETHUSDT"
INTERVAL = "5m"

ATR_PERIOD = 22
ATR_MULTIPLIER = 3.0
USE_CLOSE_EXTREMUMS = True

CHECK_INTERVAL = 10
CANDLE_LIMIT = 500

def get_candles():
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": CANDLE_LIMIT
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()

    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume",
        "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")

    return df


def calculate_ce(df):
    df = df.copy()

    previous_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs()
    ], axis=1).max(axis=1)

    # Pine Script ta.atr() = Wilder RMA
    atr = tr.ewm(
        alpha=1 / ATR_PERIOD,
        adjust=False,
        min_periods=ATR_PERIOD
    ).mean()

    if len(df) > ATR_PERIOD:
        first_valid = tr.first_valid_index()
        if first_valid is not None:
            seed_index = first_valid + ATR_PERIOD - 1
            if seed_index < len(df):
                atr.iloc[seed_index] = tr.iloc[
                    first_valid:seed_index + 1
                ].mean()
                for i in range(seed_index + 1, len(df)):
                    atr.iloc[i] = (
                        atr.iloc[i - 1] * (ATR_PERIOD - 1)
                        + tr.iloc[i]
                    ) / ATR_PERIOD

    df["atr"] = atr * ATR_MULTIPLIER

    if USE_CLOSE_EXTREMUMS:
        highest = df["close"].rolling(ATR_PERIOD).max()
        lowest = df["close"].rolling(ATR_PERIOD).min()
    else:
        highest = df["high"].rolling(ATR_PERIOD).max()
        lowest = df["low"].rolling(ATR_PERIOD).min()

    long_stop = highest - df["atr"]
    short_stop = lowest + df["atr"]

    long_values = [float("nan")] * len(df)
    short_values = [float("nan")] * len(df)
    directions = [1] * len(df)

    for i in range(len(df)):
        if i == 0:
            long_values[i] = long_stop.iloc[i]
            short_values[i] = short_stop.iloc[i]
            continue

        prev_long = long_values[i - 1]
        prev_short = short_values[i - 1]

        current_long = long_stop.iloc[i]
        current_short = short_stop.iloc[i]

        if pd.notna(prev_long):
            if df["close"].iloc[i - 1] > prev_long:
                current_long = max(current_long, prev_long)

        if pd.notna(prev_short):
            if df["close"].iloc[i - 1] < prev_short:
                current_short = min(current_short, prev_short)

        long_values[i] = current_long
        short_values[i] = current_short

        if pd.notna(prev_short) and df["close"].iloc[i] > prev_short:
            directions[i] = 1
        elif pd.notna(prev_long) and df["close"].iloc[i] < prev_long:
            directions[i] = -1
        else:
            directions[i] = directions[i - 1]

    df["direction"] = directions

    previous_direction = df["direction"].shift(1)

    df["buy_signal"] = (
        (df["direction"] == 1) &
        (previous_direction == -1)
    )

    df["sell_signal"] = (
        (df["direction"] == -1) &
        (previous_direction == 1)
    )

    return df


def main():
    print("================================")
    print(" BINANCE FUTURES DEMO CE BOT")
    print("================================")
    print("Parite:", SYMBOL)
    print("Zaman:", INTERVAL)
    print("Strateji: Chandelier Exit 22 / 3")
    print("Mod: Sinyal testi - Emir yok")
    print("--------------------------------")

    last_candle = None

    while True:
        try:
            df = get_candles()

            # Son mum henüz kapanmamış olabilir.
            # Bu nedenle yalnızca kapanmış mumları kullan.
            closed_df = df.iloc[:-1].copy()

            if len(closed_df) < 100:
                print("Yeterli mum verisi yok.")
                time.sleep(CHECK_INTERVAL)
                continue

            result = calculate_ce(closed_df)

            candle = result.iloc[-1]
            candle_time = candle["open_time"]

            if candle_time != last_candle:
                last_candle = candle_time

                print("\nKapanan mum:", candle_time)
                print("ETHUSDT:", candle["close"])

                if candle["buy_signal"]:
                    print("🟢 CE BUY - LONG SİNYALİ")
                elif candle["sell_signal"]:
                    print("🔴 CE SELL - SHORT SİNYALİ")
                else:
                    print("Sinyal yok.")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print("HATA:", e)
            time.sleep(15)


if __name__ == "__main__":
    main()
