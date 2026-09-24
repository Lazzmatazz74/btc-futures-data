#!/usr/bin/env python3
"""comp_rng_engine_rev1.py (2026-09-24) - compression-breakout LONG, range-low stop, for the daily checks.
Helpers load / resample_4h / wilder_atr / supertrend are verbatim from bounce_reclaim_rev2.py; low_third and comp()
are verbatim from recheck_edges_rev1.py (stopmode='range'); fees/funding as recheck_edges_rev1.finish().
Only change: DATA directory and symbol list are parameters; returns the trade frame (F063 incl. settled funding)."""
import numpy as np, pandas as pd

ST_ATR_LEN, ST_MULT = 10, 2.5
FEES = {"F080": 0.00080, "F063": 0.00063, "F040": 0.000395}


def load(data, sym, tf):
    df = pd.read_csv(f"{data}/{sym}{tf}.csv")
    df["dt"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("dt")[["open", "high", "low", "close", "volume"]].astype(float)


def resample_4h(d):
    return pd.DataFrame({"open": d["open"].resample("4h").first(), "high": d["high"].resample("4h").max(),
                         "low": d["low"].resample("4h").min(), "close": d["close"].resample("4h").last(),
                         "volume": d["volume"].resample("4h").sum()}).dropna()


def wilder_atr(h, l, c, n):
    pc = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs())).values
    out = np.full(len(tr), np.nan)
    if len(tr) > n:
        out[n] = np.nanmean(tr[1:n + 1])
        for i in range(n + 1, len(tr)):
            out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return pd.Series(out, index=h.index)


def supertrend(df, n=ST_ATR_LEN, mult=ST_MULT):
    h, l, c = df["high"], df["low"], df["close"]
    atr = wilder_atr(h, l, c, n); hl2 = (h + l) / 2
    up = (hl2 + mult * atr).values; lo = (hl2 - mult * atr).values; cl = c.values; av = atr.values
    fu = np.full(len(cl), np.nan); fl = np.full(len(cl), np.nan); dirn = np.full(len(cl), np.nan)
    for i in range(len(cl)):
        if np.isnan(av[i]): continue
        if (np.isnan(fu[i - 1]) if i > 0 else True):
            fu[i] = up[i]; fl[i] = lo[i]; dirn[i] = 1; continue
        fu[i] = up[i] if (up[i] < fu[i - 1] or cl[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lo[i] if (lo[i] > fl[i - 1] or cl[i - 1] < fl[i - 1]) else fl[i - 1]
        if cl[i] > fu[i - 1]: dirn[i] = 1
        elif cl[i] < fl[i - 1]: dirn[i] = -1
        else: dirn[i] = dirn[i - 1]
    return pd.Series(dirn, index=df.index)


def low_third(v, LOOK=120):
    v = np.asarray(v); out = np.zeros(len(v), bool)
    for t in range(LOOK, len(v)):
        w = v[t - LOOK:t]
        if not np.isnan(w).any() and not np.isnan(v[t]): out[t] = (w < v[t]).mean() <= 1 / 3
    return out


def comp_trades(data, syms, funding_dir):
    rows = []
    for s in syms:
        df = resample_4h(load(data, f"{s}USDT", "1h")); st = supertrend(df)
        o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"]); idx = df.index; n = len(c)
        atr = wilder_atr(df["high"], df["low"], df["close"], 14)
        cp = low_third((atr / df["close"]).values); stv = st.values; atr = atr.values
        in_pos = False; exit_bar = -1
        for t in range(20, n):
            if np.isnan(atr[t]) or np.isnan(stv[t]): continue
            if in_pos:
                if t < exit_bar: continue
                in_pos = False
            if not cp[t - 1] or not (c[t] > h[t - 20:t].max() and c[t] > o[t]): continue
            stop = l[t - 20:t].min()
            entry = c[t]; risk = entry - stop
            if risk <= 0: continue
            armed = stv[t] == 1; px = None; is_open = False
            for j in range(t + 1, n):
                if l[j] <= stop: px = min(stop, o[j]); xb = j; break
                if stv[j] == 1: armed = True
                if armed and stv[j] == -1: px = c[j]; xb = j; break
            if px is None: px = c[-1]; xb = n - 1; is_open = True
            rows.append(dict(sym=s, d=1, t_in=(idx[t] + pd.Timedelta(hours=4)).tz_localize(None),
                             t_out=(idx[xb] + pd.Timedelta(hours=4)).tz_localize(None), entry=entry, exit=px,
                             stop=stop, risk=risk, gross_R=(px - entry) / risk, open=is_open))
            in_pos = True; exit_bar = xb
    D = pd.DataFrame(rows).sort_values("t_in").reset_index(drop=True)
    fr = []
    FUND = {}
    for s in syms:
        f = pd.read_csv(f"{funding_dir}/{s}USDT-funding.csv"); t = pd.to_datetime(f.funding_time, unit="ms").dt.floor("min")
        FUND[s] = (t.values, np.r_[0, np.cumsum(f.funding_rate.values)], t.max())
    for r in D.itertuples():
        tv, cs, tmax = FUND[r.sym]
        a = np.searchsorted(tv, np.datetime64(r.t_in), side="right"); b = np.searchsorted(tv, np.datetime64(r.t_out), side="right")
        fr.append((r.d * (cs[b] - cs[a]) * r.entry / r.risk, pd.Timestamp(r.t_out) <= tmax))
    D["fund_R"] = [x[0] for x in fr]; D["fund_ok"] = [x[1] for x in fr]
    cost = (D.entry + D.exit) / D.risk
    for k, rt in FEES.items(): D[k] = D.gross_R - rt / 2 * cost - D.fund_R
    return D
