#!/usr/bin/env python3
"""
Market-state table builder  (rev2: skips empty or header-only input files instead of crashing)
One row per coin per 1h bar: everything we know about positioning and flow at that hour.
Any study joins its trades to this ONE table instead of re-deriving inputs.

Reads  : data/{SYM}-1h.csv, data/{SYM}-metrics.csv, data/{SYM}-funding.csv   (existing repo)
         data/extra/*  (optional - used when present: premium, spot, coinbase, DVOL, CFTC,
                         Deribit options snapshots)
Writes : data/state/{SYM}-state-1h.csv

NO-LOOKAHEAD RULE: a row stamped T (bar open time) only uses information available at
T + 1h, i.e. at the close of that bar. To use it for an entry at time E, take the last row
with open_time + 1h <= E (helper: state_at(), below).
  * metrics (5-min snapshots): the last snapshot with create_time <= bar close.
  * funding: the last settled funding rate <= bar close.
  * CFTC: reports are as-of Tuesday, published Friday 15:30 ET -> made available
    from the following Saturday 00:00 UTC (report date + 4 days).  [assumption, flagged]
  * Rolling percentiles use trailing windows only.

Columns (all floats; NaN where the source doesn't cover that period)
  close, ret_4h, ret_24h
  perp_cvd_4h, perp_cvd_24h     net taker buying / volume over window, range -1..1
  oi_chg_24h, oi_chg_7d         % change in open interest (contracts)
  lev_ratio_pct90               OI value / 24h quote volume, trailing-90d percentile (0-1)
  retail_ls, retail_ls_pct90    Binance account long/short ratio, level + 90d percentile
  top_ls, top_ls_pct90          top-trader POSITION long/short ratio, level + 90d percentile
  top_minus_retail              top_ls_pct90 - retail_ls_pct90 (smart vs crowd)
  taker_ls_24h                  mean taker long/short volume ratio over 24h
  funding_last                  last settled funding rate
  -- from data/extra when present --
  prem_8h                       mean premium index over last 8h (live funding proxy)
  spot_cvd_24h, spot_share_24h  spot net taker buying/volume; spot volume share of spot+perp
  cb_premium_bps, cb_premium_24h   Coinbase USD vs Binance USDT spot, in bps (BTC/ETH)
  dvol, dvol_chg_24h            Deribit implied vol index (BTC/ETH)
  cftc_levfund_net_pct          CME leveraged funds (net long - short) / OI   (BTC only)
  cftc_assetmgr_net_pct         CME asset managers   (net long - short) / OI  (BTC only)
  opt_skew10, opt_pc_oi         Deribit 10% OTM put-call IV skew, put/call OI (forward only)
"""
import os, numpy as np, pandas as pd

DATA = "data"; EXTRA = os.path.join(DATA, "extra"); OUT = os.path.join(DATA, "state")
COINS = ["BTC", "ETH", "XRP", "BNB", "HYPE"]
H = pd.Timedelta(hours=1)


def _read(path, **kw):
    """None if the file is missing, empty or header-only (e.g. a collector run cut short)."""
    if not os.path.exists(path): return None
    try:
        df = pd.read_csv(path, low_memory=False, **kw)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return None
    return df if len(df) else None

def _ms(s):
    return pd.to_datetime(s, unit="ms", utc=True)

