# Full-grid consumed-history diagnostic

Computed 25 October 2026 from the second batch's saved stressed daily results only. No reserved ES2024 or HFD prices/signals/P&L were read. This assessment does not provide fresh holdout evidence.

## Search-wide max-statistic result

All 12,960 supplied configuration columns were retained, including inactive columns. The diagnostic resampled the same circular five-session blocks across all columns, centered each candidate's daily P&L at zero, studentized with a Bartlett HAC standard error, and compared observed t statistics with bootstrap maximum t statistics. There were1,000 resamples, seed20261025, and two OpenBLAS threads.

| Case | Sessions | Candidates | Best observed t | Best candidate | Global/max-adjusted p |
|---|---:|---:|---:|---|---:|
| Combined assets on shared dates | 325 | 12,960 | 2.414 | NQ_01459 | 1.000 |
| Nasdaq full consumed history | 542 | 6,480 | 2.256 | NQ_04004 | 0.998 |
| S&P full consumed history | 326 | 6,480 | 2.505 | ES_01596 | 0.987 |

This diagnostic does not find evidence that the best positive mean is unusual compared with maxima produced by the searched alternatives under its centered bootstrap. It is an exploratory max-t calculation, not a full White Reality Check or Hansen SPA test. Approximate stationarity, the selected block length and finite-sample studentization matter. It does not correct human research iteration or establish absence of any possible market edge.

Complete observed t statistics and familywise-adjusted p-values are in `searchwide_max_t.json` and the three `*_searchwide_statistics.csv` files.

## Proposed strict static screen

The specified strict full-history screen required stressed PF>=1.20 and at least150 trades before additional stability tests. **No candidate in either asset met those first two conditions together.** Therefore none passed the complete screen.

Additional reported diagnostics were at least two positive chronological thirds, strictly more than half the observed calendar quarters positive, at least four scored one-step parameter neighbors, at least60% positive neighbors, and a positive95% block-bootstrap daily-mean lower bound. The CI stage did not run for strict survivors because there were none.

Do not lower these gates after seeing the empty result and describe that as confirmation. Weaker results can be recorded as new hypotheses, explicitly labeled, before testing reserved data.

## Research hypotheses only

| Candidate | Mechanism | Trades | Stressed net | PF | Positive thirds | Positive quarters | Positive neighbors | Median neighbor net |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| NQ_00755 | Failed opening range | 100 | $893.76 | 1.348 | 3/3 | 7/10 | 3/8 | −$301.23 |
| NQ_06009 | Bollinger reversion | 116 | $721.50 | 1.256 | 2/3 | 7/10 | 4/8 | −$152.81 |
| NQ_05377 | VWAP reversion | 282 | $858.82 | 1.196 | 2/3 | 5/10 | 5/9 | $239.92 |
| ES_02711 | Failed Donchian breakout | 154 | $396.60 | 1.160 | 2/3 | 4/7 | 1/8 | −$436.29 |

The highest positive sample PF results tend to have small trade counts, while higher-count results have weak cost-stressed edges. Neighbor results do not show a strong broad plateau. The previously failed rolling-selection procedure remains failed; these static, full-sample summaries do not replace its result.

`strict_broad_history_screen.json` and each asset's `full_consumed_history_stability.csv` retain all diagnostics. Reproduce with `OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python searchwide_diagnostic.py`.
