# LucidFlex 25K strategy study: plan before results

Created 2026-10-25 UTC, before any strategy performance computation.

## Scope
Research and simulation only; no brokerage connections, purchases, or orders.
Use NQ front-month one-minute OHLCV to model MNQ ($2 per point). This is a price proxy: MNQ's order book/fills are not independently observed. All indicators reset daily, no overnight exposure or cross-contract price signals. Public third-party data is not exchange-certified.

## Data splits
- Development: 2024-08-05 through 2025-06-30.
- Validation: 2025-07-01 through 2025-12-31.
- Final historical holdout: 2026-01-01 through latest available (2026-10-08).
- Use only complete 390-minute NY RTH sessions, 09:30 through15:59. Missing/holiday-short sessions excluded, never filled. Indicators use completed bars; signals execute next-minute open. Common signal window10:00 through11:29 ET (60-minute OR naturally starts10:30); entries no later11:30. Flatten no later15:55. No economic calendar/news filtering. Window clarified before any performance run to match engine implementation.

## Fixed candidate grid
297 configurations across4families, no additional grid after final holdout inspection:
- Opening-range breakout: OR15/30/60minutes × ATR stop1.5/2.5/4 × target1/1.5/2R × hold30/60/90minutes =81.
- Failed opening-range breakout: same81configurations.
- VWAP reversion: ATR band1/1.5/2 × ATR stop1.5/2.5/4 × target1/1.5/2R × hold30/60/90minutes =81.
- EMA pullback: fast9/20, slow50 × ATR stop1.5/2.5/4 × target1/1.5/2R × hold30/60/90minutes =54.
- ATR14 on one-minute RTH bars; minimum stop5points, maximum60points. Maximum2trades/session, no concurrent positions per strategy. Both long/short, no direction tuning.

## Execution/costs
One MNQ base logs; primary account sizing2MNQ constant. Tick0.25. Commission$1.24roundtrip per micro (research assumption; official posted fee$1RT). One tick adverse slippage each side baseline; two ticks each side stress. Protective stop orders use adverse open for gaps; bars hitting stop and target resolve stop first. Worst intratrade equity must be recorded. No optimistic limit fills.

## Selection before holdout
Development eligibility: at least100trades; net PF>=1.10; at2MNQ maximum closed-trade drawdown<=1000; positive net stressed PNL; at least2of3consecutive development subperiods positive. Rank by net PNL/max(closed-trade drawdown,100). Retain at most3per family. Evaluate these on validation only.
Validation eligibility: >=30trades, positive net baseline and stressed PNL, PF>=1.05. Rank eligible candidates by validation net PNL/max(drawdown,100); freeze up to3, at most1per family. If none survive, report no validated strategy rather than search after looking at final data.
Report all development configurations, validation shortlists, and final failures. PF and drawdown gates are screening heuristics, not statistical significance tests. A final holdout failure disqualifies deployment; no retuning using it. Correlated neighboring parameters do not count as independent discoveries.

## Fleet
If multiple families survive, assess equal1MNQ signals with a single position at a time: chronological entries, reject overlapping trades (including opposing directions), fixed family priority from validation ranking. No cherry-picked final-period combination. Report the single selected candidates even if fleet fails. Fleet aggregate maximum2trades/day; separate positions not account hedging.

## Account replay
Rules in /workspace/lucid_rules.md. Baseline40%consistency, DLLoff; EOD high-water trail$1000, initial floor24000, locked cap25100, touching active floor intraday breaches. Evaluation target1250; next-day funded reset25000. Conservative first payout500gross(450net) only after1500funded profit and5days>=100; preserve900headroom after withdrawal. Fixed2MNQ for singles,1each for fleet. Start replay each5th eligible session with full120sessionhorizon, plus separate60sessionfunded-only outcomes if available. Overlapping starts are descriptive, not independent success probabilities. No extrapolation past first payout. Fees for evaluations/reset/hosting not included because checkout costs not verified; no claims of business profitability.

## Final deliverables
Exact strategy rules/configs, all search results, trade logs, baseline and stressed split metrics, drawdown and payout replay, reproducible code and source provenance, limitations and pass/fail decision. Actual forward test remains unperformed in this session.
