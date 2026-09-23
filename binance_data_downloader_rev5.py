#!/usr/bin/env python3
"""
Binance FUTURES (USDT-M perp) historical + incremental downloader  (rev5)
NO API KEY NEEDED. Only uses the Python standard library.

CHANGES vs rev4 (strict superset — nothing removed):
  1. METRICS download (NEW) — open interest + long/short ratios + taker ratio,
     from Binance's Vision "metrics" daily dumps (full history, not the
     30-day REST window). One CSV per symbol: <symbol>-metrics.csv, columns:
         create_time, symbol, sum_open_interest, sum_open_interest_value,
         count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio,
         count_long_short_ratio, sum_taker_long_short_vol_ratio
     This is the OI/long-short feed the funding/OI regime study needs.
  2. SYMBOLS extended to add BNBUSDT + HYPEUSDT (alt-tilt candidates).
  3. 1m dropped from the DEFAULT kline timeframe set (nothing in the project
     uses sub-5m; 1m is ~80% of download volume). Re-add it in one line below.

Inherited unchanged from rev4:
  - Klines keep taker-buy columns so CVD/delta is computable
    (per-bar delta = 2*taker_buy_base - volume).
  - Funding-rate history per symbol (<symbol>-funding.csv).

All three streams (klines / funding / metrics) are incremental and safe to
run on a schedule — a re-run only appends rows newer than what's on disk.

------------------------------------------------------------------------------
ASSUMPTIONS / VERIFY-ON-FIRST-RUN  (flagged, per project standing rules):

  A. METRICS PATH NOT LIVE-TESTED FROM BUILD ENV. The metrics filename/path
     (.../daily/metrics/{sym}/{sym}-metrics-{date}.zip) and its create_time
     format (a datetime STRING, not epoch-ms like klines/funding) are taken
     from Binance's public-data schema, but could not be hit from the build
     sandbox. THE FIRST RUN IS THE REAL TEST. If every symbol prints
     "metrics +0 rows", the path/format changed — the klines+funding halves
     are untouched from your working rev4 and are unaffected.

  B. METRICS_START default = (2021, 1). Binance's metrics dumps begin later
     than klines (klines go back to 2019; metrics roughly 2021-2023 depending
     on symbol). Daily requests before coverage just 404 and are skipped.
       - Raise to (2023, 1) to cut wasted early-404 requests.
       - Lower to (2020, 1) only if you want to probe for earlier coverage.

  C. METRICS ARE DAILY-DUMP-ONLY (5-min granularity inside each day). A full
     metrics backfill iterates day-by-day, so it is the SLOW part: a fresh
     2021->now pull is ~2,000 days x N symbols. Budget ~30-45 min for the
     first full run (klines+funding+metrics, 5 symbols). Incremental re-runs
     after that are quick. Resample the 5-min metrics to 1h yourself.

  D. HYPEUSDT may not be listed on Binance USD-M futures, or under a different
     symbol. If it prints "0 days" across the board, drop it or fix the symbol.

  E. Funding fallback (unchanged): if the whole funding pull is empty, flip
     USE_REST_FUNDING = True.
------------------------------------------------------------------------------

Source: https://data.binance.vision  (Binance public historical-data bucket)
"""
import csv, os, io, zipfile, urllib.request, urllib.parse, json, datetime as dt, time

# ------------------------- SETTINGS -------------------------
SYMBOLS    = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "HYPEUSDT"]
MARKET     = "futures/um"
TIMEFRAMES = ["5m", "15m", "1h", "1d"]   # rev5: 1m dropped from default; add "1m" to re-enable
START      = (2019, 9)                    # kline/funding backfill start
OUTDIR     = "data"
REQUEST_DELAY_SEC = 0.15

KEEP_TAKER       = True     # keep taker-buy base/quote in klines (CVD)
DOWNLOAD_FUNDING = True     # pull funding-rate history
USE_REST_FUNDING = False    # fallback if the Vision funding dumps are unavailable

DOWNLOAD_METRICS = True     # rev5: pull OI + long/short + taker ratio
METRICS_START    = (2021, 1)  # see assumption B above
# ------------------------------------------------------------

MONTHLY_URL = "https://data.binance.vision/data/{mkt}/monthly/klines/{sym}/{tf}/{sym}-{tf}-{y}-{m:02d}.zip"
DAILY_URL   = "https://data.binance.vision/data/{mkt}/daily/klines/{sym}/{tf}/{sym}-{tf}-{y}-{m:02d}-{d:02d}.zip"
FUND_MONTHLY_URL = "https://data.binance.vision/data/{mkt}/monthly/fundingRate/{sym}/{sym}-fundingRate-{y}-{m:02d}.zip"
FUND_REST_URL    = "https://fapi.binance.com/fapi/v1/fundingRate"
METRICS_DAILY_URL = "https://data.binance.vision/data/{mkt}/daily/metrics/{sym}/{sym}-metrics-{y}-{m:02d}-{d:02d}.zip"

# Binance kline column indices: 0 open_time,1 o,2 h,3 l,4 c,5 vol,6 close_time,
# 7 quote_vol,8 n_trades,9 taker_buy_base,10 taker_buy_quote,11 ignore
KLINE_HEADER = ["open_time","open","high","low","close","volume"]
if KEEP_TAKER:
    KLINE_HEADER += ["taker_buy_base","taker_buy_quote"]

METRICS_HEADER = ["create_time","symbol","sum_open_interest","sum_open_interest_value",
                  "count_toptrader_long_short_ratio","sum_toptrader_long_short_ratio",
                  "count_long_short_ratio","sum_taker_long_short_vol_ratio"]


def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12: m, y = 1, y + 1

