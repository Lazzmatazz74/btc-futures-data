# X3 signal dossiers — data to 2026-10-15 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH SHORT — PW FSB — entry 2026-10-14 21:15 UTC (closed 2026-10-14 21:45, -1.07R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2403.82 | 2424.88 | 2340.64 | 0.88% | SKIP (OI down/unknown) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -1.27% | 0.34 | MID | +0.15R (n=158, -0.13..+0.42) |
| oi_chg_24h | +3.65% | 0.76 | HIGH | +0.35R (n=160, +0.07..+0.65) |
| retail_ls_pct90 | 0.979 | 0.77 | HIGH | +0.37R (n=155, +0.09..+0.68) |
| taker_ls_24h | 1.309 | 0.96 | HIGH | +0.21R (n=144, -0.06..+0.50) |
| premium_8h | -0.0436% | 0.45 | MID | +0.16R (n=189, -0.09..+0.43) |
| dvol_pct365 | 0.262 | 0.37 | MID | +0.27R (n=77, -0.13..+0.68) |
| perp_cvd_4h | -0.079 | 0.35 | MID | -0.02R (n=189, -0.24..+0.23) |
| perp_cvd_24h | -0.061 | 0.27 | LOW | +0.21R (n=190, -0.04..+0.46) |
| dist_wlevel_R | 0.02R | 0.02 | LOW | +0.06R (n=190, -0.17..+0.30) |

- Book reference: 568 past shorts, +0.13R.
- Case against: perp_cvd_4h in MID third (pct 0.35): past same-side trades there averaged -0.02R (n=189, 95% CI -0.24..+0.23) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: retail_ls_pct90 HIGH +0.37R (n=155)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
