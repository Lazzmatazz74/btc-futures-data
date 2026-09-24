#!/usr/bin/env python3
"""
edge_health_rev1.py  (2026-09-24)  -  Workstream A: is HTF X3+G3 still behaving like its own history?

PRE-REGISTERED SPEC (written and approved by Laz 2026-09-24 18:46 local, BEFORE any result was computed)
-------------------------------------------------------------------------------------------------
Input  out/integrity_X3_with_oi_rev1.csv  (integrity_check_rev1.py: X3 1,302 trades +0.1752R F063 incl. funding,
       BTC/ETH/XRP/BNB, candles to 2026-09-22 23:45 UTC; oi_chg_7d attached with the repo state builder).
Books  X3G3 (headline) = all X3 longs + X3 shorts with oi_chg_7d >= 0 (unknown OI -> skip).  X3 (base) alongside.
       Open trades at data end (entry + 7d > 2026-09-23 and R not in {-1,3}) are EXCLUDED (4 longs, 21 Sep).
Fees   F063 headline (thresholds, alarms, table). F080 and F040: full re-fit, summary rows only.
Order  Trades are ordered by EXIT time (R is only known at exit). Period labels use ENTRY time:
       H1 < 2023-05-01 <= H2 ;  L12 = 2025-09-23 .. 2026-07-31 ;  OOS >= 2026-08-01.
Reference (decision 1): mu0 and all thresholds are fitted on H1 trades only. The alarm is evaluated on H2.
       (H1 firings are reported as in-sample, info only.)
Alarms
  R30 / R60 : rolling mean of the last 30 / 60 closed trades < 5th percentile of all H1-only rolling windows.
  CUSUM     : S_i = max(0, S_{i-1} + (mu0 - R_i) - k), k = mu0/2  (tuned to detect a drop to 0R).
              Limit h fixed on H1 by iid bootstrap of H1 R so that the in-control average run length
              ARL0 = 300 trades (decision 3, ~2 years). ARL1 (shift of -mu0, i.e. true mean 0) reported.
  ANY       : R30 or R60 or CUSUM  (the brief's alarm; headline).
  An alarm FIRES on a crossing (condition false at previous exit, true now), only while not already paused.
Action (decision 2): after an alarm fires at exit time T_a, every trade ENTERED after T_a is paper-only
  (skipped) until the CUSUM (updated on all trades, live and paper, in exit order) is back at 0 at some
  exit j after the alarm; trades entered up to and including T_clear = exit time of j are skipped.
  If the data ends first, the pause is 'open'.
Scoring  skipped R (sum, F063): negative = R saved.  Alarm is a FALSE alarm if its skipped trades summed > 0;
  false-alarm cost = sum of those positive sums.  OOS effect = skipped R among OOS-entry trades.
Shuffle baseline  1,000 permutations of R among H2 trades (positions/timestamps fixed, H1 fixed):
  p_fires = share of shuffles with >= the actual number of H2 firings (does badness CLUSTER in time?),
  p_saved = share of shuffles whose skipped-R sum <= actual (does it save more than a random-timed pause?).
Stress  top-3 removal (3 largest-R trades of the book dropped, rerun); R-cap 10 is non-binding (max ~3.6R);
  per coin = share of skipped trades and skipped R; per year = skipped trades / R / paused days.
Question 4 - was the L12 window (entries 2025-09-23..2026-07-31) a real break?
  Reference = all closed trades with exit < 2025-09-23.  n = number of L12 trades.
  (a) iid bootstrap 20,000 x n draws -> p = P(mean <= observed)
  (b) weekly block bootstrap (weeks by entry, resampled with replacement until >= n trades, first n kept), 20,000
  (c) percentile of the observed mean among all earlier n-trade rolling windows (exit order, fully before window)
  Verdict: REAL BREAK if p < 0.05 in both (a) and (b); NORMAL VARIANCE if both p > 0.10; else INCONCLUSIVE.
  Caveat pre-stated: the window was chosen after it was known to be poor (selection), so borderline p is weak.
Seeds fixed (numpy default_rng(20260924)).
Outputs  out/edge_health_alarms_rev1.csv (alarm history, all books/fees/rules); summary printed to stdout.
-------------------------------------------------------------------------------------------------
"""
import numpy as np, pandas as pd