def days(start_date, end_date):
    d = start_date
    while d <= end_date:
        yield d
        d += dt.timedelta(days=1)

def last_complete_month():
    prev = dt.date.today().replace(day=1) - dt.timedelta(days=1)
    return (prev.year, prev.month)

def yesterday():
    return dt.date.today() - dt.timedelta(days=1)

def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except Exception:
        return None
    finally:
        time.sleep(REQUEST_DELAY_SEC)

def read_last_first_col_int(path):
    """Last line's first column as int (epoch ms). For klines & funding."""
    if not os.path.exists(path): return None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END); size = f.tell()
        if size == 0: return None
        f.seek(-min(size, 4096), os.SEEK_END)
        tail = f.read().decode("utf-8", errors="ignore")
    lines = [l for l in tail.splitlines() if l.strip()]
    if not lines: return None
    try: return int(lines[-1].split(",")[0])
    except ValueError: return None


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
            except ValueError: continue  # header
            yield ot, _kline_row(p)

def process_symbol_tf(symbol, tf):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{symbol}-{tf}.csv")
    last_ot = read_last_first_col_int(path)
    is_new = last_ot is None
    end_month = last_complete_month()
    start_month = START if is_new else (
        (lambda d: (d.year, d.month))(dt.datetime.utcfromtimestamp(last_ot/1000)))
    written = 0
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(KLINE_HEADER)
        for y, m in months(start_month, end_month):
            for ot, row in rows_from_zip(fetch(MONTHLY_URL.format(mkt=MARKET, sym=symbol, tf=tf, y=y, m=m))):
                if last_ot is not None and ot <= last_ot: continue
                w.writerow(row); last_ot = ot; written += 1
        d = dt.date.today().replace(day=1); y_end = yesterday()
        while d <= y_end:
            for ot, row in rows_from_zip(fetch(DAILY_URL.format(mkt=MARKET, sym=symbol, tf=tf, y=d.year, m=d.month, d=d.day))):
                if last_ot is not None and ot <= last_ot: continue
                w.writerow(row); last_ot = ot; written += 1
            d += dt.timedelta(days=1)
    print(f"{symbol:10s} {tf:4s}  +{written:,} rows  -> {path}")
    return written


# ------------------------- FUNDING -------------------------
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
            except ValueError: continue  # header
            interval = p[1] if len(p) >= 3 else ""
            rate = p[2] if len(p) >= 3 else p[1]
            yield t, [str(t), interval, rate]

def funding_via_rest(symbol, since_ms):
    out, start = [], (since_ms + 1 if since_ms else 0)
    while True:
        q = {"symbol": symbol, "limit": 1000}
        if start: q["startTime"] = start
        data = fetch(FUND_REST_URL + "?" + urllib.parse.urlencode(q))
        if not data: break
        try: arr = json.loads(data)
        except Exception: break
        if not arr: break
        for r in arr:
            out.append([str(r["fundingTime"]), "", str(r["fundingRate"])])
        start = arr[-1]["fundingTime"] + 1
        if len(arr) < 1000: break
    return out

def process_funding(symbol):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{symbol}-funding.csv")
    last_ot = read_last_first_col_int(path)
    is_new = last_ot is None
    written = 0
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(["funding_time","funding_interval_hours","funding_rate"])
        if USE_REST_FUNDING:
            for row in funding_via_rest(symbol, last_ot):
                ot = int(row[0])
                if last_ot is not None and ot <= last_ot: continue
                w.writerow(row); last_ot = ot; written += 1
        else:
            start_month = START if is_new else (
                (lambda d: (d.year, d.month))(dt.datetime.utcfromtimestamp(last_ot/1000)))
            for y, m in months(start_month, last_complete_month()):
                for ot, row in rows_from_funding_zip(fetch(FUND_MONTHLY_URL.format(mkt=MARKET, sym=symbol, y=y, m=m))):
                    if last_ot is not None and ot <= last_ot: continue
                    w.writerow(row); last_ot = ot; written += 1
    print(f"{symbol:10s} fund  +{written:,} rows  -> {path}")
    return written


# ------------------------- METRICS (OI + long/short) -------------------------
def _metric_ms(s):
    """metrics create_time -> epoch ms. Accepts epoch-ms or a datetime string."""
    s = s.strip()
    if not s: return None
    if s.isdigit(): return int(s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc)
            return int(d.timestamp() * 1000)
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
    if not lines: return None
    return _metric_ms(lines[-1].split(",")[0])

def rows_from_metrics_zip(data):
    """Yield (ms, full_row_list). Preserves all 8 metrics columns verbatim."""
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
            if ms is None: continue  # header or unparseable
            yield ms, p

def process_metrics(symbol):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{symbol}-metrics.csv")
    last_ms = read_last_metric_ms(path)
    is_new = last_ms is None
    start_day = (dt.date(*METRICS_START, 1) if is_new
                 else dt.datetime.utcfromtimestamp(last_ms/1000).date())
    written = 0
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(METRICS_HEADER)
        for d in days(start_day, yesterday()):
            url = METRICS_DAILY_URL.format(mkt=MARKET, sym=symbol, y=d.year, m=d.month, d=d.day)
            for ms, row in rows_from_metrics_zip(fetch(url)):
                if last_ms is not None and ms <= last_ms: continue
                w.writerow(row); last_ms = ms; written += 1
    print(f"{symbol:10s} metr  +{written:,} rows  -> {path}")
    return written


def main():
    total = 0
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            total += process_symbol_tf(symbol, tf)
        if DOWNLOAD_FUNDING:
            total += process_funding(symbol)
        if DOWNLOAD_METRICS:
            total += process_metrics(symbol)
    print(f"\n[done] {total:,} new rows written.")

if __name__ == "__main__":
    main()
