#!/usr/bin/env python3
"""
hl_trader_screen_rev1.py
Hyperliquid trader screen - stage 1 (data collection only, no scoring).

What it does
  1. Downloads the public Hyperliquid leaderboard and saves it as a CSV (all rows).
  2. Pre-filters to a shortlist of candidate accounts (thresholds below, all overridable by env vars).
  3. For each shortlisted account downloads:
       - trade fills (userFillsByTime, aggregated by time; API only keeps the 10,000 most recent fills)
       - account value / PnL history (portfolio)
       - current open positions (clearinghouseState)
  4. Writes everything to data/hyperliquid/ and a run_log.json with counts, settings and errors.

Scoring (trades/day, maker share, BTC/ETH share, hold time, monthly spread, top-3 removal, drawdown)
is done later in the analysis session, not here.

Stdlib only - no pip install needed.

API facts used (from the Hyperliquid docs, checked 2026-09-23):
  - REST weight limit 1200 per minute per IP.
  - clearinghouseState weight 2; other info requests weight 20;
    userFills / userFillsByTime add weight per 20 items returned.
  - userFillsByTime: max 2000 fills per response, only the 10,000 most recent fills available.
"""

import csv
import gzip
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------- settings
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
INFO_URL = "https://api.hyperliquid.xyz/info"
OUT_DIR = os.environ.get("HL_OUT_DIR", "data/hyperliquid")


def _env_float(name, default):
    v = os.environ.get(name, "")
    return float(v) if v.strip() else default


# Pre-filter thresholds (placeholders - meant to remove obvious non-candidates only)
MIN_ALLTIME_PNL = _env_float("HL_MIN_ALLTIME_PNL", 100_000)      # USD
MIN_MONTH_PNL = _env_float("HL_MIN_MONTH_PNL", 0)                 # USD, must be > this
MIN_ACCOUNT_VALUE = _env_float("HL_MIN_ACCOUNT_VALUE", 50_000)    # USD
MAX_ACCOUNT_VALUE = _env_float("HL_MAX_ACCOUNT_VALUE", 20_000_000)
MAX_VLM_TO_ACCT = _env_float("HL_MAX_VLM_TO_ACCT", 3000)          # all-time volume / account value
SHORTLIST_SIZE = int(_env_float("HL_SHORTLIST_SIZE", 150))

# Rate limiting: stay under the 1200/min limit with margin
WEIGHT_BUDGET_PER_MIN = 900
FILLS_PAGE_LIMIT = 2000
MAX_FILL_CALLS_PER_ACCOUNT = 8

FILL_FIELDS = ["time", "coin", "dir", "side", "px", "sz", "startPosition", "closedPnl",
               "fee", "feeToken", "crossed", "oid", "tid", "hash"]


# ---------------------------------------------------------------- rate limiter
class WeightLimiter:
    def __init__(self, budget):
        self.budget = budget
        self.events = []  # (timestamp, weight)

    def _used(self):
        now = time.time()
        self.events = [(t, w) for t, w in self.events if now - t < 60]
        return sum(w for _, w in self.events)

    def wait_for(self, weight):
        while self._used() + weight > self.budget:
            oldest = min(t for t, _ in self.events)
            time.sleep(max(0.5, 60 - (time.time() - oldest) + 0.1))

    def record(self, weight):
        self.events.append((time.time(), weight))


LIMITER = WeightLimiter(WEIGHT_BUDGET_PER_MIN)


