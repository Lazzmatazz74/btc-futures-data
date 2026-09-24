#!/usr/bin/env python3
"""
move_scan_rev1.py  (2026-09-24)  -  Workstream C: does anything warn of a big 7-day move?

PRE-REGISTERED SPEC (approved by Laz 2026-09-24 20:35 local, BEFORE any result was computed)
-------------------------------------------------------------------------------------------------
Data     repo candles (15m -> UTC days) BTC/ETH/XRP/BNB to 2026-09-23; metrics via build_market_state_rev2 (unchanged);
         premium 1h and Deribit DVOL 1h from data/extra.
Unit     one observation per coin per UTC day d, taken at the daily close (d+1 00:00 UTC).
Event    ret7 = |ln(C[d+7] / C[d])|. EVENT if ret7 >= 80th percentile of the trailing 365 ret7 values that had
         already finished by close d (windows starting d-7-364 .. d-7; >= 180 needed). Base rate = realised event
         rate in the same period/coin cell (only days where the flag is defined), not a flat 20%.
Flags    (on/off; 'bottom/top third' = trailing-365-day percentile rank of that coin's own daily series, incl. d,
          >= 180 days of history; closed data only)
  C1 ATR compression        ATR14/close (simple mean of daily TR) in bottom third
  C2 Bollinger squeeze      (upper-lower)/mid of BB(20, 2 sd) in bottom third
  C3 OI building while quiet (C1 or C2) and oi_chg_7d (state row closing at d+1 00:00) in top third
  C4 premium near zero      |mean of the day's 24 hourly premium-index closes| in bottom third
  C5 near weekly level      close within 1 x ATR14 of the last completed Mon-Sun week's high or low
  C6 options cheap vs RV    DVOL / (30d realised vol, annualised x sqrt(365), %) in bottom third  (BTC/ETH only ->
                            cannot meet the 3-of-4-coin rule; information only)
  (Hyperliquid tilt excluded: snapshot history too short.)
Periods  by d: H1 < 2023-05-01 <= H2;  L12 2025-09-23..2026-07-31;  OOS >= 2026-08-01 (reported, not in the rule).
Metrics  precision = P(event | on), lift = precision / base, recall = P(on | event), n_on.  Pooled and per coin.
PASS     all of: pooled precision > base in H1 AND H2 AND L12; full-sample precision > base in >= 3 of 4 coins;
         circular-shift baseline p < 0.05 (1,000 shifts, each coin's flag series shifted by an independent random
         offset of >= 30 days; p = share of shifts with pooled full-sample lift >= actual).
         Luck check: the same (period + coin) criteria applied to shifted flags -> expected number of passes
         vs the actual number.
Stage 2  ONLY for a flag that passes.
  (a) gate on reclaim4h and comp_rng (recheck_trades_*_rev1.csv, F063 incl. funding): keep a trade only if the flag
      was on at the last daily close before entry. Success = kept runner share (>10R) > book runner share AND
      kept >= 25% of trades AND kept mean R > book mean in H1 and in H2.
  (b) direction: on flagged days followed by an event, does the side of the latest X3 ACC entry on that coin in the
      prior 7 days match the sign of the 7-day move more often than chance (binomial vs the up-share of those days)?
Seeds    numpy default_rng(20260924).
Outputs  out/move_scan_results_rev1.csv (flag x period x coin), out/move_scan_gate_rev1.csv (only if stage 2 runs).
-------------------------------------------------------------------------------------------------
"""
import sys, numpy as np, pandas as pd
W = "/home/claude/work"; RAW = "/home/claude/data"; C = f"{W}/candles"
sys.path.insert(0, W)
import build_market_state_rev2 as S
S.DATA = RAW
SYMS = ["BTC", "ETH", "XRP", "BNB"]
FLAGS = ["C1", "C2", "C3", "C4", "C5", "C6"]
H1_END, L12, OOS0 = pd.Timestamp("2023-05-01"), (pd.Timestamp("2025-09-23"), pd.Timestamp("2026-08-01")), pd.Timestamp("2026-08-01")
RNG = np.random.default_rng(20260924)
N_SHIFT = 1000


