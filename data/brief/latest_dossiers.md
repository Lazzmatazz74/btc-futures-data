# X3 signal dossiers — data to 2026-09-26 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## BTC LONG — PW ACC — entry 2026-09-21 12:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 84849.9 | 81697.2 | 94308 | 3.72% | n/a (long) | above |

| Feature (vs past longs) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d | +3.95% | 0.41 | MID | +0.14R (n=171, -0.13..+0.40) |
| oi_chg_24h ★ | +1.14% | 0.24 | LOW | +0.36R (n=172, +0.07..+0.63) |
| retail_ls_pct90 ★ | 0.017 | 0.20 | LOW | +0.18R (n=170, -0.07..+0.46) |
| taker_ls_24h | 1.100 | 0.50 | MID | +0.16R (n=163, -0.11..+0.43) |
| premium_8h ★ | -0.0377% | 0.28 | LOW | +0.36R (n=243, +0.12..+0.60) |
| dvol_pct365 | 0.198 | 0.33 | LOW | +0.34R (n=91, -0.03..+0.74) |
| perp_cvd_4h | 0.115 | 0.95 | HIGH | +0.46R (n=245, +0.23..+0.70) |
| perp_cvd_24h | 0.065 | 0.96 | HIGH | +0.37R (n=245, +0.14..+0.61) |
| dist_wlevel_R | open air | 0.83 | MID | +0.15R (n=489, -0.02..+0.31) |

- Book reference: 734 past longs, +0.21R.
- Case against: oi_chg_7d in MID third (pct 0.41): past same-side trades there averaged +0.14R (n=171, 95% CI -0.13..+0.40) vs book +0.21R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h HIGH +0.46R (n=245)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history
