#!/usr/bin/env python3
"""
Binance FUTURES (USDT-M perp) historical + incremental downloader  (rev6, 2026-09-24)
NO API KEY NEEDED. Standard library only.

WHY rev6 (fixes found 2026-09-24; rev5 is left in the repo untouched)
  1. GAP-SAFE KLINES. rev5 appended any day it could fetch and silently skipped a day whose
     archive was not published yet. Because it only ever appends rows newer than the last one,
     a skipped day was lost for good as soon as a later day was written. rev6 walks the days
     strictly in order and STOPS at the first day that is not available yet ("waiting"), so a
     later day is never written before an earlier one.
  2. MONTH ROLLOVER. rev5 took the last days of a finished month only from the MONTHLY archive,
     which Binance publishes some days into the new month. If it was not out yet, rev5 wrote the
     new month's first day and the previous month's last days were skipped forever. rev6 uses the
     monthly file when it exists and otherwise falls back to that month's DAILY files.
  3. GAP-SAFE METRICS. Same in-order rule for the OI / long-short daily dumps.
  4. CONTINUITY CHECK after every run -> data/status_download.json:
       per file: last bar (UTC), lag in hours, rows added, day it is waiting for, gaps found.
     The script exits with code 1 (job shows red in GitHub Actions) if
       - a kline file has a gap that is not on the KNOWN_GAPS list, or bars out of order,
       - a kline file lags more than MAX_LAG_HOURS,
       - a network error (not a plain "not published yet") stopped a download.
     The workflow's commit step runs with `if: always()`, so whatever was downloaded is still saved.

UNCHANGED from rev5: symbols, timeframes, file names and columns, funding (monthly archives,
REST fallback switch), metrics columns. Output files are byte-compatible with rev5.

RULES FOR A MISSING DAY (flagged assumptions)
  * File still empty (coin not listed yet)           -> skip the day, keep going.
  * Day is newer than GAP_GIVE_UP_DAYS               -> "waiting": stop this file, retry next run.
  * Day is older than GAP_GIVE_UP_DAYS and still 404 -> treat as a permanent Binance hole:
    skip it, record it in status as a NEW gap (job goes red until you inspect it and, if it is
    genuine, add it to KNOWN_GAPS below).
  * Network error (anything but HTTP 404)           -> stop this file, retry next run.
  GAP_GIVE_UP_DAYS = 5 and MAX_LAG_HOURS = 60 are choices, not facts - change them if needed.

KNOWN_GAPS: holes in Binance's own archive, verified in the repo files on 2026-09-24 (all 4 TFs):
  XRPUSDT 2022-02-26..2022-02-28 and 2022-04-01..2022-04-02. No other coin/TF has a gap.

Source: https://data.binance.vision  (Binance public historical-data bucket)
"""
import csv, os, io, sys, zipfile, urllib.request, urllib.error, urllib.parse, json, time
import datetime as dt

# ------------------------- SETTINGS -------------------------
SYMBOLS    = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "HYPEUSDT"]
MARKET     = "futures/um"
TIMEFRAMES = ["5m", "15m", "1h", "1d"]
START      = (2019, 9)                    # kline/funding backfill start (new files only)
OUTDIR     = "data"
STATUS     = os.path.join(OUTDIR, "status_download.json")
REQUEST_DELAY_SEC = 0.15
RETRIES    = 3                            # for network errors (not for 404)

KEEP_TAKER       = True
DOWNLOAD_FUNDING = True
USE_REST_FUNDING = False
DOWNLOAD_METRICS = True
METRICS_START    = (2021, 1)

GAP_GIVE_UP_DAYS = 5
MAX_LAG_HOURS    = 60

KNOWN_GAPS = {   # symbol -> list of (first missing day, last missing day), inclusive, UTC
    "XRPUSDT": [(dt.date(2022, 2, 26), dt.date(2022, 2, 28)),
                (dt.date(2022, 4, 1), dt.date(2022, 4, 2))],
}
# ------------------------------------------------------------

MONTHLY_URL = "https://data.binance.vision/data/{mkt}/monthly/klines/{sym}/{tf}/{sym}-{tf}-{y}-{m:02d}.zip"
DAILY_URL   = "https://data.binance.vision/data/{mkt}/daily/klines/{sym}/{tf}/{sym}-{tf}-{y}-{m:02d}-{d:02d}.zip"
FUND_MONTHLY_URL = "https://data.binance.vision/data/{mkt}/monthly/fundingRate/{sym}/{sym}-fundingRate-{y}-{m:02d}.zip"
FUND_REST_URL    = "https://fapi.binance.com/fapi/v1/fundingRate"
METRICS_DAILY_URL = "https://data.binance.vision/data/{mkt}/daily/metrics/{sym}/{sym}-metrics-{y}-{m:02d}-{d:02d}.zip"