def roll_pct(s, win):
    """Trailing percentile of the latest value inside a window of `win` rows (0..1)."""
    return s.rolling(win, min_periods=win // 3).rank(pct=True)

def asof(left_idx, right, cols, avail_col="avail"):
    """For each time in left_idx take the last right row with avail <= time."""
    r = right.sort_values(avail_col).copy()
    r[avail_col] = r[avail_col].astype("datetime64[ns, UTC]")
    l = pd.DataFrame({"t": pd.DatetimeIndex(left_idx).astype("datetime64[ns, UTC]")})
    m = pd.merge_asof(l, r[[avail_col] + cols], left_on="t", right_on=avail_col, direction="backward")
    m.index = left_idx
    return m[cols]


def build(coin):
    sym = f"{coin}USDT"
    k = _read(os.path.join(DATA, f"{sym}-1h.csv"))
    if k is None: return None
    k.index = _ms(k.open_time); k = k[~k.index.duplicated()].sort_index()
    close_t = k.index + H                                   # info available at bar close
    st = pd.DataFrame(index=k.index)
    st["close"] = k.close
    st["ret_4h"] = k.close.pct_change(4)
    st["ret_24h"] = k.close.pct_change(24)
    delta = 2 * k.taker_buy_base - k.volume
    for w in (4, 24):
        st[f"perp_cvd_{w}h"] = delta.rolling(w).sum() / k.volume.rolling(w).sum()
    qvol24 = (k.close * k.volume).rolling(24).sum()           # approx quote volume

    # ---- metrics (5-min OI / long-short)
    m = _read(os.path.join(DATA, f"{sym}-metrics.csv"))
    if m is not None:
        m["avail"] = pd.to_datetime(m.create_time, utc=True)
        m = m.drop_duplicates("avail")
        cols = ["sum_open_interest", "sum_open_interest_value", "count_long_short_ratio",
                "sum_toptrader_long_short_ratio", "sum_taker_long_short_vol_ratio"]
        for c in cols: m[c] = pd.to_numeric(m[c], errors="coerce")
        a = asof(close_t, m, cols); a.index = st.index
        # stale guard: if the last snapshot is >6h old, treat as missing (recent Binance dumps have multi-hour holes)
        last_av = asof(close_t, m.assign(av2=m.avail), ["av2"]).av2.values
        stale = (close_t.values - last_av) > np.timedelta64(6, "h")
        a[stale] = np.nan
        oi = a.sum_open_interest
        st["oi_chg_24h"] = oi.pct_change(24, fill_method=None)
        st["oi_chg_7d"] = oi.pct_change(168, fill_method=None)
        st["lev_ratio_pct90"] = roll_pct(a.sum_open_interest_value / qvol24, 24 * 90)
        st["retail_ls"] = a.count_long_short_ratio
        st["retail_ls_pct90"] = roll_pct(a.count_long_short_ratio, 24 * 90)
        st["top_ls"] = a.sum_toptrader_long_short_ratio
        st["top_ls_pct90"] = roll_pct(a.sum_toptrader_long_short_ratio, 24 * 90)
        st["top_minus_retail"] = st.top_ls_pct90 - st.retail_ls_pct90
        st["taker_ls_24h"] = a.sum_taker_long_short_vol_ratio.rolling(24, min_periods=12).mean()

    # ---- funding (settled)
    f = _read(os.path.join(DATA, f"{sym}-funding.csv"))
    if f is not None:
        f["avail"] = _ms(f.funding_time)
        a = asof(close_t, f, ["funding_rate"]); a.index = st.index
        last_f = f.avail.max()
        st["funding_last"] = a.funding_rate.where(close_t <= last_f + pd.Timedelta(hours=8))

    # ---- extra: premium index
    p = _read(os.path.join(EXTRA, f"{sym}-premium-1h.csv"))
    if p is not None:
        p.index = _ms(p.open_time); p = p[~p.index.duplicated()]
        st["prem_8h"] = p.close.reindex(st.index).rolling(8, min_periods=6).mean()

    # ---- extra: spot klines
    s = _read(os.path.join(EXTRA, f"{sym}-spot-1h.csv"))
    if s is not None:
        s.index = _ms(s.open_time); s = s[~s.index.duplicated()].reindex(st.index)
        sd = 2 * s.taker_buy_base - s.volume
        st["spot_cvd_24h"] = sd.rolling(24).sum() / s.volume.rolling(24).sum()
        st["spot_share_24h"] = s.volume.rolling(24).sum() / (s.volume.rolling(24).sum() + k.volume.rolling(24).sum())
        spot_close = s.close
    else:
        spot_close = None

    # ---- extra: Coinbase premium (BTC, ETH)
    cb = _read(os.path.join(EXTRA, f"coinbase-{coin}-USD-1h.csv"))
    if cb is not None and spot_close is not None:
        cb.index = _ms(cb.open_time); cb = cb[~cb.index.duplicated()].reindex(st.index)
        prem = (cb.close / spot_close - 1) * 1e4
        st["cb_premium_bps"] = prem
        st["cb_premium_24h"] = prem.rolling(24, min_periods=12).mean()

    # ---- extra: DVOL (BTC, ETH)
    dv = _read(os.path.join(EXTRA, f"deribit-dvol-{coin}-1h.csv"))
    if dv is not None:
        dv.index = _ms(dv.open_time); dv = dv[~dv.index.duplicated()].reindex(st.index)
        st["dvol"] = dv.close
        st["dvol_chg_24h"] = dv.close - dv.close.shift(24)

    # ---- extra: CFTC (BTC)
    if coin == "BTC":
        c = _read(os.path.join(EXTRA, "cftc-cme-bitcoin-tff.csv"))
        if c is not None:
            c["avail"] = _ms(c.report_time) + pd.Timedelta(days=4)
            c["lev"] = (c.lev_money_positions_long - c.lev_money_positions_short) / c.open_interest_all
            c["am"] = (c.asset_mgr_positions_long - c.asset_mgr_positions_short) / c.open_interest_all
            a = asof(close_t, c, ["lev", "am"]); a.index = st.index
            st["cftc_levfund_net_pct"] = a.lev
            st["cftc_assetmgr_net_pct"] = a.am

    # ---- extra: Deribit options snapshots (forward only)
    if coin in ("BTC", "ETH"):
        o = _read(os.path.join(EXTRA, f"deribit-options-{coin}.csv"))
        if o is not None:
            o["avail"] = _ms(o.snap_time)
            a = asof(close_t, o, ["skew10_put_minus_call", "put_call_oi_ratio_45d"]); a.index = st.index
            snap_t = asof(close_t, o.assign(a2=o.avail), ["a2"]).a2.values
            fresh = pd.Series((close_t.values - snap_t) <= np.timedelta64(2, "D"), index=st.index)
            st["opt_skew10"] = a.skew10_put_minus_call.where(fresh)
            st["opt_pc_oi"] = a.put_call_oi_ratio_45d.where(fresh)

    st.insert(0, "open_time", ((st.index - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)).astype("int64"))
    return st


def state_at(state, t):
    """Row of `state` usable for a decision at time t (last bar CLOSED at or before t)."""
    return state.loc[: t - H].iloc[-1]


def main():
    os.makedirs(OUT, exist_ok=True)
    for coin in COINS:
        st = build(coin)
        if st is None: continue
        path = os.path.join(OUT, f"{coin}USDT-state-1h.csv")
        st.round(6).to_csv(path, index=False)
        print(f"{coin}: {len(st):,} rows, {st.shape[1]} cols -> {path}")

if __name__ == "__main__":
    main()
