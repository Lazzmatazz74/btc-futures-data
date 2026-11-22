# X3 signal dossiers — data to 2026-11-22 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## BTC SHORT — PW FSB — entry 2026-11-19 21:30 UTC (closed 2026-11-19 23:00, -1.07R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 61712.8 | 62304 | 59939.2 | 0.96% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -4.40% | 0.20 | LOW | -0.09R (n=164, -0.33..+0.16) |
| oi_chg_24h | +1.19% | 0.55 | MID | +0.02R (n=165, -0.23..+0.29) |
| retail_ls_pct90 | 0.992 | 0.85 | HIGH | +0.36R (n=160, +0.06..+0.64) |
| taker_ls_24h | 1.174 | 0.85 | HIGH | +0.22R (n=150, -0.07..+0.51) |
| premium_8h | -0.0334% | 0.61 | MID | +0.22R (n=193, -0.04..+0.49) |
| dvol_pct365 | 0.715 | 0.76 | HIGH | -0.13R (n=81, -0.48..+0.22) |
| perp_cvd_4h | 0.004 | 0.95 | HIGH | +0.08R (n=195, -0.16..+0.33) |
| perp_cvd_24h | -0.010 | 0.94 | HIGH | +0.14R (n=195, -0.10..+0.40) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=195, -0.02..+0.46) |

- Book reference: 584 past shorts, +0.14R.
- Case against: dvol_pct365 in HIGH third (pct 0.76): past same-side trades there averaged -0.13R (n=81, 95% CI -0.48..+0.22) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: retail_ls_pct90 HIGH +0.36R (n=160)
- Flags: F4 (short, OI falling 7d (G3 skip)), F5 (short, DVOL high in its year)
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## BNB SHORT — PW FSB — entry 2026-11-20 13:30 UTC (closed 2026-11-20 14:00, -1.06R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 565.17 | 570.77 | 548.37 | 0.99% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -4.51% | 0.20 | LOW | -0.09R (n=164, -0.33..+0.17) |
| oi_chg_24h | +0.91% | 0.52 | MID | +0.02R (n=165, -0.24..+0.30) |
| retail_ls_pct90 | 0.821 | 0.44 | MID | +0.15R (n=159, -0.11..+0.44) |
| taker_ls_24h | 1.045 | 0.52 | MID | -0.05R (n=150, -0.31..+0.23) |
| premium_8h | +0.0280% | 0.84 | HIGH | +0.13R (n=194, -0.10..+0.38) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.124 | 0.09 | LOW | +0.35R (n=195, +0.12..+0.60) |
| perp_cvd_24h | -0.048 | 0.47 | MID | +0.07R (n=195, -0.18..+0.33) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=195, -0.04..+0.46) |

- Book reference: 585 past shorts, +0.14R.
- Case against: oi_chg_7d in LOW third (pct 0.20): past same-side trades there averaged -0.09R (n=164, 95% CI -0.33..+0.17) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h LOW +0.35R (n=195)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history

## BTC SHORT — PW ACC — entry 2026-11-20 15:00 UTC (closed 2026-11-20 15:30, +2.91R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 61744 | 62158 | 60502 | 0.67% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -3.89% | 0.22 | LOW | -0.10R (n=165, -0.34..+0.14) |
| oi_chg_24h | +1.09% | 0.54 | MID | +0.01R (n=166, -0.24..+0.27) |
| retail_ls_pct90 | 0.916 | 0.58 | MID | +0.13R (n=159, -0.14..+0.41) |
| taker_ls_24h | 1.128 | 0.76 | HIGH | +0.22R (n=150, -0.06..+0.52) |
| premium_8h | -0.0420% | 0.48 | MID | +0.21R (n=194, -0.04..+0.46) |
| dvol_pct365 | 0.784 | 0.84 | HIGH | -0.13R (n=81, -0.48..+0.26) |
| perp_cvd_4h | -0.047 | 0.66 | MID | -0.03R (n=195, -0.25..+0.22) |
| perp_cvd_24h | -0.003 | 0.97 | HIGH | +0.14R (n=195, -0.10..+0.39) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=195, -0.04..+0.49) |

