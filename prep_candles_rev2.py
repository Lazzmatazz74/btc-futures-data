#!/usr/bin/env python3
"""
prep_candles_rev2.py  (2026-09-24) - repo CSVs -> legacy-named, gap-filled candles for the engines.

Same output as prep_candles_rev1.py (files {SYM}{tf}.csv with open_time, open, high, low, close,
volume, taker_buy_base; missing bars filled flat at the prior close, volume 0), with two changes:

  1. GAPS ARE REPORTED, NOT FILLED SILENTLY. Every filled stretch is checked against KNOWN_GAPS
     (holes in Binance's own archive, verified 2026-09-24: XRPUSDT 2022-02-26..28, 2022-04-01..02).
     A known gap is filled quietly. Any other gap is still filled flat (so the engines run), but a
     WARNING is printed and the gap is written to prep_gap_report_rev2.csv.
     --strict makes an unknown gap stop the script instead.
  2. TRAILING PARTIAL DAY IS TRIMMED. The HTF engine reshapes 15m bars into whole UTC days and
     crashes on a partial last day; rev1 relied on the data ending at 23:45. rev2 trims every
     timeframe to the last complete UTC day. (Change vs rev1 - flagged.)

Also importable: forward_signal_log_rev2.py uses prepare() so the forward log and the research
sessions build candles the same way.

Usage (research session defaults are the same paths as rev1):
    python3 prep_candles_rev2.py                       # /home/claude/data -> /home/claude/work/candles
    python3 prep_candles_rev2.py --raw data --out /tmp/candles --syms BTC ETH XRP BNB --strict
"""
import argparse, datetime as dt, os, sys
import pandas as pd

KNOWN_GAPS = {
    "XRPUSDT": [(dt.date(2022, 2, 26), dt.date(2022, 2, 28)),
                (dt.date(2022, 4, 1), dt.date(2022, 4, 2))],
}
FREQ = {"15m": "15min", "1h": "1h", "1d": "1D"}


class GapError(RuntimeError):
    pass


def _known(sym, ts):
    d = ts.date()
    return any(a <= d <= b for a, b in KNOWN_GAPS.get(sym, []))


def prepare(df, sym, tf, strict=False):
    """df: repo kline frame (open_time ms, ...). Returns (prepared frame, list of unknown gaps)."""
    fr = FREQ[tf]
    d = df.copy(); d.index = pd.to_datetime(d.open_time, unit="ms")
    d = d[~d.index.duplicated(keep="first")].sort_index()
    start = d.index[0] if d.index[0] == d.index[0].normalize() else d.index[0].ceil("1D")
    last_full_day_end = (d.index[-1] + pd.Timedelta(fr)).normalize()      # first bar NOT in a full day
    d = d[(d.index >= start) & (d.index < last_full_day_end)]
    full = pd.date_range(start, last_full_day_end - pd.Timedelta(fr), freq=fr)
    missing = full.difference(d.index)
    unknown = []
    if len(missing):
        s = pd.Series(missing)
        runs = (s.diff() != pd.Timedelta(fr)).cumsum()
        for _, g in s.groupby(runs):
            a, b = g.iloc[0], g.iloc[-1]
            if not all(_known(sym, x) for x in (a, b)):
                unknown.append(dict(sym=sym, tf=tf, first_missing=a, last_missing=b, bars=len(g)))
    if unknown and strict:
        raise GapError(f"{sym} {tf}: unknown gaps {unknown}")
    d = d.reindex(full); pc = d.close.ffill()
    for k in ["open", "high", "low", "close"]: d[k] = d[k].fillna(pc)
    for k in ["volume", "taker_buy_base"]: d[k] = d[k].fillna(0)
    d["open_time"] = ((full - pd.Timestamp("1970-01-01")) // pd.Timedelta("1ms")).astype("int64")
    return d[["open_time", "open", "high", "low", "close", "volume", "taker_buy_base"]], unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="/home/claude/data")
    ap.add_argument("--out", default="/home/claude/work/candles")
    ap.add_argument("--syms", nargs="+", default=["BTC", "ETH", "XRP", "BNB"])
    ap.add_argument("--tfs", nargs="+", default=["15m", "1h", "1d"])
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    report = []
    for c in a.syms:
        s = f"{c}USDT"
        for tf in a.tfs:
            raw = pd.read_csv(f"{a.raw}/{s}-{tf}.csv")
            try:
                d, unk = prepare(raw, s, tf, a.strict)
            except GapError as e:
                print("STOP:", e); sys.exit(1)
            d.to_csv(f"{a.out}/{s}{tf}.csv", index=False)
            for u in unk:
                print(f"WARNING {s} {tf}: gap {u['first_missing']} .. {u['last_missing']} "
                      f"({u['bars']} bars) filled flat - not on KNOWN_GAPS, inspect it")
            report += unk
            print(f"{s} {tf}: {len(d):,} bars {d.open_time.iloc[0]}..{d.open_time.iloc[-1]}"
                  f"{'  (' + str(len(unk)) + ' unknown gaps)' if unk else ''}")
    if report:
        pd.DataFrame(report).to_csv(os.path.join(a.out, "prep_gap_report_rev2.csv"), index=False)
        print(f"{len(report)} unknown gap(s) -> {a.out}/prep_gap_report_rev2.csv")
    else:
        print("no unknown gaps")


if __name__ == "__main__":
    main()
