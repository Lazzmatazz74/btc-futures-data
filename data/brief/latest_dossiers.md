# X3 signal dossiers — data to 2026-10-14 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## XRP SHORT — PW FSB — entry 2026-10-07 13:45 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1.4316 | 1.477 | 1.2954 | 3.17% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +2.29% | 0.56 | MID | +0.17R (n=157, -0.11..+0.48) |
| oi_chg_24h | +1.07% | 0.53 | MID | -0.00R (n=158, -0.26..+0.28) |
| retail_ls_pct90 | 0.080 | 0.00 | LOW | -0.04R (n=154, -0.29..+0.22) |
| taker_ls_24h | 1.007 | 0.36 | MID | -0.02R (n=143, -0.28..+0.30) |
| premium_8h | -0.0560% | 0.19 | LOW | +0.12R (n=188, -0.13..+0.37) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.064 | 0.50 | MID | -0.00R (n=188, -0.25..+0.24) |
| perp_cvd_24h | -0.066 | 0.21 | LOW | +0.21R (n=188, -0.03..+0.47) |
| dist_wlevel_R | 0.64R | 0.32 | LOW | +0.06R (n=188, -0.17..+0.31) |

- Book reference: 564 past shorts, +0.13R.
- Case against: retail_ls_pct90 in LOW third (pct 0.00): past same-side trades there averaged -0.04R (n=154, 95% CI -0.29..+0.22) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_24h LOW +0.21R (n=188)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
