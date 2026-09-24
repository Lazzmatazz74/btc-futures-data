#!/usr/bin/env python3
"""
dossier_rev1.py  (2026-09-24)  -  Workstream B: signal dossier + red team, historical walk-forward + scoring.

PRE-REGISTERED SPEC (approved by Laz 2026-09-24 20:16 local, BEFORE any result was computed)
-------------------------------------------------------------------------------------------------
Data     repo Lazzmatazz74/btc-futures-data pulled 2026-09-24 ~18:20 UTC; candles to 2026-09-23 23:45 UTC
         (status_download.json ok, no new gaps). Funding ends 2026-08-31 (later settlements = 0, flagged).
Signals  ALL X3 signals (engine/htf_book_engine_rev1.py unchanged), 4 coins, incl. shorts G3 would skip.
         R = F063 incl. funding (finish() from recheck_edges_rev1.py). Open trades are not scored.
Walk-forward  every field uses only data known at the signal's entry time:
         state row = last 1h bar closed <= entry (tolerance 2h), repo build_market_state_rev2.build() unchanged;
         reference set = past X3 trades on the SAME SIDE (all coins) whose EXIT < this entry.
Features oi_chg_7d, oi_chg_24h, retail_ls_pct90, taker_ls_24h, premium_8h (mean of last 8 closed 1h premium
         closes), dvol_pct365 (DVOL rank in trailing 365d, BTC/ETH only), perp_cvd_4h, perp_cvd_24h,
         dist_wlevel_R (nearest high/low of the last 8 completed Mon-Sun UTC weeks beyond entry in trade
         direction, in R; none = 'open air' coded 99).
         For each: percentile vs reference, tercile (cut at reference 1/3, 2/3 quantiles), that tercile's past
         n / mean R / bootstrap 95% CI (2,000 resamples; CI for the dossier sets only). Needs >= 30 reference values.
Facts    coin, side, level (PW/SW), entry type (ACC/FSB), entry/stop/target, stop %, G3 status, 200-DMA side
         (last completed daily close vs mean of the last 200 completed daily closes).
Case against = the signal's tercile with the LOWEST past mean R (n >= 20). Counter = whether that tercile's CI
         includes the book's past mean, plus the signal's best tercile.
Flags (fixed, max 3, priority order F4, F6, F1, F2, F3, F5; '*' = one of the four 'fade fresh crowd leverage' buckets)
   F4* short & (oi_chg_7d < 0 or unknown)       F6  long & below 200-DMA
   F1* long & oi_chg_24h in top tercile          F2* long & premium_8h in top tercile
   F3* long & retail_ls_pct90 in top tercile     F5  short & dvol_pct365 in top tercile (BTC/ETH only)
   Missing feature -> that flag cannot fire (logged as a data gap).
Macro    context only, not scored; looked up (official Fed/BLS sources) for the 21-Sep dossiers only.
Scoring  PRIMARY  = last 60 CLOSED X3 signals by entry time.   SECONDARY = all closed X3 signals entered >= 2023-05-01.
   Test: mean R flagged (>=1 flag) minus unflagged; one-sided permutation p (10,000 label shuffles) that flagged
   is worse. Per flag: flagged vs non-flagged trades of the same side. Luck baseline: 1,000 shuffles of R within
   side; count flags with one-sided Welch p < 0.05 vs the actual count.
   PASS rule: primary p < 0.05. Otherwise the dossier is INFORMATION ONLY and never blocks a trade.
Stated in advance: power is low (SE of the gap ~0.5R on 60 signals); F4 (G3) and F6 (200-DMA) were found partly
   on these months, so their scores are flattered; flags logged now carry today's UTC time but outcomes are
   already known - the 'logged before outcome' guarantee starts only with live signals.
Outputs  out/dossier_features_rev1.csv, out/dossier_flags_rev1.csv (+ dossier_open_signals_rev1.md written separately)
-------------------------------------------------------------------------------------------------
"""
import sys, datetime as dt, numpy as np, pandas as pd
W = "/home/claude/work"; RAW = "/home/claude/data"; C = f"{W}/candles"
sys.path.insert(0, f"{W}/engine"); sys.path.insert(0, W)
import htf_book_engine_rev1 as H
import build_market_state_rev2 as S
S.DATA = RAW
SYMS = ["BTC", "ETH", "XRP", "BNB"]
END = pd.Timestamp("2026-09-24 00:00")
FEES = {"F080": 0.00080, "F063": 0.00063, "F040": 0.000395}
FEAT = ["oi_chg_7d", "oi_chg_24h", "retail_ls_pct90", "taker_ls_24h", "premium_8h", "dvol_pct365",
        "perp_cvd_4h", "perp_cvd_24h", "dist_wlevel_R"]
