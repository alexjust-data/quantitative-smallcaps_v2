import os, requests, pandas as pd
from datetime import datetime

BASE = "https://api.twelvedata.com"

def fetch_twelvedata_1min(symbol: str, date: str, api_key: str = None):
    """
    Fetch 1-minute OHLCV data from Twelve Data API for a specific date

    Args:
        symbol: Stock ticker (e.g., 'AAPL')
        date: Date in YYYY-MM-DD format
        api_key: Twelve Data API key (or from env TWELVEDATA_API_KEY)

    Returns:
        DataFrame with columns: t, open, high, low, close, volume
    """
    if api_key is None:
        api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key:
        raise RuntimeError("TWELVEDATA_API_KEY not set.")

    # Twelve Data requires start_date and end_date
    # Format: YYYY-MM-DD
    url = f"{BASE}/time_series"
    params = {
        "symbol": symbol,
        "interval": "1min",
        "start_date": f"{date} 00:00:00",
        "end_date": f"{date} 23:59:59",
        "timezone": "UTC",  # Request data in UTC
        "apikey": api_key,
        "format": "JSON"
    }

    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        # Check for API error messages
        if "status" in data and data["status"] == "error":
            raise RuntimeError(f"Twelve Data API error: {data.get('message', 'Unknown error')}")

        # Extract values array
        if "values" not in data or not data["values"]:
            return pd.DataFrame(columns=["t", "open", "high", "low", "close", "volume"])

        values = data["values"]

        # Convert to DataFrame
        df = pd.DataFrame(values)

        # Parse timestamp (format: "2025-05-13 09:30:00")
        df["t"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")

        # Rename columns to match our schema
        df = df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume"
        })

        # Convert OHLC to float, volume to int
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

        # Select and sort
        out = df[["t", "open", "high", "low", "close", "volume"]].dropna(subset=["t"]).sort_values("t")

        return out

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Twelve Data API request failed: {str(e)}")
