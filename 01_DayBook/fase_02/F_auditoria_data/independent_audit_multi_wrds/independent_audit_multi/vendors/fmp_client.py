import os, requests, pandas as pd
from datetime import datetime, timedelta

BASE = "https://financialmodelingprep.com/api/v3"

def fetch_fmp_1min(symbol: str, date: str, api_key: str = None):
    """
    Fetch 1-minute OHLCV data from Financial Modeling Prep API for a specific date

    Args:
        symbol: Stock ticker (e.g., 'AAPL')
        date: Date in YYYY-MM-DD format
        api_key: FMP API key (or from env FMP)

    Returns:
        DataFrame with columns: t, open, high, low, close, volume
    """
    if api_key is None:
        api_key = os.getenv("FMP")
    if not api_key:
        raise RuntimeError("FMP API key not set (env variable: FMP).")

    # FMP historical-chart endpoint
    # Format: /historical-chart/1min/{SYMBOL}?from=YYYY-MM-DD&to=YYYY-MM-DD
    url = f"{BASE}/historical-chart/1min/{symbol}"

    # FMP requires 'from' and 'to' parameters
    params = {
        "from": date,
        "to": date,
        "apikey": api_key
    }

    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        # Check for API error
        if isinstance(data, dict) and "Error Message" in data:
            raise RuntimeError(f"FMP API error: {data['Error Message']}")

        if not data or not isinstance(data, list):
            return pd.DataFrame(columns=["t", "open", "high", "low", "close", "volume"])

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # FMP returns timestamp in format "2025-05-13 09:30:00" (US/Eastern)
        # Need to convert to UTC
        if "date" in df.columns:
            try:
                import pytz
                eastern = pytz.timezone("US/Eastern")
                # Parse as Eastern time, then convert to UTC
                dt = pd.to_datetime(df["date"], errors="coerce")
                dt = dt.dt.tz_localize(eastern, nonexistent='NaT', ambiguous='NaT').dt.tz_convert("UTC")
                df["t"] = dt
            except Exception:
                # Fallback: assume UTC
                df["t"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        else:
            raise RuntimeError("FMP response missing 'date' field")

        # Ensure all OHLCV columns exist
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = None

        # Convert types
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

        # Select and sort
        out = df[["t", "open", "high", "low", "close", "volume"]].dropna(subset=["t"]).sort_values("t")

        return out

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"FMP API request failed: {str(e)}")
