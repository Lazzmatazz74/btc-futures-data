#!/usr/bin/env python3
"""macro_data_downloader_rev1.py — outside-market history for the macro watch (2026-11-03, account A).

Spec: claude-work Trading/MACRO_WATCH_SPEC_rev3.md (Part B). Runs in btc-futures-data, workflow fetch_macro_rev1.yml.
Times: UTC epoch ms, open time of the bar. Output folder data/macro/.

Modes:
  duka    raw_macro/<inst>_<bid|ask>_<year>.csv (written by dukascopy-node in the workflow)
          -> data/macro/duka_<name>_1h.csv.gz  (mid = (bid+ask)/2, plus spread = ask close - bid close)
  yahoo   Yahoo chart API -> data/macro/yahoo_<name>_1d.csv (2019-01-01 -> now, explicit period)
                          -> data/macro/yahoo_<name>_1h.csv (range 730d)
  flows   Farside "all data" table -> data/macro/etf_flows_daily.csv (US$ m per fund + total)
  check   data/macro/macro_data_check.json + job annotation: rows, first/last, largest gap, and Dukascopy vs
          Yahoo on the same hours (median and p99 absolute % gap).
"""
import glob, io, json, os, re, sys, time, urllib.request, datetime as dt
import pandas as pd
import numpy as np

RAW, OUT = "raw_macro", "data/macro"
os.makedirs(OUT, exist_ok=True)
UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
UA = {"User-Agent": "Mozilla/5.0 (macro-downloader)"}

DUKA = {"usa500idxusd": "sp500", "usatechidxusd": "nasdaq100", "xauusd": "gold", "lightcmdusd": "wti",
        "brentcmdusd": "brent", "usdjpy": "usdjpy", "dollaridxusd": "dxy"}
YAHOO = {"^NDX": "nasdaq100", "^GSPC": "sp500", "GC=F": "gold", "CL=F": "wti", "DX-Y.NYB": "dxy", "^TNX": "us10y",
         "^VIX": "vix", "JPY=X": "usdjpy", "MSTR": "mstr", "COIN": "coin", "IBIT": "ibit", "HYG": "hyg",
         "BTC-USD": "btcusd", "NQ=F": "nq_fut", "ES=F": "es_fut"}
YAHOO_1H = ["^VIX", "MSTR", "COIN", "NQ=F", "ES=F", "GC=F", "CL=F", "DX-Y.NYB", "JPY=X"]
# stock index 1h bars on Yahoo open at :30, so the same-hour checks use the index futures (bars at :00)
# same-hour cross-checks: Dukascopy name -> Yahoo name
PAIRS = {"sp500": "es_fut", "nasdaq100": "nq_fut", "gold": "gold", "wti": "wti", "dxy": "dxy", "usdjpy": "usdjpy"}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            print("retry", i, url[:90], repr(e)[:100]); time.sleep(3 * (i + 1))
    return None


def notice(title, rows):
    msg = "\n".join(rows).replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title={title}::{msg}")
    print(f"----- {title}\n" + "\n".join(rows))


# ------------------------------------------------------------------ Dukascopy
def read_raw(path):
    d = pd.read_csv(path)
    d.columns = [c.lower() for c in d.columns]
    return d[["timestamp", "open", "high", "low", "close"]].set_index("timestamp")


def duka():
    for inst, name in DUKA.items():
        parts = []
        for bid in sorted(glob.glob(f"{RAW}/{inst}_bid_*.csv")):
            ask = bid.replace("_bid_", "_ask_")
            if not os.path.exists(ask):
                print("missing ask", ask); continue
            try:
                b, a = read_raw(bid), read_raw(ask)
            except Exception as e:
                print("skip", bid, repr(e)[:80]); continue
            j = b.join(a, lsuffix="_b", rsuffix="_a", how="inner")
            if j.empty:
                continue
            m = pd.DataFrame({k: (j[f"{k}_b"] + j[f"{k}_a"]) / 2 for k in ["open", "high", "low", "close"]})
            m["spread"] = j["close_a"] - j["close_b"]
            parts.append(m)
        if not parts:
            print("no data", inst); continue
        d = pd.concat(parts).sort_index()
        d = d[~d.index.duplicated()]
        d.index = d.index.astype("int64")
        d.index.name = "open_time"
        d.round(5).to_csv(f"{OUT}/duka_{name}_1h.csv.gz", compression="gzip")
        print(name, len(d), "rows")


