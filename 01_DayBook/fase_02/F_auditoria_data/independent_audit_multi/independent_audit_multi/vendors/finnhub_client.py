import os, requests, pandas as pd
BASE = "https://finnhub.io/api/v1"
def fetch_finnhub_1min(symbol: str, date: str, token: str=None):
    if token is None:
        token = os.getenv("FINNHUB_API_KEY")
    if not token:
        raise RuntimeError("FINNHUB_API_KEY not set.")
    start = int(pd.Timestamp(date + " 00:00:00", tz="UTC").timestamp())
    end   = int(pd.Timestamp(date + " 23:59:59", tz="UTC").timestamp())
    url = f"{BASE}/stock/candle"
    params = {"symbol": symbol, "resolution": 1, "from": start, "to": end, "token": token}
    r = requests.get(url, params=params, timeout=60); r.raise_for_status()
    js = r.json()
    if js.get("s") != "ok":
        return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pd.DataFrame({"t": js["t"], "open": js["o"], "high": js["h"], "low": js["l"], "close": js["c"], "volume": js["v"]})
    df["t"] = pd.to_datetime(df["t"], unit="s", utc=True)
    return df[["t","open","high","low","close","volume"]].sort_values("t")