def rank365(x):
    return x.rolling(365, min_periods=180).rank(pct=True)


def daily(sym):
    c = pd.read_csv(f"{C}/{sym}USDT15m.csv"); c.index = pd.to_datetime(c.open_time, unit="ms")
    d = c.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    d = d[d.index + pd.Timedelta(days=1) <= c.index[-1] + pd.Timedelta(minutes=15)]      # complete days only
    t = pd.DataFrame(index=d.index)
    lc = np.log(d.close)
    t["ret7"] = (lc.shift(-7) - lc).abs()
    past = t.ret7.shift(7)                                   # ret7 windows that had finished by close d
    t["thr"] = past.rolling(365, min_periods=180).quantile(0.8)
    t["event"] = np.where(t.ret7.notna() & t.thr.notna(), (t.ret7 >= t.thr).astype(float), np.nan)
    t["sign7"] = np.sign(lc.shift(-7) - lc)
    pc = d.close.shift(1)
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(1)
    atr = tr.rolling(14).mean()
    t["atrn"] = atr / d.close
    mid = d.close.rolling(20).mean(); sd = d.close.rolling(20).std(ddof=0)
    t["bbw"] = 4 * sd / mid
    r_atr, r_bb = rank365(t.atrn), rank365(t.bbw)
    C1 = r_atr <= 1 / 3; C2 = r_bb <= 1 / 3
    # OI: state row stamped 23:00 of day d (available at d+1 00:00)
    st = S.build(sym)
    oi = st.oi_chg_7d; oi.index = oi.index.tz_localize(None)
    oi_d = oi[oi.index.hour == 23]; oi_d.index = oi_d.index.normalize()
    t["oi7"] = oi_d.reindex(t.index)
    r_oi = rank365(t.oi7)
    C3 = (C1 | C2) & (r_oi >= 2 / 3)
    # premium: mean of the day's 24 hourly closes
    p = pd.read_csv(f"{RAW}/extra/{sym}USDT-premium-1h.csv"); p.index = pd.to_datetime(p.open_time, unit="ms")
    pm = p.close.resample("1D").agg(["mean", "size"]); pm = pm["mean"].where(pm["size"] >= 20)
    t["prem_abs"] = pm.reindex(t.index).abs()
    r_pr = rank365(t.prem_abs); C4 = r_pr <= 1 / 3
    # last completed Mon-Sun week high/low
    wk = d.resample("W-MON", label="left", closed="left").agg({"high": "max", "low": "min"})
    wk_end = wk.index + pd.Timedelta(days=7)
    close_t = d.index + pd.Timedelta(days=1)
    j = np.searchsorted(wk_end.values, close_t.values, side="right") - 1
    wh = np.where(j >= 0, wk.high.values[np.clip(j, 0, None)], np.nan)
    wl = np.where(j >= 0, wk.low.values[np.clip(j, 0, None)], np.nan)
    dist = np.minimum(np.abs(d.close.values - wh), np.abs(d.close.values - wl))
    C5 = pd.Series(dist <= atr.values, index=t.index)
    # DVOL vs realised vol
    try:
        v = pd.read_csv(f"{RAW}/extra/deribit-dvol-{sym}-1h.csv"); v.index = pd.to_datetime(v.open_time, unit="ms")
        dv = v.close.resample("1D").last()
        rv = np.log(d.close).diff().rolling(30).std() * np.sqrt(365) * 100
        t["dvol_rv"] = dv.reindex(t.index) / rv
        C6 = rank365(t.dvol_rv) <= 1 / 3; C6 = C6.where(t.dvol_rv.notna())
    except FileNotFoundError:
        t["dvol_rv"] = np.nan; C6 = pd.Series(np.nan, index=t.index)
    defined = {"C1": r_atr.notna(), "C2": r_bb.notna(), "C3": r_oi.notna() & r_atr.notna() & r_bb.notna(),
               "C4": r_pr.notna(), "C5": atr.notna() & pd.Series(~np.isnan(wh), index=t.index), "C6": t.dvol_rv.notna() & rank365(t.dvol_rv).notna()}
    for k, s in zip(FLAGS, (C1, C2, C3, C4, C5, C6)):
        t[k] = np.where(defined[k], s.astype(float), np.nan)
    t["sym"] = sym
    t["per"] = np.where(t.index < H1_END, "H1", "H2")
    t["L12"] = (t.index >= L12[0]) & (t.index < L12[1]); t["OOS"] = t.index >= OOS0
    return t


