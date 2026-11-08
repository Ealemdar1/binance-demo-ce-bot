
import requests
import pandas as pd

BASE_URL = "https://demo-fapi.binance.com"
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
ATR_PERIOD = 22
ATR_MULTIPLIER = 3.0
CANDLE_LIMIT = 500

def get_candles():
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": CANDLE_LIMIT
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    columns = [
        "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume",
        "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ]

    df = pd.DataFrame(response.json(), columns=columns)

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def calculate_ce(df):
    df = df.copy()

    prev_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    # Wilder ATR (Pine Script ta.atr)
    atr = pd.Series(float("nan"), index=df.index)

    if len(df) <= ATR_PERIOD:
        raise ValueError("Yetersiz mum verisi")

    seed = tr.iloc[1:ATR_PERIOD + 1].mean()
    atr.iloc[ATR_PERIOD] = seed

    for i in range(ATR_PERIOD + 1, len(df)):
        atr.iloc[i] = (
            atr.iloc[i - 1] * (ATR_PERIOD - 1) + tr.iloc[i]
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
        if i == 0:
            long_stop[i] = raw_long.iloc[i]
            short_stop[i] = raw_short.iloc[i]
            continue

        prev_long = long_stop[i - 1]
        prev_short = short_stop[i - 1]

        current_long = raw_long.iloc[i]
        current_short = raw_short.iloc[i]

        if pd.notna(prev_long) and df["close"].iloc[i - 1] > prev_long:
            current_long = max(current_long, prev_long)

        if pd.notna(prev_short) and df["close"].iloc[i - 1] < prev_short:
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

    df = get_candles()

    # Açık olan son mumu çıkar.
    closed_df = df.iloc[:-1].copy()

    if len(closed_df) < 100:
        raise ValueError("Yeterli kapanmış mum yok")

    result = calculate_ce(closed_df)
    candle = result.iloc[-1]

    print("--------------------------------")
    print("Kapanan mum:", candle["open_time"])
    print("ETHUSDT fiyatı:", candle["close"])

    if candle["buy_signal"]:
        print("🟢 CE BUY - LONG SİNYALİ")
    elif candle["sell_signal"]:
        print("🔴 CE SELL - SHORT SİNYALİ")
    else:
        print("Sinyal yok.")

    print("--------------------------------")
    print("TEST TAMAMLANDI - EMİR GÖNDERİLMEDİ")


if __name__ == "__main__":
    main()
