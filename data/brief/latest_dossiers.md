# X3 signal dossiers — data to 2026-10-18 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH SHORT — PW ACC — entry 2026-10-15 06:00 UTC (closed 2026-10-15 15:15, -1.02R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2348.39 | 2417.45 | 2141.21 | 2.94% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +0.18% | 0.41 | MID | +0.14R (n=158, -0.13..+0.43) |
| oi_chg_24h | +4.45% | 0.81 | HIGH | +0.35R (n=160, +0.06..+0.65) |
| retail_ls_pct90 | 0.995 | 0.89 | HIGH | +0.37R (n=155, +0.09..+0.68) |
| taker_ls_24h | 1.009 | 0.37 | MID | -0.01R (n=144, -0.27..+0.27) |
| premium_8h | -0.0512% | 0.30 | LOW | +0.14R (n=190, -0.11..+0.39) |
| dvol_pct365 | 0.275 | 0.38 | MID | +0.25R (n=78, -0.16..+0.68) |
| perp_cvd_4h | -0.120 | 0.10 | LOW | +0.35R (n=190, +0.09..+0.60) |
| perp_cvd_24h | -0.074 | 0.14 | LOW | +0.19R (n=190, -0.05..+0.44) |
| dist_wlevel_R | 6.90R | 0.81 | HIGH | +0.22R (n=190, -0.03..+0.48) |

- Book reference: 569 past shorts, +0.13R.
- Case against: taker_ls_24h in MID third (pct 0.37): past same-side trades there averaged -0.01R (n=144, 95% CI -0.27..+0.27) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: retail_ls_pct90 HIGH +0.37R (n=155)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## BTC SHORT — PW FSB — entry 2026-10-15 13:30 UTC (closed 2026-10-15 15:00, -1.03R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 80188 | 81775.1 | 75426.7 | 1.98% | SKIP (OI down/unknown) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -4.89% | 0.19 | LOW | -0.11R (n=159, -0.35..+0.15) |
| oi_chg_24h | +1.14% | 0.54 | MID | +0.00R (n=160, -0.25..+0.29) |
| retail_ls_pct90 | 0.860 | 0.50 | MID | +0.11R (n=155, -0.15..+0.40) |
| taker_ls_24h | 1.247 | 0.93 | HIGH | +0.20R (n=145, -0.07..+0.51) |
| premium_8h | -0.0480% | 0.35 | MID | +0.14R (n=189, -0.11..+0.40) |
| dvol_pct365 | 0.383 | 0.47 | MID | +0.25R (n=78, -0.14..+0.65) |
| perp_cvd_4h | -0.085 | 0.30 | LOW | +0.35R (n=190, +0.10..+0.61) |
| perp_cvd_24h | -0.050 | 0.43 | MID | +0.10R (n=189, -0.14..+0.34) |
| dist_wlevel_R | 0.40R | 0.23 | LOW | +0.06R (n=190, -0.17..+0.31) |

- Book reference: 569 past shorts, +0.13R.
- Case against: oi_chg_7d in LOW third (pct 0.19): past same-side trades there averaged -0.11R (n=159, 95% CI -0.35..+0.15) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h LOW +0.35R (n=190)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
