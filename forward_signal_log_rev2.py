#!/usr/bin/env python3
"""
Forward-test signal log  (rev2, 2026-09-24)
Runs the unchanged HTF book engine (engine/htf_book_engine_rev1.py) on the latest repo data and
keeps an APPEND-ONLY log of every X3 / X2 signal with the state filters at entry.
Output: data/forward/forward_signals_rev2.csv   (rev1's forward_signals_rev1.csv is not touched)

WHAT CHANGED vs rev1
  1. "LIVE" IS DEFINED BY THE DATA, NOT A 36h CLOCK.
     rev1: live = logged within 36h of entry. The engine only sees whole UTC days and Binance's
     daily archive can land a day late, so real live signals were logged 26-50h after entry and
     were marked live=False forever.
     rev2: every run records, per coin, the data end it processed (data/forward/forward_runs_rev2.csv).
     A new signal is live if its entry bar was NOT in the data of the previous run, i.e. it
     appeared the first time its bar could be seen. A signal that shows up only later, although its
     bar was already in earlier data, is live=False (repaint / late appearance).
     The first run has no previous run: its rows are live=False (backfill), EXCEPT for BTC/ETH,
     where the previous data end is seeded from forward_signals_rev1.csv (rev1's last run).
     log_lag_h (first_logged - entry, hours) is kept as information only.
  2. 4 COINS: BTC, ETH, XRP, BNB (HYPE excluded, as in the research). Candles are built with
     prep_candles_rev2.prepare() - the same gap-fill as the research sessions; unknown gaps are
     printed and written to the run log.
  3. COSTS ON THE RESEARCH BASIS: R_F063 is the headline (0.063% RT), R_F080 and R_F040 alongside,
     fees charged half on entry and half on exit notional (same as recheck_edges_rev1.py), and
     FUNDING charged: long pays, short receives, settlements strictly inside (entry, exit].
       * settled funding from data/{SYM}USDT-funding.csv where it exists;
       * after the last settled rate (the monthly archive lags up to a month) funding is ESTIMATED
         from the premium index (data/extra/{SYM}USDT-premium-1h.csv):
             rate = mean premium over the funding interval + clamp(I - premium, -0.05%, +0.05%),
             I = 0.01% per 8h (scaled to the coin's interval; 0 for BNB - see INTEREST_8H).
         Checked against settled funding 2024-01..2026-08: correlation 0.91-0.95 per coin, mean
         within 0.3 bp per settlement.
         ASSUMPTIONS (flagged): Binance's published formula as I understand it; mean of hourly
         premium closes stands in for Binance's 5-second sampling; settlement times are multiples
         of the last known interval from 00:00 UTC. Set FUNDING_EST=0 to switch the estimate off.
       * where neither exists yet the settlement counts 0 and is counted in fund_unknown_n.
  4. Filters, TAKE/SKIP rule, VANISHED handling and backfill start (2026-07-01): unchanged.

Inputs : data/{SYM}USDT-15m.csv, -funding.csv, data/extra/{SYM}USDT-premium-1h.csv,
         data/state/{SYM}USDT-state-1h.csv (build_market_state_rev2.py), engine/, prep_candles_rev2.py
"""
import os, sys, datetime as dt, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "engine")); sys.path.insert(0, HERE)
from htf_common_rev1 import prep, DAYB, FLOOR                    # noqa: E402
from htf_book_engine_rev1 import BOOKS, signals, sim_exit         # noqa: E402
from prep_candles_rev2 import prepare                             # noqa: E402

DATA = os.environ.get("DATA_DIR", "data")
FWD = os.path.join(DATA, "forward")
OUT = os.path.join(FWD, "forward_signals_rev2.csv")
RUNS = os.path.join(FWD, "forward_runs_rev2.csv")
REV1 = os.path.join(FWD, "forward_signals_rev1.csv")
SYMBOLS = ("BTC", "ETH", "XRP", "BNB")
LOG_BACKFILL_FROM = pd.Timestamp("2026-07-01")
CROWD_THR = 0.151
FEES = {"F080": 0.00080, "F063": 0.00063, "F040": 0.000395}
FUNDING_EST = os.environ.get("FUNDING_EST", "1") != "0"
# interest-rate part of the funding formula, per 8h. BNB uses 0: checked 2024-01..2026-08 against
# settled funding, the estimate tracks it with I=0 (corr 0.95, mean -0.96 vs -1.23 bp) and not with
# 0.01% (mean +5.4 bp). BTC/ETH/XRP with 0.01%: corr 0.91-0.93, mean within 0.2 bp of settled.
INTEREST_8H = {"BNB": 0.0}
KEY = ["book", "sym", "entry_time", "side", "ent"]


