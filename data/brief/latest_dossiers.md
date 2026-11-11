# X3 signal dossiers — data to 2026-11-11 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH SHORT — PW ACC — entry 2026-11-09 01:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2143.28 | 2227.4 | 1890.92 | 3.92% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -3.56% | 0.22 | LOW | -0.13R (n=162, -0.36..+0.13) |
| oi_chg_24h | -3.43% | 0.19 | LOW | +0.10R (n=163, -0.16..+0.35) |
| retail_ls_pct90 | 0.987 | 0.82 | HIGH | +0.35R (n=158, +0.06..+0.64) |
| taker_ls_24h | 0.960 | 0.20 | LOW | +0.05R (n=148, -0.22..+0.33) |
| premium_8h | -0.0454% | 0.40 | MID | +0.17R (n=191, -0.08..+0.42) |
| dvol_pct365 | 0.537 | 0.60 | MID | +0.24R (n=79, -0.16..+0.65) |
| perp_cvd_4h | -0.091 | 0.26 | LOW | +0.31R (n=193, +0.06..+0.56) |
| perp_cvd_24h | -0.070 | 0.18 | LOW | +0.17R (n=193, -0.06..+0.41) |
| dist_wlevel_R | 1.11R | 0.44 | MID | +0.11R (n=192, -0.14..+0.36) |

- Book reference: 577 past shorts, +0.12R.
- Case against: oi_chg_7d in LOW third (pct 0.22): past same-side trades there averaged -0.13R (n=162, 95% CI -0.36..+0.13) vs book +0.12R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: retail_ls_pct90 HIGH +0.35R (n=158)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## XRP SHORT — PW FSB — entry 2026-11-09 07:15 UTC (closed 2026-11-09 08:30, -1.07R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1.0843 | 1.0943 | 1.0543 | 0.92% | TAKE (OI up 7d) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +15.56% | 0.94 | HIGH | +0.45R (n=161, +0.19..+0.75) |
| oi_chg_24h | -4.66% | 0.13 | LOW | +0.10R (n=163, -0.17..+0.34) |
| retail_ls_pct90 | 0.757 | 0.35 | MID | +0.12R (n=157, -0.15..+0.40) |
| taker_ls_24h | 1.456 | 1.00 | HIGH | +0.19R (n=147, -0.10..+0.49) |
| premium_8h | -0.0505% | 0.32 | LOW | +0.11R (n=191, -0.14..+0.37) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.068 | 0.46 | MID | -0.01R (n=192, -0.24..+0.23) |
| perp_cvd_24h | -0.053 | 0.37 | MID | +0.08R (n=192, -0.17..+0.34) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=192, -0.05..+0.46) |

- Book reference: 577 past shorts, +0.12R.
- Case against: perp_cvd_4h in MID third (pct 0.46): past same-side trades there averaged -0.01R (n=192, 95% CI -0.24..+0.23) vs book +0.12R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_7d HIGH +0.45R (n=161)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
