# X3 signal dossiers — data to 2026-11-08 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## XRP SHORT — PW ACC — entry 2026-11-06 09:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1.1874 | 1.2044 | 1.1364 | 1.43% | TAKE (OI up 7d) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +23.95% | 0.98 | HIGH | +0.43R (n=161, +0.14..+0.72) |
| oi_chg_24h | -1.99% | 0.26 | LOW | +0.07R (n=163, -0.18..+0.34) |
| retail_ls_pct90 | 0.889 | 0.54 | MID | +0.12R (n=157, -0.15..+0.39) |
| taker_ls_24h | 0.995 | 0.32 | LOW | +0.03R (n=147, -0.24..+0.32) |
| premium_8h | -0.0286% | 0.64 | MID | +0.16R (n=190, -0.11..+0.41) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.044 | 0.69 | HIGH | +0.08R (n=192, -0.17..+0.32) |
| perp_cvd_24h | -0.028 | 0.77 | HIGH | +0.12R (n=192, -0.12..+0.38) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=192, -0.03..+0.46) |

- Book reference: 576 past shorts, +0.12R.
- Case against: taker_ls_24h in LOW third (pct 0.32): past same-side trades there averaged +0.03R (n=147, 95% CI -0.24..+0.32) vs book +0.12R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_7d HIGH +0.43R (n=161)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
