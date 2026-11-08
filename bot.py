
import requests
import pandas as pd

# ==============================
# OKX CHANDELIER EXIT SIGNAL BOT
# ==============================

BASE_URL = "https://www.okx.com"
SYMBOL = "ETH-USDT"
INTERVAL = "5m"

ATR_PERIOD = 22
ATR_MULTIPLIER = 3.0
USE_CLOSE = True


def get_candles():
    url = BASE_URL + "/api/v5/market/candles"

    params = {
        "instId": SYMBOL,
        "bar": INTERVAL,
        "limit": "300"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    result = response.json()

    if result["code"] != "0":
        raise Exception("OKX hatası: " + result["msg"])

    df = pd.DataFrame(result["data"], columns=[
        "time", "open", "high", "low", "close",
        "volume", "vol_ccy", "vol_quote", "confirm"
    ])

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])

    df["time"] = pd.to_datetime(
        pd.to_numeric(df["time"]),
        unit="ms",
        utc=True
    )

    # Sadece kapanmış mumları kullan
    df = df[df["confirm"] == "1"].copy()

    return df.sort_values("time").reset_index(drop=True)


def calculate_ce(df):
    df = df.copy()

    previous_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs()
    ], axis=1).max(axis=1)

    # Wilder ATR (Pine ta.atr mantığı)
    atr = pd.Series(float("nan"), index=df.index)

    if len(df) >= ATR_PERIOD:
        atr.iloc[ATR_PERIOD - 1] = (
            tr.iloc[:ATR_PERIOD].mean()
        )

        for i in range(ATR_PERIOD, len(df)):
            atr.iloc[i] = (
                atr.iloc[i - 1] * (ATR_PERIOD - 1)
                + tr.iloc[i]
            ) / ATR_PERIOD

    atr = atr * ATR_MULTIPLIER

    if USE_CLOSE:
        highest = df["close"].rolling(ATR_PERIOD).max()
        lowest = df["close"].rolling(ATR_PERIOD).min()
    else:
        highest = df["high"].rolling(ATR_PERIOD).max()
        lowest = df["low"].rolling(ATR_PERIOD).min()

    raw_long = highest - atr
    raw_short = lowest + atr

    long_stop = [float("nan")] * len(df)
    short_stop = [float("nan")] * len(df)
    direction = [1] * len(df)

    for i in range(len(df)):

        if pd.isna(raw_long.iloc[i]) or pd.isna(raw_short.iloc[i]):
            if i > 0:
                direction[i] = direction[i - 1]
            continue

        current_long = raw_long.iloc[i]
        current_short = raw_short.iloc[i]

        if i == 0:
            previous_long = current_long
            previous_short = current_short
        else:
            previous_long = long_stop[i - 1]
            previous_short = short_stop[i - 1]

            if pd.isna(previous_long):
                previous_long = current_long

            if pd.isna(previous_short):
                previous_short = current_short

            if df["close"].iloc[i - 1] > previous_long:
                current_long = max(current_long, previous_long)

            if df["close"].iloc[i - 1] < previous_short:
                current_short = min(current_short, previous_short)

        long_stop[i] = current_long
        short_stop[i] = current_short

        if i > 0:
            if df["close"].iloc[i] > previous_short:
                direction[i] = 1
            elif df["close"].iloc[i] < previous_long:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]

    df["direction"] = direction

    previous_direction = df["direction"].shift(1)

    df["buy_signal"] = (
        (df["direction"] == 1)
        & (previous_direction == -1)
    )

    df["sell_signal"] = (
        (df["direction"] == -1)
        & (previous_direction == 1)
    )

    return df


def main():

    print("================================")
    print(" OKX CHANDELIER EXIT BOT")
    print("================================")

    df = get_candles()

    if len(df) < 100:
        raise Exception("Yeterli kapanmis mum bulunamadi.")

    result = calculate_ce(df)

    candle = result.iloc[-1]

    print("Parite:", SYMBOL)
    print("Zaman dilimi:", INTERVAL)
    print("Mum zamani:", candle["time"])
    print("Fiyat:", candle["close"])
    print("ATR:", round(candle["close"] * 0 + 1, 2)
          if pd.isna(candle["close"]) else "Hesaplandi")

    if candle["buy_signal"]:
        print("")
        print("******** LONG SINYALI ********")

    elif candle["sell_signal"]:
        print("")
        print("******** SHORT SINYALI ********")

    else:
        print("Sinyal yok.")

    print("--------------------------------")
    print("Emir gonderilmedi.")
    print("Test tamamlandi.")


if __name__ == "__main__":
    main()
