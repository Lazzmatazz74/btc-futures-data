#!/usr/bin/env python3
"""
build_brief_doc_rev1.py — builds the daily brief document (schema v2) from fetched files.
Trading project, 2026-10-06, account B. Run by the scheduled "Trading1 daily brief" task (prompt rev3).

Every number in the brief comes from these files - nothing is typed by hand:
  --live      data/brief/live/live_latest.json   (live_snapshot_rev4.py: levels, vol, positioning, options, movers)
  --latest    data/brief/latest.json             (daily_checks_rev1.py: research books X3 / C3 / gauge / scoreboards)
  --gauge     data/brief/gauge_log_rev1.csv
  --dossiers  data/brief/latest_dossiers.md
  --calendar  calendar.json  written by the brief task from the official Fed / BLS pages:
              {"verified": true|false, "events": [{"when_utc": "YYYY-MM-DD HH:MM", "what": "...", "src": "url"}],
               "checked": ["url", ...], "note": "..."}
  --trades    folder of Trade Journal "trades" documents (ArtifactData out_dir), optional
  --headline / --changed / --journal  plain-English text written by the task (optional; defaults are built here)
  --out       brief.json  (document for the brief page, collection "briefs", doc id = date)

Prints a FACTS block - the task writes its headline from those facts only.
Information only: no forecasts, no trade calls.
"""
import argparse, csv, glob, json, os, re, datetime as dt

UTC = dt.timezone.utc
COINS = ["BTC", "ETH", "XRP", "BNB", "LTC", "HYPE"]


