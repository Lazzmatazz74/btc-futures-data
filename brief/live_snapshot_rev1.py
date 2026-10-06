#!/usr/bin/env python3
"""
live_snapshot_rev1.py — live market snapshot for the daily brief (Trading project, 2026-10-06, account B).

Runs in GitHub Actions (btc-futures-data, workflow live_snapshot_rev1.yml). Writes:
  data/brief/live/live_latest.json          newest snapshot (overwritten each run)
  data/brief/live/history/live_<day>.json   last snapshot of each UTC day
  data/brief/live/positioning_log_rev1.csv  one row per coin per run (append-only)

Sections (information only - no forecasts, no trade calls):
  levels      Key Levels rev10 levels (PDH/PDL, DO, WO, PWH/PWL, PWM, MONH/MONL, WKH/WKL, MO, PMH/PML)
              with distance % and state untouched / swept / accepted (4 consecutive 1h closes beyond),
              reset at each level's period start - same rules as key_levels_rev10.pine f_state().
              Also yesterday's daily-level outcome.
  vol         yesterday's range %, 20-day average range %, percentile of yesterday among 90 days; DVOL.
  positioning Hyperliquid + OKX funding (annualised) and OI; OKX OI change 24h / 7d; Coinbase premium.
  options     Deribit BTC/ETH option open interest by expiry (next expiries).
  movers      Binance spot 24h movers (USDT pairs, >= 20M USDT volume, stables / leveraged tokens removed).

Price data: Binance USDT-M perp archive (repo files data/<SYM>-1h.csv, -1d.csv) up to the archive end;
hours after that from Binance SPOT (data-api.binance.vision - the futures API is blocked on GitHub runners,
see LIVE_SOURCE_TEST_2026-10-06_rev1.md); HYPE falls back to OKX perp if Binance spot has no pair.
Every level carries the source of the bars it was built from ("perp" / "spot" / "okx" / "mixed").
"""
import json, os, sys, time, urllib.request, urllib.error, datetime as dt
import pandas as pd
import numpy as np

COINS = ["BTC", "ETH", "XRP", "BNB", "LTC", "HYPE"]
OUT = "data/brief/live"
ACC_N = 4                      # Key Levels default: 4 x 1h closes beyond = accepted
UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
ERR = []                       # every failed call is reported in the JSON, never hidden


