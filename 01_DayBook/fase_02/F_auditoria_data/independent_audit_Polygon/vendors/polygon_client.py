import os, requests, pandas as pd

BASE = "https://api.polygon.io"

def fetch_polygon_1min(symbol: str, date: str, api_key: str=None, adjusted: bool=True):
    if api_key is None:
        api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY not set. Export it or pass api_key.")
    url = f"{BASE}/v2/aggs/ticker/{symbol}/range/1/minute/{date}/{date}"
    params = {
        "adjusted": "true" if adjusted else "false",
        "sort": "asc",
        "apiKey": api_key
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    js = r.json()
    results = js.get("results", [])
    if not results:
        return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pd.DataFrame(results)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df = df.rename(columns={"o":"open","h":"high","l":"low","c":"close","v":"volume"})
    df = df[["t","open","high","low","close","volume"]].sort_values("t")
    return df
