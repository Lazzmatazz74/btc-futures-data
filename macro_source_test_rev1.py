#!/usr/bin/env python3
"""macro_source_test_rev1.py — which outside-market data sources a GitHub runner can reach (2026-11-03, account A).

Spec: claude-work Trading/MACRO_WATCH_SPEC_rev2.md (data section). Read-only test: prints to the log and
sends results as job annotations; writes nothing to the repo.

Modes:
  web    Yahoo chart API (daily + hourly depth), Stooq, FRED, Farside ETF flows, Hyperliquid HIP-3 dexes/candles
  duka   summarise the dukascopy-node CSVs the workflow wrote to ./duka_test (rows, first/last time, last close)
"""
import csv, glob, json, os, sys, time, urllib.request, urllib.error, datetime as dt

UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
UA = {"User-Agent": "Mozilla/5.0 (macro-source-test)", "Content-Type": "application/json"}


def call(url, body=None, n=600):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read()
            return r.status, raw, int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, e.read(n), int((time.time() - t0) * 1000)
    except Exception as e:
        return None, repr(e)[:n].encode(), int((time.time() - t0) * 1000)


def notice(title, rows):
    msg = "\n".join(rows).replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title={title}::{msg}")
    print(f"----- {title}\n" + "\n".join(rows))


def ts(sec):
    return dt.datetime.fromtimestamp(sec, UTC).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- Yahoo
YAHOO = ["^NDX", "^GSPC", "NQ=F", "ES=F", "GC=F", "CL=F", "DX-Y.NYB", "^TNX", "^VIX", "JPY=X",
         "MSTR", "COIN", "IBIT", "HYG", "BTC-USD"]


def yahoo(sym, rng, itv):
    q = urllib.request.quote(sym)
    st, raw, ms = call(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range={rng}&interval={itv}")
    if st != 200:
        return f"{sym} {rng}/{itv} | {st} | {raw[:120].decode('utf-8', 'replace')}"
    try:
        j = json.loads(raw)["chart"]["result"][0]
        t = j.get("timestamp") or []
        c = j["indicators"]["quote"][0]["close"]
        last = next((x for x in reversed(c) if x is not None), None)
        return f"{sym} {rng}/{itv} | 200 | rows {len(t)} | {ts(t[0]) if t else '-'} -> {ts(t[-1]) if t else '-'} | last {last}"
    except Exception as e:
        return f"{sym} {rng}/{itv} | 200 parse error {repr(e)[:80]}"


# ---------------------------------------------------------------- Stooq / FRED / Farside
STOOQ = ["^ndx", "^spx", "gc.f", "cl.f", "dx.f", "10usy.b", "^vix", "usdjpy", "mstr.us", "coin.us"]
FRED = ["DGS10", "VIXCLS", "BAMLH0A0HYM2", "DTWEXBGS", "DCOILWTICO", "SP500", "NASDAQ100", "DEXJPUS"]


def csv_head_tail(st, raw, ms, label):
    txt = raw.decode("utf-8", "replace")
    if st != 200:
        return f"{label} | {st} | {txt[:120]}"
    lines = [l for l in txt.splitlines() if l.strip()]
    if len(lines) < 2:
        return f"{label} | 200 | {ms}ms | not csv: {txt[:120]}"
    return f"{label} | 200 | {ms}ms | rows {len(lines) - 1} | first {lines[1][:40]} | last {lines[-1][:60]}"


def farside():
    out = []
    for url in ["https://farside.co.uk/bitcoin-etf-flow-all-data/", "https://farside.co.uk/btc/"]:
        st, raw, ms = call(url)
        txt = raw.decode("utf-8", "replace")
        out.append(f"{url} | {st} | {ms}ms | bytes {len(raw)} | has 'IBIT' {('IBIT' in txt)} | "
                   f"cloudflare {('cf-' in txt.lower() or 'challenge' in txt.lower())}")
    return out


# ---------------------------------------------------------------- Hyperliquid HIP-3
def hyperliquid():
    rows = []
    st, raw, ms = call("https://api.hyperliquid.xyz/info", {"type": "perpDexs"})
    dexes = []
    if st == 200:
        j = json.loads(raw)
        dexes = [d["name"] for d in j if isinstance(d, dict) and d.get("name")]
        rows.append(f"perpDexs | 200 | {ms}ms | {', '.join(dexes)[:400]}")
    else:
        rows.append(f"perpDexs | {st} | {raw[:120].decode('utf-8', 'replace')}")
    want = ["GOLD", "SILVER", "CL", "OIL", "WTI", "BRENT", "XYZ100", "SP500", "SPX", "NDX", "NASDAQ", "US500",
            "USA500", "MSTR", "COIN", "JPY", "DXY", "VIX"]
    picks = []
    for d in dexes:
        st, raw, ms = call("https://api.hyperliquid.xyz/info", {"type": "meta", "dex": d})
        if st != 200:
            rows.append(f"meta {d} | {st}"); continue
        names = [u["name"] for u in json.loads(raw).get("universe", [])]
        hit = [n for n in names if any(w in n.upper().split(":")[-1] for w in want)]
        rows.append(f"meta {d} | {len(names)} markets | relevant: {', '.join(hit)[:300]}")
        picks += hit[:6]
    end = int(NOW.timestamp() * 1000)
    for coin in picks[:12]:
        for itv, days in [("1h", 30), ("1d", 400)]:
            st, raw, ms = call("https://api.hyperliquid.xyz/info", {"type": "candleSnapshot", "req": {
                "coin": coin, "interval": itv, "startTime": end - days * 86400000, "endTime": end}})
            if st == 200:
                c = json.loads(raw)
                rows.append(f"candles {coin} {itv} | rows {len(c)} | "
                            f"{ts(c[0]['t'] / 1000) if c else '-'} -> {ts(c[-1]['t'] / 1000) if c else '-'} | last {c[-1]['c'] if c else '-'}")
            else:
                rows.append(f"candles {coin} {itv} | {st} | {raw[:100].decode('utf-8', 'replace')}")
    return rows


def web():
    y = [yahoo(s, "5d", "1d") for s in YAHOO]
    y2 = [yahoo(s, rng, itv) for s in ["^NDX", "GC=F", "DX-Y.NYB", "^VIX"] for rng, itv in [("730d", "1h"), ("max", "1d")]]
    notice("yahoo_daily", y)
    notice("yahoo_depth", y2)
    notice("stooq", [csv_head_tail(*call(f"https://stooq.com/q/d/l/?s={urllib.request.quote(s)}&i=d"), s) for s in STOOQ])
    notice("fred", [csv_head_tail(*call(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}"), s) for s in FRED])
    notice("farside", farside())
    notice("hyperliquid_hip3", hyperliquid())


def duka():
    rows = []
    for p in sorted(glob.glob("duka_test/*.csv")):
        with open(p) as f:
            r = list(csv.reader(f))
        if len(r) < 2:
            rows.append(f"{os.path.basename(p)} | empty"); continue
        t0, t1 = int(float(r[1][0])) // 1000, int(float(r[-1][0])) // 1000
        rows.append(f"{os.path.basename(p)} | rows {len(r) - 1} | {ts(t0)} -> {ts(t1)} | last close {r[-1][4]}")
    for p in sorted(glob.glob("duka_test/*.log")):
        txt = open(p).read()
        if "FAILED" in txt or "rror" in txt:
            rows.append(f"{os.path.basename(p)} | {txt.strip()[-160:]}")
    notice("dukascopy", rows or ["no files written"])


if __name__ == "__main__":
    {"web": web, "duka": duka}[sys.argv[1]]()
