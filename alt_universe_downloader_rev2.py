#!/usr/bin/env python3
"""
Binance USDT-M perp ALT UNIVERSE downloader  (rev2, 2026-10-03)

WHY rev2 (two defects found in the first full run of rev1, ALT_BACKFILL_CHECK_2026-10-03_rev1.md; Matej OK 11:39)
  1. STATE FROM VOLUME. Binance keeps publishing flat zero-volume candles for delisted perps, so rev1 called
     130 dead coins "active". symbols.csv now has last_traded_day and zero_volume_days; state = "active" only
     if the coin traded (volume > 0) within ACTIVE_WITHIN_DAYS; the 30-day liquidity median ends at the last
     traded day. The candle files themselves are left exactly as Binance publishes them.
  2. MISSING DAYS FILLED FROM DAILY FILES. Binance's monthly archives have holes (e.g. 26-28 Feb and 1-2 Apr 2022
     for ~48 coins). rev2 tries the daily file for every missing day: while downloading, and once for the holes
     already in the rev1 files (the file is rewritten in order). A day whose daily file does not exist either is
     written to data/alts/known_gaps.csv and not asked for again (delete its line there to retry).
  Unchanged: file names and columns of 1d/ and funding/, symbol listing, categories. rev1 stays in the repo.
Standard library only. Separate from the daily pipeline (binance_data_downloader_rev7.py), which it does not touch.

WHAT IT DOES (Trading/ALT_RESEARCH_PLAN_rev1.md, data part)
  1. Lists EVERY USDT-M perpetual symbol that ever had data in Binance's public archive - delisted ones
     included (no survivorship bias) - from the bucket index of data.binance.vision.
  2. Per symbol: 1d candles (monthly archives, then daily files for the newest days) and funding
     (monthly archives). Incremental: a later run only fetches what is newer than the file's last row.
  3. data/alts/symbols.csv: first / last day, days, missing days, 30-day median quote volume, state,
     state from volume, last traded day, old_coin flag (perp listed before 2021-01-01).
  4. Categories from the CoinGecko Demo API (key in env CG_DEMO_KEY, never in a file):
     data/alts/categories_latest.csv + a dated copy in data/alts/categories/ (labels are today's,
     NOT point-in-time; the dated copies build a history from now on).
  5. data/alts/status_alts.json. Exit code 1 (red X in Actions) on a network error or if no symbol is found.

OUTPUT
  data/alts/1d/<SYMBOL>.csv        open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_quote
  data/alts/funding/<SYMBOL>.csv   funding_time,funding_interval_hours,funding_rate
  data/alts/symbols.csv, categories_latest.csv, categories/categories_<date>.csv, status_alts.json, known_gaps.csv

USAGE
  python alt_universe_downloader_rev2.py                    everything
  python alt_universe_downloader_rev2.py --limit 5          first 5 symbols only (test run)
  python alt_universe_downloader_rev2.py --symbols LTCUSDT,DOGEUSDT
  python alt_universe_downloader_rev2.py --mode prices      prices + funding only  (--mode categories: categories only)
  python alt_universe_downloader_rev2.py --selftest         offline test of the parsers (no network)

CATEGORIES (chosen 2026-10-03; Matej: "you choose strategic categories")
  From CoinGecko: meme, ai, defi, layer1, layer2, rwa, gaming, depin, privacy.
  From Binance data itself (point-in-time correct): old_coin = perp listed before 2021-01-01;
  new listings are derived in the studies from first_day.
  CoinGecko category ids are resolved at run time against /coins/categories/list (candidates below);
  what was resolved is written to status_alts.json.

ASSUMPTIONS (flagged. Listing, klines and funding were proven by the rev1 runs of 2026-10-03 (900 symbols).
NOT yet run live: the CoinGecko part - no CG_DEMO_KEY secret existed.)
  * Bucket index: https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=...
    returns S3 ListBucketResult XML, 1000 entries per page, continued with marker=.
  * Futures archive timestamps are in milliseconds (values above 1e14 are treated as microseconds).
  * A perpetual symbol ends with USDT and has no "_" (delivery contracts like BTCUSDT_210326 are skipped).
  * A day newer than GAP_GIVE_UP_DAYS that is not the next expected day is not appended (wait for the
    missing day). Older holes: daily file tried once; if it is not there the hole is accepted, listed in
    known_gaps.csv and counted in symbols.csv (missing_days). Holes longer than GAP_FILL_MAX_DAYS are not tried.
"""
import csv, os, io, sys, re, zipfile, json, time, argparse, urllib.request, urllib.error, urllib.parse
import datetime as dt
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

