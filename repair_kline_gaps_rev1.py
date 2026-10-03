#!/usr/bin/env python3
"""
One-time repair of holes in the main kline files  (rev1, 2026-10-03). Standard library only.

WHY: data/XRPUSDT-{5m,15m,1h,1d}.csv miss 26-28 Feb 2022 and 1-2 Apr 2022 (KNOWN_GAPS in
  binance_data_downloader_rev7.py). Those days are missing from Binance's MONTHLY archives, but the alt
  downloader found the DAILY 1d files for them on 2026-10-03, and LTC (backfilled by rev7, which falls back to
  daily files) has all of them. This script looks for the daily file of every missing day and inserts the rows.

WHAT IT DOES: for every data/<SYMBOL>-<tf>.csv of the daily pipeline it finds missing bars between the first
  and the last row, downloads the daily archive of each affected day, inserts the rows that are missing (in
  order, existing lines untouched, same columns as rev7) and rewrites the file. Nothing is ever removed.
  Days newer than SKIP_RECENT_DAYS are left to the daily downloader. Result: data/status_gap_repair.json.
  The daily downloader is not changed; its KNOWN_GAPS list only silences an alarm and is harmless once filled.

USAGE: python repair_kline_gaps_rev1.py            (--check = report only, write nothing; --selftest = offline test)
"""
import os, io, sys, json, time, zipfile, urllib.request, urllib.error
import datetime as dt

SYMBOLS    = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "HYPEUSDT", "LTCUSDT"]
TIMEFRAMES = ["5m", "15m", "1h", "1d"]
OUTDIR     = "data"
MARKET     = "futures/um"
SKIP_RECENT_DAYS = 7
RETRIES    = 3
DAILY_URL  = "https://data.binance.vision/data/{mkt}/daily/klines/{sym}/{tf}/{sym}-{tf}-{d}.zip"
STEP_MS    = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "1d": 86_400_000}
DAY_MS     = 86_400_000

def fetch(url):
    """-> ('ok', bytes) | ('missing', None) for HTTP 404 | ('error', message)."""
    last = "unknown"
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return "ok", r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return "missing", None
            last = f"HTTP {e.code}"
        except Exception as e:
            last = type(e).__name__
        time.sleep(2 * (attempt + 1))
    return "error", last

