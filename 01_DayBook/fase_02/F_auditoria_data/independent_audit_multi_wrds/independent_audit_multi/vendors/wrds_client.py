import pathlib
import pandas as pd

def _parse_time_cols(df: pd.DataFrame):
    # Try common TAQ time columns: 'time_m' in milliseconds past midnight, or 'time'/'timestamp'
    if "time_m" in df.columns:
        # Assume 'date' exists as YYYY-MM-DD or YYYYMMDD
        if "date" in df.columns:
            try:
                dtdate = pd.to_datetime(df["date"].astype(str), errors="coerce")
            except Exception:
                dtdate = pd.to_datetime(df["date"], errors="coerce")
        else:
            # If no 'date' column, caller must supply per-file date in filename; this client expects 'date' present.
            raise RuntimeError("WRDS TAQ trades must include a 'date' column when using 'time_m'.")
        # time_m is milliseconds after midnight (local market time in TAQ). Assume US/Eastern then convert to UTC.
        try:
            eastern = pd.Timestamp.now(tz="US/Eastern").tz
        except Exception:
            import pytz
            eastern = pytz.timezone("US/Eastern")
        # Build timestamps
        base = pd.to_datetime(dtdate.dt.strftime("%Y-%m-%d") + " 00:00:00")
        t = base + pd.to_timedelta(df["time_m"].astype("int64"), unit="ms")
        t = t.dt.tz_localize(eastern, nonexistent="NaT", ambiguous="NaT").dt.tz_convert("UTC")
        return t
    # Fallbacks
    for col in ["timestamp","ts","time"]:
        if col in df.columns:
            t = pd.to_datetime(df[col], errors="coerce", utc=True)
            if t.dt.tz is None:
                t = t.dt.tz_localize("UTC")
            return t
    raise RuntimeError("Cannot infer time column: expected 'time_m' or 'timestamp'/'time'.")

def _eligible_trade_mask(df: pd.DataFrame, include_codes=None, exclude_codes=None):
    # TAQ trades typically have sale condition in a column like 'tr_scond' or 'sale_condition'
    sc = None
    for c in ["tr_scond","sale_condition","salecond","SaleCondition","cond","condition"]:
        if c in df.columns:
            sc = df[c].astype(str).fillna("")
            break
    if sc is None:
        # If no sale condition column, accept all
        return pd.Series([True]*len(df), index=df.index)
    sc = sc.str.upper()

    if include_codes:
        mask_inc = sc.apply(lambda s: any(code.upper() in s for code in include_codes))
    else:
        mask_inc = pd.Series([True]*len(df), index=df.index)

    if exclude_codes:
        mask_exc = sc.apply(lambda s: any(code.upper() in s for code in exclude_codes))
    else:
        mask_exc = pd.Series([False]*len(df), index=df.index)

    return mask_inc & (~mask_exc)

def load_wrds_taq_minute(wrds_root: str, symbol: str, date: str,
                         include_codes=None, exclude_codes=None):
    """
    Load WRDS/TAQ trades for a given symbol and date, filter by sale-condition codes,
    and aggregate to 1-minute OHLCV in UTC.
    Expected file layout:
      {wrds_root}/{symbol}/date={YYYY-MM-DD}/trades.csv
    with columns including at least: price, size, date, and one of time_m | timestamp | time.
    Returns DataFrame with columns: t (UTC minute), open, high, low, close, volume
    """
    p = pathlib.Path(wrds_root) / symbol / f"date={date}" / "trades.csv"
    if not p.exists():
        # Also allow pre-aggregated minute CSV if present
        p_min = p.with_name("minute.csv")
        if p_min.exists():
            dfm = pd.read_csv(p_min)
            if "t" in dfm.columns:
                dfm["t"] = pd.to_datetime(dfm["t"], utc=True, errors="coerce")
            return dfm[["t","open","high","low","close","volume"]].dropna().sort_values("t")
        return pd.DataFrame(columns=["t","open","high","low","close","volume"])

    df = pd.read_csv(p)
    # Normalize essential columns
    price_col = None
    for c in ["price","prc","trade_price","p"]:
        if c in df.columns:
            price_col = c; break
    size_col = None
    for c in ["size","shares","qty","s"]:
        if c in df.columns:
            size_col = c; break
    if price_col is None or size_col is None:
        raise RuntimeError("WRDS TAQ trades must include 'price' and 'size' (or equivalent) columns.")

    # Build timestamp
    t = _parse_time_cols(df)
    df = df.assign(_t=t).dropna(subset=["_t"])

    # Filter eligible trades by sale-condition codes (typical regular sale '@' or empty)
    mask = _eligible_trade_mask(df, include_codes=include_codes, exclude_codes=exclude_codes)
    df = df.loc[mask]

    # Aggregate to 1-minute OHLCV by floor minute
    df["_t_min"] = df["_t"].dt.floor("min")
    # Use first/last by time for open/close
    df = df.sort_values("_t")
    grp = df.groupby("_t_min")
    o = grp[price_col].first()
    h = grp[price_col].max()
    l = grp[price_col].min()
    c = grp[price_col].last()
    v = grp[size_col].sum()

    out = pd.DataFrame({"t": o.index, "open": o.values, "high": h.values, "low": l.values, "close": c.values, "volume": v.values})
    out["t"] = pd.to_datetime(out["t"], utc=True)
    return out.sort_values("t")[["t","open","high","low","close","volume"]]
