
import os
import time
import requests
import pandas as pd

BASE_URL = "https://demo-fapi.binance.com"
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
ATR_PERIOD = 22
ATR_MULTIPLIER = 3.0


def get_candles():
    url = BASE_URL + "/fapi/v1/klines"

    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": 300
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    df = pd.DataFrame(response.json(), columns=[
        "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume",
        "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    df["time"] = pd.to_datetime(
        df["open_time"], unit="ms"
    )

    # Son mum henüz kapanmadıysa çıkar
    now_ms = int(time.time() * 1000)
    df = df[df["close_time"] < now_ms].copy()

    return df.sort_values("open_time").reset_index(drop=True)


def calculate_ce(df):
    df = df.copy()

    prev_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    atr = pd.Series(float("nan"), index=df.index)

    if len(df) <= ATR_PERIOD:
        raise Exception("Yeterli mum yok")

    atr.iloc[ATR_PERIOD - 1] = tr.iloc[:ATR_PERIOD].mean()

    for i in range(ATR_PERIOD, len(df)):
        atr.iloc[i] = (
            atr.iloc[i - 1] * (ATR_PERIOD - 1)
            + tr.iloc[i]
        ) / ATR_PERIOD

    atr = atr * ATR_MULTIPLIER

    highest = df["close"].rolling(ATR_PERIOD).max()
    lowest = df["close"].rolling(ATR_PERIOD).min()

    raw_long = highest - atr
    raw_short = lowest + atr

    long_stop = [float("nan")] * len(df)
    short_stop = [float("nan")] * len(df)
    direction = [1] * len(df)

    for i in range(len(df)):
        current_long = raw_long.iloc[i]
        current_short = raw_short.iloc[i]

        if i == 0:
            long_stop[i] = current_long
            short_stop[i] = current_short
            continue

        prev_long = long_stop[i - 1]
        prev_short = short_stop[i - 1]

        if pd.notna(prev_long) and df["close"].iloc[i - 1] > prev_long:
            if pd.notna(current_long):
                current_long = max(current_long, prev_long)

        if pd.notna(prev_short) and df["close"].iloc[i - 1] < prev_short:
            if pd.notna(current_short):
                current_short = min(current_short, prev_short)

        long_stop[i] = current_long
        short_stop[i] = current_short

        if pd.notna(prev_short) and df["close"].iloc[i] > prev_short:
            direction[i] = 1
        elif pd.notna(prev_long) and df["close"].iloc[i] < prev_long:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]

    df["direction"] = direction

    previous = df["direction"].shift(1)

    df["buy_signal"] = (
        (df["direction"] == 1) & (previous == -1)
    )

    df["sell_signal"] = (
        (df["direction"] == -1) & (previous == 1)
    )

    return df


def main():
    print("================================")
    print(" BINANCE DEMO - CHANDELIER EXIT")
    print("================================")

    df = get_candles()

    if len(df) < 100:
        raise Exception("Yeterli kapanmis mum yok")

    result = calculate_ce(df)
    candle = result.iloc[-1]

    print("Parite:", SYMBOL)
    print("Zaman dilimi:", INTERVAL)
    print("Mum zamani:", candle["time"])
    print("Fiyat:", candle["close"])

    if candle["buy_signal"]:
        print("LONG SINYALI")
    elif candle["sell_signal"]:
        print("SHORT SINYALI")
    else:
        print("Sinyal yok.")

    print("--------------------------------")
    print("TEST TAMAMLANDI")
    print("EMIR GONDERILMEDI")


if __name__ == "__main__":
    main()