W = "/home/claude/work"
H1_END, L12 = pd.Timestamp("2023-05-01"), (pd.Timestamp("2025-09-23"), pd.Timestamp("2026-08-01"))
OOS0, DATA_END = pd.Timestamp("2026-08-01"), pd.Timestamp("2026-09-23")
ARL0_TARGET, N_SHUF, N_BOOT = 300, 1000, 20000
RNG = np.random.default_rng(20260924)
RULES = ["R30", "R60", "CUSUM", "ANY"]


def load():
    A = pd.read_csv(f"{W}/out/integrity_X3_with_oi_rev1.csv", parse_dates=["t_in", "t_out"])
    open_ = (A.t_in + pd.Timedelta(days=7) > DATA_END) & (~A.gross_R.isin([-1.0, 3.0]))
    A = A[~open_].copy()
    A["per"] = np.where(A.t_in < H1_END, "H1", "H2")
    A["L12"] = (A.t_in >= L12[0]) & (A.t_in < L12[1]); A["OOS"] = A.t_in >= OOS0
    g3 = (A.d == 1) | ((A.d == -1) & (A.oi_chg_7d >= 0))
    books = {"X3G3": A[g3], "X3": A}
    return {k: v.sort_values(["t_out", "t_in", "sym"]).reset_index(drop=True) for k, v in books.items()}, int(open_.sum())


def roll(x, w):
    c = np.r_[0, np.cumsum(x)]; out = np.full(len(x), np.nan)
    out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def cusum(x, mu0, k):
    S = np.zeros(len(x)); s = 0.0
    for i, r in enumerate(x):
        s = max(0.0, s + (mu0 - r) - k); S[i] = s
    return S


def run_lengths(pool, mu0, k, h_grid, paths=3000, T=4000, shift=0.0):
    """iid bootstrap from pool (+shift); first-passage time of S above each h (capped at T)."""
    X = RNG.choice(pool, size=(paths, T)).astype(np.float32) + shift
    S = np.zeros(paths, np.float32); M = np.empty((paths, T), np.float32)
    for t in range(T):
        S = np.maximum(0, S + (mu0 - X[:, t]) - k); M[:, t] = S
    M = np.maximum.accumulate(M, axis=1)
    out = []
    for h in h_grid:
        hit = M > h; rl = np.where(hit.any(1), hit.argmax(1) + 1, T)
        out.append((h, rl.mean(), np.median(rl)))
    return out


def fit(D, col):
    h1 = D[D.per == "H1"]; x1 = h1[col].values; mu0 = x1.mean(); k = mu0 / 2
    # rolling windows entirely inside H1 (exit order, H1 trades only)
    thr = {w: np.nanpercentile(roll(x1, w), 5) for w in (30, 60)}
    lo, hi = 0.5, 40.0                                       # bisection on ARL0
    for _ in range(18):
        mid = (lo + hi) / 2
        arl = run_lengths(x1, mu0, k, [mid], paths=1500, T=3000)[0][1]
        lo, hi = (mid, hi) if arl < ARL0_TARGET else (lo, mid)
    h = (lo + hi) / 2
    a0 = run_lengths(x1, mu0, k, [h])[0]; a1 = run_lengths(x1, mu0, k, [h], shift=-mu0)[0]
    return dict(mu0=mu0, k=k, thr30=thr[30], thr60=thr[60], h=h, ARL0=a0[1], ARL0_med=a0[2], ARL1=a1[1], ARL1_med=a1[2])


def backtest(D, col, P, rules=RULES, x=None):
    """returns per-trade skipped flag per rule and an alarm list"""
    x = D[col].values if x is None else x
    r30, r60, S = roll(x, 30), roll(x, 60), cusum(x, P["mu0"], P["k"])
    cond = {"R30": r30 < P["thr30"], "R60": r60 < P["thr60"], "CUSUM": S > P["h"]}
    cond["ANY"] = cond["R30"] | cond["R60"] | cond["CUSUM"]
    tin, tout = D.t_in.values, D.t_out.values
    res = {}
    for rule in rules:
        c = cond[rule]; prev = np.r_[False, c[:-1]]; fire = c & ~prev
        pauses = []; i = 0; n = len(x)
        while i < n:
            if fire[i]:
                j = i + 1
                while j < n and S[j] > 0: j += 1
                t_a = tout[i]; t_c = tout[j] if j < n else None
                pauses.append((i, j if j < n else None, t_a, t_c))
                i = j + 1 if j < n else n
            else:
                i += 1
        skip = np.zeros(n, bool); pid = np.full(n, -1)
        for p, (i0, j0, t_a, t_c) in enumerate(pauses):
            m = (tin > t_a) & ((tin <= t_c) if t_c is not None else True)
            skip |= m; pid[m] = p
        res[rule] = (skip, pid, pauses)
    return res, dict(r30=r30, r60=r60, S=S)


