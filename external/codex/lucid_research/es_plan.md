# ES/MES exploratory branch — registered before performance testing

Registered 2026-10-25. This is a new asset with a shorter development history than the NQ branches and must not be interpreted as an independent long-history confirmation of a selected NQ result.

## Data and split

Actual contributed ES unadjusted front-month minute OHLCV: `/workspace/market_data/ES_1min_stitched.csv`. Source/provenance/audit: `/workspace/market_data/DATA_PROVENANCE.md`. Price feed is ES, strategy PNL is priced as MES ($5/point), so micro fills must be reproduced separately before deployment.

- Development: New York session dates 2025-06-20 through 2025-09-30.
- Validation: 2025-10-01 through 2025-12-31.
- Final holdout: 2026-01-01 onward, left untouched by this branch task. No strategy performance, signals or trade results from 2026 may be inspected during search and freeze.
- Canonical `engine.prepare_data`: complete390-minute 09:30–15:59 ET sessions only; session-reset features; holidays/partial sessions excluded without filling.

## Fixed search

Exactly256 configurations from `higher_tf_study.configs()`, preserving family and all existing timeframes, structural fractions, ATR multipliers, targets and windows. Change only minimum stop from5 to1 ES point and maximum stop from100 to20 ES points; tick remains0.25. Rename to E001…E256 and retain source H identifier.

Four families: opening-range breakout, failed breakout, VWAP reversion and EMA pullback. Completed5/15-minute signals and next-minute-open fills. Maximum one trade per day for each configuration. Fixed2MES for every configuration; do not optimize quantity.

## MES PNL and costs

Engine remains unchanged. Its point trade/stop fills and chronology are reused. Convert one-contract trade output:

- `pnl_usd = pnl_points*5 - 1.24`.
- `mae_usd = (original_mae_usd+1.24)*2.5-1.24`.
- `mfe_usd = (original_mfe_usd+1.24)*2.5-1.24`.

Dollar metrics multiply one-MES values by2. Average R divides one-MES PNL by stop_points*5. Base slippage1tick per side; stress2ticks per side; commission$1.24 per MES round trip for both. Costs are assumptions requiring platform confirmation. Stop-first ambiguous bars, adverse gap fills, no overnight positions and no pyramiding follow canonical engine.

## Selection gates frozen before run

Development requires at least30trades; profit factor>=1.15; closed-trade maximum drawdown<=600 dollars at2MES; positive stressed netPNL; positive PNL in at least2of3 chronological equal-session thirds. Rank eligible candidates by development netPNL/max(closed drawdown,100); shortlist top2 per family.

Validation requires at least20trades; profit factor>=1.05; positive base and stressed netPNL; closed maximum drawdown<=800 dollars. Rank by validation return/drawdown using the same formula; freeze top1 per family, at most3 configurations overall. If none qualify, freeze an empty selection and do not inspect holdout.

Retain all configurations, full development metrics, validation shortlist metrics, session counts, and exact frozen_selection.json. Do not rework thresholds after results. No evaluation/payout success assertion follows from this search alone.
