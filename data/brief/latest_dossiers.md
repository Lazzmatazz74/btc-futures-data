# X3 signal dossiers — data to 2026-10-26 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## XRP SHORT — PW FSB — entry 2026-10-24 15:45 UTC (closed 2026-10-24 16:00, -1.07R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1.2539 | 1.2656 | 1.2188 | 0.93% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +0.36% | 0.42 | MID | +0.14R (n=159, -0.13..+0.41) |
| oi_chg_24h | -0.57% | 0.37 | MID | -0.00R (n=161, -0.26..+0.27) |
| retail_ls_pct90 | 0.770 | 0.36 | MID | +0.11R (n=155, -0.15..+0.39) |
| taker_ls_24h | 1.207 | 0.89 | HIGH | +0.20R (n=145, -0.10..+0.48) |
| premium_8h | -0.0507% | 0.31 | LOW | +0.13R (n=191, -0.12..+0.39) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.016 | 0.87 | HIGH | +0.08R (n=190, -0.17..+0.33) |
| perp_cvd_24h | -0.043 | 0.54 | MID | +0.10R (n=190, -0.15..+0.36) |
| dist_wlevel_R | 0.70R | 0.34 | MID | +0.11R (n=190, -0.15..+0.37) |

- Book reference: 571 past shorts, +0.13R.
- Case against: oi_chg_24h in MID third (pct 0.37): past same-side trades there averaged -0.00R (n=161, 95% CI -0.26..+0.27) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: taker_ls_24h HIGH +0.20R (n=145)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