def cell(df, f):
    x = df[df[f].notna() & df.event.notna()]
    n = len(x); on = x[f] == 1; ev = x.event == 1
    if n == 0: return dict(n_days=0)
    base = ev.mean(); prec = ev[on].mean() if on.sum() else np.nan
    return dict(n_days=n, n_on=int(on.sum()), n_events=int(ev.sum()), base=base, precision=prec,
                lift=prec / base if base else np.nan, recall=on[ev].mean() if ev.sum() else np.nan)


PERIODS = {"FULL": lambda d: d.index == d.index, "H1": lambda d: d.per == "H1", "H2": lambda d: d.per == "H2",
           "L12": lambda d: d.L12, "OOS": lambda d: d.OOS}


def criteria(T, f):
    """period + coin criteria of the pass rule (without the shift test)."""
    ok_per = all((lambda c: c.get("n_on", 0) > 0 and c["precision"] > c["base"])(cell(T[PERIODS[p](T)], f)) for p in ("H1", "H2", "L12"))
    coins = sum((lambda c: c.get("n_on", 0) > 0 and c["precision"] > c["base"])(cell(T[T.sym == s], f)) for s in SYMS)
    return ok_per, coins


def shifted(T, f, rng):
    parts = []
    for s in SYMS:
        g = T[T.sym == s].copy(); v = g[f].values; n = len(v)
        k = rng.integers(30, n - 30); g[f] = np.roll(v, k); parts.append(g)
    return pd.concat(parts)


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    T = pd.concat([daily(s) for s in SYMS])
    print("days per coin with an event label:", T[T.event.notna()].groupby("sym").size().to_dict())
    print("flag on-rate (defined days):", {f: round(T[f].mean(), 3) for f in FLAGS})
    rows = []
    for f in FLAGS:
        for p, sel in PERIODS.items():
            rows.append(dict(flag=f, period=p, coin="ALL", **cell(T[sel(T)], f)))
            for s in SYMS:
                g = T[T.sym == s]; rows.append(dict(flag=f, period=p, coin=s, **cell(g[sel(g)], f)))
    R = pd.DataFrame(rows)
    # pass rule
    summ = []; shift_crit = {f: [] for f in FLAGS}
    actual_lift = {f: cell(T, f)["lift"] for f in FLAGS}
    shift_lift = {f: [] for f in FLAGS}
    for it in range(N_SHIFT):
        for f in FLAGS:
            Ts = shifted(T, f, RNG)
            shift_lift[f].append(cell(Ts, f)["lift"])
            if it < 200:                                       # luck count on 200 shift sets (cost)
                okp, nc = criteria(Ts, f); shift_crit[f].append(okp and nc >= 3)
    for f in FLAGS:
        okp, nc = criteria(T, f)
        p_shift = (np.array(shift_lift[f]) >= actual_lift[f]).mean()
        eligible = f != "C6"
        summ.append(dict(flag=f, lift_full=actual_lift[f], H1_H2_L12_all_above=okp, coins_above=nc,
                         p_shift=p_shift, eligible=eligible,
                         PASS=bool(eligible and okp and nc >= 3 and p_shift < 0.05)))
    Sm = pd.DataFrame(summ)
    exp_luck = sum(np.mean(shift_crit[f]) for f in FLAGS if f != "C6")
    act_crit = int(sum(r.H1_H2_L12_all_above and r.coins_above >= 3 for r in Sm.itertuples() if r.flag != "C6"))
    R = R.merge(Sm[["flag", "p_shift", "PASS"]], on="flag")
    R.to_csv(f"{W}/out/move_scan_results_rev1.csv", index=False)
    print("\n=== POOLED (ALL coins) ==="); print(R[R.coin == "ALL"].drop(columns=["coin"]).round(3).to_string(index=False))
    print("\n=== PER COIN, FULL ==="); print(R[(R.period == "FULL") & (R.coin != "ALL")][["flag", "coin", "n_days", "n_on", "base", "precision", "lift", "recall"]].round(3).to_string(index=False))
    print("\n=== PASS RULE ==="); print(Sm.round(4).to_string(index=False))
    print(f"period+coin criteria met: actual {act_crit} of 5 eligible vs {exp_luck:.2f} expected on shifted flags")

    passed = Sm[Sm.PASS].flag.tolist()
    if not passed:
        print("\nNo flag passes -> Stage 2 not run (per spec).")
    else:
        print(f"\nStage 2 for {passed}")
        U = "/root/.claude/uploads/20233afd-fef6-5311-8e9c-79766891bbfc"
        books = {"reclaim4h": f"{U}/7bd05721-recheck_trades_reclaim4h_rev1.csv", "comp_rng": f"{U}/e2bc96a7-recheck_trades_comp_rng_rev1.csv"}
        grow = []
        for f in passed:
            for b, path in books.items():
                tr = pd.read_csv(path, parse_dates=["t_in"])
                day = (tr.t_in - pd.Timedelta(days=1)).dt.normalize()       # last daily close before entry
                key = T.rename_axis("day").reset_index()[["day", "sym", f]]
                tr = tr.assign(day=day).merge(key, on=["day", "sym"], how="left")
                kept = tr[tr[f] == 1]; run = lambda x: (x.F063 > 10).mean()
                for per, m in (("FULL", tr.t_in == tr.t_in), ("H1", tr.t_in < H1_END), ("H2", tr.t_in >= H1_END)):
                    a, k = tr[m], kept[m.loc[kept.index]]
                    grow.append(dict(flag=f, book=b, period=per, n_book=len(a), n_kept=len(k), kept_share=len(k) / max(len(a), 1),
                                     runner_share_book=run(a), runner_share_kept=run(k) if len(k) else np.nan,
                                     mean_book=a.F063.mean(), mean_kept=k.F063.mean(), sum_book=a.F063.sum(), sum_kept=k.F063.sum()))
        G = pd.DataFrame(grow); G.to_csv(f"{W}/out/move_scan_gate_rev1.csv", index=False)
        print(G.round(3).to_string(index=False))
        # (b) direction
        X = pd.read_csv(f"{W}/out/integrity_X3_trades_rev1.csv", parse_dates=["t_in"])
        X = X[X.ent == "ACC"]
        for f in passed:
            ev = T[(T[f] == 1) & (T.event == 1)].rename_axis("day").reset_index()
            hits = []
            for r in ev.itertuples():
                close_t = r.day + pd.Timedelta(days=1)
                a = X[(X.sym == r.sym) & (X.t_in <= close_t) & (X.t_in > close_t - pd.Timedelta(days=7))]
                if len(a): hits.append((a.sort_values("t_in").d.iloc[-1] == r.sign7, r.sign7 > 0))
            if hits:
                from scipy.stats import binomtest
                h = np.array(hits); up = h[:, 1].mean(); k = int(h[:, 0].sum()); n = len(h)
                p0 = max(up, 1 - up)
                print(f"direction {f}: n={n} with a recent ACC signal, hit {k/n:.3f} vs naive {p0:.3f}, "
                      f"binomial p={binomtest(k, n, p0, alternative='greater').pvalue:.4f}")
