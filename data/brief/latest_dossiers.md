# X3 signal dossiers — data to 2026-11-18 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH SHORT — SW ACC — entry 2026-11-15 00:00 UTC (closed 2026-11-15 09:15, -1.02R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1768.36 | 1838.89 | 1556.77 | 3.99% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -1.46% | 0.33 | LOW | -0.08R (n=163, -0.32..+0.19) |
| oi_chg_24h | -0.26% | 0.41 | MID | +0.03R (n=164, -0.23..+0.30) |
| retail_ls_pct90 | 0.683 | 0.27 | LOW | -0.02R (n=161, -0.28..+0.24) |
| taker_ls_24h | 1.121 | 0.74 | HIGH | +0.23R (n=149, -0.05..+0.52) |
| premium_8h | -0.0593% | 0.14 | LOW | +0.12R (n=193, -0.13..+0.36) |
| dvol_pct365 | 0.653 | 0.70 | HIGH | -0.07R (n=80, -0.43..+0.32) |
| perp_cvd_4h | -0.082 | 0.34 | MID | -0.02R (n=194, -0.26..+0.22) |
| perp_cvd_24h | -0.056 | 0.34 | MID | +0.07R (n=194, -0.17..+0.33) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=194, -0.04..+0.47) |

- Book reference: 582 past shorts, +0.14R.
- Case against: oi_chg_7d in LOW third (pct 0.33): past same-side trades there averaged -0.08R (n=163, 95% CI -0.32..+0.19) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: taker_ls_24h HIGH +0.23R (n=149)
- Flags: F4 (short, OI falling 7d (G3 skip)), F5 (short, DVOL high in its year)
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## BTC SHORT — SW FSB — entry 2026-11-15 01:45 UTC (closed 2026-11-15 02:15, -1.07R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 62451.9 | 63030.9 | 60714.9 | 0.93% | TAKE (OI up 7d) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +1.87% | 0.53 | MID | +0.13R (n=163, -0.14..+0.39) |
| oi_chg_24h | -0.19% | 0.41 | MID | +0.03R (n=164, -0.24..+0.30) |
| retail_ls_pct90 | 0.967 | 0.71 | HIGH | +0.37R (n=159, +0.08..+0.66) |
| taker_ls_24h | 1.054 | 0.55 | MID | -0.04R (n=149, -0.30..+0.23) |
| premium_8h | -0.0540% | 0.24 | LOW | +0.12R (n=193, -0.13..+0.37) |
| dvol_pct365 | 0.808 | 0.85 | HIGH | -0.07R (n=80, -0.43..+0.29) |
| perp_cvd_4h | -0.023 | 0.83 | HIGH | +0.09R (n=194, -0.15..+0.33) |
| perp_cvd_24h | -0.046 | 0.50 | MID | +0.07R (n=194, -0.17..+0.32) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=194, -0.04..+0.46) |

- Book reference: 582 past shorts, +0.14R.
- Case against: dvol_pct365 in HIGH third (pct 0.85): past same-side trades there averaged -0.07R (n=80, 95% CI -0.43..+0.29) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: retail_ls_pct90 HIGH +0.37R (n=159)
- Flags: F5 (short, DVOL high in its year)
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