# ------------------------- SETTINGS -------------------------
MARKET   = "futures/um"
OUTDIR   = os.path.join("data", "alts")
WORKERS  = 6
RETRIES  = 3
REQUEST_DELAY_SEC = 0.05
GAP_GIVE_UP_DAYS  = 5
ACTIVE_WITHIN_DAYS = 4                 # last candle WITH VOLUME this recent -> state "active", else "ended"
GAP_FILL_MAX_DAYS  = 45                # longer holes are not looked up day by day
OLD_COIN_BEFORE = dt.date(2021, 1, 1)
EXCLUDE = {"BTCUSDT"}                  # BTC is the benchmark, kept in the daily pipeline (ETH etc. stay in: they are alts)

BUCKET   = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FILES    = "https://data.binance.vision/"
P_MONTHLY_K = "data/{mkt}/monthly/klines/"
P_DAILY_K   = "data/{mkt}/daily/klines/"
P_MONTHLY_F = "data/{mkt}/monthly/fundingRate/"

CG_BASE = "https://api.coingecko.com/api/v3"
CG_DELAY_SEC = 2.5                     # Demo plan: 30 calls/min
CG_MAX_PAGES = 4                       # 250 coins per page, by market cap
CATEGORIES = {   # our label -> (candidate CoinGecko category ids, candidate names; first match wins)
    "meme":    (["meme-token"],                 ["Meme"]),
    "ai":      (["artificial-intelligence"],    ["Artificial Intelligence (AI)", "Artificial Intelligence"]),
    "defi":    (["decentralized-finance-defi"], ["Decentralized Finance (DeFi)"]),
    "layer1":  (["layer-1"],                    ["Layer 1 (L1)"]),
    "layer2":  (["layer-2"],                    ["Layer 2 (L2)"]),
    "rwa":     (["real-world-assets-rwa"],      ["Real World Assets (RWA)"]),
    "gaming":  (["gaming"],                     ["Gaming (GameFi)", "Gaming"]),
    "depin":   (["depin"],                      ["DePIN"]),
    "privacy": (["privacy-coins"],              ["Privacy Coins", "Privacy"]),
}
MULT_PREFIX = re.compile(r"^(1000000|1000|1M)(?=[A-Z0-9])")    # 1000PEPE -> PEPE, 1MBABYDOGE -> BABYDOGE

K_HEADER = ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_quote"]
F_HEADER = ["funding_time", "funding_interval_hours", "funding_rate"]
DAY_MS = 86_400_000
STATUS = {"problems": [], "symbols": {}, "categories": {}}
KNOWN_GAPS = set()                     # (symbol, "YYYY-MM-DD") whose daily file does not exist; loaded from known_gaps.csv


# ------------------------- helpers -------------------------
def utc_today():
    return dt.datetime.now(dt.timezone.utc).date()

def ms_to_date(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()

def norm_ms(t):
    return t // 1000 if t > 10**14 else t

def fetch(url, headers=None):
    """-> ('ok', bytes) | ('missing', None) for HTTP 404 | ('error', message)."""
    last = "unknown"
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=60) as r:
                return "ok", r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "missing", None
            last = f"HTTP {e.code}"
            if e.code == 429: time.sleep(30)
        except Exception as e:
            last = type(e).__name__
        finally:
            time.sleep(REQUEST_DELAY_SEC)
        time.sleep(2 * (attempt + 1))
    return "error", last

def parse_listing(xml_bytes):
    """S3 ListBucketResult -> (common prefixes, keys, truncated, next_marker)."""
    root = ET.fromstring(xml_bytes)
    tag = lambda e: e.tag.split("}")[-1]
    prefixes, keys, truncated, nxt = [], [], False, None
    for el in root:
        t = tag(el)
        if t == "CommonPrefixes":
            for c in el:
                if tag(c) == "Prefix" and c.text: prefixes.append(c.text)
        elif t == "Contents":
            for c in el:
                if tag(c) == "Key" and c.text: keys.append(c.text)
        elif t == "IsTruncated":
            truncated = (el.text or "").strip().lower() == "true"
        elif t == "NextMarker":
            nxt = el.text
    return prefixes, keys, truncated, nxt

