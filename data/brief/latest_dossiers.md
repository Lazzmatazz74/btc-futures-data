# X3 signal dossiers — data to 2026-11-06 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH LONG — PW FSB — entry 2026-11-04 15:15 UTC (closed 2026-11-05 15:00, -1.03R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2387.76 | 2344.63 | 2517.15 | 1.81% | n/a (long) | above |

| Feature (vs past longs) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d | -1.05% | 0.15 | LOW | +0.30R (n=174, +0.04..+0.57) |
| oi_chg_24h ★ | +0.39% | 0.20 | LOW | +0.35R (n=174, +0.07..+0.61) |
| retail_ls_pct90 ★ | 0.053 | 0.33 | LOW | +0.17R (n=172, -0.07..+0.45) |
| taker_ls_24h | 1.308 | 0.92 | HIGH | +0.33R (n=165, +0.05..+0.62) |
| premium_8h ★ | -0.0273% | 0.39 | MID | +0.28R (n=244, +0.04..+0.51) |
| dvol_pct365 | 0.227 | 0.35 | MID | +0.21R (n=91, -0.14..+0.60) |
| perp_cvd_4h | 0.072 | 0.80 | HIGH | +0.45R (n=247, +0.22..+0.68) |
| perp_cvd_24h | 0.029 | 0.73 | HIGH | +0.36R (n=247, +0.14..+0.60) |
| dist_wlevel_R | 0.36R | 0.15 | LOW | +0.32R (n=247, +0.08..+0.55) |

- Book reference: 740 past longs, +0.20R.
- Case against: retail_ls_pct90 in LOW third (pct 0.33): past same-side trades there averaged +0.17R (n=172, 95% CI -0.07..+0.45) vs book +0.20R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h HIGH +0.45R (n=247)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
