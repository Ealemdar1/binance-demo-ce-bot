
import os
import time
import hmac
import hashlib
import requests
import pandas as pd
from urllib.parse import urlencode

# OKX VERI AYARLARI
BASE_URL = "https://www.okx.com"
SYMBOL = "ETH-USDT"
INTERVAL = "5m"

# CHANDELIER EXIT
ATR_PERIOD = 22
ATR_MULTIPLIER = 3.0

# BINANCE DEMO
BINANCE_BASE_URL = "https://demo-fapi.binance.com"
BINANCE_SYMBOL = "ETHUSDT"
LEVERAGE = 2
MARGIN_USDT = 10


def get_binance_position():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise Exception("Binance API anahtarlari bulunamadi!")

    params = {
        "timestamp": int(time.time() * 1000),
        "recvWindow": 10000
    }

    query = urlencode(params)

    signature = hmac.new(
        api_secret.encode(),
        query.encode(),
        hashlib.sha256
    ).hexdigest()

    url = (
        BINANCE_BASE_URL
        + "/fapi/v3/account?"
        + query
        + "&signature="
        + signature
    )

    response = requests.get(
        url,
        headers={"X-MBX-APIKEY": api_key},
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    positions = []

    for p in data.get("positions", []):
        if p["symbol"] != BINANCE_SYMBOL:
            continue

        amount = float(p["positionAmt"])
        side = p.get("positionSide", "BOTH")

        if amount == 0:
            continue

        if side == "LONG":
            positions.append("LONG")
        elif side == "SHORT":
            positions.append("SHORT")
        elif amount > 0:
            positions.append("LONG")
        elif amount < 0:
            positions.append("SHORT")

    positions = sorted(set(positions))

    if not positions:
        return "NONE"

    return "+".join(positions)


def get_candles():
    url = BASE_URL + "/api/v5/market/candles"

    params = {
        "instId": SYMBOL,
        "bar": INTERVAL,
        "limit": "300"
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    response.raise_for_status()
    result = response.json()

    if result["code"] != "0":
        raise Exception(result["msg"])

    df = pd.DataFrame(
        result["data"],
        columns=[
            "time", "open", "high", "low", "close",
            "volume", "vol_ccy", "vol_quote", "confirm"
        ]
    )

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    df["time"] = pd.to_datetime(
        df["time"].astype("int64"),
        unit="ms"
    )

    # SADECE KAPANMIS MUMLAR
    df = df[df["confirm"] == "1"].copy()

    return df.sort_values(
        "time"
    ).reset_index(drop=True)


def calculate_ce(df):
    df = df.copy()

    prev_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    atr = pd.Series(
        float("nan"),
        index=df.index
    )

    atr.iloc[ATR_PERIOD] = tr.iloc[
        1:ATR_PERIOD + 1
    ].mean()

    for i in range(ATR_PERIOD + 1, len(df)):
        atr.iloc[i] = (
            atr.iloc[i - 1] * (ATR_PERIOD - 1)
            + tr.iloc[i]
        ) / ATR_PERIOD

    atr = atr * ATR_MULTIPLIER

    highest = df["close"].rolling(
        ATR_PERIOD
    ).max()

    lowest = df["close"].rolling(
        ATR_PERIOD
    ).min()

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

        if (
            pd.notna(prev_long)
            and df["close"].iloc[i - 1] > prev_long
            and pd.notna(current_long)
        ):
            current_long = max(
                current_long,
                prev_long
            )

        if (
            pd.notna(prev_short)
            and df["close"].iloc[i - 1] < prev_short
            and pd.notna(current_short)
        ):
            current_short = min(
                current_short,
                prev_short
            )

        long_stop[i] = current_long
        short_stop[i] = current_short

        if (
            pd.notna(prev_short)
            and df["close"].iloc[i] > prev_short
        ):
            direction[i] = 1

        elif (
            pd.notna(prev_long)
            and df["close"].iloc[i] < prev_long
        ):
            direction[i] = -1

        else:
            direction[i] = direction[i - 1]

    df["direction"] = direction

    previous = df["direction"].shift(1)

    df["buy_signal"] = (
        (df["direction"] == 1)
        & (previous == -1)
    )

    df["sell_signal"] = (
        (df["direction"] == -1)
        & (previous == 1)
    )

    return df


def main():
    print("================================")
    print(" CHANDELIER EXIT DEMO BOT")
    print("================================")

    # BINANCE POZISYON KONTROLU
    position = get_binance_position()

    print(
        "Binance Demo mevcut pozisyon:",
        position
    )

    # OKX VERI AL
    df = get_candles()

    if len(df) < 100:
        raise Exception(
            "Yeterli kapanmis mum yok!"
        )

    result = calculate_ce(df)
    candle = result.iloc[-1]

    print("--------------------------------")
    print("Parite:", SYMBOL)
    print("Zaman dilimi:", INTERVAL)
    print("Mum zamani:", candle["time"])
    print("Fiyat:", candle["close"])

    if candle["buy_signal"]:
        print("🟢 LONG SINYALI")

    elif candle["sell_signal"]:
        print("🔴 SHORT SINYALI")

    else:
        print("Sinyal yok.")

    print("--------------------------------")
    print("Kaldirac hedefi:", LEVERAGE)
    print("Teminat hedefi:", MARGIN_USDT, "USDT")
    print("EMIR GONDERILMEDI.")
    print("TEST TAMAMLANDI.")


if __name__ == "__main__":
    main()