KNOWN4 = {"oi_chg_24h": "long", "premium_8h": "long", "retail_ls_pct90": "long", "oi_chg_7d": "short"}
FLAG_ORDER = ["F4", "F6", "F1", "F2", "F3", "F5"]
H2_START = pd.Timestamp("2023-05-01")
RNG = np.random.default_rng(20260924)
NOW = pd.Timestamp(dt.datetime.now(dt.timezone.utc)).tz_localize(None).floor("s")


# ---------------- trades ----------------
def prep_candles():
    for s in SYMS:
        d = pd.read_csv(f"{RAW}/{s}USDT-15m.csv"); d.index = pd.to_datetime(d.open_time, unit="ms")
        start = d.index[0] if d.index[0] == d.index[0].normalize() else d.index[0].ceil("1D")
        d = d[(d.index >= start) & (d.index < END)]; full = pd.date_range(start, d.index[-1], freq="15min")
        d = d.reindex(full); pc = d.close.ffill()
        for k in ["open", "high", "low", "close"]: d[k] = d[k].fillna(pc)
        d["open_time"] = ((full - pd.Timestamp("1970-01-01")) // pd.Timedelta("1ms")).astype("int64")
        d[["open_time", "open", "high", "low", "close"]].to_csv(f"{C}/{s}USDT15m.csv", index=False)


FUND = {}
def funding_R(sym, t0, t1, d, entry, risk):
    tv, cs, tmax = FUND[sym]
    a = np.searchsorted(tv, np.datetime64(t0), side="right"); b = np.searchsorted(tv, np.datetime64(t1), side="right")
    return d * (cs[b] - cs[a]) * entry / risk, pd.Timestamp(t1) <= tmax


def trades():
    for s in SYMS:
        f = pd.read_csv(f"{RAW}/{s}USDT-funding.csv"); t = pd.to_datetime(f.funding_time, unit="ms").dt.floor("min")
        FUND[s] = (t.values, np.r_[0, np.cumsum(f.funding_rate.values)], t.max())
    D = H.run_books(SYMS, C)["X3"].rename(columns={"time": "t_in", "exit_time": "t_out"})
    fr = [funding_R(r.sym, r.t_in, r.t_out, r.d, r.entry, r.risk) for r in D.itertuples()]
    D["fund_R"] = [x[0] for x in fr]; D["fund_ok"] = [x[1] for x in fr]
    cost = (D.entry + D.exit) / D.risk
    for k, rt in FEES.items(): D[k] = D.gross_R - rt / 2 * cost - D.fund_R
    D["open"] = (D.t_in + pd.Timedelta(days=7) > END) & (~D.gross_R.isin([-1.0, 3.0]))
    D["side"] = np.where(D.d == 1, "long", "short")
    return D.sort_values(["t_in", "sym"]).reset_index(drop=True)


# ---------------- features at entry ----------------
def attach_features(D):
    parts = []
    for s, g in D.groupby("sym"):
        st = S.build(s)
        tab = pd.DataFrame({"avail": st.index + pd.Timedelta(hours=1)})
        for c in ["oi_chg_7d", "oi_chg_24h", "retail_ls_pct90", "taker_ls_24h", "perp_cvd_4h", "perp_cvd_24h"]:
            tab[c] = st[c].values
        p = pd.read_csv(f"{RAW}/extra/{s}USDT-premium-1h.csv")
        p = pd.DataFrame({"avail": pd.to_datetime(p.open_time, unit="ms", utc=True) + pd.Timedelta(hours=1),
                          "premium_8h": p.close.rolling(8).mean().values})
        try:
            v = pd.read_csv(f"{RAW}/extra/deribit-dvol-{s}-1h.csv")
            v = pd.DataFrame({"avail": pd.to_datetime(v.open_time, unit="ms", utc=True) + pd.Timedelta(hours=1),
                              "dvol_pct365": v.close.rolling(8760, min_periods=2920).rank(pct=True).values})
        except FileNotFoundError:
            v = None
        g = g.assign(tu=g.t_in.dt.tz_localize("UTC")).sort_values("tu")
        for t in (tab, p, v):
            if t is None: continue
            g = pd.merge_asof(g, t.sort_values("avail"), left_on="tu", right_on="avail", direction="backward",
                              tolerance=pd.Timedelta(hours=2)).drop(columns="avail")
        if v is None: g["dvol_pct365"] = np.nan
        # daily closes / weekly levels from the engine candles (15m -> UTC days)
        c = pd.read_csv(f"{C}/{s}USDT15m.csv"); c.index = pd.to_datetime(c.open_time, unit="ms")
        dy = c.resample("1D").agg({"high": "max", "low": "min", "close": "last"})
        dy_end = dy.index + pd.Timedelta(days=1)
        sma = dy.close.rolling(200).mean()
        wk = c.resample("W-MON", label="left", closed="left").agg({"high": "max", "low": "min"})  # Mon-start weeks
        wk_end = wk.index + pd.Timedelta(days=7)
        side200, dist = [], []
        for r in g.itertuples():
            k = np.searchsorted(dy_end, r.t_in, side="right") - 1
            side200.append(("above" if dy.close.iloc[k] > sma.iloc[k] else "below") if k >= 199 else np.nan)
            j = np.searchsorted(wk_end, r.t_in, side="right")
            lv = np.r_[wk.high.values[max(0, j - 8):j], wk.low.values[max(0, j - 8):j]]
            lv = lv[lv > r.entry] - r.entry if r.d == 1 else r.entry - lv[lv < r.entry]
            dist.append(lv.min() / r.risk if len(lv) else 99.0)
        g["dma200"] = side200; g["dist_wlevel_R"] = dist
        parts.append(g.drop(columns="tu"))
    return pd.concat(parts).sort_values(["t_in", "sym"]).reset_index(drop=True)


# ---------------- walk-forward dossier fields ----------------
def boot_ci(x, n=2000):
    if len(x) < 2: return (np.nan, np.nan)
    m = RNG.choice(x, size=(n, len(x))).mean(1)
    return tuple(np.percentile(m, [2.5, 97.5]))


def walk(D, idx, with_ci):
    rows = []
    closed = D[~D.open]
    for i in idx:
        r = D.loc[i]
        ref = closed[(closed.side == r.side) & (closed.t_out < r.t_in)]
        out = dict(i=i, ref_n=len(ref), ref_mean=ref.F063.mean())
        for f in FEAT:
            x = ref[f].dropna(); v = r[f]
            if len(x) < 30 or pd.isna(v):
                out.update({f"{f}_pct": np.nan, f"{f}_bucket": None}); continue
            q1, q2 = np.quantile(x, [1 / 3, 2 / 3])
            b = "LOW" if v <= q1 else ("HIGH" if v > q2 else "MID")
            sel = ref[f].notna() & ((ref[f] <= q1) if b == "LOW" else ((ref[f] > q2) if b == "HIGH" else ((ref[f] > q1) & (ref[f] <= q2))))
            rb = ref[sel].F063.values
            out.update({f"{f}_pct": (x < v).mean() + 0.5 * (x == v).mean(), f"{f}_bucket": b,
                        f"{f}_bkt_n": len(rb), f"{f}_bkt_mean": rb.mean()})
            if with_ci:
                lo, hi = boot_ci(rb); out.update({f"{f}_bkt_lo": lo, f"{f}_bkt_hi": hi})
        # flags
        fl = []
        if r.side == "short" and (pd.isna(r.oi_chg_7d) or r.oi_chg_7d < 0): fl.append("F4")
        if r.side == "long" and r.dma200 == "below": fl.append("F6")
        if r.side == "long" and out.get("oi_chg_24h_bucket") == "HIGH": fl.append("F1")
        if r.side == "long" and out.get("premium_8h_bucket") == "HIGH": fl.append("F2")
        if r.side == "long" and out.get("retail_ls_pct90_bucket") == "HIGH": fl.append("F3")
        if r.side == "short" and out.get("dvol_pct365_bucket") == "HIGH": fl.append("F5")
        out["flags_all"] = ",".join(fl); out["flags"] = ",".join([f for f in FLAG_ORDER if f in fl][:3])
        out["n_flags"] = len(out["flags"].split(",")) if out["flags"] else 0
        # case against / counter
        cands = [(out[f"{f}_bkt_mean"], f) for f in FEAT if out.get(f"{f}_bucket") and out[f"{f}_bkt_n"] >= 20]
        if cands:
            (wm, wf), (bm, bf) = min(cands), max(cands)
            out["case_against"] = (f"{wf} in {out[wf + '_bucket']} third (pct {out[wf + '_pct']:.2f}): past same-side trades "
                                   f"there averaged {wm:+.2f}R (n={out[wf + '_bkt_n']}" +
                                   (f", 95% CI {out[wf + '_bkt_lo']:+.2f}..{out[wf + '_bkt_hi']:+.2f})" if with_ci else ")") +
                                   f" vs book {out['ref_mean']:+.2f}R")
            inside = with_ci and out[wf + "_bkt_lo"] <= out["ref_mean"] <= out[wf + "_bkt_hi"]
            out["counter"] = ((f"that CI includes the book mean -> not distinguishable from normal; " if inside else
                               (f"that CI excludes the book mean; " if with_ci else "")) +
                              f"best third: {bf} {out[bf + '_bucket']} {bm:+.2f}R (n={out[bf + '_bkt_n']})")
        gaps = []
        if not r.fund_ok: gaps.append("funding after 2026-08-31 not settled (counted 0)")
        for f in ("oi_chg_7d", "oi_chg_24h", "retail_ls_pct90", "taker_ls_24h"):
            if pd.isna(r[f]): gaps.append(f"{f} missing (sparse/stale Binance metrics)")
        if pd.isna(r.premium_8h): gaps.append("premium missing")
        if r.sym in ("XRP", "BNB"): gaps.append("no DVOL for this coin")
        gaps.append("no Hyperliquid snapshot history")
        out["data_gaps"] = "; ".join(gaps)
        rows.append(out)
    return pd.DataFrame(rows).set_index("i")


# ---------------- scoring ----------------
def perm_p(R, flag, n=10000):
    R = np.asarray(R, float); flag = np.asarray(flag, bool)
    if flag.sum() == 0 or (~flag).sum() == 0: return np.nan, np.nan
    obs = R[flag].mean() - R[~flag].mean(); k = flag.sum()
    diffs = np.empty(n)
    for t in range(n):
        p = RNG.permutation(len(R)); f = np.zeros(len(R), bool); f[p[:k]] = True
        diffs[t] = R[f].mean() - R[~f].mean()
    return obs, (diffs <= obs).mean()


def welch_p(a, b):
    from scipy import stats
    if len(a) < 2 or len(b) < 2: return np.nan
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return p / 2 if t < 0 else 1 - p / 2


def per_flag(T):
    rows = []
    for f, side in (("F4", "short"), ("F6", "long"), ("F1", "long"), ("F2", "long"), ("F3", "long"), ("F5", "short")):
        g = T[T.side == side]; m = g["flags"].str.contains(f).values
        obs, p = perm_p(g.F063.values, m, 5000) if m.sum() else (np.nan, np.nan)
        rows.append(dict(flag=f, side=side, n_side=len(g), n_flagged=int(m.sum()),
                         mean_flagged=g.F063[m].mean(), mean_rest=g.F063[~m].mean(), diff=obs, p_perm=p,
                         p_welch=welch_p(g.F063[m].values, g.F063[~m].values)))
    return pd.DataFrame(rows)


def luck(T, n=1000):
    actual = (per_flag_welch(T, T.F063.values) < 0.05).sum(); cnt = []
    for _ in range(n):
        R = T.F063.values.copy()
        for s in ("long", "short"):
            m = (T.side == s).values; R[m] = RNG.permutation(R[m])
        cnt.append((per_flag_welch(T, R) < 0.05).sum())
    cnt = np.array(cnt); return actual, cnt.mean(), (cnt >= actual).mean()


def per_flag_welch(T, R):
    out = []
    for f, side in (("F4", "short"), ("F6", "long"), ("F1", "long"), ("F2", "long"), ("F3", "long"), ("F5", "short")):
        m = (T.side == side).values; fl = T["flags"].str.contains(f).values
        out.append(welch_p(R[m & fl], R[m & ~fl]))
    return np.array([np.nan_to_num(x, nan=1.0) for x in out])


def score(T, label):
    fl = (T.n_flags > 0).values
    obs, p = perm_p(T.F063.values, fl)
    print(f"\n=== {label}: n={len(T)} ({T.t_in.min().date()} .. {T.t_in.max().date()}), flagged {fl.sum()}, unflagged {(~fl).sum()}")
    print(f"  mean R flagged {T.F063[fl].mean():+.3f}  unflagged {T.F063[~fl].mean():+.3f}  diff {obs:+.3f}  "
          f"one-sided permutation p = {p:.4f}   -> {'PASS' if p < 0.05 else 'NO MEASURABLE DIFFERENCE'}")
    se = T.F063.std(ddof=1) * np.sqrt(1 / max(fl.sum(), 1) + 1 / max((~fl).sum(), 1))
    print(f"  (SE of the gap = {se:.3f}R; F080 diff {T.F080[fl].mean() - T.F080[~fl].mean():+.3f}, "
          f"F040 diff {T.F040[fl].mean() - T.F040[~fl].mean():+.3f})")
    print(per_flag(T).round(3).to_string(index=False))
    a, e, pl = luck(T)
    print(f"  flags with Welch p<0.05: actual {a} vs {e:.2f} expected by luck (p={pl:.3f})")
    by_n = T.groupby("n_flags").F063.agg(["size", "mean"]); print("  by number of flags:\n" + by_n.round(3).to_string())
    return dict(set=label, n=len(T), n_flagged=int(fl.sum()), mean_flagged=T.F063[fl].mean(),
                mean_unflagged=T.F063[~fl].mean(), diff=obs, p_perm=p, se=se, luck_actual=a, luck_expected=e, luck_p=pl)


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
    prep_candles(); D = trades(); D = attach_features(D)
    closed = D[~D.open]
    last60 = closed.tail(60).index
    h2 = closed[closed.t_in >= H2_START].index
    sep21 = D[(D.t_in >= "2026-09-21") & (D.t_in < "2026-09-22")].index
    print(f"X3 signals {len(D)} (open {int(D.open.sum())}); last60 {D.loc[last60].t_in.min()} .. {D.loc[last60].t_in.max()}; "
          f"H2 closed {len(h2)}; 21-Sep signals {len(sep21)}")
    ci_set = sorted(set(last60) | set(sep21))
    Wci = walk(D, ci_set, True); Wh2 = walk(D, [i for i in h2 if i not in ci_set], False)
    Wall = pd.concat([Wci, Wh2]).sort_index()
    F = D.join(Wall, how="inner")
    F["g3"] = np.where(F.side == "short", np.where(F.oi_chg_7d >= 0, "TAKE (OI up 7d)", "SKIP (OI down/unknown)"), "n/a (long)")
    F["in_last60"] = F.index.isin(last60); F["in_h2"] = F.index.isin(h2); F["in_sep21"] = F.index.isin(sep21)
    F["stop_pct"] = 100 * F.risk / F.entry; F["target"] = F.entry + F.d * 3 * F.risk
    F["outcome_R_F063"] = F.F063.where(~F.open)
    res = [score(F[F.in_last60], "PRIMARY last 60 closed X3 signals"),
           score(F[F.in_h2], "SECONDARY all closed X3 signals since 2023-05")]
    pd.DataFrame(res).to_csv(f"{W}/out/dossier_scores_tmp.csv", index=False)
    keep = ["sym", "side", "lvl", "ent", "t_in", "entry", "stop", "target", "stop_pct", "g3", "dma200", "open", "t_out",
            "outcome_R_F063", "F080", "F040", "fund_ok", "in_last60", "in_h2", "in_sep21", "ref_n", "ref_mean"] + \
           [c for f in FEAT for c in (f, f"{f}_pct", f"{f}_bucket", f"{f}_bkt_n", f"{f}_bkt_mean", f"{f}_bkt_lo", f"{f}_bkt_hi") if c in F.columns] + \
           ["flags", "flags_all", "n_flags", "case_against", "counter", "data_gaps"]
    F[keep].to_csv(f"{W}/out/dossier_features_rev1.csv", index=False)
    FL = F[F.in_last60 | F.in_sep21 | F.in_h2][["sym", "side", "t_in", "flags", "n_flags"]].copy()
    FL.insert(0, "logged_utc", NOW)
    FL["log_type"] = "historical walk-forward (outcome already known at log time)"
    FL.to_csv(f"{W}/out/dossier_flags_rev1.csv", index=False)
    print("\n21-Sep signals:"); print(F[F.in_sep21][["sym", "side", "lvl", "ent", "t_in", "open", "outcome_R_F063", "flags", "case_against"]].to_string())
