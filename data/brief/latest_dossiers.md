# X3 signal dossiers — data to 2026-11-20 00:00 UTC

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
