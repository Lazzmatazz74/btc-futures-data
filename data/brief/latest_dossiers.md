# X3 signal dossiers — data to 2026-10-02 00:00 UTC

Information only — no call. The flags have NOT passed their test (Workstream B: primary p = 0.92); they must never block a trade. Live verdict after 60 live signals.

## BNB SHORT — PW FSB — entry 2026-09-29 01:45 UTC (closed 2026-09-30 12:45, -1.02R)

| Entry | Stop | Target (3R) | Stop % | G3 | 200-DMA |
|---|---|---|---|---|---|
| 756.11 | 773.83 | 702.95 | 2.34% | SKIP (OI down/unknown) | above |

| Feature (vs past shorts) | Value | Pct | Third | Past R in that third (n, 95% CI) |
|---|---|---|---|---|
| oi_chg_7d ★ | -7.93% | 0.11 | LOW | -0.10R (n=157, -0.34..+0.16) |
| oi_chg_24h | -1.56% | 0.29 | LOW | +0.10R (n=159, -0.16..+0.37) |
| retail_ls_pct90 | 0.224 | 0.04 | LOW | -0.04R (n=153, -0.30..+0.24) |
| taker_ls_24h | 1.087 | 0.66 | MID | -0.01R (n=142, -0.27..+0.29) |
| premium_8h | +0.0371% | 0.85 | HIGH | +0.13R (n=188, -0.12..+0.37) |
| dvol_pct365 | n/a | — | — | n/a |
| perp_cvd_4h | 0.026 | 0.99 | HIGH | +0.08R (n=188, -0.16..+0.33) |
| perp_cvd_24h | -0.071 | 0.16 | LOW | +0.23R (n=188, -0.01..+0.49) |
| dist_wlevel_R | 1.63R | 0.54 | MID | +0.12R (n=187, -0.13..+0.39) |

- Book reference: 563 past shorts, +0.13R.
- Case against: oi_chg_7d in LOW third (pct 0.11): past same-side trades there averaged -0.10R (n=157, 95% CI -0.34..+0.16) vs book +0.13R
- Case against that: that CI includes the book mean -> not distinguishable from normal; best third: perp_cvd_24h LOW +0.23R (n=188)
- Flags: F4 (short, OI falling 7d (G3 skip))
- Data gaps: no DVOL for this coin; no Hyperliquid snapshot history