def jload(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def parse_t(s):
    if not s:
        return None
    s = str(s).replace("T", " ").replace("Z", "")[:16]
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    except ValueError:
        try:
            return dt.datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None


def hm(t):
    return t.strftime("%Y-%m-%d %H:%M") if t else None


# ------------------------------------------------------------------ research (unchanged meaning vs brief rev2)
def dossier_sections(md):
    out = {}
    if not md:
        return out
    for block in re.split(r"\n(?=## )", md):
        m = re.match(r"## (\w+) (LONG|SHORT) — (\S+) (\S+) — entry (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC", block)
        if not m:
            continue
        sec = {"g3": None, "dma200": None, "caseAgainst": None, "counter": None, "gaps": []}
        rows = [l for l in block.splitlines() if l.startswith("| ") and not l.startswith("| Entry") and not l.startswith("|---")]
        if rows:
            cells = [c.strip() for c in rows[0].strip("|").split("|")]
            if len(cells) >= 6:
                sec["g3"], sec["dma200"] = cells[4], cells[5]
        for l in block.splitlines():
            if l.startswith("- Case against that:"):
                sec["counter"] = l.split(":", 1)[1].strip()
            elif l.startswith("- Case against:"):
                sec["caseAgainst"] = l.split(":", 1)[1].strip()
            elif l.startswith("- Data gaps:"):
                g = l.split(":", 1)[1].strip()
                sec["gaps"] = [] if g.lower() in ("none", "", "[]") else [g]
        out[(m.group(1), m.group(2).lower(), m.group(5))] = sec
    return out


def research(latest, gauge_rows, dossiers_md, today0):
    if not latest:
        return {"dataEnd": None, "behindDays": None, "researchMissing": True}
    de = parse_t(latest.get("data_end"))
    behind = max(0, (today0 - de).days) if de else None
    h = latest.get("health") or {}
    g = latest.get("edge_gauge") or {}
    prev = None
    if len(gauge_rows) >= 2:
        p = gauge_rows[-2]
        prev = {"r30": num(p.get("rolling30")), "r60": num(p.get("rolling60")), "cusum": num(p.get("cusum"))}
    dos = dossier_sections(dossiers_md)
    sigs, seen = [], set()
    for s in (latest.get("x3_new_signals") or []):
        t = parse_t(s.get("entry_time"))
        d = dos.get((s.get("sym"), s.get("side"), hm(t)), {})
        flags = s.get("flags") or ""
        flags = [x for x in flags.split(",") if x] if isinstance(flags, str) else list(flags)
        sigs.append({"sym": s.get("sym"), "side": s.get("side"), "lvl": s.get("lvl"), "ent": s.get("ent"),
                     "entryTime": hm(t), "entry": num(s.get("entry")), "stop": num(s.get("stop")), "flags": flags,
                     "g3": d.get("g3"), "dma200": d.get("dma200"), "status": s.get("status"),
                     "R": num(s.get("R_F063")), "caseAgainst": d.get("caseAgainst"), "counter": d.get("counter"),
                     "macro": None, "gaps": d.get("gaps", [])})
        seen.add((s.get("sym"), s.get("side"), hm(t)))
    opn = []
    for o in (latest.get("x3_open") or []):
        t = parse_t(o.get("entry_time"))
        opn.append({"sym": o.get("sym"), "side": o.get("side"), "entryTime": hm(t), "entry": num(o.get("entry")),
                    "stop": num(o.get("stop")), "markR": num(o.get("mark_R_F063"))})
        if (o.get("sym"), o.get("side"), hm(t)) not in seen:
            d = dos.get((o.get("sym"), o.get("side"), hm(t)), {})
            sigs.append({"sym": o.get("sym"), "side": o.get("side"), "lvl": None, "ent": None, "entryTime": hm(t),
                         "entry": num(o.get("entry")), "stop": num(o.get("stop")), "flags": [], "g3": d.get("g3"),
                         "dma200": d.get("dma200"), "status": "open", "R": None, "caseAgainst": d.get("caseAgainst"),
                         "counter": d.get("counter"), "macro": None, "gaps": d.get("gaps", [])})
    c3 = {k: {"on": v.get("C3"), "quiet": v.get("quiet"), "oi7d": num(v.get("oi_chg_7d"))}
          for k, v in (latest.get("c3_status") or {}).items()}
    c3day = next((v.get("day") for v in (latest.get("c3_status") or {}).values()), None)
    comp = [{"sym": c.get("sym"), "side": c.get("side"), "entryTime": hm(parse_t(c.get("entry_time"))),
             "entry": num(c.get("entry")), "stop": num(c.get("stop")), "c3": c.get("C3_at_entry"),
             "status": c.get("status")} for c in (latest.get("comp_new_signals") or [])]
    sb = latest.get("scoreboards") or {}
    G, F, C = sb.get("G3", {}), sb.get("FLAGS", {}), sb.get("C3", {})
    return {
        "dataEnd": hm(de), "behindDays": behind, "researchRunUtc": latest.get("run_utc"),
        "health": {"downloadOk": h.get("download_ok"), "problems": h.get("download_problems") or [],
                   "gaps": [str(x) for x in (latest.get("unknown_gaps") or [])],
                   "oiDensity": h.get("metrics_density_7d"),
                   "fundingUntil": (min((v or "")[:10] for v in (h.get("funding_settled_until") or {}).values())
                                    if h.get("funding_settled_until") else None), "notes": []},
        "gauge": {"nClosed": g.get("n_closed"), "r30": num(g.get("rolling30")), "r60": num(g.get("rolling60")),
                  "cusum": num(g.get("cusum")), "limit": num(g.get("cusum_limit")), "thr30": num(g.get("thr30")),
                  "thr60": num(g.get("thr60")), "lastZero": (g.get("cusum_last_zero_exit") or "")[:16] or None,
                  "lastExit": (g.get("last_exit") or "")[:16] or None, "prev": prev},
        "signals": sigs, "open": opn, "c3": c3, "c3Day": c3day, "comp": comp,
        "scoreboards": {
            "G3": {"n": G.get("n_live_closed"), "target": 30, "a": {"n": G.get("take_n"), "mean": num(G.get("take_mean"))},
                   "b": {"n": G.get("skip_n"), "mean": num(G.get("skip_mean"))}},
            "FLAGS": {"n": F.get("n_live_closed"), "target": 60, "a": {"n": F.get("flagged_n"), "mean": num(F.get("flagged_mean"))},
                      "b": {"n": F.get("unflagged_n"), "mean": num(F.get("unflagged_mean"))}},
            "C3": {"n": C.get("n_live_closed_C3on"), "target": 30, "a": {"n": C.get("n_live_closed_C3on"), "mean": num(C.get("on_mean"))},
                   "b": {"n": C.get("n_live_closed_C3off"), "mean": num(C.get("off_mean"))}}},
    }


# ------------------------------------------------------------------ live market sections
def coins_block(live):
    out = {}
    pos = (live or {}).get("positioning") or {}
    for c in COINS:
        x = ((live or {}).get("coins") or {}).get(c)
        if not x:
            continue
        p = pos.get(c) or {}
        hl, ok = p.get("hl") or {}, p.get("okx") or {}
        lv = [{"name": l["name"], "kind": l.get("kind"), "price": l["price"], "dist": l["dist_pct"],
               "state": l.get("state"), "src": l.get("src")} for l in x.get("levels", [])]
        out[c] = {"price": x.get("price"), "priceSrc": x.get("price_src"), "archiveEnd": x.get("archive_end_utc"),
                  "lastBar": x.get("last_closed_bar_utc"), "levels": lv,
                  "above": x.get("nearest_above", []), "below": x.get("nearest_below", []),
                  "yday": x.get("yesterday_daily_levels", []), "vol": x.get("vol"),
                  "gap": x.get("spot_perp_gap_30d"),
                  "pos": {"hlFundAnn": hl.get("funding_ann_pct"), "hlOiUsd": hl.get("oi_usd"), "hlPremPct": hl.get("premium_pct"),
                          "okxFundAnn": ok.get("funding_ann_pct"), "okxOiUsd": ok.get("oi_all_usd") or ok.get("oi_usd"),
                          "oi24": ok.get("oi_chg_24h_pct"), "oi7d": ok.get("oi_chg_7d_pct"),
                          "oi24Span": ok.get("oi_chg_24h_from_to_utc"), "oi7dSpan": ok.get("oi_chg_7d_from_to_utc")}}
    return out


def calendar_block(cal, live, now):
    end = now + dt.timedelta(days=7)
    ev = []
    for e in ((cal or {}).get("events") or []):
        t = parse_t(e.get("when_utc"))
        if t and now - dt.timedelta(hours=6) <= t <= end:
            ev.append({"whenUtc": hm(t), "what": e.get("what"), "kind": "macro", "src": e.get("src")})
    for cur, o in (((live or {}).get("options")) or {}).items():
        for x in (o or {}).get("next", []):
            t = parse_t(x.get("expiry_utc"))
            if t and now <= t <= end and (x.get("oi_usd") or 0) >= 1e9:
                ev.append({"whenUtc": hm(t), "what": f"{cur} options expiry, open interest ${x['oi_usd'] / 1e9:.1f}B "
                           f"(put/call {x.get('put_call')})", "kind": "options", "src": "deribit.com"})
        big = (o or {}).get("largest_next_30d")
        if big:
            t = parse_t(big.get("expiry_utc"))
            if t and now <= t <= end and not any(e["whenUtc"] == hm(t) and e["what"].startswith(cur) for e in ev):
                ev.append({"whenUtc": hm(t), "what": f"{cur} largest options expiry in 30 days, open interest "
                           f"${(big.get('oi_usd') or 0) / 1e9:.1f}B (put/call {big.get('put_call')})", "kind": "options",
                           "src": "deribit.com"})
    d = now.date()
    for i in range(8):
        day = d + dt.timedelta(days=i)
        t = dt.datetime(day.year, day.month, day.day, tzinfo=UTC)
        if t < now - dt.timedelta(hours=6) or t > end:
            continue
        if day.day == 1:
            ev.append({"whenUtc": hm(t), "what": "New month: monthly open (MO) resets, PMH/PML roll", "kind": "period", "src": None})
        if day.weekday() == 0:
            ev.append({"whenUtc": hm(t), "what": "New week: weekly open (WO) resets, PWH/PWL and weekend H/L roll", "kind": "period", "src": None})
    ev.sort(key=lambda e: e["whenUtc"])
    return {"verified": bool((cal or {}).get("verified")), "checked": (cal or {}).get("checked", []),
            "note": (cal or {}).get("note"), "events": ev, "windowDays": 7}


def market_block(live):
    lv = live or {}
    btc_pos = ((lv.get("positioning") or {}).get("BTC") or {})
    opts = {}
    for cur, o in (lv.get("options") or {}).items():
        if o:
            opts[cur] = {"next": o.get("next", []), "largest30d": o.get("largest_next_30d"), "totalOi": o.get("total_oi_coins")}
    return {"dvol": lv.get("dvol"), "cbPremium": btc_pos.get("coinbase_premium"), "options": opts,
            "movers": lv.get("movers"), "hlBaselineAnn": lv.get("hl_baseline_funding_ann_pct", 10.95)}


# ------------------------------------------------------------------ trade journal
def trades_block(folder, now):
    if not folder or not os.path.isdir(folder):
        return {"read": False, "n": 0, "trades": [], "note": "Journal not read."}
    since = now - dt.timedelta(hours=24)
    s_ms = since.timestamp() * 1000
    rows = []
    for p in glob.glob(os.path.join(folder, "**", "*.json"), recursive=True):
        d = jload(p)
        if not isinstance(d, dict):
            continue
        t = d.get("data", d) if isinstance(d.get("data"), dict) else d
        stamps = [t.get("createdAt") or 0] + [f.get("at") or 0 for f in (t.get("fills") or [])] + \
                 [((t.get("close") or {}).get("at")) or 0]
        if max(stamps) < s_ms:
            continue
        ch, cl = t.get("checks") or {}, t.get("close") or {}
        fills = t.get("fills") or []
        rows.append({"id": t.get("id"), "account": t.get("account"), "symbol": t.get("symbol"), "dir": t.get("dir"),
                     "status": t.get("status"), "grade": ch.get("grade"),
                     "fails": ch.get("fails") if isinstance(ch.get("fails"), (int, float)) else len(ch.get("fails") or []),
                     "warns": ch.get("warns") if isinstance(ch.get("warns"), (int, float)) else len(ch.get("warns") or []),
                     "entries": sum(1 for f in fills if f.get("side") == "entry"),
                     "unplannedAdds": sum(1 for f in fills if f.get("side") == "entry" and f.get("planned") is False),
                     "exits": sum(1 for f in fills if f.get("side") == "exit"),
                     "netPnl": num(cl.get("netPnl")), "netR": num(cl.get("netR")), "followedPlan": cl.get("followedPlan")})
    rows.sort(key=lambda r: (r["account"] or "", r["symbol"] or ""))
    return {"read": True, "n": len(rows), "trades": rows, "windowFromUtc": hm(since),
            "note": None if rows else "No trades logged in the journal in the last 24 hours."}


# ------------------------------------------------------------------ facts + defaults
def facts(doc):
    F = []
    s = doc["snap"]
    F.append(f"Snapshot {s['runUtc']} UTC ({s['ageH']} h old), errors: {len(s['errors'])}")
    for c, x in doc["coins"].items():
        L = {l["name"]: l for l in x["levels"]}
        ab = ", ".join(f"{n} {L[n]['price']} ({L[n]['dist']:+.2f}%{', ' + L[n]['state'] if L[n]['state'] else ''})" for n in x["above"][:2] if n in L)
        be = ", ".join(f"{n} {L[n]['price']} ({L[n]['dist']:+.2f}%{', ' + L[n]['state'] if L[n]['state'] else ''})" for n in x["below"][:2] if n in L)
        yd = "; ".join(f"{y['name']} {y['state']}" for y in x["yday"])
        v = x.get("vol") or {}
        p = x["pos"]
        F.append(f"{c} {x['price']}: above {ab or '-'} | below {be or '-'} | yesterday {yd or '-'} | range y {v.get('yesterday_range_pct')}% "
                 f"vs avg20 {v.get('avg20_range_pct')}% | OKX fund {p['okxFundAnn']}%/yr, OI 24h {p['oi24']}%, 7d {p['oi7d']}%")
    m = doc["market"]
    if m.get("dvol"):
        F.append("DVOL " + ", ".join(f"{k} {v['dvol']} (1y pct {v['pctile_1y']})" for k, v in m["dvol"].items()))
    mv = m.get("movers") or {}
    if mv:
        F.append(f"Movers: {mv.get('up_n')}/{mv.get('universe_n')} up, {mv.get('beat_btc_n')} beat BTC ({mv.get('btc_chg_24h_pct')}%); "
                 f"top {[(x['sym'], x['chg_24h_pct']) for x in mv.get('top', [])[:3]]}; bottom {[(x['sym'], x['chg_24h_pct']) for x in mv.get('bottom', [])[:3]]}")
    cal = doc["calendar"]
    F.append(f"Calendar (verified={cal['verified']}): " + ("; ".join(f"{e['whenUtc']} {e['what']}" for e in cal["events"]) or "nothing in 7 days"))
    tr = doc["tradesLog"]
    F.append(f"Journal: {tr['n']} trade(s) in last 24h" + ("" if tr.get("read") else " (not read)"))
    F.append(f"Research: data to {doc.get('dataEnd')} ({doc.get('behindDays')} d behind), new/open X3 {len(doc.get('signals') or [])}, "
             f"open {len(doc.get('open') or [])}, C3 on {[k for k, v in (doc.get('c3') or {}).items() if v.get('on')]}, "
             f"comp signals {len(doc.get('comp') or [])}")
    return F


def main():
    ap = argparse.ArgumentParser()
    for a in ("live", "latest", "gauge", "dossiers", "calendar", "trades", "headline", "changed", "journal", "out"):
        ap.add_argument("--" + a)
    ap.add_argument("--date")
    ap.add_argument("--sources", nargs="*", default=[])
    A = ap.parse_args()
    now = dt.datetime.now(UTC)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    live, latest = jload(A.live), jload(A.latest)
    gauge_rows = []
    if A.gauge and os.path.exists(A.gauge):
        with open(A.gauge) as f:
            gauge_rows = list(csv.DictReader(f))
    md = open(A.dossiers).read() if A.dossiers and os.path.exists(A.dossiers) else ""
    snap_t = parse_t((live or {}).get("run_utc"))
    doc = {"v": 2, "date": A.date or now.strftime("%Y-%m-%d"), "runUtc": now.strftime("%Y-%m-%d %H:%M:%S"),
           "snap": {"runUtc": (live or {}).get("run_utc"),
                    "ageH": round((now - snap_t).total_seconds() / 3600, 1) if snap_t else None,
                    "script": (live or {}).get("script"), "errors": (live or {}).get("errors", ["live snapshot missing"] if not live else [])},
           "coins": coins_block(live), "market": market_block(live),
           "calendar": calendar_block(jload(A.calendar), live, now),
           "tradesLog": trades_block(A.trades, now)}
    doc.update(research(latest, gauge_rows, md, today0))
    snap_stale = doc["snap"]["ageH"] is None or doc["snap"]["ageH"] > 6
    doc["snap"]["stale"] = snap_stale
    if not A.headline:
        parts = []
        if snap_stale:
            parts.append(f"Live snapshot is stale or missing ({doc['snap']['ageH']} h old).")
        b = doc["coins"].get("BTC")
        if b:
            L = {l["name"]: l for l in b["levels"]}
            a = b["above"][0] if b["above"] else None
            z = b["below"][0] if b["below"] else None
            parts.append(f"BTC {b['price']:,}: nearest above {a} ({L[a]['dist']:+.2f}%), nearest below {z} ({L[z]['dist']:+.2f}%)." if a and z else f"BTC {b['price']}.")
        if doc["calendar"]["events"]:
            e = doc["calendar"]["events"][0]
            parts.append(f"Next event: {e['what']} ({e['whenUtc']} UTC).")
        doc["headline"] = " ".join(parts)
    else:
        doc["headline"] = A.headline
    doc["changed"] = A.changed or ""
    doc["journal"] = A.journal or ""
    doc["sources"] = A.sources
    with open(A.out or "brief.json", "w") as f:
        json.dump(doc, f, indent=1, default=str)
    print("FACTS (write the headline from these only):")
    for line in facts(doc):
        print(" -", line)
    print(f"wrote {A.out or 'brief.json'} ({os.path.getsize(A.out or 'brief.json')} bytes)")


if __name__ == "__main__":
    main()