STEP_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "1d": 86_400_000}

KLINE_HEADER = ["open_time", "open", "high", "low", "close", "volume"]
if KEEP_TAKER:
    KLINE_HEADER += ["taker_buy_base", "taker_buy_quote"]
METRICS_HEADER = ["create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
                  "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
                  "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]

STATUS_DATA = {"files": {}, "problems": []}


# ------------------------- helpers -------------------------
def utc_today():
    return dt.datetime.now(dt.timezone.utc).date()

def yesterday():
    return utc_today() - dt.timedelta(days=1)

def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12: m, y = 1, y + 1

def last_complete_month():
    prev = utc_today().replace(day=1) - dt.timedelta(days=1)
    return (prev.year, prev.month)

def ms_to_date(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()

def ms_to_str(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")

def fetch(url):
    """-> ('ok', bytes) | ('missing', None) for HTTP 404 | ('error', message)."""
    last = "unknown"
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return "ok", r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "missing", None
            last = f"HTTP {e.code}"
        except Exception as e:                      # timeout, DNS, reset ...
            last = type(e).__name__
        finally:
            time.sleep(REQUEST_DELAY_SEC)
        time.sleep(2 * (attempt + 1))
    return "error", last

def read_last_first_col_int(path):
    if not os.path.exists(path): return None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END); size = f.tell()
        if size == 0: return None
        f.seek(-min(size, 4096), os.SEEK_END)
        tail = f.read().decode("utf-8", errors="ignore")
    lines = [l for l in tail.splitlines() if l.strip()]
    if not lines: return None
    try: return int(float(lines[-1].split(",")[0]))
    except ValueError: return None

def in_known_gap(symbol, day):
    return any(a <= day <= b for a, b in KNOWN_GAPS.get(symbol, []))


# ------------------------- KLINES -------------------------
def _kline_row(p):
    row = [p[0], p[1], p[2], p[3], p[4], p[5]]
    if KEEP_TAKER:
        row += [p[9] if len(p) > 9 else "", p[10] if len(p) > 10 else ""]
    return row

def rows_from_zip(data):
    if data is None: return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return
    with zf.open(zf.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            p = line.strip().split(",")
            if len(p) < 6: continue
            try: ot = int(p[0])
            except ValueError: continue
            yield ot, _kline_row(p)

class MonthCache:
    """Monthly archive split into days: {date: [(ot,row),...]}. status 'ok'|'missing'|'error'."""
    def __init__(self):
        self.c = {}
    def get(self, symbol, tf, y, m):
        k = (symbol, tf, y, m)
        if k not in self.c:
            st, data = fetch(MONTHLY_URL.format(mkt=MARKET, sym=symbol, tf=tf, y=y, m=m))
            days = {}
            if st == "ok":
                for ot, row in rows_from_zip(data):
                    days.setdefault(ms_to_date(ot), []).append((ot, row))
                if not days: st = "missing"          # unreadable / empty zip
            self.c = {k: (st, days)}                  # keep only one month in memory
        return self.c[k]

def day_rows(symbol, tf, day, cache):
    """Rows for one UTC day. Complete months: monthly archive first, daily as fallback."""
    y, m = day.year, day.month
    if (y, m) <= last_complete_month():
        st, days = cache.get(symbol, tf, y, m)
        if st == "ok" and days.get(day):
            return "ok", days[day]
        if st == "error":
            return "error", days
    st, data = fetch(DAILY_URL.format(mkt=MARKET, sym=symbol, tf=tf, y=y, m=m, d=day.day))
    if st != "ok":
        return st, data
    rows = list(rows_from_zip(data))
    return ("ok", rows) if rows else ("missing", None)

def process_symbol_tf(symbol, tf):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{symbol}-{tf}.csv")
    last_ot = read_last_first_col_int(path)
    is_new = last_ot is None
    info = dict(kind="klines", rows_added=0, waiting_for=None, skipped_gap_days=[], error=None)
    start_day = dt.date(*START, 1) if is_new else ms_to_date(last_ot + STEP_MS[tf])
    cache = MonthCache()
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(KLINE_HEADER)
        day, end = start_day, yesterday()
        while day <= end:
            # fast path for a fresh backfill: a whole pre-listing month is skipped in one request
            if last_ot is None and day.day == 1 and (day.year, day.month) < last_complete_month():
                st, days = cache.get(symbol, tf, day.year, day.month)
                if st == "missing":
                    nxt = (day.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
                    day = nxt; continue
            st, rows = day_rows(symbol, tf, day, cache)
            if st == "ok":
                for ot, row in rows:
                    if last_ot is not None and ot <= last_ot: continue
                    w.writerow(row); last_ot = ot; info["rows_added"] += 1
            elif st == "missing":
                if last_ot is None:
                    pass                                         # not listed yet
                elif (utc_today() - day).days > GAP_GIVE_UP_DAYS:
                    info["skipped_gap_days"].append(str(day))    # permanent hole -> reported
                else:
                    info["waiting_for"] = str(day); break        # not published yet
            else:
                info["error"] = f"{day}: {rows}"; break
            day += dt.timedelta(days=1)
    print(f"{symbol:10s} {tf:4s}  +{info['rows_added']:,} rows"
          + (f"  (waiting for {info['waiting_for']})" if info["waiting_for"] else "")
          + (f"  ERROR {info['error']}" if info["error"] else ""))
    STATUS_DATA["files"][f"{symbol}-{tf}"] = info
    return info["rows_added"]


# ------------------------- FUNDING (unchanged from rev5) -------------------------
def rows_from_funding_zip(data):
    if data is None: return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return
    with zf.open(zf.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            p = line.strip().split(",")
            if len(p) < 2: continue
            try: t = int(p[0])
            except ValueError: continue
            interval = p[1] if len(p) >= 3 else ""
            rate = p[2] if len(p) >= 3 else p[1]
            yield t, [str(t), interval, rate]

def funding_via_rest(symbol, since_ms):
    out, start = [], (since_ms + 1 if since_ms else 0)
    while True:
        q = {"symbol": symbol, "limit": 1000}
        if start: q["startTime"] = start
        st, data = fetch(FUND_REST_URL + "?" + urllib.parse.urlencode(q))
        if st != "ok": break
        try: arr = json.loads(data)
        except Exception: break
        if not arr: break
        for r in arr:
            out.append([str(r["fundingTime"]), "", str(r["fundingRate"])])
        start = arr[-1]["fundingTime"] + 1
        if len(arr) < 1000: break
    return out

def process_funding(symbol):
    path = os.path.join(OUTDIR, f"{symbol}-funding.csv")
    last_ot = read_last_first_col_int(path)
    is_new = last_ot is None
    written = 0
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(["funding_time", "funding_interval_hours", "funding_rate"])
        if USE_REST_FUNDING:
            for row in funding_via_rest(symbol, last_ot):
                ot = int(row[0])
                if last_ot is not None and ot <= last_ot: continue
                w.writerow(row); last_ot = ot; written += 1
        else:
            start_month = START if is_new else (lambda d: (d.year, d.month))(ms_to_date(last_ot))
            for y, m in months(start_month, last_complete_month()):
                st, data = fetch(FUND_MONTHLY_URL.format(mkt=MARKET, sym=symbol, y=y, m=m))
                if st != "ok": continue          # funding is monthly-only; a late month is retried next run
                for ot, row in rows_from_funding_zip(data):
                    if last_ot is not None and ot <= last_ot: continue
                    w.writerow(row); last_ot = ot; written += 1
    print(f"{symbol:10s} fund  +{written:,} rows")
    STATUS_DATA["files"][f"{symbol}-funding"] = dict(kind="funding", rows_added=written)
    return written


# ------------------------- METRICS -------------------------
def _metric_ms(s):
    s = s.strip()
    if not s: return None
    if s.isdigit(): return int(s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return int(dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        except ValueError:
            continue
    return None

def read_last_metric_ms(path):
    if not os.path.exists(path): return None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END); size = f.tell()
        if size == 0: return None
        f.seek(-min(size, 4096), os.SEEK_END)
        tail = f.read().decode("utf-8", errors="ignore")
    lines = [l for l in tail.splitlines() if l.strip()]
    return _metric_ms(lines[-1].split(",")[0]) if lines else None

def rows_from_metrics_zip(data):
    if data is None: return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return
    with zf.open(zf.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            p = line.strip().split(",")
            if len(p) < 3: continue
            ms = _metric_ms(p[0])
            if ms is None: continue
            yield ms, p

def process_metrics(symbol):
    path = os.path.join(OUTDIR, f"{symbol}-metrics.csv")
    last_ms = read_last_metric_ms(path)
    is_new = last_ms is None
    info = dict(kind="metrics", rows_added=0, waiting_for=None, skipped_gap_days=[], error=None)
    # next 5-min snapshot's day: re-fetches a partly filled day, moves on after a 23:55 snapshot
    day = dt.date(*METRICS_START, 1) if is_new else ms_to_date(last_ms + 300_000)
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(METRICS_HEADER)
        while day <= yesterday():
            st, data = fetch(METRICS_DAILY_URL.format(mkt=MARKET, sym=symbol, y=day.year, m=day.month, d=day.day))
            if st == "ok":
                for ms, row in rows_from_metrics_zip(data):
                    if last_ms is not None and ms <= last_ms: continue
                    w.writerow(row); last_ms = ms; info["rows_added"] += 1
            elif st == "missing":
                if last_ms is None:
                    pass
                elif (utc_today() - day).days > GAP_GIVE_UP_DAYS:
                    info["skipped_gap_days"].append(str(day))
                else:
                    info["waiting_for"] = str(day); break
            else:
                info["error"] = f"{day}: {data}"; break
            day += dt.timedelta(days=1)
    print(f"{symbol:10s} metr  +{info['rows_added']:,} rows"
          + (f"  (waiting for {info['waiting_for']})" if info["waiting_for"] else "")
          + (f"  ERROR {info['error']}" if info["error"] else ""))
    STATUS_DATA["files"][f"{symbol}-metrics"] = info
    return info["rows_added"]


# ------------------------- CONTINUITY CHECK -------------------------
def check_klines(symbol, tf):
    """Full scan of one kline file: gaps not on KNOWN_GAPS, bars out of order, last bar, lag."""
    path = os.path.join(OUTDIR, f"{symbol}-{tf}.csv")
    res = dict(new_gaps=[], known_gap_bars=0, out_of_order=0, last_bar_utc=None, lag_hours=None)
    if not os.path.exists(path): return res
    step = STEP_MS[tf]; prev = None
    with open(path, newline="") as f:
        rd = csv.reader(f); next(rd, None)
        for r in rd:
            if not r: continue
            try: t = int(float(r[0]))
            except ValueError: continue
            if prev is not None:
                if t <= prev:
                    res["out_of_order"] += 1
                elif t - prev != step:
                    miss = range(prev + step, t, step)
                    unknown = [x for x in miss if not in_known_gap(symbol, ms_to_date(x))]
                    res["known_gap_bars"] += len(miss) - len(unknown)
                    if unknown:
                        res["new_gaps"].append(f"{ms_to_str(unknown[0])} .. {ms_to_str(unknown[-1])} "
                                               f"({len(unknown)} bars)")
            prev = t
    if prev is not None:
        res["last_bar_utc"] = ms_to_str(prev)
        close = (prev + step) / 1000
        res["lag_hours"] = round((time.time() - close) / 3600, 1)
    return res

def last_metric_lag(symbol):
    ms = read_last_metric_ms(os.path.join(OUTDIR, f"{symbol}-metrics.csv"))
    if ms is None: return None, None
    return ms_to_str(ms), round((time.time() - ms / 1000) / 3600, 1)


def main():
    total = 0
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            total += process_symbol_tf(symbol, tf)
        if DOWNLOAD_FUNDING:
            total += process_funding(symbol)
        if DOWNLOAD_METRICS:
            total += process_metrics(symbol)
    print(f"\n[download] {total:,} new rows written.\n")

    problems = STATUS_DATA["problems"]
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            key = f"{symbol}-{tf}"
            chk = check_klines(symbol, tf)
            STATUS_DATA["files"].setdefault(key, {}).update(chk)
            info = STATUS_DATA["files"][key]
            if chk["new_gaps"]:
                problems.append(f"{key}: NEW GAP {chk['new_gaps']}")
            if chk["out_of_order"]:
                problems.append(f"{key}: {chk['out_of_order']} bars out of order")
            if chk["lag_hours"] is not None and chk["lag_hours"] > MAX_LAG_HOURS:
                problems.append(f"{key}: last bar {chk['last_bar_utc']} UTC is {chk['lag_hours']}h old")
            if info.get("error"):
                problems.append(f"{key}: download error {info['error']}")
        if DOWNLOAD_METRICS:
            mk = f"{symbol}-metrics"; info = STATUS_DATA["files"].get(mk, {})
            info["last_utc"], info["lag_hours"] = last_metric_lag(symbol)
            if info.get("skipped_gap_days"):
                problems.append(f"{mk}: skipped missing days {info['skipped_gap_days']}")
            if info.get("error"):
                problems.append(f"{mk}: download error {info['error']}")

    STATUS_DATA["run_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    STATUS_DATA["ok"] = not problems
    with open(STATUS, "w") as f:
        json.dump(STATUS_DATA, f, indent=1)

    print("[check] last bars:")
    for symbol in SYMBOLS:
        k = STATUS_DATA["files"].get(f"{symbol}-15m", {})
        print(f"  {symbol:10s} 15m last {k.get('last_bar_utc')} UTC, lag {k.get('lag_hours')}h"
              + (f", waiting for {k['waiting_for']}" if k.get("waiting_for") else ""))
    if problems:
        print("\n[check] PROBLEMS:")
        for p in problems: print("  -", p)
        sys.exit(1)
    print("[check] OK - no new gaps, nothing out of order, lag within limit.")

if __name__ == "__main__":
    main()
