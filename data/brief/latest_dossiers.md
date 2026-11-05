# X3 signal dossiers — data to 2026-11-05 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## BNB SHORT — PW ACC — entry 2026-10-30 00:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 697.96 | 745.53 | 555.25 | 6.82% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +8.77% | 0.85 | HIGH | +0.43R (n=160, +0.15..+0.73) |
| oi_chg_24h | +7.16% | 0.92 | HIGH | +0.34R (n=161, +0.06..+0.65) |
| retail_ls_pct90 | 1.000 | 0.95 | HIGH | +0.36R (n=156, +0.08..+0.65) |
| taker_ls_24h | 1.330 | 0.97 | HIGH | +0.19R (n=146, -0.10..+0.47) |
| premium_8h | n/a | — | — | n/a |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.006 | 0.92 | HIGH | +0.08R (n=191, -0.16..+0.33) |
| perp_cvd_24h | -0.013 | 0.91 | HIGH | +0.12R (n=191, -0.12..+0.36) |
| dist_wlevel_R | 0.48R | 0.26 | LOW | +0.06R (n=191, -0.17..+0.29) |

- Book reference: 572 past shorts, +0.13R.
- Case against: dist_wlevel_R in LOW third (pct 0.26): past same-side trades there averaged +0.06R (n=191, 95% CI -0.17..+0.29) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_7d HIGH +0.43R (n=160)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); premium missing; no DVOL for this coin; no Hyperliquid snapshot history

## ETH LONG — PW FSB — entry 2026-11-04 15:15 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2387.76 | 2344.63 | 2517.15 | 1.81% | n/a (long) | above |

| Feature (vs past longs) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d | -1.05% | 0.15 | LOW | +0.30R (n=174, +0.04..+0.60) |
| oi_chg_24h ★ | +0.39% | 0.20 | LOW | +0.35R (n=174, +0.07..+0.63) |
| retail_ls_pct90 ★ | 0.053 | 0.33 | LOW | +0.17R (n=172, -0.10..+0.43) |
| taker_ls_24h | 1.308 | 0.92 | HIGH | +0.33R (n=165, +0.04..+0.63) |
| premium_8h ★ | -0.0273% | 0.39 | MID | +0.28R (n=244, +0.05..+0.52) |
| dvol_pct365 | 0.227 | 0.35 | MID | +0.21R (n=91, -0.13..+0.58) |
| perp_cvd_4h | 0.072 | 0.80 | HIGH | +0.45R (n=247, +0.22..+0.68) |
| perp_cvd_24h | 0.029 | 0.73 | HIGH | +0.36R (n=247, +0.14..+0.58) |
| dist_wlevel_R | 0.36R | 0.15 | LOW | +0.32R (n=247, +0.09..+0.56) |

- Book reference: 740 past longs, +0.20R.
- Case against: retail_ls_pct90 in LOW third (pct 0.33): past same-side trades there averaged +0.17R (n=172, 95% CI -0.10..+0.43) vs book +0.20R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h HIGH +0.45R (n=247)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