# ---------------------------------------------------------------- http
def http_get_json(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "hl-trader-screen/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def info_post(payload, base_weight=20, per_item=False, retries=5):
    """POST to /info with rate limiting and retry on 429 / 5xx / network errors."""
    est = base_weight + (FILLS_PAGE_LIMIT // 20 if per_item else 0)
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        LIMITER.wait_for(est)
        req = urllib.request.Request(INFO_URL, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "hl-trader-screen/1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            items = len(data) if (per_item and isinstance(data, list)) else 0
            LIMITER.record(base_weight + math.ceil(items / 20))
            return data
        except urllib.error.HTTPError as e:
            LIMITER.record(base_weight)
            if e.code == 429 or e.code >= 500:
                time.sleep(min(60, 5 * 2 ** attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"info_post failed after {retries} attempts: {payload.get('type')}")


# ---------------------------------------------------------------- helpers
def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def window_map(wp):
    """windowPerformances may be a list of [name, {...}] pairs or a dict. Return dict."""
    if isinstance(wp, dict):
        return wp
    out = {}
    if isinstance(wp, list):
        for item in wp:
            if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict):
                out[item[0]] = item[1]
    return out


def write_csv_gz(path, fieldnames, rows):
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------- step 1: leaderboard
LB_FIELDS = ["address", "display_name", "account_value"] + [
    f"{w}_{m}" for w in ("day", "week", "month", "allTime") for m in ("pnl", "roi", "vlm")]


def parse_leaderboard(raw):
    rows_raw = raw.get("leaderboardRows") if isinstance(raw, dict) else raw
    if not isinstance(rows_raw, list) or not rows_raw:
        raise ValueError("Leaderboard format not recognised (no leaderboardRows list).")
    rows = []
    for r in rows_raw:
        wm = window_map(r.get("windowPerformances"))
        row = {"address": (r.get("ethAddress") or "").lower(),
               "display_name": r.get("displayName") or "",
               "account_value": to_float(r.get("accountValue"))}
        for w in ("day", "week", "month", "allTime"):
            perf = wm.get(w, {})
            for m in ("pnl", "roi", "vlm"):
                row[f"{w}_{m}"] = to_float(perf.get(m))
        if row["address"]:
            rows.append(row)
    return rows


def shortlist(rows):
    keep = []
    for r in rows:
        av, ap, mp, vlm = r["account_value"], r["allTime_pnl"], r["month_pnl"], r["allTime_vlm"]
        if None in (av, ap, mp, vlm) or av <= 0:
            continue
        if ap < MIN_ALLTIME_PNL or mp <= MIN_MONTH_PNL:
            continue
        if not (MIN_ACCOUNT_VALUE <= av <= MAX_ACCOUNT_VALUE):
            continue
        ratio = vlm / av
        if ratio > MAX_VLM_TO_ACCT:
            continue
        keep.append(dict(r, vlm_to_acct=round(ratio, 1)))
    keep.sort(key=lambda r: r["allTime_pnl"], reverse=True)
    return keep[:SHORTLIST_SIZE]


# ---------------------------------------------------------------- step 2: per-account data
def fetch_fills(addr):
    """Collect up to 10k most recent fills. Pages both forward and backward from the first
    response and de-duplicates by tid, so it works whichever end of the window the API returns."""
    seen, fills, calls = set(), [], 0

    def add(batch):
        new = 0
        for f in batch or []:
            key = (f.get("tid"), f.get("oid"), f.get("time"), f.get("px"), f.get("sz"))
            if key not in seen:
                seen.add(key)
                fills.append(f)
                new += 1
        return new

    def call(start, end=None):
        nonlocal calls
        calls += 1
        p = {"type": "userFillsByTime", "user": addr, "startTime": int(start), "aggregateByTime": True}
        if end is not None:
            p["endTime"] = int(end)
        return info_post(p, base_weight=20, per_item=True)

    first = call(0)
    add(first)
    if not first or len(first) < FILLS_PAGE_LIMIT:
        return fills, calls

    # forward from newest seen time
    while calls < MAX_FILL_CALLS_PER_ACCOUNT:
        batch = call(max(f["time"] for f in fills)) or []
        if add(batch) == 0 or len(batch) < FILLS_PAGE_LIMIT:
            break
    # backward from oldest seen time
    while calls < MAX_FILL_CALLS_PER_ACCOUNT:
        batch = call(0, min(f["time"] for f in fills)) or []
        if add(batch) == 0 or len(batch) < FILLS_PAGE_LIMIT:
            break
    fills.sort(key=lambda f: f["time"])
    return fills, calls


def fetch_portfolio(addr):
    raw = info_post({"type": "portfolio", "user": addr}, base_weight=20)
    out = []
    for w, d in window_map(raw).items():
        if w not in ("allTime", "perpAllTime") or not isinstance(d, dict):
            continue
        pnl = {int(t): v for t, v in d.get("pnlHistory", [])}
        for t, av in d.get("accountValueHistory", []):
            out.append({"address": addr, "window": w, "time": int(t),
                        "account_value": av, "pnl": pnl.get(int(t), "")})
    return out


def fetch_positions(addr):
    raw = info_post({"type": "clearinghouseState", "user": addr}, base_weight=2)
    out = []
    for ap in (raw or {}).get("assetPositions", []):
        p = ap.get("position", {})
        lev = p.get("leverage", {})
        out.append({"address": addr, "coin": p.get("coin"), "szi": p.get("szi"),
                    "entryPx": p.get("entryPx"), "positionValue": p.get("positionValue"),
                    "unrealizedPnl": p.get("unrealizedPnl"),
                    "leverage_type": lev.get("type") if isinstance(lev, dict) else "",
                    "leverage": lev.get("value") if isinstance(lev, dict) else lev,
                    "liquidationPx": p.get("liquidationPx")})
    return out


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(os.path.join(OUT_DIR, "fills"), exist_ok=True)
    log = {"run_utc": run_ts, "settings": {
        "MIN_ALLTIME_PNL": MIN_ALLTIME_PNL, "MIN_MONTH_PNL": MIN_MONTH_PNL,
        "MIN_ACCOUNT_VALUE": MIN_ACCOUNT_VALUE, "MAX_ACCOUNT_VALUE": MAX_ACCOUNT_VALUE,
        "MAX_VLM_TO_ACCT": MAX_VLM_TO_ACCT, "SHORTLIST_SIZE": SHORTLIST_SIZE},
        "errors": []}

    # 1. leaderboard
    print("Downloading leaderboard ...", flush=True)
    raw = http_get_json(LEADERBOARD_URL)
    sample = raw.get("leaderboardRows", [])[:3] if isinstance(raw, dict) else raw[:3]
    with open(os.path.join(OUT_DIR, "leaderboard_sample_raw.json"), "w") as f:
        json.dump(sample, f, indent=1)          # lets us verify the raw format
    rows = parse_leaderboard(raw)
    del raw
    write_csv_gz(os.path.join(OUT_DIR, "leaderboard_latest.csv.gz"), LB_FIELDS, rows)
    log["leaderboard_rows"] = len(rows)
    print(f"  {len(rows)} leaderboard rows", flush=True)

    sl = shortlist(rows)
    write_csv(os.path.join(OUT_DIR, "shortlist.csv"), LB_FIELDS + ["vlm_to_acct"], sl)
    log["shortlist_rows"] = len(sl)
    print(f"  {len(sl)} accounts shortlisted", flush=True)

    # 2. per-account data
    portfolio_rows, position_rows, summary = [], [], []
    for i, r in enumerate(sl, 1):
        addr = r["address"]
        try:
            fills, calls = fetch_fills(addr)
            write_csv_gz(os.path.join(OUT_DIR, "fills", f"{addr}.csv.gz"), FILL_FIELDS, fills)
            portfolio_rows += fetch_portfolio(addr)
            position_rows += fetch_positions(addr)
            first_t = fills[0]["time"] if fills else None
            last_t = fills[-1]["time"] if fills else None
            summary.append({"address": addr, "n_fills": len(fills), "fill_calls": calls,
                            "first_fill_utc": datetime.fromtimestamp(first_t / 1000, timezone.utc).isoformat() if first_t else "",
                            "last_fill_utc": datetime.fromtimestamp(last_t / 1000, timezone.utc).isoformat() if last_t else "",
                            "hit_10k_cap": len(fills) >= 9990})
            print(f"  [{i}/{len(sl)}] {addr}  fills={len(fills)}", flush=True)
        except Exception as e:  # keep going; record the error
            log["errors"].append({"address": addr, "error": repr(e)[:300]})
            print(f"  [{i}/{len(sl)}] {addr}  ERROR {e!r}", flush=True)

    write_csv_gz(os.path.join(OUT_DIR, "portfolio_history.csv.gz"),
                 ["address", "window", "time", "account_value", "pnl"], portfolio_rows)
    write_csv(os.path.join(OUT_DIR, "positions_snapshot.csv"),
              ["address", "coin", "szi", "entryPx", "positionValue", "unrealizedPnl",
               "leverage_type", "leverage", "liquidationPx"], position_rows)
    write_csv(os.path.join(OUT_DIR, "fills_summary.csv"),
              ["address", "n_fills", "fill_calls", "first_fill_utc", "last_fill_utc", "hit_10k_cap"], summary)

    log["accounts_done"] = len(summary)
    log["minutes"] = round((time.time() - t0) / 60, 1)
    with open(os.path.join(OUT_DIR, "run_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    print(f"Done in {log['minutes']} min, {len(log['errors'])} errors.", flush=True)
    return 0 if summary or not sl else 1


if __name__ == "__main__":
    sys.exit(main())