def list_bucket(prefix, marker=None, folders=False):
    """All entries under a prefix (after `marker`). -> ('ok', [prefixes or keys]) | ('error', msg)."""
    out = []
    while True:
        q = {"delimiter": "/", "prefix": prefix}
        if marker: q["marker"] = marker
        st, data = fetch(BUCKET + "?" + urllib.parse.urlencode(q))
        if st != "ok":
            return ("error", data) if st == "error" else ("ok", out)
        try:
            prefixes, keys, truncated, nxt = parse_listing(data)
        except ET.ParseError as e:
            return "error", f"bad listing XML: {e}"
        page = prefixes if folders else keys
        out += page
        if not truncated: break
        marker = nxt or (page[-1] if page else None)
        if not marker: break
    return "ok", out

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

def zip_lines(data):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        with zf.open(zf.namelist()[0]) as f:
            for line in io.TextIOWrapper(f, encoding="utf-8"):
                yield line.strip().split(",")
    except Exception:
        return

def kline_rows(data):
    for p in zip_lines(data):
        if len(p) < 6: continue
        try: ot = norm_ms(int(p[0]))
        except ValueError: continue                      # header line
        yield ot, [str(ot), p[1], p[2], p[3], p[4], p[5],
                   p[7] if len(p) > 7 else "", p[8] if len(p) > 8 else "", p[10] if len(p) > 10 else ""]

def funding_rows(data):
    for p in zip_lines(data):
        if len(p) < 2: continue
        try: t = norm_ms(int(p[0]))
        except ValueError: continue
        yield t, [str(t), p[1] if len(p) >= 3 else "", p[2] if len(p) >= 3 else p[1]]

def is_perp_usdt(sym):
    return sym.endswith("USDT") and "_" not in sym and sym not in EXCLUDE

KEY_MONTH = re.compile(r"-(\d{4})-(\d{2})\.zip$")
KEY_DAY   = re.compile(r"-(\d{4})-(\d{2})-(\d{2})\.zip$")


# ------------------------- per symbol -------------------------
def daily_key(sym, day):
    return P_DAILY_K.format(mkt=MARKET) + f"{sym}/1d/{sym}-1d-{day.year}-{day.month:02d}-{day.day:02d}.zip"

def fetch_day(sym, day, info):
    """Daily file of one day -> list of (ot,row) for that day, [] if it does not exist (remembered) or failed."""
    if (sym, str(day)) in KNOWN_GAPS: return []
    st, data = fetch(FILES + urllib.parse.quote(daily_key(sym, day)))
    if st == "error":
        info["error"] = f"{daily_key(sym, day)}: {data}"; return []
    rows = [(ot, row) for ot, row in kline_rows(data)] if st == "ok" else []
    rows = [(ot, row) for ot, row in rows if ms_to_date(ot) == day]
    if not rows: info["unfillable"].append(str(day))
    return rows

def repair_file(sym, path, info):
    """rev2: fill holes that are already inside an existing file from the daily files; rewrite in order."""
    rows = []
    with open(path, newline="") as f:
        rd = csv.reader(f); next(rd, None)
        for r in rd:
            try: rows.append((int(r[0]), r))
            except (ValueError, IndexError): continue
    found = []
    for (a, _), (b, _) in zip(rows, rows[1:]):
        n = (b - a) // DAY_MS - 1
        if n <= 0 or n > GAP_FILL_MAX_DAYS: continue
        for i in range(1, n + 1):
            found += fetch_day(sym, ms_to_date(a + i * DAY_MS), info)
    if not found: return
    have = {ot for ot, _ in rows}
    merged = sorted(rows + [x for x in found if x[0] not in have], key=lambda x: x[0])
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(K_HEADER); w.writerows(r for _, r in merged)
    os.replace(tmp, path)
    info["gap_days_filled"] += len(merged) - len(rows)

