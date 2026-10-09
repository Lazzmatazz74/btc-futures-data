# X3 signal dossiers — data to 2026-10-09 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH SHORT — PW ACC — entry 2026-10-07 06:00 UTC (closed 2026-10-08 15:30, +2.96R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2619.48 | 2659.53 | 2499.33 | 1.53% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +5.55% | 0.74 | HIGH | +0.42R (n=157, +0.15..+0.71) |
| oi_chg_24h | +4.91% | 0.83 | HIGH | +0.33R (n=159, +0.05..+0.63) |
| retail_ls_pct90 | 0.993 | 0.87 | HIGH | +0.36R (n=153, +0.08..+0.67) |
| taker_ls_24h | 0.903 | 0.09 | LOW | +0.03R (n=143, -0.24..+0.33) |
| premium_8h | -0.0582% | 0.17 | LOW | +0.12R (n=188, -0.13..+0.37) |
| dvol_pct365 | 0.008 | 0.03 | LOW | +0.35R (n=77, -0.05..+0.74) |
| perp_cvd_4h | -0.033 | 0.76 | HIGH | +0.05R (n=188, -0.18..+0.30) |
| perp_cvd_24h | -0.047 | 0.47 | MID | +0.07R (n=188, -0.18..+0.33) |
| dist_wlevel_R | 1.33R | 0.48 | MID | +0.12R (n=188, -0.13..+0.38) |

- Book reference: 564 past shorts, +0.13R.
- Case against: taker_ls_24h in LOW third (pct 0.09): past same-side trades there averaged +0.03R (n=143, 95% CI -0.24..+0.33) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_7d HIGH +0.42R (n=157)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## XRP SHORT — PW FSB — entry 2026-10-07 13:45 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1.4316 | 1.477 | 1.2954 | 3.17% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +2.29% | 0.56 | MID | +0.17R (n=157, -0.11..+0.45) |
| oi_chg_24h | +1.07% | 0.53 | MID | -0.00R (n=158, -0.26..+0.28) |
| retail_ls_pct90 | 0.080 | 0.00 | LOW | -0.04R (n=154, -0.30..+0.22) |
| taker_ls_24h | 1.007 | 0.36 | MID | -0.02R (n=143, -0.29..+0.25) |
| premium_8h | -0.0560% | 0.19 | LOW | +0.12R (n=188, -0.14..+0.37) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.064 | 0.50 | MID | -0.00R (n=188, -0.24..+0.26) |
| perp_cvd_24h | -0.066 | 0.21 | LOW | +0.21R (n=188, -0.04..+0.45) |
| dist_wlevel_R | 0.64R | 0.32 | LOW | +0.06R (n=188, -0.17..+0.30) |

- Book reference: 564 past shorts, +0.13R.
- Case against: retail_ls_pct90 in LOW third (pct 0.00): past same-side trades there averaged -0.04R (n=154, 95% CI -0.30..+0.22) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_24h LOW +0.21R (n=188)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history

## BTC SHORT — PW FSB — entry 2026-10-08 13:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 82150 | 83245 | 78865 | 1.33% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +1.53% | 0.51 | MID | +0.17R (n=157, -0.11..+0.45) |
| oi_chg_24h | +0.20% | 0.44 | MID | -0.00R (n=158, -0.26..+0.28) |
| retail_ls_pct90 | 0.916 | 0.58 | MID | +0.12R (n=153, -0.14..+0.40) |
| taker_ls_24h | 1.186 | 0.88 | HIGH | +0.22R (n=143, -0.08..+0.52) |
| premium_8h | -0.0531% | 0.25 | LOW | +0.12R (n=188, -0.12..+0.38) |
| dvol_pct365 | 0.294 | 0.38 | MID | +0.32R (n=77, -0.09..+0.75) |
| perp_cvd_4h | -0.075 | 0.40 | MID | -0.00R (n=188, -0.24..+0.24) |
| perp_cvd_24h | -0.053 | 0.38 | MID | +0.07R (n=188, -0.16..+0.32) |
| dist_wlevel_R | 0.20R | 0.13 | LOW | +0.06R (n=188, -0.17..+0.29) |

- Book reference: 564 past shorts, +0.13R.
- Case against: perp_cvd_4h in MID third (pct 0.40): past same-side trades there averaged -0.00R (n=188, 95% CI -0.24..+0.24) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: dvol_pct365 MID +0.32R (n=77)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## BNB SHORT — PW ACC — entry 2026-10-08 19:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 727.12 | 757.68 | 635.44 | 4.20% | SKIP (OI down/unknown) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -2.44% | 0.27 | LOW | -0.10R (n=158, -0.34..+0.14) |
| oi_chg_24h | -2.47% | 0.22 | LOW | +0.10R (n=159, -0.16..+0.37) |
| retail_ls_pct90 | 0.611 | 0.21 | LOW | -0.04R (n=154, -0.29..+0.23) |
| taker_ls_24h | 0.930 | 0.14 | LOW | +0.05R (n=144, -0.22..+0.32) |
| premium_8h | +0.0050% | 0.78 | HIGH | +0.11R (n=188, -0.14..+0.36) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.088 | 0.28 | LOW | +0.36R (n=189, +0.11..+0.61) |
| perp_cvd_24h | -0.083 | 0.09 | LOW | +0.23R (n=189, -0.01..+0.49) |
| dist_wlevel_R | 0.24R | 0.15 | LOW | +0.08R (n=189, -0.16..+0.32) |

- Book reference: 565 past shorts, +0.14R.
- Case against: oi_chg_7d in LOW third (pct 0.27): past same-side trades there averaged -0.10R (n=158, 95% CI -0.34..+0.14) vs book +0.14R
- Case against that: that CI excludes the book mean; best third: perp_cvd_4h LOW +0.36R (n=189)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