def rows_from_zip(data):
    """Daily archive -> {open_time: csv line in the rev7 column layout}."""
    out = {}
    zf = zipfile.ZipFile(io.BytesIO(data))
    with zf.open(zf.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            p = line.strip().split(",")
            if len(p) < 6: continue
            try: ot = int(p[0])
            except ValueError: continue                      # header line
            out[ot] = ",".join([p[0], p[1], p[2], p[3], p[4], p[5], p[9] if len(p) > 9 else "", p[10] if len(p) > 10 else ""])
    return out

def day_str(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")

def repair(symbol, tf, check_only=False):
    path = os.path.join(OUTDIR, f"{symbol}-{tf}.csv")
    info = dict(missing_bars=0, days_with_holes=[], rows_added=0, days_not_in_archive=[], still_missing_bars=0, error=None)
    if not os.path.exists(path): info["error"] = "file not found"; return info
    with open(path, "rb") as f: raw = f.read()
    nl = b"\r\n" if raw[:4096].count(b"\r\n") else b"\n"
    lines = [l for l in raw.split(nl) if l.strip()]
    header, body = lines[0], lines[1:]
    step = STEP_MS[tf]; ts = []
    for l in body:
        try: ts.append(int(float(l.split(b",", 1)[0])))
        except ValueError: ts.append(None)
    if any(t is None for t in ts) or any(b <= a for a, b in zip(ts, ts[1:])):
        info["error"] = "file has unreadable or out-of-order rows - not touched"; return info
    cutoff = (time.time() - SKIP_RECENT_DAYS * 86400) * 1000
    days = set()
    for a, b in zip(ts, ts[1:]):
        if b - a != step:
            info["missing_bars"] += (b - a) // step - 1
            for t in range(a + step, b, step):
                if t < cutoff: days.add(t // DAY_MS * DAY_MS)
    info["days_with_holes"] = [day_str(d) for d in sorted(days)]
    if not days or check_only:
        info["still_missing_bars"] = info["missing_bars"]; return info
    have = set(ts); new = {}
    for d in sorted(days):
        st, data = fetch(DAILY_URL.format(mkt=MARKET, sym=symbol, tf=tf, d=day_str(d)))
        if st == "error":
            info["error"] = f"{day_str(d)}: {data}"; continue
        got = {}
        if st == "ok":
            try: got = rows_from_zip(data)
            except Exception as e: info["error"] = f"{day_str(d)}: bad zip {type(e).__name__}"
        add = {ot: l for ot, l in got.items() if ot not in have and ts[0] < ot < ts[-1] and ot // DAY_MS * DAY_MS == d and ot % step == 0}
        if not add: info["days_not_in_archive"].append(day_str(d))
        new.update(add)
    if new:
        merged = sorted([(t, l) for t, l in zip(ts, body)] + [(t, l.encode()) for t, l in new.items()], key=lambda x: x[0])
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(header + nl + nl.join(l for _, l in merged) + nl)
        os.replace(tmp, path)
        info["rows_added"] = len(new)
        ts = [t for t, _ in merged]
    info["still_missing_bars"] = sum((b - a) // step - 1 for a, b in zip(ts, ts[1:]) if b - a != step)
    return info

def main():
    if "--selftest" in sys.argv: return selftest()
    check = "--check" in sys.argv
    status = {"run_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "check_only": check, "files": {}}
    bad = False
    for s in SYMBOLS:
        for tf in TIMEFRAMES:
            info = repair(s, tf, check)
            if info["missing_bars"] or info["error"]:
                status["files"][f"{s}-{tf}"] = info
                print(f"{s:9s} {tf:3s} missing {info['missing_bars']:5d} bars on {len(info['days_with_holes'])} days -> added {info['rows_added']}, "
                      f"still missing {info['still_missing_bars']}" + (f", no daily file: {info['days_not_in_archive']}" if info["days_not_in_archive"] else "")
                      + (f"  ERROR {info['error']}" if info["error"] else ""))
            else:
                print(f"{s:9s} {tf:3s} complete")
            bad = bad or bool(info["error"])
    status["rows_added"] = sum(i["rows_added"] for i in status["files"].values())
    status["still_missing_bars"] = sum(i["still_missing_bars"] for i in status["files"].values())
    with open(os.path.join(OUTDIR, "status_gap_repair.json"), "w") as f: json.dump(status, f, indent=1)
    print(f"[done] rows added {status['rows_added']}, bars still missing {status['still_missing_bars']}")
    if bad: sys.exit(1)

def selftest():
    import tempfile
    global OUTDIR, fetch
    def line(t, px): return f"{t},{px},{px + 1},{px - 1},{px},10,6,60"
    def zline(t, px): return f"{t},{px},{px + 1},{px - 1},{px},10,{t + 3599999},1000,5,6,60,0"
    t0 = 1645833600000                                        # 2022-02-26 00:00 UTC
    allts = [t0 - 48 * 3600000 + i * 3600000 for i in range(24 * 6)]
    hole = [t for t in allts if t0 <= t < t0 + 2 * DAY_MS]    # 26 and 27 Feb missing in the file
    def mkzip(text):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z: z.writestr("x.csv", text)
        return b.getvalue()
    z26 = mkzip("open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
                + "\n".join(zline(t, 7) for t in hole if t < t0 + DAY_MS))
    calls = []
    def fake(url):
        calls.append(url)
        return ("ok", z26) if url.endswith("XUSDT-1h-2022-02-26.zip") else ("missing", None)
    real = fetch; fetch = fake
    for nl in ("\n", "\r\n"):
        with tempfile.TemporaryDirectory() as tmp:
            OUTDIR = tmp; p = os.path.join(tmp, "XUSDT-1h.csv")
            with open(p, "w", newline="") as f:
                f.write("open_time,open,high,low,close,volume,taker_buy_base,taker_buy_quote" + nl + nl.join(line(t, 5) for t in allts if t not in hole) + nl)
            before = open(p, "rb").read()
            c = repair("XUSDT", "1h", check_only=True)
            assert c["missing_bars"] == 48 and c["days_with_holes"] == ["2022-02-26", "2022-02-27"] and open(p, "rb").read() == before, c
            r = repair("XUSDT", "1h")
            assert r["rows_added"] == 24 and r["days_not_in_archive"] == ["2022-02-27"] and r["still_missing_bars"] == 24 and not r["error"], r
            after = open(p, "rb").read(); L = after.decode().split(nl)
            assert L[-1] == "" and len(L) == 1 + (len(allts) - 24) + 1 and (b"\r\n" in after) == (nl == "\r\n")
            ts = [int(x.split(",")[0]) for x in L[1:-1]]; assert ts == sorted(ts) and len(set(ts)) == len(ts)
            assert L[1 + 48] == line(t0, 7) and all(x in after.decode() for x in before.decode().split(nl)[:5])
            for old in before.split(nl.encode()): assert old in after
            r2 = repair("XUSDT", "1h"); assert r2["rows_added"] == 0 and r2["still_missing_bars"] == 24, r2
    fetch = real
    print("selftest OK")

if __name__ == "__main__":
    main()
