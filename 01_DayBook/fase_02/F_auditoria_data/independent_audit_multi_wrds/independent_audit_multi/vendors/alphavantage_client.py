import os, requests, pandas as pd
from datetime import datetime

BASE = "https://www.alphavantage.co/query"

def fetch_alphavantage_1min(symbol: str, date: str, api_key: str = None):
    """
    Fetch 1-minute OHLCV data from Alpha Vantage API for a specific date

    WARNING: Alpha Vantage has strict rate limits:
    - Free tier: 5 API calls per minute, 100 per day
    - Must use 'month' parameter to get historical data (cannot query single day directly)

    Args:
        symbol: Stock ticker (e.g., 'AAPL')
        date: Date in YYYY-MM-DD format
        api_key: Alpha Vantage API key (or from env ALPHAVANTAGE_API_KEY)

    Returns:
        DataFrame with columns: t, open, high, low, close, volume
    """
    if api_key is None:
        api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("ALPHAVANTAGE_API_KEY not set.")

    # Extract year-month from date (Alpha Vantage requires month parameter)
    dt = datetime.strptime(date, "%Y-%m-%d")
    month = dt.strftime("%Y-%m")

    # Alpha Vantage TIME_SERIES_INTRADAY endpoint
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "1min",
        "month": month,  # Required for historical data (YYYY-MM)
        "outputsize": "full",  # Get full month
        "apikey": api_key,
        "datatype": "json"
    }

    try:
        r = requests.get(BASE, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()

        # Check for API errors
        if "Error Message" in data:
            raise RuntimeError(f"Alpha Vantage API error: {data['Error Message']}")

        if "Note" in data:
            raise RuntimeError(f"Alpha Vantage rate limit: {data['Note']}")

        # Alpha Vantage returns data in "Time Series (1min)" key
        time_series_key = "Time Series (1min)"
        if time_series_key not in data:
            return pd.DataFrame(columns=["t", "open", "high", "low", "close", "volume"])

        time_series = data[time_series_key]

        # Convert to DataFrame
        records = []
        for timestamp, values in time_series.items():
            records.append({
                "timestamp": timestamp,
                "open": values.get("1. open"),
                "high": values.get("2. high"),
                "low": values.get("3. low"),
                "close": values.get("4. close"),
                "volume": values.get("5. volume")
            })

        df = pd.DataFrame(records)

        # Parse timestamp (format: "2025-05-13 09:30:00")
        # Alpha Vantage returns times in US/Eastern by default
        try:
            import pytz
            eastern = pytz.timezone("US/Eastern")
            dt_parsed = pd.to_datetime(df["timestamp"], errors="coerce")
            dt_parsed = dt_parsed.dt.tz_localize(eastern, nonexistent='NaT', ambiguous='NaT').dt.tz_convert("UTC")
            df["t"] = dt_parsed
        except Exception:
            # Fallback: assume UTC
            df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

        # Filter to only the requested date (since we got full month)
        df["date_only"] = df["t"].dt.date
        target_date = dt.date()
        df = df[df["date_only"] == target_date]

        # Convert types
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

        # Select and sort
        out = df[["t", "open", "high", "low", "close", "volume"]].dropna(subset=["t"]).sort_values("t")

        return out

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Alpha Vantage API request failed: {str(e)}")