# ---------------- candles ----------------
def write_engine_candles(sym, tmp):
    raw = pd.read_csv(os.path.join(DATA, f"{sym}USDT-15m.csv"))
    d, unknown = prepare(raw, f"{sym}USDT", "15m")
    for u in unknown:
        print(f"WARNING {sym}: gap {u['first_missing']} .. {u['last_missing']} ({u['bars']} bars) filled flat")
    d[["open_time", "open", "high", "low", "close"]].to_csv(os.path.join(tmp, f"{sym}USDT15m.csv"), index=False)
    return len(unknown)


# ---------------- signals (rev1 logic, unchanged) ----------------
def book_signals(sym, data_dir):
    m = prep(sym, data_dir); sig = []
    for j in range(1, len(m.weeks)):
        w, pw = m.weeks[j], m.weeks[j - 1]
        if not m.wfull[pw]: continue
        a = m.ds[m.wk_start[w]]; b = m.ds[m.wk_start[m.weeks[j + 1]]] if j + 1 < len(m.weeks) else m.n
        signals(m, a, b, m.wH[pw], 1, "PW", sig); signals(m, a, b, m.wL[pw], -1, "PW", sig)
    for p in range(5, m.nd - 6):
        for s, X in ((1, m.dH), (-1, m.dL)):
            w = X[p - 5:p + 6]
            ok = (X[p] == w.max() if s == 1 else X[p] == w.min()) and (w == X[p]).sum() == 1
            if not ok: continue
            act, P = p + 6, X[p]
            if (s == 1 and m.dC[act - 1] >= P) or (s == -1 and m.dC[act - 1] <= P): continue
            end = min(act + 120, m.nd); dc = m.dC[act:end]
            dead = np.nonzero(dc > P)[0] if s == 1 else np.nonzero(dc < P)[0]
            b = m.ds[act + dead[0]] + DAYB if len(dead) else m.ds[end - 1] + DAYB
            signals(m, m.ds[act], min(b, m.n), P, s, "SW", sig)
    S = pd.DataFrame(sig)
    S["prio"] = (S.lvl != "PW") * 2 + (S.ent != "ACC") * 1
    S = S.sort_values(["i", "prio"], kind="mergesort").reset_index(drop=True)
    rows = []
    data_end = m.ts[-1] + pd.Timedelta(minutes=15)
    for bk, (T, H) in BOOKS.items():
        free = -1
        for r in S.itertuples():
            if r.i <= free: continue
            entry, stop = r.entry, r.stop
            raw = r.d * (entry - stop) / entry
            if raw <= 0: continue
            if raw < FLOOR: stop = entry * (1 - r.d * FLOOR)
            R, xi = sim_exit(m, r.i, r.d, entry, stop, T, H, r.fb)
            if R is None: continue
            risk = abs(entry - stop)
            closed = R in (-1.0, float(T)) or (r.i + 1 + H) <= m.n
            rows.append(dict(book=bk, sym=sym, entry_time=m.ts[r.i] + pd.Timedelta(minutes=15),
                             side="long" if r.d == 1 else "short", d=r.d, lvl=r.lvl, ent=r.ent,
                             level_px=r.level_px, entry=entry, stop=stop, risk=risk,
                             target=entry + r.d * T * risk, risk_pct=100 * risk / entry,
                             status="closed" if closed else "open",
                             exit_time=(m.ts[xi] + pd.Timedelta(minutes=15)),
                             R_gross=R, data_end=data_end))
            free = xi
    return pd.DataFrame(rows), data_end


# ---------------- funding + fees ----------------
def load_funding(sym):
    p = os.path.join(DATA, f"{sym}USDT-funding.csv")
    f = pd.read_csv(p)
    t = pd.to_datetime(f.funding_time, unit="ms").dt.floor("min")
    iv = pd.to_numeric(f.funding_interval_hours, errors="coerce").dropna()
    interval = int(iv.iloc[-1]) if len(iv) else 8
    prem = None
    pp = os.path.join(DATA, "extra", f"{sym}USDT-premium-1h.csv")
    if os.path.exists(pp):
        pr = pd.read_csv(pp)
        prem = pd.Series(pr.close.values, index=pd.to_datetime(pr.open_time, unit="ms"))
    return dict(sym=sym, t=t.values, rate=f.funding_rate.values.astype(float), tmax=t.max(),
                interval=interval, prem=prem)


