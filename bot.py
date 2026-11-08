import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode

BASE_URL = "https://demo-fapi.binance.com"

def main():
    print("BINANCE FUTURES DEMO BAGLANTI TESTI")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise Exception("GitHub Secrets bulunamadi!")

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

    url = BASE_URL + "/fapi/v3/account?" + query + "&signature=" + signature

    response = requests.get(
        url,
        headers={"X-MBX-APIKEY": api_key},
        timeout=20
    )

    if response.status_code != 200:
        print("API HATA KODU:", response.status_code)
        print("MESAJ:", response.text[:500])
        return

    data = response.json()

    print("BAGLANTI BASARILI!")
    print("Toplam cüzdan bakiyesi:", data.get("totalWalletBalance"))
    print("Kullanilabilir bakiye:", data.get("availableBalance"))
    print("Acik pozisyon sayisi:", sum(
        1 for p in data.get("positions", [])
        if float(p.get("positionAmt", 0)) != 0
    ))
    print("EMIR GONDERILMEDI.")

if __name__ == "__main__":
    main()
