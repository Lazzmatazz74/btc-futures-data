#!/usr/bin/env python3
"""
daily_checks_rev1.py  (2026-09-24)  -  Workstream D, part 1: the numbers behind the daily brief.
Runs in the repo (GitHub Action, after "Fetch extra data + forward log rev3"). Writes to data/brief/ and the
workflow commits it, so every flag/status carries a git timestamp from BEFORE the outcome exists.

NOTHING HERE IS NEW RESEARCH. It re-uses the approved, unchanged scripts (copied into brief/):
  edge_health_rev1.py  (Workstream A)  - gauge only, constants fixed from the approved H1 fit (below)
  dossier_rev1.py      (Workstream B)  - fact sheets + flags F1..F6, walk-forward, information only
  move_scan_rev1.py    (Workstream C)  - C3 'OI building while quiet', information only
  comp_rng_engine_rev1.py              - compression range-stop engine (verified: reproduces 531/531 reference
                                         trades, max F063 diff 2e-15) for the C3 forward test
Only paths/dates are overridden at run time; no rule, threshold or feature is changed.

PRE-REGISTERED FORWARD TESTS (fixed 2026-09-24, before any live data):
  G3     after >= 30 live X3 shorts closed (forward_signals_rev2.csv, live=True): TAKE vs SKIP mean R_F063.
  FLAGS  after 60 live X3 signals closed: mean R flagged (>=1 flag) minus unflagged, one-sided permutation p
         (10,000), same six flags, same thirds. p < 0.05 -> flags may become a journal warning; else info only.
  C3     every compression range-stop signal logged with C3 at the last daily close before entry; after 30 live
         C3-on trades closed: C3-on vs C3-off mean R (F063), one-sided permutation p. Nothing changes before that.
  Until each verdict: information only, never blocks a trade.

Edge gauge constants (edge_health_rev1 fit on H1 X3+G3 F063, 2026-09-24): mu0 0.317595, k 0.158798,
  thr30 -0.328644, thr60 -0.226033, h 19.632888.  Historical alarms were all false -> GAUGE ONLY.

Outputs (data/brief/):
  latest.json, history/YYYY-MM-DD.json      summary for the brief
  latest_dossiers.md                        fact sheets for new/open X3 signals
  dossier_flags_live_rev1.csv   APPEND-ONLY flags per X3 signal (first_logged_utc immutable)
  comp_c3_log_rev1.csv          APPEND-ONLY C3 status per comp range-stop signal (outcome columns updated)
  gauge_log_rev1.csv, brief_runs_rev1.csv   one row per run
"""
import os, sys, json, tempfile, datetime as dt, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "engine"), ROOT, HERE): sys.path.insert(0, p)
from prep_candles_rev2 import prepare                     # noqa: E402
import build_market_state_rev2 as S                       # noqa: E402
import edge_health_rev1 as E                              # noqa: E402
import dossier_rev1 as DS                                 # noqa: E402
import move_scan_rev1 as MS                               # noqa: E402
import comp_rng_engine_rev1 as CE                         # noqa: E402

DATA = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
OUT = os.path.join(DATA, "brief"); HIST = os.path.join(OUT, "history")
SYMS = ["BTC", "ETH", "XRP", "BNB"]
GAUGE = dict(mu0=0.317595286, k=0.158797643, thr30=-0.328643598, thr60=-0.226033230, h=19.632887841)
LOG_FROM = pd.Timestamp("2026-07-01")
NEW_DAYS = 3
NOW = pd.Timestamp(dt.datetime.now(dt.timezone.utc)).tz_localize(None).floor("s")
FLN = {"F4": "short, OI falling 7d (G3 skip)", "F6": "long below 200-DMA", "F1": "long, 24h OI jump (top third)",
       "F2": "long, 8h premium high (top third)", "F3": "long, retail crowd long (top third)",
       "F5": "short, DVOL high in its year"}