def get(url, body=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0 (live-snapshot)",
                                                           "Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt == 1:
                ERR.append(f"{url.split('?')[0]}: {repr(e)[:120]}")
                return None
            time.sleep(2)


def ms(d):
    return int(d.timestamp() * 1000)


def r(x, n=6):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


# ------------------------------------------------------------------ price data
def load_perp(sym, tf):
    p = f"data/{sym}USDT-{tf}.csv"
    if not os.path.exists(p):
        ERR.append(f"missing {p}")
        return pd.DataFrame(columns=["t", "o", "h", "l", "c", "src"])
    d = pd.read_csv(p, usecols=[0, 1, 2, 3, 4])
    d.columns = ["t", "o", "h", "l", "c"]
    d["t"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    d["src"] = "perp"
    return d.drop_duplicates("t").sort_values("t").reset_index(drop=True)


def spot_1h(sym, start):
    """Closed 1h bars from Binance spot after `start`, plus the last (open) bar's close as current price."""
    rows, t0 = [], ms(start)
    for _ in range(5):
        k = get(f"https://data-api.binance.vision/api/v3/klines?symbol={sym}USDT&interval=1h&startTime={t0}&limit=1000")
        if not k:
            break
        rows += k
        if len(k) < 1000:
            break
        t0 = k[-1][0] + 3600_000
    if not rows:
        return None, None
    d = pd.DataFrame([[x[0], x[1], x[2], x[3], x[4], x[6]] for x in rows], columns=["t", "o", "h", "l", "c", "ct"])
    d[["o", "h", "l", "c"]] = d[["o", "h", "l", "c"]].astype(float)
    last = float(d["c"].iloc[-1])
    d = d[d["ct"] < ms(NOW)].drop(columns="ct")          # closed bars only
    d["t"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    d["src"] = "spot"
    return d, last


def okx_1h(sym, start):
    k = get(f"https://www.okx.com/api/v5/market/candles?instId={sym}-USDT-SWAP&bar=1H&limit=300")
    if not k or k.get("code") != "0":
        return None, None
    d = pd.DataFrame([[int(x[0]), x[1], x[2], x[3], x[4], x[8]] for x in k["data"]], columns=["t", "o", "h", "l", "c", "ok"])
    d = d.sort_values("t")
    last = float(d["c"].iloc[-1])
    d = d[d["ok"] == "1"].drop(columns="ok")
    d[["o", "h", "l", "c"]] = d[["o", "h", "l", "c"]].astype(float)
    d["t"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    d = d[d["t"] >= start]
    d["src"] = "okx"
    return d, last


def hourly(coin):
    perp = load_perp(coin, "1h")
    start = (perp["t"].iloc[-1] + pd.Timedelta(hours=1)) if len(perp) else NOW - dt.timedelta(days=60)
    tail, last = spot_1h(coin, start)
    tail_src = "spot"
    if tail is None:
        tail, last = okx_1h(coin, start)
        tail_src = "okx"
    if tail is None:
        ERR.append(f"{coin}: no live bars after archive end")
        tail, last = perp.iloc[0:0], (float(perp["c"].iloc[-1]) if len(perp) else None)
        tail_src = None
    h = pd.concat([perp, tail], ignore_index=True).drop_duplicates("t", keep="first").sort_values("t").reset_index(drop=True)
    meta = {"archive_end_utc": perp["t"].iloc[-1].strftime("%Y-%m-%d %H:%M") if len(perp) else None,
            "live_source": tail_src, "live_bars": int(len(tail)),
            "last_closed_bar_utc": h["t"].iloc[-1].strftime("%Y-%m-%d %H:%M") if len(h) else None}
    return h, last, meta


def daily_from(h):
    g = h.set_index("t").groupby(pd.Grouper(freq="1D"))
    d = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(),
                      "n": g["c"].count(),
                      "src": g["src"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else "mixed")}).dropna(subset=["o"])
    return d


# ------------------------------------------------------------------ Key Levels state (key_levels_rev10 f_state)
def state(bars, px, side):
    """bars: 1h bars of the level's period so far. side 1 = high level, -1 = low level."""
    if px is None or not len(bars):
        return "untouched"
    st, run = 0, 0
    for h, l, c in zip(bars["h"].values, bars["l"].values, bars["c"].values):
        wick = h > px if side == 1 else l < px
        bey = c > px if side == 1 else c < px
        if st == 0 and wick:
            st = 1
        if st < 2:
            run = run + 1 if bey else 0
            if run >= ACC_N:
                st = 2
    if st == 0:
        return "untouched"
    if st == 2:
        return "accepted above" if side == 1 else "accepted below"
    c = bars["c"].values[-1]
    return "beyond, not accepted yet" if (c > px if side == 1 else c < px) else "swept, back inside"


def src_of(srcs):
    s = set(srcs)
    return s.pop() if len(s) == 1 else "mixed"


def levels(coin):
    h, last, meta = hourly(coin)
    if not len(h) or last is None:
        return None
    t_last = h["t"].iloc[-1]
    today = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    ystd = today - dt.timedelta(days=1)
    wk0 = today - dt.timedelta(days=today.weekday())               # Monday 00:00 UTC
    pwk0 = wk0 - dt.timedelta(days=7)
    mo0 = today.replace(day=1)
    pmo0 = (mo0 - dt.timedelta(days=1)).replace(day=1)
    T = h["t"]

    def rng(a, b):
        return h[(T >= a) & (T < b)]

    def hl(a, b):
        x = rng(a, b)
        return (None, None, None) if not len(x) else (float(x["h"].max()), float(x["l"].min()), src_of(x["src"]))

    out = []

    def add(name, px, src, period_start, side, kind):
        if px is None:
            return
        bars = rng(period_start, NOW)
        st = state(bars, px, side) if side else None
        out.append({"name": name, "kind": kind, "price": r(px, 8), "dist_pct": r((px / last - 1) * 100, 3),
                    "state": st, "src": src})

    pdh, pdl, s = hl(ystd, today);                         add("PDH", pdh, s, today, 1, "day"); add("PDL", pdl, s, today, -1, "day")
    x = rng(today, NOW)
    if len(x): add("DO", float(x["o"].iloc[0]), x["src"].iloc[0], today, 0, "day")
    x = rng(wk0, NOW)
    if len(x): add("WO", float(x["o"].iloc[0]), x["src"].iloc[0], wk0, 0, "week")
    pwh, pwl, s = hl(pwk0, wk0)
    add("PWH", pwh, s, wk0, 1, "week"); add("PWL", pwl, s, wk0, -1, "week")
    if pwh is not None: add("PWM", (pwh + pwl) / 2, s, wk0, 0, "week")
    if today.weekday() >= 1:                               # Monday range shown Tue..Sun
        mh, ml, s = hl(wk0, wk0 + dt.timedelta(days=1))
        add("MONH", mh, s, wk0 + dt.timedelta(days=1), 1, "week"); add("MONL", ml, s, wk0 + dt.timedelta(days=1), -1, "week")
    kh, kl, s = hl(wk0 - dt.timedelta(days=2), wk0)        # previous weekend Sat+Sun
    add("WKH", kh, s, wk0, 1, "week"); add("WKL", kl, s, wk0, -1, "week")
    x = rng(mo0, NOW)
    if len(x): add("MO", float(x["o"].iloc[0]), x["src"].iloc[0], mo0, 0, "month")
    pmh, pml, s = hl(pmo0, mo0)
    add("PMH", pmh, s, mo0, 1, "month"); add("PML", pml, s, mo0, -1, "month")

    # yesterday's outcome for the daily levels that applied yesterday (PDH/PDL of the day before)
    dbh, dbl, s = hl(ystd - dt.timedelta(days=1), ystd)
    yb = rng(ystd, today)
    yday = []
    for nm, px, sd in (("PDH", dbh, 1), ("PDL", dbl, -1)):
        if px is not None and len(yb):
            yday.append({"name": nm, "price": r(px, 8), "state": state(yb, px, sd), "src": s})

    above = sorted([l for l in out if l["dist_pct"] > 0], key=lambda l: l["dist_pct"])[:3]
    below = sorted([l for l in out if l["dist_pct"] <= 0], key=lambda l: -l["dist_pct"])[:3]
    return {"price": r(last, 8), "price_src": meta["live_source"], **meta,
            "levels": sorted(out, key=lambda l: -l["price"]),
            "nearest_above": [l["name"] for l in above], "nearest_below": [l["name"] for l in below],
            "yesterday_daily_levels": yday}, h


# ------------------------------------------------------------------ volatility
def vol(coin, h):
    dp = load_perp(coin, "1d").set_index("t")[["o", "h", "l", "c", "src"]]
    dl = daily_from(h)
    dl = dl[(dl.index > dp.index[-1]) & (dl["n"] == 24)] if len(dp) else dl[dl["n"] == 24]
    d = pd.concat([dp, dl[["o", "h", "l", "c", "src"]]])
    today = pd.Timestamp(NOW.date(), tz="UTC")
    d = d[d.index < today]
    if len(d) < 30:
        return None
    rng_pct = (d["h"] - d["l"]) / d["o"] * 100
    y = rng_pct.iloc[-1]
    last90 = rng_pct.iloc[-90:]
    tr = pd.concat([d["h"] - d["l"], (d["h"] - d["c"].shift()).abs(), (d["l"] - d["c"].shift()).abs()], axis=1).max(axis=1)
    return {"yesterday_utc": d.index[-1].strftime("%Y-%m-%d"), "yesterday_src": d["src"].iloc[-1],
            "yesterday_range_pct": r(y, 3), "avg20_range_pct": r(rng_pct.iloc[-20:].mean(), 3),
            "atr14_pct": r((tr.iloc[-14:].mean() / d["c"].iloc[-1]) * 100, 3),
            "yesterday_pctile_90d": r((last90 < y).mean() * 100, 1),
            "yesterday_change_pct": r((d["c"].iloc[-1] / d["o"].iloc[-1] - 1) * 100, 3)}


def spot_perp_gap(coin):
    """Median |spot - perp| on daily high / low / close over the last 30 archive days (%), to show how far
    spot-built levels can sit from perp-chart levels."""
    dp = load_perp(coin, "1d").set_index("t")
    k = get(f"https://data-api.binance.vision/api/v3/klines?symbol={coin}USDT&interval=1d&limit=45")
    if not k or not len(dp):
        return None
    s = pd.DataFrame([[x[0], float(x[2]), float(x[3]), float(x[4])] for x in k], columns=["t", "h", "l", "c"])
    s["t"] = pd.to_datetime(s["t"], unit="ms", utc=True)
    m = s.set_index("t").join(dp[["h", "l", "c"]], rsuffix="_p", how="inner").iloc[-30:]
    if not len(m):
        return None
    g = {k2: r(((m[k2] - m[k2 + "_p"]).abs() / m[k2 + "_p"] * 100).median(), 4) for k2 in ("h", "l", "c")}
    return {"days": int(len(m)), "median_abs_pct_high": g["h"], "median_abs_pct_low": g["l"], "median_abs_pct_close": g["c"]}


def dvol():
    out = {}
    for cur in ("BTC", "ETH"):
        j = get(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={cur}&resolution=1D"
                f"&start_timestamp={ms(NOW - dt.timedelta(days=370))}&end_timestamp={ms(NOW)}")
        data = (j or {}).get("result", {}).get("data") or []
        if not data:
            continue
        closes = np.array([x[4] for x in data], dtype=float)
        now_v = closes[-1]
        out[cur] = {"dvol": r(now_v, 2), "pctile_1y": r((closes[:-1] < now_v).mean() * 100, 1),
                    "change_7d": r(now_v - closes[-8], 2) if len(closes) > 8 else None, "days": int(len(closes))}
    return out


# ------------------------------------------------------------------ positioning
def positioning(spot_last):
    res = {c: {} for c in COINS}
    hl = get("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"})
    if hl and isinstance(hl, list) and len(hl) == 2:
        names = [u["name"] for u in hl[0]["universe"]]
        for c in COINS:
            if c in names:
                x = hl[1][names.index(c)]
                mark = float(x["markPx"])
                res[c]["hl"] = {"funding_hourly": r(float(x["funding"]), 10),
                                "funding_ann_pct": r(float(x["funding"]) * 24 * 365 * 100, 2),
                                "oi_coins": r(float(x["openInterest"]), 2), "oi_usd": r(float(x["openInterest"]) * mark, 0),
                                "premium_pct": r(float(x["premium"]) * 100, 4) if x.get("premium") else None,
                                "chg_24h_pct": r((mark / float(x["prevDayPx"]) - 1) * 100, 3), "mark": r(mark, 8)}
    for c in COINS:
        inst = f"{c}-USDT-SWAP"
        f = get(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst}")
        o = get(f"https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId={inst}")
        okx = {}
        if f and f.get("code") == "0" and f["data"]:
            fr = float(f["data"][0]["fundingRate"])
            okx["funding_8h_pct"] = r(fr * 100, 5)
            okx["funding_ann_pct"] = r(fr * 3 * 365 * 100, 2)
        if o and o.get("code") == "0" and o["data"]:
            okx["oi_usd"] = r(float(o["data"][0]["oiUsd"]), 0)
        hist = get(f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy={c}&period=1H")
        if hist and hist.get("code") == "0" and len(hist["data"]) > 24:
            rows = hist["data"]                                  # newest first: [ts, oi_usd, vol_usd]
            okx["oi_all_usd"] = r(float(rows[0][1]), 0)
            okx["oi_chg_24h_pct"] = r((float(rows[0][1]) / float(rows[24][1]) - 1) * 100, 2)
        hd = get(f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy={c}&period=1D")
        if hd and hd.get("code") == "0" and len(hd["data"]) > 7:
            rows = hd["data"]
            okx["oi_chg_7d_pct"] = r((float(rows[0][1]) / float(rows[7][1]) - 1) * 100, 2)
        if okx:
            res[c]["okx"] = okx
    # Coinbase premium (BTC-USD on Coinbase vs BTCUSDT on Binance spot, same closed hour; USD vs USDT not adjusted)
    cb = get("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600")
    bs = get("https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=3")
    if cb and bs:
        bmap = {int(x[0]) // 1000: float(x[4]) for x in bs}
        for row in cb:                                           # newest first, [time, low, high, open, close, vol]
            t = int(row[0])
            if t in bmap and t + 3600 <= NOW.timestamp():
                res["BTC"]["coinbase_premium"] = {"hour_utc": dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M"),
                                                  "pct": r((float(row[4]) / bmap[t] - 1) * 100, 4)}
                break
    return res


def options():
    out = {}
    for cur in ("BTC", "ETH"):
        j = get(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={cur}&kind=option")
        rows = (j or {}).get("result") or []
        agg = {}
        for x in rows:
            p = x["instrument_name"].split("-")                 # BTC-27NOV26-90000-C
            if len(p) != 4:
                continue
            e = agg.setdefault(p[1], {"call_oi": 0.0, "put_oi": 0.0, "under": x.get("underlying_price")})
            e["call_oi" if p[3] == "C" else "put_oi"] += float(x.get("open_interest") or 0)
        lst = []
        for k, v in agg.items():
            try:
                d = dt.datetime.strptime(k, "%d%b%y").replace(hour=8, tzinfo=UTC)
            except ValueError:
                continue
            if d < NOW:
                continue
            tot = v["call_oi"] + v["put_oi"]
            lst.append({"expiry_utc": d.strftime("%Y-%m-%d 08:00"), "oi_coins": r(tot, 1),
                        "oi_usd": r(tot * (v["under"] or 0), 0), "put_call": r(v["put_oi"] / v["call_oi"], 3) if v["call_oi"] else None})
        lst.sort(key=lambda e: e["expiry_utc"])
        if lst:
            big = max(lst[:12], key=lambda e: e["oi_coins"] or 0)
            out[cur] = {"next": lst[:4], "largest_next_12": big, "total_oi_coins": r(sum(e["oi_coins"] or 0 for e in lst), 1)}
    return out


STABLE = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "EUR", "EURI", "AEUR", "USD1", "XUSD", "PYUSD", "USDE", "RLUSD",
          "BFUSD", "PAXG", "XAUT", "WBTC", "WBETH", "BNSOL", "USTC", "GBP", "TRY", "BRL"}


def movers():
    t = get("https://data-api.binance.vision/api/v3/ticker/24hr")
    if not t:
        return None
    rows = []
    for x in t:
        s = x["symbol"]
        if not s.endswith("USDT"):
            continue
        b = s[:-4]
        if b in STABLE or b.endswith(("UP", "DOWN", "BULL", "BEAR")):
            continue
        qv = float(x["quoteVolume"])
        if qv < 20e6 or int(x.get("count", 0)) == 0:
            continue
        rows.append({"sym": b, "chg_24h_pct": float(x["priceChangePercent"]), "qvol_musd": round(qv / 1e6, 1)})
    if not rows:
        return None
    btc = next((x["chg_24h_pct"] for x in rows if x["sym"] == "BTC"), None)
    rows.sort(key=lambda x: x["chg_24h_pct"], reverse=True)
    up = sum(1 for x in rows if x["chg_24h_pct"] > 0)
    beat = sum(1 for x in rows if btc is not None and x["chg_24h_pct"] > btc)
    return {"source": "Binance spot, rolling 24h at snapshot time", "universe_n": len(rows), "min_qvol_musd": 20,
            "btc_chg_24h_pct": btc, "up_n": up, "beat_btc_n": beat,
            "top": rows[:8], "bottom": rows[-8:][::-1]}


# ------------------------------------------------------------------ main
def main():
    os.makedirs(f"{OUT}/history", exist_ok=True)
    snap = {"run_utc": NOW.strftime("%Y-%m-%d %H:%M:%S"), "script": "live_snapshot_rev1.py",
            "note": "Information only - no forecast, no trade call.", "coins": {}}
    for c in COINS:
        try:
            lv = levels(c)
            if lv is None:
                ERR.append(f"{c}: no price data")
                continue
            info, h = lv
            info["vol"] = vol(c, h)
            info["spot_perp_gap_30d"] = spot_perp_gap(c)
            snap["coins"][c] = info
        except Exception as e:
            ERR.append(f"{c}: {repr(e)[:160]}")
    spot_last = {c: snap["coins"].get(c, {}).get("price") for c in COINS}
    for name, fn in (("positioning", lambda: positioning(spot_last)), ("dvol", dvol), ("options", options), ("movers", movers)):
        try:
            snap[name] = fn()
        except Exception as e:
            ERR.append(f"{name}: {repr(e)[:160]}")
            snap[name] = None
    snap["errors"] = ERR
    with open(f"{OUT}/live_latest.json", "w") as f:
        json.dump(snap, f, indent=1)
    with open(f"{OUT}/history/live_{NOW.strftime('%Y-%m-%d')}.json", "w") as f:
        json.dump(snap, f, indent=1)
    log = f"{OUT}/positioning_log_rev1.csv"
    new = not os.path.exists(log)
    with open(log, "a") as f:
        if new:
            f.write("run_utc,coin,price,hl_funding_ann_pct,hl_oi_usd,okx_funding_ann_pct,okx_oi_usd,okx_oi_all_usd\n")
        for c in COINS:
            p = (snap.get("positioning") or {}).get(c, {})
            hl, ok = p.get("hl", {}), p.get("okx", {})
            vals = [snap["run_utc"], c, spot_last.get(c), hl.get("funding_ann_pct"), hl.get("oi_usd"),
                    ok.get("funding_ann_pct"), ok.get("oi_usd"), ok.get("oi_all_usd")]
            f.write(",".join("" if v is None else str(v) for v in vals) + "\n")
    print(json.dumps({"run_utc": snap["run_utc"], "coins": list(snap["coins"]), "errors": ERR}, indent=1))


if __name__ == "__main__":
    main()
