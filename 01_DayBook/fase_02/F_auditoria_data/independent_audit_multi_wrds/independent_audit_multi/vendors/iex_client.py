import os, requests, pandas as pd
BASE = "https://cloud.iexapis.com/v1"
def fetch_iex_1min(symbol: str, date: str, token: str=None):
    if token is None:
        token = os.getenv("IEX_API_TOKEN")
    if not token:
        raise RuntimeError("IEX_API_TOKEN not set.")
    date_iex = date.replace("-", "")
    url = f"{BASE}/stock/{symbol}/chart/date/{date_iex}"
    params = {"token": token, "chartByDay": "false"}
    r = requests.get(url, params=params, timeout=60); r.raise_for_status()
    js = r.json()
    if not js: return pd.DataFrame(columns=["t","open","high","low","close","volume"])
    df = pd.DataFrame(js)
    if "date" in df and "minute" in df:
        dt = pd.to_datetime(df["date"] + " " + df["minute"], errors="coerce")
        try:
            import pytz
            eastern = pytz.timezone("US/Eastern")
            dt = dt.dt.tz_localize(eastern, nonexistent='NaT', ambiguous='NaT').dt.tz_convert("UTC")
        except Exception:
            dt = dt.dt.tz_localize("UTC")
        df["t"] = dt
    elif "date" in df:
        df["t"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    for col in ["open","high","low","close","volume"]:
        if col not in df.columns: df[col] = None
    out = df[["t","open","high","low","close","volume"]].dropna().sort_values("t")
    return out