def est_rate(F, S):
    """Premium-index estimate of the funding settled at time S (None if premium doesn't cover it)."""
    if F["prem"] is None: return None
    h = F["interval"]
    w = F["prem"][(F["prem"].index >= S - pd.Timedelta(hours=h)) & (F["prem"].index < S)]
    if len(w) < h: return None
    p = float(w.mean()); I = INTEREST_8H.get(F["sym"], 0.0001) * h / 8
    return p + float(np.clip(I - p, -0.0005, 0.0005))


def funding_cost(F, t0, t1):
    """Sum of rates strictly inside (t0, t1]: settled, then estimated after the last settled rate."""
    t0, t1 = pd.Timestamp(t0), pd.Timestamp(t1)
    tv = F["t"]
    a = np.searchsorted(tv, np.datetime64(t0), side="right")
    b = np.searchsorted(tv, np.datetime64(min(t1, F["tmax"])), side="right")
    total, n_set, n_est, n_unk = float(F["rate"][a:b].sum()), int(max(b - a, 0)), 0, 0
    lo = max(t0, F["tmax"])
    if t1 > lo:
        h = F["interval"]
        S = lo.floor(f"{h}h") + pd.Timedelta(hours=h)
        while S <= t1:
            r = est_rate(F, S) if FUNDING_EST else None
            if r is None: n_unk += 1
            else: total += r; n_est += 1
            S += pd.Timedelta(hours=h)
    return total, n_set, n_est, n_unk


def add_costs(df):
    FUND = {s: load_funding(s) for s in df.sym.unique()}
    res = [funding_cost(FUND[r.sym], r.entry_time, r.exit_time if r.status == "closed" else r.data_end)
           for r in df.itertuples()]
    df["fund_rate_sum"] = [x[0] for x in res]
    df["fund_settled_n"] = [x[1] for x in res]; df["fund_est_n"] = [x[2] for x in res]
    df["fund_unknown_n"] = [x[3] for x in res]
    df["fund_R"] = df.d * df.fund_rate_sum * df.entry / df.risk
    exit_px = df.entry + df.d * df.R_gross * df.risk
    cost = (df.entry + exit_px) / df.risk
    for k, rt in FEES.items():
        df[f"R_{k}"] = df.R_gross - rt / 2 * cost - df.fund_R
    return df


# ---------------- state filters (rev1, unchanged) ----------------
def add_state(df):
    out = []
    for sym, g in df.groupby("sym"):
        p = os.path.join(DATA, "state", f"{sym}USDT-state-1h.csv")
        if not os.path.exists(p):
            out.append(g.assign(oi_chg_7d=np.nan, retail_ls_pct90=np.nan)); continue
        s = pd.read_csv(p, usecols=["open_time", "oi_chg_7d", "retail_ls_pct90"])
        s["avail"] = pd.to_datetime(s.open_time, unit="ms") + pd.Timedelta(hours=1)
        g = pd.merge_asof(g.sort_values("entry_time"), s[["avail", "oi_chg_7d", "retail_ls_pct90"]].sort_values("avail"),
                          left_on="entry_time", right_on="avail", direction="backward",
                          tolerance=pd.Timedelta(hours=6)).drop(columns="avail")
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    short_ok = df.oi_chg_7d >= 0
    df["filter_note"] = np.where(df.side == "short",
                                 np.where(short_ok, "OI up 7d: ok", "OI down/unknown: skip"),
                                 np.where(df.retail_ls_pct90 > CROWD_THR, "crowded long (info)", ""))
    df["action"] = np.where((df.book == "X3") & (df.side == "short") & ~short_ok, "SKIP", "TAKE")
    return df


# ---------------- run log / live flag ----------------
def previous_data_end():
    """{sym: data end of the latest earlier run}; seeded from rev1 for BTC/ETH on the first rev2 run."""
    if os.path.exists(RUNS):
        r = pd.read_csv(RUNS, parse_dates=["run_utc", "data_end"])
        return r.groupby("sym").data_end.max().to_dict(), r
    prev, rows = {}, []
    if os.path.exists(REV1):
        o = pd.read_csv(REV1, parse_dates=["data_end", "first_logged_utc"])
        for s, g in o.groupby("sym"):
            prev[s] = g.data_end.max()
            rows.append(dict(run_utc=g.first_logged_utc.max(), sym=s, data_end=g.data_end.max(),
                             unknown_gaps=0, note="seed from forward_signals_rev1"))
    return prev, pd.DataFrame(rows, columns=["run_utc", "sym", "data_end", "unknown_gaps", "note"])


