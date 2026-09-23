#!/usr/bin/env python3
"""
Extra market-data collector  (rev2: circuit breaker - an unreachable source is abandoned after 5 network failures; HTTP 403/451 abandons at once)  --  companion to binance_data_downloader_rev5.py
NO API KEYS. Python standard library only. Writes ONLY new files under data/extra/,
never touches the existing data/*.csv files.

What it collects (each source is isolated: one failing source never stops the others)
-------------------------------------------------------------------------------------
 1. Binance premium index klines, 1h  -> data/extra/{SYM}-premium-1h.csv
      Funding is computed from this premium, so it is a same-day proxy for funding.
      Fixes the funding lag: Binance only publishes fundingRate as MONTHLY archives,
      so data/{SYM}-funding.csv is always up to ~1 month behind.
 2. Binance SPOT klines 1h with taker-buy volume -> data/extra/{SYM}-spot-1h.csv
      Spot CVD vs perp CVD = "real demand or leverage?".
 3. Coinbase BTC-USD / ETH-USD 1h     -> data/extra/coinbase-{BTC,ETH}-USD-1h.csv
      Coinbase premium vs Binance spot = US spot demand proxy.
 4. Deribit DVOL (implied vol index) 1h -> data/extra/deribit-dvol-{BTC,ETH}-1h.csv
 5. Deribit options snapshot, 1 row/run -> data/extra/deribit-options-{BTC,ETH}.csv
      ~30-day ATM IV, 10%-OTM put/call IV, skew, put/call OI ratio, biggest OI strikes.
      FORWARD-ONLY: Deribit has no free history of this; every day not collected is lost.
 6. CFTC Commitments of Traders, CME Bitcoin (TFF report, weekly)
                                      -> data/extra/cftc-cme-bitcoin-tff.csv
 7. Health file                        -> data/extra/status.json
      last timestamp, row count and error (if any) per file. Read this first.

ASSUMPTIONS / VERIFY-ON-FIRST-RUN (flagged per project rules)
  A. Endpoint formats were checked on 2026-09-23 from outside GitHub (Deribit DVOL and
     book summary, Coinbase candles, CFTC TFF dataset gpe5-46if code 133741). The build
     workspace could NOT reach them directly, so the first Action run is the real test.
  B. GitHub runners use US IP addresses. Deribit and Coinbase may treat US traffic
     differently; if a source errors every run, status.json will show it.
  C. Binance SPOT archives switched to MICROSECOND timestamps from 2025-01-01. Handled
     below by normalising any timestamp > 1e14 to milliseconds.
  D. premiumIndexKlines monthly archives are assumed to exist like klines; if a month
     404s the script falls back to that month's daily files.
  E. HYPEUSDT may have no Binance spot market -> spot file for it simply stays absent.
"""
import csv, os, io, json, zipfile, time, urllib.request, urllib.parse, datetime as dt, traceback

SYMBOLS   = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "HYPEUSDT"]
OUTDIR    = os.path.join("data", "extra")
START     = (2020, 1)          # backfill start for premium / spot / coinbase
DELAY     = 0.15
UA        = {"User-Agent": "btc-futures-data-collector/1.0"}

VISION = "https://data.binance.vision/data"
PREM_M = VISION + "/futures/um/monthly/premiumIndexKlines/{s}/1h/{s}-1h-{y}-{m:02d}.zip"
PREM_D = VISION + "/futures/um/daily/premiumIndexKlines/{s}/1h/{s}-1h-{y}-{m:02d}-{d:02d}.zip"
SPOT_M = VISION + "/spot/monthly/klines/{s}/1h/{s}-1h-{y}-{m:02d}.zip"
SPOT_D = VISION + "/spot/daily/klines/{s}/1h/{s}-1h-{y}-{m:02d}-{d:02d}.zip"

STATUS = {}
NET_FAILS = {"n": 0}          # circuit breaker: consecutive network errors (not 404s)
MAX_NET_FAILS = 5

class SourceDown(RuntimeError):
    pass