- Book reference: 586 past shorts, +0.13R.
- Case against: dvol_pct365 in HIGH third (pct 0.84): past same-side trades there averaged -0.13R (n=81, 95% CI -0.48..+0.26) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: taker_ls_24h HIGH +0.22R (n=150)
- Flags: F4 (short, OI falling 7d (G3 skip)), F5 (short, DVOL high in its year)
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## BNB SHORT — PW ACC — entry 2026-11-20 19:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 538.13 | 571.16 | 439.04 | 6.14% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -6.63% | 0.13 | LOW | -0.07R (n=165, -0.31..+0.17) |
| oi_chg_24h | -1.22% | 0.31 | LOW | +0.09R (n=167, -0.17..+0.35) |
| retail_ls_pct90 | 0.725 | 0.30 | LOW | -0.03R (n=162, -0.29..+0.24) |
| taker_ls_24h | 1.135 | 0.78 | HIGH | +0.24R (n=151, -0.04..+0.52) |
| premium_8h | +0.0128% | 0.80 | HIGH | +0.11R (n=194, -0.12..+0.36) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.107 | 0.15 | LOW | +0.35R (n=196, +0.09..+0.61) |
| perp_cvd_24h | -0.076 | 0.13 | LOW | +0.22R (n=196, -0.02..+0.47) |
| dist_wlevel_R | open air | 0.91 | HIGH | +0.22R (n=196, -0.03..+0.48) |

- Book reference: 587 past shorts, +0.14R.
- Case against: oi_chg_7d in LOW third (pct 0.13): past same-side trades there averaged -0.07R (n=165, 95% CI -0.31..+0.17) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h LOW +0.35R (n=196)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history

## ETH SHORT — PW ACC — entry 2026-11-20 19:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1615.85 | 1747.95 | 1219.55 | 8.18% | TAKE (OI up 7d) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +3.42% | 0.64 | MID | +0.10R (n=164, -0.17..+0.37) |
| oi_chg_24h | -1.74% | 0.28 | LOW | +0.09R (n=167, -0.17..+0.35) |
| retail_ls_pct90 | 0.640 | 0.23 | LOW | -0.03R (n=162, -0.28..+0.24) |
| taker_ls_24h | 0.867 | 0.04 | LOW | +0.08R (n=151, -0.19..+0.35) |
| premium_8h | -0.0526% | 0.26 | LOW | +0.11R (n=195, -0.14..+0.36) |
| dvol_pct365 | 0.688 | 0.73 | HIGH | -0.13R (n=81, -0.48..+0.26) |
| perp_cvd_4h | -0.061 | 0.53 | MID | -0.01R (n=195, -0.23..+0.23) |
| perp_cvd_24h | -0.043 | 0.54 | MID | +0.05R (n=195, -0.19..+0.30) |
| dist_wlevel_R | open air | 0.91 | HIGH | +0.22R (n=196, -0.03..+0.48) |

- Book reference: 587 past shorts, +0.14R.
- Case against: dvol_pct365 in HIGH third (pct 0.73): past same-side trades there averaged -0.13R (n=81, 95% CI -0.48..+0.26) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: dist_wlevel_R HIGH +0.22R (n=196)
- Flags: F5 (short, DVOL high in its year)
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## XRP SHORT — PW FSB — entry 2026-11-20 20:45 UTC (closed 2026-11-20 21:45, -1.05R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 0.8911 | 0.9017 | 0.8593 | 1.19% | SKIP (OI down/unknown) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -8.31% | 0.11 | LOW | -0.07R (n=165, -0.31..+0.18) |
| oi_chg_24h | +3.48% | 0.75 | HIGH | +0.33R (n=166, +0.04..+0.62) |
| retail_ls_pct90 | 0.926 | 0.60 | MID | +0.15R (n=160, -0.13..+0.41) |
| taker_ls_24h | 1.102 | 0.68 | HIGH | +0.24R (n=151, -0.04..+0.53) |
| premium_8h | -0.0415% | 0.49 | MID | +0.21R (n=194, -0.04..+0.47) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | 0.001 | 0.95 | HIGH | +0.08R (n=196, -0.17..+0.34) |
| perp_cvd_24h | -0.032 | 0.71 | HIGH | +0.15R (n=196, -0.10..+0.42) |
| dist_wlevel_R | open air | 0.91 | HIGH | +0.22R (n=196, -0.03..+0.48) |

- Book reference: 587 past shorts, +0.14R.
- Case against: oi_chg_7d in LOW third (pct 0.11): past same-side trades there averaged -0.07R (n=165, 95% CI -0.31..+0.18) vs book +0.14R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_24h HIGH +0.33R (n=166)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
