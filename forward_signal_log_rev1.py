#!/usr/bin/env python3
"""
Forward-test signal log  (rev1)
Runs the unchanged HTF book engine (htf_book_engine_rev1.py) on the latest repo data and keeps an
APPEND-ONLY log of every X3 / X2 signal with the state filters at entry.

Why: a genuine out-of-sample record that cannot be re-fitted later. The column `first_logged_utc`
is written once, when a signal first appears, and is never changed. A signal whose
first_logged_utc is much later than its entry time was NOT known live (backfill or repaint) -
those rows are flagged `live=False` and must be excluded from the forward-test verdict.

Filters recorded (they decide `action`, trades are logged either way):
  X3 SHORT : take only if 7d open-interest change >= 0 (unknown OI -> SKIP)
  LONGS    : flag 'crowded' when retail long/short 90d percentile > CROWD_THR (info; not a skip rule yet)

Inputs : data/{SYM}USDT-15m.csv (repo), data/state/{SYM}USDT-state-1h.csv (build_market_state_rev2.py)
Output : data/forward/forward_signals_rev1.csv
ASSUMPTIONS (flagged)
  * net_R_est = gross R minus 0.08% round-trip fee at entry price, funding ignored (estimate only).
  * LOG_BACKFILL_FROM: signals before the first run are written with live=False for reference.
  * 'open' trades are marked to the latest close; their R changes until they close.
"""
import os, sys, datetime as dt, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "engine"))
from htf_common_rev1 import prep, DAYB, FLOOR          # noqa: E402
from htf_book_engine_rev1 import BOOKS, signals, sim_exit   # noqa: E402

DATA = os.environ.get("DATA_DIR", "data")
OUT = os.path.join(DATA, "forward", "forward_signals_rev1.csv")
SYMBOLS = ("BTC", "ETH")
LOG_BACKFILL_FROM = pd.Timestamp("2026-07-01")
CROWD_THR = 0.151          # X3 long threshold from eval_mc_filtered_rev1 (fitted 2022-2023)
FEE_RT = 0.0008
LIVE_LAG = pd.Timedelta(hours=36)   # daily data job -> a live signal is logged within ~1.5 days
KEY = ["book", "sym", "entry_time", "side", "ent"]


def full_day_copy(sym, tmp):
    """engine expects {sym}USDT15m.csv of whole UTC days; trim the repo file accordingly"""
    df = pd.read_csv(os.path.join(DATA, f"{sym}USDT-15m.csv"))
    t = pd.to_datetime(df.open_time, unit="ms")
    first = np.nonzero((t.dt.hour == 0) & (t.dt.minute == 0))[0][0]
    df = df.iloc[first:]
    df = df.iloc[: (len(df) // DAYB) * DAYB]
    df[["open_time", "open", "high", "low", "close"]].to_csv(os.path.join(tmp, f"{sym}USDT15m.csv"), index=False)


def book_signals(sym, data_dir):
    """Same loop as htf_book_engine_rev1.run_books, plus open/closed status and signal bar."""
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
    for bk, (T, H) in BOOKS.items():
        free = -1
        for r in S.itertuples():
            if r.i <= free: continue
            entry, stop = r.entry, r.stop
            raw = r.d * (entry - stop) / entry
            if raw <= 0: continue
            if raw < FLOOR: stop = entry * (1 - r.d * FLOOR)
            R, xi = sim_exit(m, r.i, r.d, entry, stop, T, H, r.fb)
            if R is None:                       # signal on the very last bar: not tradeable yet
                continue
            risk = abs(entry - stop)
            closed = R in (-1.0, float(T)) or (r.i + 1 + H) <= m.n
            rows.append(dict(book=bk, sym=sym, entry_time=m.ts[r.i] + pd.Timedelta(minutes=15),
                             side="long" if r.d == 1 else "short", lvl=r.lvl, ent=r.ent,
                             level_px=r.level_px, entry=entry, stop=stop,
                             target=entry + r.d * T * risk, risk_pct=100 * risk / entry,
                             status="closed" if closed else "open",
                             exit_time=(m.ts[xi] + pd.Timedelta(minutes=15)) if closed else pd.NaT,
                             R_gross=R, R_net_est=R - FEE_RT * entry / risk,
                             data_end=m.ts[-1] + pd.Timedelta(minutes=15)))
            free = xi
    return pd.DataFrame(rows)


def add_state(df):
    out = []
    for sym, g in df.groupby("sym"):
        p = os.path.join(DATA, "state", f"{sym}USDT-state-1h.csv")
        if not os.path.exists(p):
            g = g.assign(oi_chg_7d=np.nan, retail_ls_pct90=np.nan); out.append(g); continue
        s = pd.read_csv(p, usecols=["open_time", "oi_chg_7d", "retail_ls_pct90"])
        s["avail"] = pd.to_datetime(s.open_time, unit="ms") + pd.Timedelta(hours=1)
        g = g.sort_values("entry_time")
        g = pd.merge_asof(g, s[["avail", "oi_chg_7d", "retail_ls_pct90"]].sort_values("avail"),
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


def main():
    import tempfile
    now = pd.Timestamp(dt.datetime.now(dt.timezone.utc)).tz_localize(None).floor("min")
    with tempfile.TemporaryDirectory() as tmp:
        for s in SYMBOLS: full_day_copy(s, tmp)
        cur = pd.concat([book_signals(s, tmp) for s in SYMBOLS], ignore_index=True)
    cur = cur[cur.entry_time >= LOG_BACKFILL_FROM]
    cur = add_state(cur)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        old = pd.read_csv(OUT, parse_dates=["entry_time", "exit_time", "first_logged_utc", "data_end"])
        first_run = False
    else:
        old = pd.DataFrame(columns=KEY + ["first_logged_utc", "live"]); first_run = True
    keep = old.set_index(KEY)[["first_logged_utc", "live"]] if len(old) else None
    cur = cur.set_index(KEY)
    if keep is not None:
        cur = cur.join(keep, how="left")
    else:
        cur["first_logged_utc"] = pd.NaT; cur["live"] = np.nan
    new = cur.first_logged_utc.isna()
    cur.loc[new, "first_logged_utc"] = now
    cur.loc[new, "live"] = (~first_run) & ((now - cur.index.get_level_values("entry_time")[new]) <= LIVE_LAG)
    # signals that were logged before but vanished now = repaint -> keep them, mark
    if keep is not None:
        gone = keep.index.difference(cur.index)
        if len(gone):
            g = old.set_index(KEY).loc[gone].copy(); g["status"] = "VANISHED (repaint?)"
            cur = pd.concat([cur, g])
    cur["live"] = cur["live"].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
    cur = cur.reset_index().sort_values(["entry_time", "book", "sym"])
    cur.to_csv(OUT, index=False, float_format="%.6g")
    print(f"log: {len(cur)} rows ({int(new.sum())} new) -> {OUT}")
    show = cur[cur.book == "X3"].tail(12)[["sym", "entry_time", "side", "lvl", "ent", "entry", "stop",
                                            "status", "R_gross", "oi_chg_7d", "action", "live"]]
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
