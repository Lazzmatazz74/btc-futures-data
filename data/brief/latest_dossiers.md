# X3 signal dossiers — data to 2026-11-04 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## BNB SHORT — PW ACC — entry 2026-10-30 00:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 697.96 | 745.53 | 555.25 | 6.82% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +8.77% | 0.85 | HIGH | +0.43R (n=160, +0.15..+0.73) |
| oi_chg_24h | +7.16% | 0.92 | HIGH | +0.34R (n=161, +0.06..+0.65) |
| retail_ls_pct90 | 1.000 | 0.95 | HIGH | +0.36R (n=156, +0.08..+0.65) |
| taker_ls_24h | 1.330 | 0.97 | HIGH | +0.19R (n=146, -0.10..+0.47) |
| premium_8h | n/a | — | — | n/a |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | -0.006 | 0.92 | HIGH | +0.08R (n=191, -0.16..+0.33) |
| perp_cvd_24h | -0.013 | 0.91 | HIGH | +0.12R (n=191, -0.12..+0.36) |
| dist_wlevel_R | 0.48R | 0.26 | LOW | +0.06R (n=191, -0.17..+0.29) |

- Book reference: 572 past shorts, +0.13R.
- Case against: dist_wlevel_R in LOW third (pct 0.26): past same-side trades there averaged +0.06R (n=191, 95% CI -0.17..+0.29) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: oi_chg_7d HIGH +0.43R (n=160)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); premium missing; no DVOL for this coin; no Hyperliquid snapshot history

## BTC SHORT — PW ACC — entry 2026-10-30 00:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 77962.6 | 80814.8 | 69406 | 3.66% | SKIP (OI down/unknown) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -3.14% | 0.24 | LOW | -0.12R (n=160, -0.35..+0.14) |
| oi_chg_24h | +0.15% | 0.43 | MID | -0.00R (n=161, -0.26..+0.27) |
| retail_ls_pct90 | 0.997 | 0.92 | HIGH | +0.36R (n=156, +0.08..+0.67) |
| taker_ls_24h | 0.829 | 0.02 | LOW | +0.04R (n=146, -0.23..+0.32) |
| premium_8h | n/a | — | — | n/a |
| dvol_pct365 | 0.520 | 0.58 | MID | +0.25R (n=78, -0.15..+0.69) |
| perp_cvd_4h | -0.082 | 0.33 | LOW | +0.32R (n=191, +0.06..+0.58) |
| perp_cvd_24h | -0.039 | 0.60 | MID | +0.08R (n=190, -0.17..+0.33) |
| dist_wlevel_R | 0.63R | 0.31 | LOW | +0.06R (n=191, -0.17..+0.31) |

- Book reference: 572 past shorts, +0.13R.
- Case against: oi_chg_7d in LOW third (pct 0.24): past same-side trades there averaged -0.12R (n=160, 95% CI -0.35..+0.14) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: retail_ls_pct90 HIGH +0.36R (n=156)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: funding after 2026-08-31 not settled (counted 0); premium missing; no Hyperliquid snapshot history

## ETH SHORT — PW ACC — entry 2026-10-30 00:00 UTC (OPEN)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 2252.34 | 2335.92 | 2001.6 | 3.71% | TAKE (OI up 7d) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | +3.05% | 0.61 | MID | +0.14R (n=159, -0.13..+0.42) |
| oi_chg_24h | -1.00% | 0.34 | MID | -0.00R (n=161, -0.27..+0.26) |
| retail_ls_pct90 | 0.933 | 0.62 | MID | +0.10R (n=156, -0.16..+0.37) |
| taker_ls_24h | 0.896 | 0.08 | LOW | +0.04R (n=146, -0.24..+0.33) |
| premium_8h | n/a | — | — | n/a |
| dvol_pct365 | 0.517 | 0.58 | MID | +0.25R (n=78, -0.15..+0.64) |
| perp_cvd_4h | -0.095 | 0.23 | LOW | +0.32R (n=191, +0.08..+0.60) |
| perp_cvd_24h | -0.067 | 0.20 | LOW | +0.19R (n=191, -0.06..+0.44) |
| dist_wlevel_R | open air | 0.92 | HIGH | +0.21R (n=191, -0.04..+0.48) |

- Book reference: 572 past shorts, +0.13R.
- Case against: oi_chg_24h in MID third (pct 0.34): past same-side trades there averaged -0.00R (n=161, 95% CI -0.27..+0.26) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_4h LOW +0.32R (n=191)
- Flags: none
- Data gaps: funding after 2026-08-31 not settled (counted 0); premium missing; no Hyperliquid snapshot history
