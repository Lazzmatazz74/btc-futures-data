#!/usr/bin/env python3
"""
hl_daily_snapshot_rev1.py - point-in-time "smart vs dumb money" positioning on Hyperliquid.

Runs every 4h (GitHub Action fetch_hl_snapshot_rev1.yml). Builds history going forward only:
nothing here uses information from the future, so the positioning series can be tested honestly later.

Once per UTC day (first run of the day):
  - download the leaderboard, save a compact copy of recently active funded traders
  - pick two groups using ONLY that day's leaderboard:
      eligible = account value >= $20k, month volume >= $1M, all-time volume >= $10M,
                 all-time volume / account value <= 3000 (drops market makers / bots),
                 |all-time PnL per $ traded| <= 50 bps (drops long-term holders / airdrop accounts)
      SMART = top 200 eligible by all-time PnL per $ traded (bps)
      DUMB  = bottom 200 eligible by the same measure
Every run:
  - read current positions (clearinghouseState, weight 2 each) for both groups
  - append raw positions for tracked coins to positions/positions_YYYY-MM.csv
  - append one aggregate line per group x coin to summary.csv (the signal file)

Output: data/hyperliquid/snapshot/
Stdlib only. Reuses the HTTP / rate-limit helpers from hl_trader_screen_rev2.py.
"""
import csv, gzip, os, sys, time
from datetime import datetime, timezone
import hl_trader_screen_rev2 as base

OUT = os.environ.get("HL_SNAP_DIR", "data/hyperliquid/snapshot")
GROUP_SIZE = int(base._env_float("HL_GROUP_SIZE", 200))
COINS = ["BTC", "ETH", "SOL", "HYPE", "XRP", "BNB"]
MAX_ABS_BPS = 50.0


def eligible(r):
    av, vlm, mv, ap = r["account_value"], r["allTime_vlm"], r["month_vlm"], r["allTime_pnl"]
    if None in (av, vlm, mv, ap) or av < 20_000 or mv < 1_000_000 or vlm < 10_000_000:
        return False
    if vlm / av > 3000:
        return False
    return abs(ap / vlm * 1e4) <= MAX_ABS_BPS