def main():
    import tempfile
    now = pd.Timestamp(dt.datetime.now(dt.timezone.utc)).tz_localize(None).floor("min")
    prev_end, runs = previous_data_end()
    frames, ends, gaps = [], {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        for s in SYMBOLS:
            gaps[s] = write_engine_candles(s, tmp)
            f, ends[s] = book_signals(s, tmp); frames.append(f)
    cur = pd.concat(frames, ignore_index=True)
    cur = cur[cur.entry_time >= LOG_BACKFILL_FROM]
    cur = add_state(add_costs(cur))
    cur = cur.drop(columns=["d", "risk", "fund_rate_sum"])

    os.makedirs(FWD, exist_ok=True)
    if os.path.exists(OUT):
        old = pd.read_csv(OUT, parse_dates=["entry_time", "exit_time", "first_logged_utc", "data_end",
                                            "data_end_at_first_log"])
    else:
        old = pd.DataFrame(columns=KEY + ["first_logged_utc", "data_end_at_first_log", "live"])
    keep = old.set_index(KEY)[["first_logged_utc", "data_end_at_first_log", "live"]] if len(old) else None
    cur = cur.set_index(KEY)
    if keep is not None:
        cur = cur.join(keep, how="left")
    else:
        cur["first_logged_utc"] = pd.NaT; cur["data_end_at_first_log"] = pd.NaT; cur["live"] = np.nan
    cur["live"] = cur["live"].astype(object)
    new = cur.first_logged_utc.isna()
    et = pd.Series(cur.index.get_level_values("entry_time"), index=cur.index)
    sy = pd.Series(cur.index.get_level_values("sym"), index=cur.index)
    pe = sy.map(lambda s: prev_end.get(s, pd.NaT))
    cur.loc[new, "first_logged_utc"] = now
    cur.loc[new, "data_end_at_first_log"] = sy[new].map(ends)
    cur.loc[new, "live"] = (pe[new].notna() & (et[new] > pe[new])).values
    if keep is not None:
        gone = keep.index.difference(cur.index)
        if len(gone):
            g = old.set_index(KEY).loc[gone].copy(); g["status"] = "VANISHED (repaint?)"
            cur = pd.concat([cur, g])
    cur["live"] = cur["live"].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
    cur["log_lag_h"] = ((pd.to_datetime(cur.first_logged_utc) - pd.to_datetime(cur.index.get_level_values("entry_time")))
                        / pd.Timedelta(hours=1)).round(1)
    cur = cur.reset_index().sort_values(["entry_time", "book", "sym"])
    cols = KEY + ["lvl", "level_px", "entry", "stop", "target", "risk_pct", "status", "exit_time",
                  "R_gross", "R_F063", "R_F080", "R_F040", "fund_R", "fund_settled_n", "fund_est_n",
                  "fund_unknown_n", "data_end", "oi_chg_7d", "retail_ls_pct90", "filter_note", "action",
                  "first_logged_utc", "data_end_at_first_log", "live", "log_lag_h"]
    cur[cols].to_csv(OUT, index=False, float_format="%.6g")

    # run log: one row per coin whose data end moved (so an unchanged re-run commits nothing)
    add = [dict(run_utc=now, sym=s, data_end=e, unknown_gaps=gaps[s], note="")
           for s, e in ends.items() if pd.isna(prev_end.get(s)) or e > prev_end.get(s)]
    if add or not os.path.exists(RUNS):
        pd.concat([runs, pd.DataFrame(add)], ignore_index=True).to_csv(RUNS, index=False)

    fresh = cur[cur.first_logged_utc == now]
    print(f"log: {len(cur)} rows ({len(fresh)} new, {int(fresh.live.sum())} of them live) -> {OUT}")
    print("data end per coin:", {s: str(e) for s, e in ends.items()})
    show = cur[cur.book == "X3"].tail(12)[["sym", "entry_time", "side", "lvl", "ent", "status",
                                            "R_gross", "R_F063", "oi_chg_7d", "action", "live"]]
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