def update_klines(sym):
    os.makedirs(os.path.join(OUTDIR, "1d"), exist_ok=True)
    path = os.path.join(OUTDIR, "1d", f"{sym}.csv")
    info = dict(rows_added=0, waiting_for=None, error=None, gap_days_filled=0, unfillable=[])
    last = read_last_first_col_int(path); is_new = last is None
    if not is_new: repair_file(sym, path, info)
    today = utc_today()
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(K_HEADER)

        def append(rows):
            nonlocal last
            for ot, row in rows:
                if last is not None and ot <= last: continue
                day = ms_to_date(ot)
                if last is not None and ot != last + DAY_MS:
                    if (today - day).days <= GAP_GIVE_UP_DAYS:
                        info["waiting_for"] = str(ms_to_date(last + DAY_MS)); return False
                    n = (ot - last) // DAY_MS - 1                       # rev2: older hole -> try the daily files
                    if 0 < n <= GAP_FILL_MAX_DAYS:
                        for i in range(1, n + 1):
                            for fot, frow in fetch_day(sym, ms_to_date(ot - (n - i + 1) * DAY_MS), info):
                                if fot > last:
                                    w.writerow(frow); last = fot; info["rows_added"] += 1; info["gap_days_filled"] += 1
                w.writerow(row); last = ot; info["rows_added"] += 1
            return True

        # monthly archives newer than what we have
        mp = P_MONTHLY_K.format(mkt=MARKET) + f"{sym}/1d/"
        marker = None
        if last is not None:
            d = ms_to_date(last)
            if d.month == (d + dt.timedelta(days=1)).month:        # month of `last` not finished in our file
                d = d.replace(day=1) - dt.timedelta(days=1)
            marker = f"{mp}{sym}-1d-{d.year}-{d.month:02d}.zip.CHECKSUM"
        st, keys = list_bucket(mp, marker)
        if st != "ok": info["error"] = f"monthly listing: {keys}"; return info
        for key in sorted(k for k in keys if KEY_MONTH.search(k)):
            st, data = fetch(FILES + urllib.parse.quote(key))
            if st == "error": info["error"] = f"{key}: {data}"; return info
            if st == "ok" and not append(kline_rows(data)): return info
        # daily files after the last row
        dp = P_DAILY_K.format(mkt=MARKET) + f"{sym}/1d/"
        marker = None
        if last is not None:
            d = ms_to_date(last)
            marker = f"{dp}{sym}-1d-{d.year}-{d.month:02d}-{d.day:02d}.zip.CHECKSUM"
        st, keys = list_bucket(dp, marker)
        if st != "ok": info["error"] = f"daily listing: {keys}"; return info
        for key in sorted(k for k in keys if KEY_DAY.search(k)):
            st, data = fetch(FILES + urllib.parse.quote(key))
            if st == "error": info["error"] = f"{key}: {data}"; return info
            if st == "ok" and not append(kline_rows(data)): return info
    return info