def build_groups(day):
    raw = base.http_get_json(base.LEADERBOARD_URL)
    rows = base.parse_leaderboard(raw)
    del raw
    # compact daily copy: recently active, funded traders only (keeps the repo small, ~0.1-0.2 MB/day)
    active = [r for r in rows if (r["month_vlm"] or 0) >= 1_000_000 and (r["allTime_vlm"] or 0) >= 10_000_000
              and (r["account_value"] or 0) >= 20_000]
    os.makedirs(f"{OUT}/leaderboard", exist_ok=True)
    base.write_csv_gz(f"{OUT}/leaderboard/lb_{day}.csv.gz", base.LB_FIELDS, active)
    el = [dict(r, bps=r["allTime_pnl"] / r["allTime_vlm"] * 1e4) for r in rows if eligible(r)]
    el.sort(key=lambda r: r["bps"], reverse=True)
    smart = el[:GROUP_SIZE]
    dumb = el[-GROUP_SIZE:] if len(el) >= 2 * GROUP_SIZE else el[len(el) // 2:]
    out = [dict(r, group="SMART", rank=i + 1) for i, r in enumerate(smart)] + \
          [dict(r, group="DUMB", rank=i + 1) for i, r in enumerate(reversed(dumb))]
    os.makedirs(f"{OUT}/groups", exist_ok=True)
    base.write_csv(f"{OUT}/groups/groups_{day}.csv",
                   ["group", "rank", "address", "account_value", "bps", "allTime_pnl", "allTime_vlm", "month_pnl", "month_vlm"], out)
    return out, len(rows), len(el)


def load_groups(day):
    p = f"{OUT}/groups/groups_{day}.csv"
    if not os.path.exists(p):
        return None
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def append_csv(path, fields, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    now = datetime.now(timezone.utc)
    day, ts = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M")
    os.makedirs(f"{OUT}/positions", exist_ok=True)
    groups = load_groups(day)
    info = {}
    if groups is None:
        print("Building today's groups from the leaderboard ...", flush=True)
        groups, n_lb, n_el = build_groups(day)
        info = {"leaderboard_rows": n_lb, "eligible": n_el}
        print(f"  {n_lb} rows, {n_el} eligible, {len(groups)} accounts in groups", flush=True)

    pos_rows, errors = [], 0
    agg = {(g, c): {"n_accounts": 0, "n_long": 0, "n_short": 0, "long_usd": 0.0, "short_usd": 0.0}
           for g in ("SMART", "DUMB") for c in COINS}
    counted = {"SMART": 0, "DUMB": 0}
    for i, g in enumerate(groups, 1):
        try:
            st = base.info_post({"type": "clearinghouseState", "user": g["address"]}, base_weight=2)
        except Exception as e:
            errors += 1
            print(f"  error {g['address']}: {e!r}", flush=True)
            continue
        counted[g["group"]] += 1
        held = {}
        for ap in (st or {}).get("assetPositions", []):
            p = ap.get("position", {})
            c = p.get("coin")
            if c in COINS:
                szi = base.to_float(p.get("szi")) or 0.0
                val = base.to_float(p.get("positionValue")) or 0.0
                held[c] = (szi, val)
                lev = p.get("leverage", {})
                pos_rows.append({"ts_utc": ts, "group": g["group"], "rank": g["rank"], "address": g["address"], "coin": c,
                                 "szi": p.get("szi"), "entryPx": p.get("entryPx"), "positionValue": p.get("positionValue"),
                                 "unrealizedPnl": p.get("unrealizedPnl"),
                                 "leverage": lev.get("value") if isinstance(lev, dict) else lev,
                                 "liquidationPx": p.get("liquidationPx")})
        for c in COINS:
            a = agg[(g["group"], c)]
            a["n_accounts"] += 1
            if c in held:
                szi, val = held[c]
                if szi > 0: a["n_long"] += 1; a["long_usd"] += val
                elif szi < 0: a["n_short"] += 1; a["short_usd"] += val
    append_csv(f"{OUT}/positions/positions_{now.strftime('%Y-%m')}.csv",
               ["ts_utc", "group", "rank", "address", "coin", "szi", "entryPx", "positionValue", "unrealizedPnl", "leverage", "liquidationPx"],
               pos_rows)
    summ = []
    for (g, c), a in agg.items():
        gross = a["long_usd"] + a["short_usd"]
        held_n = a["n_long"] + a["n_short"]
        summ.append({"ts_utc": ts, "group": g, "coin": c, **{k: round(v, 2) if isinstance(v, float) else v for k, v in a.items()},
                     "net_usd": round(a["long_usd"] - a["short_usd"], 2),
                     "tilt": round((a["long_usd"] - a["short_usd"]) / gross, 4) if gross else "",
                     "breadth": round((a["n_long"] - a["n_short"]) / held_n, 4) if held_n else ""})
    append_csv(f"{OUT}/summary.csv", ["ts_utc", "group", "coin", "n_accounts", "n_long", "n_short", "long_usd", "short_usd",
                                      "net_usd", "tilt", "breadth"], summ)
    append_csv(f"{OUT}/run_log.csv", ["ts_utc", "accounts_ok_smart", "accounts_ok_dumb", "errors", "position_rows", "leaderboard_rows", "eligible"],
               [{"ts_utc": ts, "accounts_ok_smart": counted["SMART"], "accounts_ok_dumb": counted["DUMB"], "errors": errors,
                 "position_rows": len(pos_rows), **info}])
    print(f"Done: {counted} accounts read, {errors} errors, {len(pos_rows)} position rows.", flush=True)
    return 0 if (counted["SMART"] + counted["DUMB"]) else 1


if __name__ == "__main__":
    sys.exit(main())
