# X3 signal dossiers — data to 2026-10-22 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## BTC LONG — PW ACC — entry 2026-10-21 18:00 UTC (closed 2026-10-22 01:45, -1.05R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 84634.3 | 83564.4 | 87844 | 1.26% | n/a (long) | above |

| Feature (vs past longs) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d | +7.12% | 0.57 | MID | +0.11R (n=173, -0.16..+0.37) |
| oi_chg_24h ★ | +4.85% | 0.59 | MID | +0.27R (n=173, +0.00..+0.55) |
| retail_ls_pct90 ★ | 0.194 | 0.62 | MID | +0.22R (n=171, -0.04..+0.49) |
| taker_ls_24h | 1.204 | 0.79 | HIGH | +0.33R (n=165, +0.03..+0.61) |
| premium_8h ★ | -0.0522% | 0.09 | LOW | +0.36R (n=244, +0.13..+0.59) |
| dvol_pct365 | 0.213 | 0.34 | MID | +0.21R (n=91, -0.15..+0.60) |
| perp_cvd_4h | 0.042 | 0.60 | MID | +0.04R (n=246, -0.17..+0.27) |
| perp_cvd_24h | 0.051 | 0.91 | HIGH | +0.36R (n=246, +0.14..+0.60) |
| dist_wlevel_R | 2.19R | 0.48 | MID | +0.14R (n=492, -0.01..+0.30) |

- Book reference: 739 past longs, +0.20R.
- Case against: perp_cvd_4h in MID third (pct 0.60): past same-side trades there averaged +0.04R (n=246, 95% CI -0.17..+0.27) vs book +0.20R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_24h HIGH +0.36R (n=246)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