# ------------------------------------------------------------------ Yahoo
def yahoo_one(sym, query):
    raw = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}?{query}")
    if raw is None:
        return None
    r = json.loads(raw)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    d = pd.DataFrame({"open_time": np.array(r["timestamp"], dtype="int64") * 1000, "open": q["open"],
                      "high": q["high"], "low": q["low"], "close": q["close"], "volume": q.get("volume")})
    return d.dropna(subset=["close"]).drop_duplicates("open_time").sort_values("open_time")


def yahoo():
    p1, p2 = int(dt.datetime(2019, 1, 1, tzinfo=UTC).timestamp()), int(NOW.timestamp())
    for sym, name in YAHOO.items():
        d = yahoo_one(sym, f"period1={p1}&period2={p2}&interval=1d")
        if d is not None:
            d.to_csv(f"{OUT}/yahoo_{name}_1d.csv", index=False); print(name, "1d", len(d))
        time.sleep(1)
    for sym in YAHOO_1H:
        d = yahoo_one(sym, "range=730d&interval=1h")
        if d is not None:
            d.to_csv(f"{OUT}/yahoo_{YAHOO[sym]}_1h.csv", index=False); print(YAHOO[sym], "1h", len(d))
        time.sleep(1)


# ------------------------------------------------------------------ Farside ETF flows
def num(x):
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "nan", "None"):
        return np.nan
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return np.nan
    return -v if neg else v


def flows():
    raw = get("https://farside.co.uk/bitcoin-etf-flow-all-data/")
    if raw is None:
        print("farside: no page"); return
    tables = pd.read_html(io.StringIO(raw.decode("utf-8", "replace")))
    t = max(tables, key=len)
    t.columns = [str(c[-1] if isinstance(c, tuple) else c).strip() for c in t.columns]
    t = t.rename(columns={t.columns[0]: "date"})
    t["date"] = pd.to_datetime(t["date"], format="%d %b %Y", errors="coerce")
    t = t.dropna(subset=["date"])
    for c in t.columns[1:]:
        t[c] = t[c].map(num)
    t.sort_values("date").to_csv(f"{OUT}/etf_flows_daily.csv", index=False)
    print("flows", len(t), "rows, columns", list(t.columns))


# ------------------------------------------------------------------ check
def load(path):
    d = pd.read_csv(path)
    return d.set_index("open_time").sort_index()


def check():
    rep, rows = {"run_utc": NOW.strftime("%Y-%m-%d %H:%M"), "files": {}, "pairs": {}}, []
    for p in sorted(glob.glob(f"{OUT}/*.csv*")):
        n = os.path.basename(p)
        if n.startswith("etf_flows"):
            d = pd.read_csv(p)
            tot = [c for c in d.columns if c.lower() == "total"]
            info = {"rows": len(d), "first": str(d["date"].min())[:10], "last": str(d["date"].max())[:10],
                    "columns": len(d.columns), "total_col": bool(tot),
                    "total_last5": d[tot[0]].tail(5).tolist() if tot else None}
        else:
            d = load(p)
            t = pd.to_datetime(d.index, unit="ms", utc=True)
            gap = (t[1:] - t[:-1]).max() if len(t) > 1 else pd.Timedelta(0)
            info = {"rows": len(d), "first": str(t.min())[:16], "last": str(t.max())[:16],
                    "max_gap_h": round(gap.total_seconds() / 3600, 1), "last_close": float(d["close"].iloc[-1])}
        rep["files"][n] = info
        rows.append(f"{n} | " + " | ".join(f"{k} {v}" for k, v in info.items()))
    for dn, yn in PAIRS.items():
        fd, fy = f"{OUT}/duka_{dn}_1h.csv.gz", f"{OUT}/yahoo_{yn}_1h.csv"
        if not (os.path.exists(fd) and os.path.exists(fy)):
            continue
        a, b = load(fd)["close"], load(fy)["close"]
        j = pd.concat([a, b], axis=1, keys=["d", "y"], join="inner").dropna()
        if j.empty:
            continue
        g = ((j["d"] - j["y"]) / j["y"] * 100).abs()
        rc = j.pct_change().dropna()
        info = {"hours": len(j), "median_gap_pct": round(g.median(), 3), "p99_gap_pct": round(g.quantile(.99), 3),
                "hourly_return_corr": round(rc["d"].corr(rc["y"]), 3)}
        rep["pairs"][dn] = info
        rows.append(f"PAIR {dn} duka vs yahoo | " + " | ".join(f"{k} {v}" for k, v in info.items()))
    json.dump(rep, open(f"{OUT}/macro_data_check.json", "w"), indent=1)
    notice("macro_data_check", rows)


if __name__ == "__main__":
    {"duka": duka, "yahoo": yahoo, "flows": flows, "check": check}[sys.argv[1]]()