KEY = ["sym", "entry_time", "side", "ent", "lvl"]


def jsonable(o):
    if isinstance(o, dict): return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [jsonable(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, (pd.Timestamp, dt.datetime)): return str(o)
    if isinstance(o, np.bool_): return bool(o)
    return o


def prev_run():
    p = os.path.join(OUT, "brief_runs_rev1.csv")
    if not os.path.exists(p): return None, pd.DataFrame()
    r = pd.read_csv(p, parse_dates=["run_utc", "data_end"])
    return (r.data_end.iloc[-1] if len(r) else None), r


def candles(tmp):
    gaps, ends = [], []
    for s in SYMS:
        for tf in ("15m", "1h"):
            d, unk = prepare(pd.read_csv(os.path.join(DATA, f"{s}USDT-{tf}.csv")), f"{s}USDT", tf)
            d.to_csv(os.path.join(tmp, f"{s}USDT{tf}.csv"), index=False); gaps += unk
            if tf == "15m": ends.append(pd.to_datetime(d.open_time.iloc[-1], unit="ms") + pd.Timedelta(minutes=15))
    return min(ends), max(ends), gaps


def health(data_end):
    h = {"data_end_utc": data_end}
    p = os.path.join(DATA, "status_download.json")
    if os.path.exists(p):
        st = json.load(open(p)); h["download_ok"] = st.get("ok"); h["download_problems"] = st.get("problems")
        h["download_run_utc"] = st.get("run_utc")
        h["lag_hours"] = {k: v.get("lag_hours") for k, v in st.get("files", {}).items() if k.endswith("-15m")}
    dens, fund = {}, {}
    for s in SYMS:
        m = pd.read_csv(os.path.join(DATA, f"{s}USDT-metrics.csv"), usecols=[0])
        t = pd.to_datetime(m.create_time); last7 = t[t >= data_end - pd.Timedelta(days=7)]
        dens[s] = round(len(last7) / (7 * 288), 3)
        f = pd.read_csv(os.path.join(DATA, f"{s}USDT-funding.csv"), usecols=["funding_time"])
        fund[s] = str(pd.to_datetime(f.funding_time.max(), unit="ms"))
    h["metrics_density_7d"] = dens; h["funding_settled_until"] = fund
    return h


def gauge(D):
    g = D[(~D.open) & ((D.d == 1) | ((D.d == -1) & (D.oi_chg_7d >= 0)))].sort_values(["t_out", "t_in", "sym"])
    x = g.F063.values
    r30, r60, Sc = E.roll(x, 30)[-1], E.roll(x, 60)[-1], E.cusum(x, GAUGE["mu0"], GAUGE["k"])
    above = np.nonzero(Sc <= 0)[0]
    return dict(n_closed=len(g), last_exit=g.t_out.iloc[-1], rolling30=r30, rolling60=r60, cusum=Sc[-1],
                cusum_limit=GAUGE["h"], thr30=GAUGE["thr30"], thr60=GAUGE["thr60"],
                r30_below=bool(r30 < GAUGE["thr30"]), r60_below=bool(r60 < GAUGE["thr60"]),
                cusum_over=bool(Sc[-1] > GAUGE["h"]),
                cusum_last_zero_exit=(g.t_out.iloc[above[-1]] if len(above) else None),
                note="GAUGE ONLY - every historical alarm was a false alarm (edge_health_rev1); never a stop signal")


def fmt(v, f):
    if pd.isna(v): return "n/a"
    if f == "dist_wlevel_R": return "open air" if v >= 99 else f"{v:.2f}R"
    if f in ("oi_chg_7d", "oi_chg_24h"): return f"{v * 100:+.2f}%"
    if f == "premium_8h": return f"{v * 100:+.4f}%"
    return f"{v:.3f}"


def dossier_md(F, data_end):
    L = [f"# X3 signal dossiers — data to {data_end:%Y-%m-%d %H:%M} UTC", "",
         "Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); "
         "they must never block a trade. Live verdict after 60 live signals.", ""]
    if not len(F): return "\n".join(L + ["No new or open X3 signals."])
    for r in F.sort_values("t_in").itertuples():
        rr = r._asdict(); side = r.side
        L += [f"## {r.sym} {side.upper()} — {r.lvl} {r.ent} — entry {r.t_in:%Y-%m-%d %H:%M} UTC "
              f"({'OPEN' if r.open else f'closed {r.t_out:%Y-%m-%d %H:%M}, {r.F063:+.2f}R'})", "",
              "| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |", "|---|---|---|---|---|---|",
              f"| {r.entry:g} | {r.stop:g} | {r.target:g} | {r.stop_pct:.2f}% | {r.g3} | {r.dma200} |", "",
              f"| Feature (vs past {side}s) | Value | Pct | Third | Past R in that third (n, 95% CI) |", "|---|---|---|---|---|"]
        for f in DS.FEAT:
            star = " ★" if DS.KNOWN4.get(f) == side else ""
            b = rr.get(f + "_bucket")
            if b is None or (isinstance(b, float) and np.isnan(b)):
                L.append(f"| {f}{star} | {fmt(rr[f], f)} | — | — | n/a |"); continue
            L.append(f"| {f}{star} | {fmt(rr[f], f)} | {rr[f + '_pct']:.2f} | {b} | {rr[f + '_bkt_mean']:+.2f}R "
                     f"(n={int(rr[f + '_bkt_n'])}, {rr[f + '_bkt_lo']:+.2f}..{rr[f + '_bkt_hi']:+.2f}) |")
        fl = r.flags if isinstance(r.flags, str) and r.flags else ""
        L += ["", f"- Book reference: {int(r.ref_n)} past {side}s, {r.ref_mean:+.2f}R.",
              f"- Case against: {r.case_against}", f"- Case against that: {r.counter}",
              "- Flags: " + (", ".join(f"{x} ({FLN[x]})" for x in fl.split(",")) if fl else "none"),
              f"- Data gaps: {r.data_gaps}", ""]
    return "\n".join(L)


def append_only(path, cur, key, immutable, updatable=()):
    """Rows are keyed; existing rows keep every column except `updatable` (outcome columns). All stored as text."""
    cur = cur.copy()
    for c in cur.columns:
        if pd.api.types.is_datetime64_any_dtype(cur[c]): cur[c] = cur[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    cur = cur.astype(object).where(cur.notna(), None)
    if os.path.exists(path):
        old = pd.read_csv(path, dtype=str, keep_default_na=False).replace({"": None})
        oi = old.set_index(key); ci = cur.set_index(key)
        new = ci.loc[ci.index.difference(oi.index)]
        both = oi.index.intersection(ci.index)
        for c in updatable:
            if c in ci.columns: oi.loc[both, c] = ci.loc[both, c].map(lambda v: None if v is None else str(v))
        out = pd.concat([oi, new]).reset_index()
    else:
        out = cur; new = cur
    out.to_csv(path, index=False)
    return out, len(new)


def main():
    os.makedirs(HIST, exist_ok=True)
    prev_end, runs = prev_run()
    tmp = tempfile.mkdtemp()
    data_end, data_end_max, gaps = candles(tmp)
    # ---- X3 trades + features (dossier_rev1, unchanged logic)
    DS.RAW = DATA; DS.C = tmp; DS.END = data_end; S.DATA = DATA
    MS.RAW = DATA; MS.C = tmp
    D = DS.trades(); D = DS.attach_features(D)
    D["target"] = D.entry + D.d * 3 * D.risk; D["stop_pct"] = 100 * D.risk / D.entry
    D["g3"] = np.where(D.side == "short", np.where(D.oi_chg_7d >= 0, "TAKE (OI up 7d)", "SKIP (OI down/unknown)"), "n/a (long)")
    # ---- gauge
    G = gauge(D)
    # ---- dossiers for new + open signals
    idx = D[(D.t_in >= data_end - pd.Timedelta(days=NEW_DAYS)) | D.open].index.tolist()
    F = D.loc[idx].join(DS.walk(D, idx, True)) if idx else D.iloc[:0]
    open(os.path.join(OUT, "latest_dossiers.md"), "w").write(dossier_md(F, data_end))
    # ---- flag log (all X3 signals from LOG_FROM; append-only) + live from the forward log
    lg = D[D.t_in >= LOG_FROM].index.tolist()
    W = DS.walk(D, lg, False)
    FL = D.loc[lg, ["sym", "t_in", "side", "ent", "lvl"]].rename(columns={"t_in": "entry_time"}).join(W[["flags", "n_flags"]])
    fwd_p = os.path.join(DATA, "forward", "forward_signals_rev2.csv")
    fwd = pd.read_csv(fwd_p, parse_dates=["entry_time"]) if os.path.exists(fwd_p) else pd.DataFrame()
    if len(fwd):
        fx = fwd[fwd.book == "X3"].drop_duplicates(KEY)[KEY + ["live"]]
        FL = FL.merge(fx, on=KEY, how="left")
        FL["live"] = FL.live.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
    else:
        FL["live"] = False
    FL["first_logged_utc"] = NOW; FL["data_end_at_first_log"] = data_end
    FLOG, n_new_flags = append_only(os.path.join(OUT, "dossier_flags_live_rev1.csv"), FL, KEY,
                                    immutable=["flags", "n_flags", "live", "first_logged_utc"])
    # ---- C3 status per coin + comp range-stop forward log
    days = {s: MS.daily(s) for s in SYMS}
    c3 = {}
    for s, t in days.items():
        last = t[t.C1.notna() | t.C2.notna()].iloc[-1]
        c3[s] = dict(day=str(last.name.date()), C3=None if pd.isna(last.C3) else bool(last.C3 == 1),
                     quiet=bool((last.C1 == 1) or (last.C2 == 1)), oi_chg_7d=last.oi7)
    CT = CE.comp_trades(tmp, SYMS, DATA)
    CT = CT[CT.t_in >= LOG_FROM].copy()
    def c3_at(r):
        t = days[r.sym]; day = (r.t_in - pd.Timedelta(days=1)).normalize()
        v = t.C3.get(day, np.nan); return None if pd.isna(v) else bool(v == 1)
    CT["C3_at_entry"] = [c3_at(r) for r in CT.itertuples()] if len(CT) else []
    CT = CT.rename(columns={"t_in": "entry_time"})
    pe = pd.Series({s: (runs[runs.sym == s].data_end.iloc[-1] if len(runs) and (runs.sym == s).any() else pd.NaT) for s in SYMS})
    CT["live"] = [bool(pd.notna(pe[r.sym]) and r.entry_time > pe[r.sym]) for r in CT.itertuples()]
    CT["status"] = np.where(CT.open, "open", "closed"); CT["first_logged_utc"] = NOW
    CT = CT[["sym", "entry_time", "entry", "stop", "C3_at_entry", "live", "first_logged_utc", "status", "t_out", "F063", "F080", "F040", "fund_ok"]]
    CLOG, n_new_comp = append_only(os.path.join(OUT, "comp_c3_log_rev1.csv"), CT, ["sym", "entry_time"],
                                   immutable=["C3_at_entry", "live", "first_logged_utc"],
                                   updatable=["status", "t_out", "F063", "F080", "F040", "fund_ok"])
    # ---- scoreboards (counts toward the pre-registered verdicts; means are information only)
    sb = {}
    if len(fwd):
        xs = fwd[(fwd.book == "X3") & (fwd.side == "short") & (fwd.status == "closed")]
        xs = xs[xs.live.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))]
        sb["G3"] = dict(target=30, n_live_closed=len(xs), take_n=int((xs.action == "TAKE").sum()),
                        take_mean=xs[xs.action == "TAKE"].R_F063.mean(), skip_n=int((xs.action == "SKIP").sum()),
                        skip_mean=xs[xs.action == "SKIP"].R_F063.mean())
        m = FLOG.copy(); m["entry_time"] = pd.to_datetime(m.entry_time)
        m = m[m.live.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))].merge(
            fwd[fwd.book == "X3"][KEY + ["status", "R_F063"]], on=KEY, how="left")
        m = m[m.status == "closed"]; fl = pd.to_numeric(m.n_flags) > 0
        sb["FLAGS"] = dict(target=60, n_live_closed=len(m), flagged_n=int(fl.sum()), flagged_mean=m[fl].R_F063.mean(),
                           unflagged_n=int((~fl).sum()), unflagged_mean=m[~fl].R_F063.mean())
    cl = CLOG[(CLOG.live.map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))) & (CLOG.status == "closed")]
    on = cl.C3_at_entry.map(lambda v: str(v).strip().lower() == "true")
    R3 = pd.to_numeric(cl.F063)
    sb["C3"] = dict(target=30, n_live_closed_C3on=int(on.sum()), on_mean=R3[on].mean(),
                    n_live_closed_C3off=int((~on).sum()), off_mean=R3[~on].mean())
    # ---- summary
    newsig = D.loc[[i for i in idx if D.loc[i, "t_in"] >= data_end - pd.Timedelta(days=NEW_DAYS)]]
    opn = D[D.open]
    summ = dict(run_utc=NOW, data_end=data_end, data_end_latest_coin=data_end_max,
                previous_run_data_end=prev_end, unknown_gaps=gaps, health=health(data_end), edge_gauge=G,
                x3_new_signals=[dict(sym=r.sym, side=r.side, lvl=r.lvl, ent=r.ent, entry_time=r.t_in, entry=r.entry, stop=r.stop,
                                     flags=F.loc[i, "flags"] if i in F.index else None,
                                     status="open" if r.open else "closed", R_F063=None if r.open else r.F063)
                                for i, r in newsig.iterrows()],
                x3_open=[dict(sym=r.sym, side=r.side, entry_time=r.t_in, entry=r.entry, stop=r.stop, mark_R_F063=r.F063)
                         for r in opn.itertuples()],
                c3_status=c3, c3_record="C3 on: 21.6% of days followed by a top-20% 7-day move vs 18.0% base (lift 1.20); "
                                        "no direction information (Workstream C). Information only.",
                comp_new_signals=[dict(sym=r.sym, entry_time=r.entry_time, C3_at_entry=r.C3_at_entry, live=r.live, status=r.status)
                                  for r in CT[CT.entry_time >= data_end - pd.Timedelta(days=NEW_DAYS)].itertuples()],
                scoreboards=sb, new_rows=dict(flag_log=n_new_flags, comp_log=n_new_comp))
    js = json.dumps(jsonable(summ), indent=1, default=str)
    open(os.path.join(OUT, "latest.json"), "w").write(js)
    open(os.path.join(HIST, f"{NOW:%Y-%m-%d_%H%M}.json"), "w").write(js)
    gl = os.path.join(OUT, "gauge_log_rev1.csv")
    pd.DataFrame([dict(run_utc=NOW, data_end=data_end, **{k: G[k] for k in ("n_closed", "rolling30", "rolling60", "cusum", "cusum_over")})]
                 ).to_csv(gl, mode="a", header=not os.path.exists(gl), index=False)
    rows = pd.DataFrame([dict(run_utc=NOW, sym=s, data_end=data_end) for s in SYMS])
    pd.concat([runs, rows], ignore_index=True).to_csv(os.path.join(OUT, "brief_runs_rev1.csv"), index=False)
    print(js[:3000])


if __name__ == "__main__":
    main()