def alarm_table(D, col, P, res, trace, book, fee):
    rows = []
    for rule, (skip, pid, pauses) in res.items():
        for p, (i0, j0, t_a, t_c) in enumerate(pauses):
            m = pid == p; sk = D[m]
            rows.append(dict(book=book, fee=fee, rule=rule, alarm_no=p + 1,
                             fired_at_exit=pd.Timestamp(t_a), fired_trade_period=D.per.iloc[i0],
                             r30=trace["r30"][i0], r60=trace["r60"][i0], cusum=trace["S"][i0],
                             cleared_at=pd.Timestamp(t_c) if t_c is not None else "OPEN",
                             paused_days=((pd.Timestamp(t_c) if t_c is not None else DATA_END) - pd.Timestamp(t_a)).days,
                             n_skipped=int(m.sum()), skipped_R=sk[col].sum(), skipped_mean=sk[col].mean() if len(sk) else np.nan,
                             n_skipped_OOS=int(sk.OOS.sum()), skipped_R_OOS=sk[sk.OOS][col].sum(),
                             n_skipped_L12=int(sk.L12.sum()), skipped_R_L12=sk[sk.L12][col].sum(),
                             false_alarm=bool(sk[col].sum() > 0)))
    return rows


def summarize(D, col, res, period_mask, label):
    out = []
    for rule, (skip, pid, pauses) in res.items():
        m = period_mask
        fired = [p for p, (i0, *_ ) in enumerate(pauses) if m[i0]]
        sk = D[skip & m]
        per_alarm = [D[(pid == p)][col].sum() for p in fired]
        out.append(dict(rule=rule, period=label, n_trades=int(m.sum()), fires=len(fired),
                        n_skipped=len(sk), pct_skipped=100 * len(sk) / max(1, m.sum()),
                        skipped_R=sk[col].sum(), saved_R=-sk[col].sum(),
                        false_alarms=sum(v > 0 for v in per_alarm),
                        false_alarm_cost=sum(v for v in per_alarm if v > 0),
                        kept_mean=D[~skip & m][col].mean(), base_mean=D[m][col].mean(),
                        skipped_OOS_R=sk[sk.OOS][col].sum(), n_skipped_OOS=int(sk.OOS.sum())))
    return out


def shuffle_test(D, col, P, actual):
    h2 = np.nonzero((D.per == "H2").values)[0]; x0 = D[col].values.copy()
    fires = {r: [] for r in RULES}; saved = {r: [] for r in RULES}
    for _ in range(N_SHUF):
        x = x0.copy(); x[h2] = RNG.permutation(x0[h2])
        res, _ = backtest(D, col, P, x=x)
        m = (D.per == "H2").values
        for r, (skip, pid, pauses) in res.items():
            fires[r].append(sum(1 for (i0, *_ ) in pauses if m[i0]))
            saved[r].append(x[skip & m].sum())
    rows = []
    for r in RULES:
        af, asr = actual[r]
        f, s = np.array(fires[r]), np.array(saved[r])
        rows.append(dict(rule=r, H2_fires=af, shuffle_fires_mean=f.mean(), p_fires=(f >= af).mean(),
                         H2_skipped_R=asr, shuffle_skipped_R_mean=s.mean(), p_saved=(s <= asr).mean()))
    return pd.DataFrame(rows)


