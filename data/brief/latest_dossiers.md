# X3 signal dossiers — data to 2026-11-07 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## ETH LONG — PW FSB — entry 2026-11-04 15:15 UTC (closed 2026-11-05 15:00, -1.03R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2387.76 | 2344.63 | 2517.15 | 1.81% | n/a (long) | above |

| Feature (vs past longs) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d | -1.05% | 0.15 | LOW | +0.30R (n=174, +0.04..+0.57) |
| oi_chg_24h ★ | +0.39% | 0.20 | LOW | +0.35R (n=174, +0.07..+0.61) |
| retail_ls_pct90 ★ | 0.053 | 0.33 | LOW | +0.17R (n=172, -0.07..+0.45) |
| taker_ls_24h | 1.308 | 0.92 | HIGH | +0.33R (n=165, +0.05..+0.62) |
| premium_8h ★ | -0.0273% | 0.39 | MID | +0.28R (n=244, +0.04..+0.51) |
| dvol_pct365 | 0.227 | 0.35 | MID | +0.21R (n=91, -0.14..+0.60) |
| perp_cvd_4h | 0.072 | 0.80 | HIGH | +0.45R (n=247, +0.22..+0.68) |
| perp_cvd_24h | 0.029 | 0.73 | HIGH | +0.36R (n=247, +0.14..+0.60) |
| dist_wlevel_R | 0.36R | 0.15 | LOW | +0.32R (n=247, +0.08..+0.55) |

- Book reference: 740 past longs, +0.20R.
- Case against: retail_ls_pct90 in LOW third (pct 0.33): past same-side trades there averaged +0.17R (n=172, 95% CI -0.07..+0.45) vs book +0.20R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h HIGH +0.45R (n=247)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no Hyperliquid snapshot history

## XRP SHORT — PW ACC — entry 2026-11-06 09:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 1.1874 | 1.2044 | 1.1364 | 1.43% | TAKE (OI up 7d) | below |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +23.95% | 0.98 | HIGH | +0.43R (n=161, +0.15..+0.72) |
| oi_chg_24h | -1.99% | 0.26 | LOW | +0.07R (n=163, -0.19..+0.33) |
| retail_ls_pct90 | 0.889 | 0.54 | MID | +0.12R (n=157, -0.14..+0.41) |
| taker_ls_24h | 0.995 | 0.32 | LOW | +0.03R (n=147, -0.24..+0.31) |
| premium_8h | -0.0286% | 0.64 | MID | +0.16R (n=190, -0.11..+0.41) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.044 | 0.69 | HIGH | +0.08R (n=192, -0.15..+0.34) |
| perp_cvd_24h | -0.028 | 0.77 | HIGH | +0.12R (n=192, -0.14..+0.36) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=192, -0.04..+0.47) |

- Book reference: 576 past shorts, +0.12R.
- Case against: taker_ls_24h in LOW third (pct 0.32): past same-side trades there averaged +0.03R (n=147, 95% CI -0.24..+0.31) vs book +0.12R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_7d HIGH +0.43R (n=161)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); no DVOL for this coin; no Hyperliquid snapshot history