# ----------------------------------------------------------------- helpers
def fetch(url, tries=3):
    """None = not found. Raises SourceDown after MAX_NET_FAILS consecutive network failures,
    so an unreachable source is abandoned quickly instead of retrying every file."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                NET_FAILS["n"] = 0
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                NET_FAILS["n"] = 0
                return None                      # file not there: normal, don't retry
            if e.code in (400, 403, 451):
                raise SourceDown(f"HTTP {e.code} (blocked or bad request) for {url}")
            time.sleep(2 * (i + 1))
        except SourceDown:
            raise
        except Exception:
            time.sleep(2 * (i + 1))
        finally:
            time.sleep(DELAY)
    NET_FAILS["n"] += 1
    if NET_FAILS["n"] >= MAX_NET_FAILS:
        raise SourceDown(f"{MAX_NET_FAILS} consecutive network failures, last: {url}")
    return None

def fetch_json(url):
    b = fetch(url)
    return json.loads(b) if b else None

def to_ms(t):
    t = int(t)
    return t // 1000 if t > 10**14 else t        # microseconds -> ms (Binance spot 2025+)

def last_ts(path):
    if not os.path.exists(path): return None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END); n = f.tell()
        if n == 0: return None
        f.seek(-min(n, 4096), os.SEEK_END)
        lines = [l for l in f.read().decode("utf-8", "ignore").splitlines() if l.strip()]
    try: return int(lines[-1].split(",")[0])
    except (ValueError, IndexError): return None

def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12: y, m = y + 1, 1

def today():      return dt.datetime.now(dt.timezone.utc).date()
def yesterday():  return today() - dt.timedelta(days=1)
def last_full_month():
    p = today().replace(day=1) - dt.timedelta(days=1)
    return (p.year, p.month)

def zip_rows(blob):
    if not blob: return
    try: zf = zipfile.ZipFile(io.BytesIO(blob))
    except Exception: return
    with zf.open(zf.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            p = line.strip().split(",")
            if len(p) < 6: continue
            try: ot = to_ms(p[0])
            except ValueError: continue          # header line
            yield ot, p

def record(name, path, err=None):
    rows, last = 0, last_ts(path) if path and os.path.exists(path) else None
    if path and os.path.exists(path):
        with open(path) as f: rows = max(sum(1 for _ in f) - 1, 0)
    STATUS[name] = {
        "file": path, "rows": rows,
        "last_utc": dt.datetime.fromtimestamp(last / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if last else None,
        "error": err,
    }
    print(f"{name:34s} rows={rows:>8,}  last={STATUS[name]['last_utc']}  {'ERR: ' + err if err else ''}")

def guarded(name, path, fn, *a):
    NET_FAILS["n"] = 0
    try:
        fn(*a); record(name, path)
    except Exception as e:
        record(name, path, f"{type(e).__name__}: {e}")
        traceback.print_exc()

# --------------------------------------------- 1+2: Binance archive klines
def vision_klines(symbol, path, url_m, url_d, header, pick):
    last = last_ts(path)
    new = last is None
    start = START if new else (lambda d: (d.year, d.month))(dt.datetime.utcfromtimestamp(last / 1000))
    wrote = 0
    with open(path, "w" if new else "a", newline="") as fh:
        w = csv.writer(fh)
        if new: w.writerow(header)
        def emit(blob):
            nonlocal last, wrote
            for ot, p in zip_rows(blob):
                if last is not None and ot <= last: continue
                w.writerow([ot] + pick(p)); last = ot; wrote += 1
        for y, m in months(start, last_full_month()):
            blob = fetch(url_m.format(s=symbol, y=y, m=m))
            if blob: emit(blob)
            elif (y, m) == last_full_month():    # just-ended month not archived yet -> daily
                # (older missing months = symbol not listed yet; skip, avoids ~30 404s/month)
                d = dt.date(y, m, 1)
                while d.month == m:
                    emit(fetch(url_d.format(s=symbol, y=d.year, m=d.month, d=d.day)))
                    d += dt.timedelta(days=1)
        d = today().replace(day=1)
        while d <= yesterday():
            emit(fetch(url_d.format(s=symbol, y=d.year, m=d.month, d=d.day)))
            d += dt.timedelta(days=1)
    if new and wrote == 0:
        os.remove(path)
        raise RuntimeError("no data returned (symbol not listed or path changed)")

def premium(symbol):
    path = os.path.join(OUTDIR, f"{symbol}-premium-1h.csv")
    guarded(f"{symbol} premium 1h", path, vision_klines, symbol, path, PREM_M, PREM_D,
            ["open_time", "open", "high", "low", "close"], lambda p: p[1:5])

def spot(symbol):
    path = os.path.join(OUTDIR, f"{symbol}-spot-1h.csv")
    guarded(f"{symbol} spot 1h", path, vision_klines, symbol, path, SPOT_M, SPOT_D,
            ["open_time", "open", "high", "low", "close", "volume", "taker_buy_base", "taker_buy_quote"],
            lambda p: p[1:6] + [p[9], p[10]])

# ------------------------------------------------------------- 3: Coinbase
def coinbase(product):
    path = os.path.join(OUTDIR, f"coinbase-{product}-1h.csv")
    def run():
        last = last_ts(path)
        new = last is None
        cur = (dt.datetime(*START, 1, tzinfo=dt.timezone.utc) if new
               else dt.datetime.fromtimestamp(last / 1000, dt.timezone.utc) + dt.timedelta(hours=1))
        end = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        with open(path, "w" if new else "a", newline="") as fh:
            w = csv.writer(fh)
            if new: w.writerow(["open_time", "open", "high", "low", "close", "volume"])
            while cur < end:
                nxt = min(cur + dt.timedelta(hours=300), end)       # API max 300 candles
                q = urllib.parse.urlencode({"granularity": 3600,
                    "start": cur.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end": (nxt - dt.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")})
                arr = fetch_json(f"https://api.exchange.coinbase.com/products/{product}/candles?{q}")
                if arr is None: raise RuntimeError(f"request failed at {cur}")
                # format: [time_s, low, high, open, close, volume], newest first
                for r in sorted(arr, key=lambda r: r[0]):
                    ot = int(r[0]) * 1000
                    if last is not None and ot <= last: continue
                    if ot >= int(end.timestamp() * 1000): continue    # skip unfinished hour
                    w.writerow([ot, r[3], r[2], r[1], r[4], r[5]]); last = ot
                cur = nxt
                time.sleep(0.2)
    guarded(f"coinbase {product} 1h", path, run)

# --------------------------------------------------------- 4: Deribit DVOL
def dvol(ccy):
    path = os.path.join(OUTDIR, f"deribit-dvol-{ccy}-1h.csv")
    def run():
        last = last_ts(path)
        new = last is None
        start = int(dt.datetime(2021, 3, 1, tzinfo=dt.timezone.utc).timestamp() * 1000) if new else last + 1
        end = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        rows, cur = [], start
        while cur < end:
            chunk_end = min(cur + 1000 * 3600 * 1000, end)             # ~1000 hourly points
            q = urllib.parse.urlencode({"currency": ccy, "start_timestamp": cur,
                                        "end_timestamp": chunk_end, "resolution": 3600})
            js = fetch_json(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?{q}")
            if js is None or "result" not in js: raise RuntimeError(f"request failed at {cur}")
            rows += js["result"]["data"]
            cur = chunk_end + 1
        rows = sorted({int(r[0]): r for r in rows}.values(), key=lambda r: r[0])
        now_hour = end - end % 3600000
        with open(path, "w" if new else "a", newline="") as fh:
            w = csv.writer(fh)
            if new: w.writerow(["open_time", "open", "high", "low", "close"])
            for r in rows:
                if last is not None and r[0] <= last: continue
                if r[0] >= now_hour: continue                          # unfinished hour
                w.writerow(r[:5]); last = r[0]
    guarded(f"deribit DVOL {ccy} 1h", path, run)

# ---------------------------------------------- 5: Deribit options snapshot
def parse_opt(name):
    # BTC-24SEP26-90000-C
    try:
        _, exp, k, cp = name.split("-")
        ed = dt.datetime.strptime(exp, "%d%b%y").replace(hour=8, tzinfo=dt.timezone.utc)
        return ed, float(k), cp
    except Exception:
        return None

def options_snapshot(ccy):
    path = os.path.join(OUTDIR, f"deribit-options-{ccy}.csv")
    header = ["snap_time", "spot", "expiry_used", "days_to_expiry", "atm_iv", "put10_iv", "call10_iv",
              "skew10_put_minus_call", "put_call_oi_ratio_45d", "total_oi_45d",
              "max_oi_put_strike_45d", "max_oi_call_strike_45d"]
    def run():
        js = fetch_json(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={ccy}&kind=option")
        if not js or "result" not in js: raise RuntimeError("book summary unavailable")
        now = dt.datetime.now(dt.timezone.utc)
        opts = []
        for r in js["result"]:
            p = parse_opt(r.get("instrument_name", ""))
            if not p or not r.get("mark_iv"): continue
            ed, k, cp = p
            opts.append(dict(exp=ed, dte=(ed - now).total_seconds() / 86400, k=k, cp=cp,
                             iv=float(r["mark_iv"]), oi=float(r.get("open_interest") or 0),
                             S=float(r.get("underlying_price") or r.get("estimated_delivery_price") or 0)))
        if not opts: raise RuntimeError("no options parsed")
        # expiry closest to 30 days, at least 7 days out
        exps = sorted({(o["exp"], o["dte"]) for o in opts if o["dte"] >= 7}, key=lambda e: abs(e[1] - 30))
        ex, dte = exps[0]
        sub = [o for o in opts if o["exp"] == ex]
        S = sorted(o["S"] for o in sub)[len(sub) // 2]
        def nearest(cp, target):
            c = [o for o in sub if o["cp"] == cp]
            return min(c, key=lambda o: abs(o["k"] - target))["iv"] if c else None
        atm = [x for x in (nearest("C", S), nearest("P", S)) if x is not None]
        atm_iv = sum(atm) / len(atm) if atm else None
        p10, c10 = nearest("P", 0.9 * S), nearest("C", 1.1 * S)
        near = [o for o in opts if 0 < o["dte"] <= 45]
        poi = sum(o["oi"] for o in near if o["cp"] == "P"); coi = sum(o["oi"] for o in near if o["cp"] == "C")
        def top_strike(cp):
            agg = {}
            for o in near:
                if o["cp"] == cp: agg[o["k"]] = agg.get(o["k"], 0) + o["oi"]
            return max(agg, key=agg.get) if agg else None
        row = [int(now.timestamp() * 1000), round(S, 2), ex.strftime("%Y-%m-%d"), round(dte, 2),
               atm_iv, p10, c10, (p10 - c10) if p10 is not None and c10 is not None else None,
               round(poi / coi, 4) if coi else None, round(poi + coi, 2), top_strike("P"), top_strike("C")]
        new = not os.path.exists(path)
        with open(path, "a", newline="") as fh:
            w = csv.writer(fh)
            if new: w.writerow(header)
            w.writerow(row)
    guarded(f"deribit options {ccy}", path, run)

# ------------------------------------------------------------------ 6: CFTC
def cftc_bitcoin():
    path = os.path.join(OUTDIR, "cftc-cme-bitcoin-tff.csv")
    cols = ["report_date_as_yyyy_mm_dd", "open_interest_all",
            "dealer_positions_long_all", "dealer_positions_short_all",
            "asset_mgr_positions_long", "asset_mgr_positions_short",
            "lev_money_positions_long", "lev_money_positions_short",
            "other_rept_positions_long", "other_rept_positions_short",
            "nonrept_positions_long_all", "nonrept_positions_short_all"]
    def run():
        q = urllib.parse.urlencode({"$where": "cftc_contract_market_code='133741'",
                                    "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": 5000,
                                    "$select": ",".join(cols)})
        arr = fetch_json(f"https://publicreporting.cftc.gov/resource/gpe5-46if.json?{q}")
        if not arr: raise RuntimeError("CFTC query returned nothing")
        with open(path, "w", newline="") as fh:                     # small: rewrite in full
            w = csv.writer(fh)
            w.writerow(["report_time"] + cols[1:])
            for r in arr:
                d = dt.datetime.strptime(r["report_date_as_yyyy_mm_dd"][:10], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
                w.writerow([int(d.timestamp() * 1000)] + [r.get(c, "") for c in cols[1:]])
    guarded("cftc CME bitcoin TFF", path, run)

# ------------------------------------------------------------------- main
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for s in SYMBOLS:
        premium(s)
        spot(s)
    for p in ("BTC-USD", "ETH-USD"):
        coinbase(p)
    for c in ("BTC", "ETH"):
        dvol(c)
        options_snapshot(c)
    cftc_bitcoin()
    STATUS["_run_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(OUTDIR, "status.json"), "w") as f:
        json.dump(STATUS, f, indent=1)
    bad = [k for k, v in STATUS.items() if isinstance(v, dict) and v.get("error")]
    print(f"\n[done] {len(STATUS) - 1} sources, {len(bad)} with errors: {bad}")

if __name__ == "__main__":
    main()
