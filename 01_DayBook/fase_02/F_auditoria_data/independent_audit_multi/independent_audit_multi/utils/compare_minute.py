import numpy as np, pandas as pd
def compare_ohlcv(df_ref: pd.DataFrame, df_ours: pd.DataFrame, price_tol=0.002, vol_tol=0.05):
    df_ref = df_ref.copy().sort_values("t").drop_duplicates("t")
    df_ours = df_ours.copy().sort_values("t").drop_duplicates("t")
    df_ref["t_min"] = df_ref["t"].dt.floor("min")
    df_ours["t_min"] = df_ours["t"].dt.floor("min")
    m = pd.merge(df_ref, df_ours, on="t_min", how="inner", suffixes=("_ref","_ours"))
    if m.empty: return {"rows_compared": 0, "match_rate": 0.0, "breaks": [], "stats": {}}
    def rd(a,b):
        denom = np.where(np.abs(b)<1e-12, 1.0, b); return (a-b)/denom
    m["d_open"]=abs(rd(m["open_ours"],m["open_ref"])); m["d_high"]=abs(rd(m["high_ours"],m["high_ref"]))
    m["d_low"]=abs(rd(m["low_ours"],m["low_ref"])); m["d_close"]=abs(rd(m["close_ours"],m["close_ref"])); m["d_vol"]=abs(rd(m["volume_ours"],m["volume_ref"]))
    m["d_price_max"]=m[["d_open","d_high","d_low","d_close"]].max(axis=1); m["pass"]=(m["d_price_max"]<=price_tol)&(m["d_vol"]<=vol_tol)
    rows=len(m); passed=int(m["pass"].sum()); match_rate=(passed/rows) if rows else 0.0
    br=m.loc[~m["pass"],["t_min","open_ref","high_ref","low_ref","close_ref","volume_ref","open_ours","high_ours","low_ours","close_ours","volume_ours","d_price_max","d_vol"]]
    breaks=br.to_dict(orient="records")
    stats={"rows":rows,"passed":passed,"match_rate":match_rate,"mean_d_price":float(m["d_price_max"].mean() if rows else 0.0),"mean_d_vol":float(m["d_vol"].mean() if rows else 0.0),"p95_d_price":float(m["d_price_max"].quantile(0.95) if rows else 0.0),"p95_d_vol":float(m["d_vol"].quantile(0.95) if rows else 0.0)}
    return {"rows_compared":rows,"match_rate":match_rate,"breaks":breaks,"stats":stats}
