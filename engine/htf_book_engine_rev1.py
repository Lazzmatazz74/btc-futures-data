#!/usr/bin/env python3
"""htf_book_engine_rev1.py - signal + book logic copied verbatim from htf_combined_rules_rev2.py
(project file). Only changes: no plotting/CLI, returns trades with gross_R/entry/stop so any fee can be applied,
and symbols/data are parameters. ACC + FSB, PW > SW priority, one position per symbol, X2 (2R/24h), X3 (3R/7d)."""
import numpy as np, pandas as pd
from htf_common_rev1 import prep, DAYB, FLOOR

BOOKS = {"X2": (2, 96), "X3": (3, 672)}


def sim_exit(m, i, d, entry, stop, T, H, fillbar):
    risk = abs(entry - stop)
    if fillbar and ((d == 1 and m.l[i] <= stop) or (d == -1 and m.h[i] >= stop)):
        return -1.0, i
    a, b = i + 1, min(i + 1 + H, m.n)
    if a >= b:
        return None, None
    hh, ll = m.h[a:b], m.l[a:b]
    sh = np.nonzero(ll <= stop)[0] if d == 1 else np.nonzero(hh >= stop)[0]
    tp = entry + d * T * risk
    th = np.nonzero(hh >= tp)[0] if d == 1 else np.nonzero(ll <= tp)[0]
    si = sh[0] if len(sh) else 10**9; ti = th[0] if len(th) else 10**9
    if si <= ti and si < 10**9:
        return -1.0, a + si
    if ti < 10**9:
        return float(T), a + ti
    return d * (m.c[b - 1] - entry) / risk, b - 1


def signals(m, a, b, P, s, lvl, sig):
    h, l, c = m.h, m.l, m.c
    br = np.nonzero(h[a:b] > P)[0] if s == 1 else np.nonzero(l[a:b] < P)[0]
    if not len(br):
        return
    bi = a + br[0]
    he = m.hour_end[(m.hour_end >= bi) & (m.hour_end < bi + DAYB)]
    run = 0
    for x in he:
        run = run + 1 if ((c[x] > P) if s == 1 else (c[x] < P)) else 0
        if run == 4:
            stop = l[x - 15:x + 1].min() if s == 1 else h[x - 15:x + 1].max()
            sig.append(dict(i=int(x), d=s, entry=c[x], stop=stop, lvl=lvl, ent="ACC", fb=False, level_px=P)); break
    e = min(bi + 16, m.n)
    tr = np.nonzero(c[bi:e] < P)[0] if s == 1 else np.nonzero(c[bi:e] > P)[0]
    if len(tr):
        ti = bi + tr[0]
        ext = h[bi:ti + 1].max() if s == 1 else l[bi:ti + 1].min()
        e4 = min(ti + 1 + DAYB, m.n)
        b2 = np.nonzero(h[ti + 1:e4] > ext)[0] if s == 1 else np.nonzero(l[ti + 1:e4] < ext)[0]
        if len(b2):
            f = ti + 1 + b2[0]
            stop = l[ti:f].min() if s == 1 else h[ti:f].max()
            sig.append(dict(i=int(f), d=s, entry=ext, stop=stop, lvl=lvl, ent="FSB", fb=True, level_px=P))


def run_books(symbols=("BTC", "ETH"), data="/mnt/project"):
    trades = {k: [] for k in BOOKS}
    for sym in symbols:
        m = prep(sym, data); sig = []
        for j in range(1, len(m.weeks)):
            w, pw = m.weeks[j], m.weeks[j - 1]
            if not m.wfull[pw]:
                continue
            a = m.ds[m.wk_start[w]]; b = m.ds[m.wk_start[m.weeks[j + 1]]] if j + 1 < len(m.weeks) else m.n
            signals(m, a, b, m.wH[pw], 1, "PW", sig); signals(m, a, b, m.wL[pw], -1, "PW", sig)
        for p in range(5, m.nd - 6):
            for s, X in ((1, m.dH), (-1, m.dL)):
                w = X[p - 5:p + 6]
                ok = (X[p] == w.max() if s == 1 else X[p] == w.min()) and (w == X[p]).sum() == 1
                if not ok:
                    continue
                act, P = p + 6, X[p]
                if (s == 1 and m.dC[act - 1] >= P) or (s == -1 and m.dC[act - 1] <= P):
                    continue
                end = min(act + 120, m.nd); dc = m.dC[act:end]
                dead = np.nonzero(dc > P)[0] if s == 1 else np.nonzero(dc < P)[0]
                b = m.ds[act + dead[0]] + DAYB if len(dead) else m.ds[end - 1] + DAYB
                signals(m, m.ds[act], min(b, m.n), P, s, "SW", sig)
        S = pd.DataFrame(sig)
        S["prio"] = (S.lvl != "PW") * 2 + (S.ent != "ACC") * 1
        S = S.sort_values(["i", "prio"], kind="mergesort").reset_index(drop=True)
        for bk, (T, H) in BOOKS.items():
            free = -1
            for r in S.itertuples():
                if r.i <= free:
                    continue
                entry, stop = r.entry, r.stop
                raw = r.d * (entry - stop) / entry
                if raw <= 0:
                    continue
                if raw < FLOOR:
                    stop = entry * (1 - r.d * FLOOR)
                R, xi = sim_exit(m, r.i, r.d, entry, stop, T, H, r.fb)
                if R is None:
                    continue
                risk = abs(entry - stop)
                trades[bk].append(dict(sym=sym, time=m.ts[r.i] + pd.Timedelta(minutes=15),
                                       exit_time=m.ts[xi] + pd.Timedelta(minutes=15),
                                       d=r.d, lvl=r.lvl, ent=r.ent, entry=entry, stop=stop, risk=risk,
                                       exit=entry + r.d * R * risk, gross_R=R))
                free = xi
    return {k: pd.DataFrame(v) for k, v in trades.items()}
