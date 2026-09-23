#!/usr/bin/env python3
"""htf_common_rev1.py - shared data prep + trade simulation for the HTF-level studies.
Same conventions as htf_levels_event_study_rev1.py: UTC calendar, stop-first on same-bar conflict,
risk floor 0.20%, headline exits intra_2 (2R / 24h) and swing_3 (3R / 7d).
(verbatim copy of the project file)"""
import numpy as np, pandas as pd

BAR, DAYB = 900000, 96
FLOOR = 0.002
TARGETS = [1, 2, 3, 5]
H_INTRA, H_SWING = 96, 672


class Mkt:
    pass


def supertrend_dir(H, L, C, n=10, mult=3.0):
    pc = np.r_[C[0], C[:-1]]
    tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values
    mid = (H + L) / 2
    ub, lb = mid + mult * atr, mid - mult * atr
    d = np.ones(len(C)); fu, fl = ub.copy(), lb.copy()
    for k in range(1, len(C)):
        fu[k] = ub[k] if (ub[k] < fu[k - 1] or C[k - 1] > fu[k - 1]) else fu[k - 1]
        fl[k] = lb[k] if (lb[k] > fl[k - 1] or C[k - 1] < fl[k - 1]) else fl[k - 1]
        d[k] = 1 if C[k] > fu[k - 1] else (-1 if C[k] < fl[k - 1] else d[k - 1])
    return d


def prep(sym, data="/mnt/project"):
    df = pd.read_csv(f"{data}/{sym}USDT15m.csv")
    m = Mkt(); m.sym = sym
    t = df.open_time.values
    m.o, m.h, m.l, m.c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    m.n = len(df); m.ts = pd.to_datetime(t, unit="ms")
    m.nd = m.n // DAYB
    m.ds = np.arange(m.nd) * DAYB
    m.dH = m.h.reshape(m.nd, DAYB).max(1); m.dL = m.l.reshape(m.nd, DAYB).min(1)
    m.dC = m.c.reshape(m.nd, DAYB)[:, -1]; m.dO = m.o.reshape(m.nd, DAYB)[:, 0]
    m.dts = m.ts[m.ds]
    pc = np.r_[m.dC[0], m.dC[:-1]]
    tr = np.maximum(m.dH - m.dL, np.maximum(abs(m.dH - pc), abs(m.dL - pc)))
    m.atr = pd.Series(tr).rolling(14).mean().shift(1).values        # usable on day k (through k-1)
    m.st = np.r_[1, supertrend_dir(m.dH, m.dL, m.dC)[:-1]]          # ST dir through day k-1
    m.sma50 = pd.Series(m.dC).rolling(50).mean().shift(1).values
    m.pclose = pc
    wk = (m.dts.dayofweek.values == 0).cumsum(); m.wk = wk
    m.weeks = sorted(set(wk)); m.wk_start = {w: int(np.nonzero(wk == w)[0][0]) for w in m.weeks}
    m.wH = {w: m.dH[wk == w].max() for w in m.weeks}; m.wL = {w: m.dL[wk == w].min() for w in m.weeks}
    m.wfull = {w: (wk == w).sum() == 7 for w in m.weeks}
    m.hour_end = np.arange(3, m.n, 4)
    return m