def q4(D, col):
    w = D[D.L12]; n = len(w); obs = w[col].mean()
    ref = D[D.t_out < L12[0]]; x = ref[col].values
    a = RNG.choice(x, size=(N_BOOT, n)).mean(1); p_a = (a <= obs).mean()
    wk = ref.t_in.dt.to_period("W").astype(str).values
    groups = [g[col].values for _, g in ref.groupby(wk)]
    sizes = np.array([len(g) for g in groups]); nb = int(np.ceil(n / sizes.mean() * 2)) + 5
    b = np.empty(N_BOOT)
    for t in range(N_BOOT):
        idx = RNG.integers(0, len(groups), nb); v = np.concatenate([groups[i] for i in idx])
        while len(v) < n:
            v = np.concatenate([v, groups[RNG.integers(0, len(groups))]])
        b[t] = v[:n].mean()
    p_b = (b <= obs).mean()
    rw = roll(x, n); rw = rw[~np.isnan(rw)]; p_c = (rw <= obs).mean()
    z = (obs - x.mean()) / (x.std(ddof=1) / np.sqrt(n))
    verdict = "REAL BREAK" if (p_a < .05 and p_b < .05) else ("NORMAL VARIANCE" if (p_a > .10 and p_b > .10) else "INCONCLUSIVE")
    return dict(n=n, obs_mean=obs, ref_n=len(x), ref_mean=x.mean(), ref_sd=x.std(ddof=1), z=z,
                p_iid=p_a, p_block=p_b, p_rolling_rank=p_c, n_rolling_windows=len(rw),
                iid_5pct=np.percentile(a, 5), block_5pct=np.percentile(b, 5), verdict=verdict)


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    books, n_open = load()
    print(f"open trades excluded: {n_open}; closed: " + ", ".join(f"{k} {len(v)}" for k, v in books.items()))
    all_alarms, summaries, fits = [], [], []
    for book, D in books.items():
        for col in ("F063", "F080", "F040"):
            P = fit(D, col); fits.append(dict(book=book, fee=col, **P))
            res, tr = backtest(D, col, P)
            all_alarms += alarm_table(D, col, P, res, tr, book, col)
            for lab, m in (("H1 (in-sample)", (D.per == "H1").values), ("H2", (D.per == "H2").values)):
                for s in summarize(D, col, res, m, lab): summaries.append(dict(book=book, fee=col, **s))
    F = pd.DataFrame(fits); Sm = pd.DataFrame(summaries); AL = pd.DataFrame(all_alarms)
    AL.to_csv(f"{W}/out/edge_health_alarms_rev1.csv", index=False)
    print("\n=== FITTED ON H1 ==="); print(F.round(3).to_string(index=False))
    print("\n=== SUMMARY ==="); print(Sm.round(3).to_string(index=False))
    print("\n=== ALARM HISTORY (X3G3, F063, ANY + components) ===")
    cols = ["rule", "alarm_no", "fired_at_exit", "fired_trade_period", "r30", "r60", "cusum", "cleared_at",
            "paused_days", "n_skipped", "skipped_R", "n_skipped_L12", "skipped_R_L12", "n_skipped_OOS", "skipped_R_OOS", "false_alarm"]
    print(AL[(AL.book == "X3G3") & (AL.fee == "F063")][cols].round(3).to_string(index=False))
    print("\n=== ALARM HISTORY (X3 base, F063, ANY) ===")
    print(AL[(AL.book == "X3") & (AL.fee == "F063") & (AL.rule == "ANY")][cols].round(3).to_string(index=False))

    # shuffle baseline, stress, per coin/year, Q4 - F063 only
    for book, D in books.items():
        P = F[(F.book == book) & (F.fee == "F063")].iloc[0].to_dict()
        res, _ = backtest(D, "F063", P); m = (D.per == "H2").values
        actual = {r: (sum(1 for (i0, *_ ) in res[r][2] if m[i0]), D.F063.values[res[r][0] & m].sum()) for r in RULES}
        print(f"\n=== SHUFFLE BASELINE {book} (H2 R permuted, {N_SHUF}x) ===")
        print(shuffle_test(D, "F063", P, actual).round(3).to_string(index=False))
        # top-3 removal
        Dt = D.drop(D.F063.nlargest(3).index).reset_index(drop=True); Pt = fit(Dt, "F063"); rt, _ = backtest(Dt, "F063", Pt)
        print(f"\n--- {book} top-3 removed (refit) ---")
        print(pd.DataFrame(summarize(Dt, "F063", rt, (Dt.per == "H2").values, "H2")).round(3).to_string(index=False))
        # per coin / per year for ANY
        skip, pid, pauses = res["ANY"]; sk = D[skip & m]
        pc = pd.DataFrame({"n_trades_H2": D[m].groupby("sym").size(), "n_skipped": sk.groupby("sym").size(),
                           "skipped_R": sk.groupby("sym").F063.sum()}).fillna(0)
        print(f"\n--- {book} ANY per coin (H2) ---"); print(pc.round(3).to_string())
        py = pd.DataFrame({"n_trades": D.groupby(D.t_in.dt.year).size(), "n_skipped": D[skip].groupby(D[skip].t_in.dt.year).size(),
                           "skipped_R": D[skip].groupby(D[skip].t_in.dt.year).F063.sum()}).fillna(0)
        print(f"--- {book} ANY per entry year (all) ---"); print(py.round(3).to_string())
        print(f"\n=== Q4 {book}: L12 window vs history ===")
        for k, v in q4(D, "F063").items(): print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")