def update_funding(sym):
    os.makedirs(os.path.join(OUTDIR, "funding"), exist_ok=True)
    path = os.path.join(OUTDIR, "funding", f"{sym}.csv")
    last = read_last_first_col_int(path); is_new = last is None
    info = dict(rows_added=0, error=None)
    fp = P_MONTHLY_F.format(mkt=MARKET) + f"{sym}/"
    marker = None
    if last is not None:
        d = ms_to_date(last).replace(day=1) - dt.timedelta(days=1)   # re-read the month of the last row
        marker = f"{fp}{sym}-fundingRate-{d.year}-{d.month:02d}.zip.CHECKSUM"
    st, keys = list_bucket(fp, marker)
    if st != "ok": info["error"] = f"funding listing: {keys}"; return info
    with open(path, "w" if is_new else "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if is_new: w.writerow(F_HEADER)
        for key in sorted(k for k in keys if KEY_MONTH.search(k)):
            st, data = fetch(FILES + urllib.parse.quote(key))
            if st == "error": info["error"] = f"{key}: {data}"; return info
            if st != "ok": continue
            for t, row in funding_rows(data):
                if last is not None and t <= last: continue
                w.writerow(row); last = t; info["rows_added"] += 1
    return info

def do_symbol(sym):
    try:
        k = update_klines(sym); f = update_funding(sym)
    except Exception as e:                                # never let one symbol kill the run
        return sym, dict(rows_added=0, error=f"{type(e).__name__}: {e}", gap_days_filled=0, unfillable=[]), dict(rows_added=0, error=None)
    return sym, k, f

def summarise(sym):
    """One symbols.csv row from the symbol's 1d file. rev2: state and liquidity from days with volume."""
    path = os.path.join(OUTDIR, "1d", f"{sym}.csv")
    ts, qv, vol = [], [], []
    if os.path.exists(path):
        with open(path, newline="") as f:
            rd = csv.reader(f); next(rd, None)
            for r in rd:
                try:
                    t = int(r[0]); v = float(r[5]) if r[5] else 0.0; q = float(r[6]) if r[6] else 0.0
                except (ValueError, IndexError): continue
                ts.append(t); vol.append(v); qv.append(q)
    if not ts: return None
    first, last = ms_to_date(ts[0]), ms_to_date(ts[-1])
    span = (last - first).days + 1
    lt = max((i for i, v in enumerate(vol) if v > 0), default=None)       # index of the last day that traded
    last_traded = ms_to_date(ts[lt]) if lt is not None else None
    win = qv[max(0, lt - 29):lt + 1] if lt is not None else []
    med30 = sorted(win)[len(win) // 2] if win else 0
    active = last_traded is not None and (utc_today() - last_traded).days <= ACTIVE_WITHIN_DAYS
    return dict(symbol=sym, first_day=str(first), last_day=str(last), last_traded_day=str(last_traded) if last_traded else "",
                days=len(ts), missing_days=span - len(ts), zero_volume_days=sum(1 for v in vol if v == 0),
                state="active" if active else "ended", old_coin=int(first < OLD_COIN_BEFORE),
                median_quote_volume_30d=round(med30))


# ------------------------- categories (CoinGecko Demo) -------------------------
def base_asset(sym):
    return MULT_PREFIX.sub("", sym[:-4])

def resolve_categories(cat_list):
    """cat_list: [{'category_id','name'}] -> {label: category_id or None}"""
    by_id = {c["category_id"]: c for c in cat_list}
    by_name = {c["name"].strip().lower(): c["category_id"] for c in cat_list}
    out = {}
    for label, (ids, names) in CATEGORIES.items():
        hit = next((i for i in ids if i in by_id), None)
        if hit is None:
            hit = next((by_name[n.lower()] for n in names if n.lower() in by_name), None)
        out[label] = hit
    return out

def map_symbols(symbols, coins_by_label, overrides):
    """coins_by_label: {label: [coin dicts with id, symbol, name, market_cap, market_cap_rank]}.
    Ticker clash -> the coin with the larger market cap. overrides: {SYMBOL: cg_id} wins."""
    best = {}                                             # TICKER -> coin
    labels = {}                                           # cg id -> set(labels)
    by_id = {}
    for label, coins in coins_by_label.items():
        for c in coins:
            by_id[c["id"]] = c
            labels.setdefault(c["id"], set()).add(label)
            t = (c.get("symbol") or "").upper()
            if t and (t not in best or (c.get("market_cap") or 0) > (best[t].get("market_cap") or 0)):
                best[t] = c
    rows = []
    for sym in symbols:
        base = base_asset(sym)
        c = by_id.get(overrides.get(sym)) if sym in overrides else best.get(base)
        rows.append(dict(symbol=sym, base=base, cg_id=c["id"] if c else "", cg_name=c["name"] if c else "",
                         market_cap_rank=(c.get("market_cap_rank") or "") if c else "",
                         categories="|".join(sorted(labels.get(c["id"], []))) if c else ""))
    return rows

def update_categories(symbols):
    key = os.environ.get("CG_DEMO_KEY", "").strip()
    if not key:
        STATUS["categories"] = {"skipped": "no CG_DEMO_KEY secret"}; print("[categories] skipped: no CG_DEMO_KEY"); return
    hdr = {"x-cg-demo-api-key": key, "accept": "application/json"}
    st, data = fetch(CG_BASE + "/coins/categories/list", hdr); time.sleep(CG_DELAY_SEC)
    if st != "ok":
        STATUS["problems"].append(f"categories list: {data}"); return
    resolved = resolve_categories(json.loads(data))
    coins_by_label = {}
    for label, cid in resolved.items():
        if not cid:
            STATUS["problems"].append(f"category '{label}' not found on CoinGecko"); continue
        coins = []
        for page in range(1, CG_MAX_PAGES + 1):
            q = urllib.parse.urlencode(dict(vs_currency="usd", category=cid, order="market_cap_desc", per_page=250, page=page))
            st, data = fetch(CG_BASE + "/coins/markets?" + q, hdr); time.sleep(CG_DELAY_SEC)
            if st != "ok":
                STATUS["problems"].append(f"category '{label}' page {page}: {data}"); break
            arr = json.loads(data); coins += arr
            if len(arr) < 250: break
        coins_by_label[label] = coins
    overrides = {}
    op = os.path.join(OUTDIR, "cg_mapping_overrides.csv")              # hand-kept: symbol,cg_id
    if os.path.exists(op):
        with open(op, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("symbol") and r.get("cg_id"): overrides[r["symbol"].strip()] = r["cg_id"].strip()
    rows = map_symbols(symbols, coins_by_label, overrides)
    os.makedirs(os.path.join(OUTDIR, "categories"), exist_ok=True)
    for path in (os.path.join(OUTDIR, "categories_latest.csv"),
                 os.path.join(OUTDIR, "categories", f"categories_{utc_today()}.csv")):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    STATUS["categories"] = dict(resolved=resolved, coins={k: len(v) for k, v in coins_by_label.items()},
                                symbols_with_category=sum(1 for r in rows if r["categories"]), symbols_total=len(rows),
                                per_label={l: sum(1 for r in rows if l in r["categories"].split("|")) for l in CATEGORIES})
    print("[categories]", json.dumps(STATUS["categories"]))


# ------------------------- main -------------------------
def discover_symbols():
    syms = set()
    for p in (P_MONTHLY_K, P_DAILY_K):
        st, prefixes = list_bucket(p.format(mkt=MARKET), folders=True)
        if st != "ok":
            STATUS["problems"].append(f"symbol listing {p}: {prefixes}"); continue
        syms |= {x.rstrip("/").split("/")[-1] for x in prefixes}
    return sorted(s for s in syms if is_perp_usdt(s))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--symbols", default="")
    ap.add_argument("--mode", choices=["all", "prices", "categories"], default="all")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: return selftest()
    os.makedirs(OUTDIR, exist_ok=True)
    gp = os.path.join(OUTDIR, "known_gaps.csv")
    if os.path.exists(gp):
        with open(gp, newline="") as f:
            KNOWN_GAPS.update((r["symbol"], r["day"]) for r in csv.DictReader(f) if r.get("symbol") and r.get("day"))
    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or discover_symbols()
    print(f"[symbols] {len(symbols)} USDT perps found")
    if not symbols:
        STATUS["problems"].append("no symbols found")
    if a.limit: symbols = symbols[:a.limit]
    if a.mode in ("all", "prices") and symbols:
        t0 = time.time(); added = 0; filled = 0; new_gaps = []
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for n, (sym, k, f) in enumerate(ex.map(do_symbol, symbols), 1):
                added += k["rows_added"] + f["rows_added"]
                filled += k.get("gap_days_filled", 0); new_gaps += [(sym, d) for d in k.get("unfillable", [])]
                if k.get("error") or f.get("error") or k.get("waiting_for"):
                    STATUS["symbols"][sym] = dict(klines=k, funding=f)
                if k.get("error"): STATUS["problems"].append(f"{sym} klines: {k['error']}")
                if f.get("error"): STATUS["problems"].append(f"{sym} funding: {f['error']}")
                if n % 25 == 0 or n == len(symbols):
                    print(f"[prices] {n}/{len(symbols)} symbols, +{added:,} rows, {time.time() - t0:,.0f}s", flush=True)
        STATUS["rows_added"] = added; STATUS["gap_days_filled"] = filled; STATUS["new_unfillable_gap_days"] = len(new_gaps)
        KNOWN_GAPS.update(new_gaps)
        with open(gp, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["symbol", "day"]); w.writerows(sorted(KNOWN_GAPS))
        STATUS["known_gap_days"] = len(KNOWN_GAPS)
    # symbols.csv over everything on disk (so a --limit run does not shrink it)
    on_disk = sorted(f[:-4] for f in os.listdir(os.path.join(OUTDIR, "1d"))) if os.path.isdir(os.path.join(OUTDIR, "1d")) else []
    rows = [r for r in (summarise(s) for s in on_disk) if r]
    if rows:
        with open(os.path.join(OUTDIR, "symbols.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        STATUS.update(symbols_total=len(rows), active=sum(r["state"] == "active" for r in rows),
                      ended=sum(r["state"] == "ended" for r in rows), old_coins=sum(r["old_coin"] for r in rows),
                      with_missing_days=sum(r["missing_days"] > 0 for r in rows), missing_days_total=sum(r["missing_days"] for r in rows),
                      ended_with_zero_volume_tail=sum(r["state"] == "ended" and r["zero_volume_days"] > 0 for r in rows))
    if a.mode in ("all", "categories") and rows:
        update_categories([r["symbol"] for r in rows])
    STATUS["run_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    STATUS["ok"] = not STATUS["problems"]
    with open(os.path.join(OUTDIR, "status_alts.json"), "w") as f:
        json.dump(STATUS, f, indent=1)
    print(f"[done] symbols {STATUS.get('symbols_total')}, active {STATUS.get('active')}, ended {STATUS.get('ended')}, "
          f"rows added {STATUS.get('rows_added')}, gap days filled {STATUS.get('gap_days_filled')}, "
          f"gap days with no daily file {STATUS.get('known_gap_days')}")
    if STATUS["problems"]:
        print("[check] PROBLEMS:")
        for p in STATUS["problems"][:40]: print("  -", p)
        sys.exit(1)
    print("[check] OK")


# ------------------------- offline self-test -------------------------
def selftest():
    import tempfile
    global OUTDIR, fetch
    KNOWN_GAPS.clear()
    xml1 = (b'<?xml version="1.0" encoding="UTF-8"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            b'<Name>data.binance.vision</Name><Prefix>data/futures/um/monthly/klines/</Prefix><Marker></Marker>'
            b'<NextMarker>data/futures/um/monthly/klines/BTCUSDT_210326/</NextMarker><MaxKeys>1000</MaxKeys><Delimiter>/</Delimiter>'
            b'<IsTruncated>true</IsTruncated>'
            b'<CommonPrefixes><Prefix>data/futures/um/monthly/klines/1000PEPEUSDT/</Prefix></CommonPrefixes>'
            b'<CommonPrefixes><Prefix>data/futures/um/monthly/klines/BTCUSDT/</Prefix></CommonPrefixes>'
            b'<CommonPrefixes><Prefix>data/futures/um/monthly/klines/BTCUSDT_210326/</Prefix></CommonPrefixes></ListBucketResult>')
    p, k, tr, nx = parse_listing(xml1)
    assert len(p) == 3 and tr and nx.endswith("BTCUSDT_210326/") and not k
    assert [is_perp_usdt(x.rstrip("/").split("/")[-1]) for x in p] == [True, False, False]
    assert base_asset("1000PEPEUSDT") == "PEPE" and base_asset("1MBABYDOGEUSDT") == "BABYDOGE" and base_asset("LTCUSDT") == "LTC" \
        and base_asset("1000000MOGUSDT") == "MOG" and base_asset("1INCHUSDT") == "1INCH"

    def mkzip(name, text):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z: z.writestr(name, text)
        return b.getvalue()
    d0 = dt.date(2026, 8, 1)
    def krow(day, px):
        t = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
        return f"{t},{px},{px + 1},{px - 1},{px},100,{t + DAY_MS - 1},{px * 100},500,60,{px * 60},0"
    aug = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n" + \
          "\n".join(krow(d0 + dt.timedelta(days=i), 70 + i) for i in range(31) if i not in (9, 10))   # monthly archive lacks 10 and 11 Aug
    today = utc_today()
    store = {"data/futures/um/monthly/klines/XUSDT/1d/XUSDT-1d-2026-08.zip": mkzip("a.csv", aug)}
    store["data/futures/um/daily/klines/XUSDT/1d/XUSDT-1d-2026-08-10.zip"] = mkzip("d.csv", krow(dt.date(2026, 8, 10), 79))   # 10 Aug exists as a daily file, 11 Aug nowhere
    # daily files: 1 Sep .. today-1, except the day before yesterday (not published yet -> must wait, not skip)
    day = dt.date(2026, 9, 1); hole = today - dt.timedelta(days=2)
    while day < today:
        if day != hole:
            store[f"data/futures/um/daily/klines/XUSDT/1d/XUSDT-1d-{day}.zip"] = mkzip("d.csv", krow(day, 80))
        day += dt.timedelta(days=1)
    store["data/futures/um/monthly/fundingRate/XUSDT/XUSDT-fundingRate-2026-08.zip"] = mkzip(
        "f.csv", "calc_time,funding_interval_hours,last_funding_rate\n1785542400000,8,0.0001\n1785571200000,8,-0.0002\n")

    def fake_fetch(url, headers=None):
        if url.startswith(BUCKET):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query); pre = q["prefix"][0]; mk = q.get("marker", [""])[0]
            keys = sorted(k for k in store if k.startswith(pre) and "/" not in k[len(pre):] and k > mk)
            body = "".join(f"<Contents><Key>{k}</Key></Contents><Contents><Key>{k}.CHECKSUM</Key></Contents>" for k in keys)
            return "ok", f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><IsTruncated>false</IsTruncated>{body}</ListBucketResult>'.encode()
        k = url[len(FILES):]
        return ("ok", store[k]) if k in store else ("missing", None)
    real_fetch = fetch; fetch = fake_fetch
    with tempfile.TemporaryDirectory() as tmp:
        OUTDIR = os.path.join(tmp, "alts")
        k = update_klines("XUSDT"); f = update_funding("XUSDT")
        n_sep = (hole - dt.date(2026, 9, 1)).days
        assert k["rows_added"] == 30 + n_sep and k["waiting_for"] == str(hole) and not k["error"], k
        assert k["gap_days_filled"] == 1 and k["unfillable"] == ["2026-08-11"], k
        KNOWN_GAPS.add(("XUSDT", "2026-08-11"))
        assert f["rows_added"] == 2 and not f["error"], f
        with open(os.path.join(OUTDIR, "1d", "XUSDT.csv")) as fh: lines = fh.read().splitlines()
        assert lines[0] == ",".join(K_HEADER) and lines[1].split(",")[6] == "7000" and lines[1].split(",")[8] == "4200", lines[:2]
        assert lines[10].split(",")[1] == "79" and len(lines) == 1 + 30 + n_sep, lines[9:12]                 # 10 Aug came from the daily file, in order
        # second run: nothing new, still waiting; then the hole is published -> both remaining days arrive
        k2 = update_klines("XUSDT"); assert k2["rows_added"] == 0 and k2["waiting_for"] == str(hole), k2
        assert k2["unfillable"] == [] and k2["gap_days_filled"] == 0, k2                                     # known gap is not asked for again
        store[f"data/futures/um/daily/klines/XUSDT/1d/XUSDT-1d-{hole}.zip"] = mkzip("d.csv", krow(hole, 81))
        k3 = update_klines("XUSDT"); assert k3["rows_added"] == 2 and k3["waiting_for"] is None, k3
        f2 = update_funding("XUSDT"); assert f2["rows_added"] == 0
        s = summarise("XUSDT"); assert s["missing_days"] == 1 and s["state"] == "active" and s["old_coin"] == 0 and s["first_day"] == "2026-08-01", s
        # repair of a hole that is already inside the file: 11 Aug gets published as a daily file later
        KNOWN_GAPS.discard(("XUSDT", "2026-08-11"))
        store["data/futures/um/daily/klines/XUSDT/1d/XUSDT-1d-2026-08-11.zip"] = mkzip("d.csv", krow(dt.date(2026, 8, 11), 77))
        k4 = update_klines("XUSDT"); assert k4["gap_days_filled"] == 1 and k4["rows_added"] == 0 and not k4["unfillable"], k4
        with open(os.path.join(OUTDIR, "1d", "XUSDT.csv")) as fh: lines = fh.read().splitlines()
        ots = [int(x.split(",")[0]) for x in lines[1:]]
        assert ots == sorted(ots) and len(set(ots)) == len(ots) and lines[11].split(",")[1] == "77", lines[10:13]
        s = summarise("XUSDT"); assert s["missing_days"] == 0 and s["zero_volume_days"] == 0 and s["last_traded_day"] == s["last_day"], s
        # delisted coin: Binance keeps publishing zero-volume candles -> state must be "ended"
        with open(os.path.join(OUTDIR, "1d", "DEADUSDT.csv"), "w") as fh:
            fh.write(",".join(K_HEADER) + "\n")
            for i in range(60):
                dday = today - dt.timedelta(days=60 - i); t = int(dt.datetime(dday.year, dday.month, dday.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
                v = 100 if i < 20 else 0
                fh.write(f"{t},1,1,1,1,{v},{v * 5},10,{v}\n")
        s = summarise("DEADUSDT")
        assert s["state"] == "ended" and s["zero_volume_days"] == 40 and s["last_traded_day"] == str(today - dt.timedelta(days=41)) and s["median_quote_volume_30d"] == 500, s
    fetch = real_fetch
    cats = [{"category_id": "meme-token", "name": "Meme"}, {"category_id": "layer-1", "name": "Layer 1 (L1)"},
            {"category_id": "some-new-ai-id", "name": "Artificial Intelligence (AI)"}]
    r = resolve_categories(cats); assert r["meme"] == "meme-token" and r["ai"] == "some-new-ai-id" and r["depin"] is None, r
    coins = {"meme": [{"id": "pepe", "symbol": "pepe", "name": "Pepe", "market_cap": 9e9, "market_cap_rank": 30},
                      {"id": "pepe-fake", "symbol": "pepe", "name": "Fake", "market_cap": 1e3, "market_cap_rank": 9000}],
             "layer1": [{"id": "near", "symbol": "near", "name": "NEAR", "market_cap": 5e9, "market_cap_rank": 40}],
             "ai": [{"id": "near", "symbol": "near", "name": "NEAR", "market_cap": 5e9, "market_cap_rank": 40}]}
    m = {x["symbol"]: x for x in map_symbols(["1000PEPEUSDT", "NEARUSDT", "ZZZUSDT"], coins, {})}
    assert m["1000PEPEUSDT"]["cg_id"] == "pepe" and m["NEARUSDT"]["categories"] == "ai|layer1" and m["ZZZUSDT"]["categories"] == "", m
    m2 = map_symbols(["1000PEPEUSDT"], coins, {"1000PEPEUSDT": "pepe-fake"}); assert m2[0]["cg_id"] == "pepe-fake"
    print("selftest OK")

if __name__ == "__main__":
    main()
