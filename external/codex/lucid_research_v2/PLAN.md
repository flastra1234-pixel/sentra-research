# Continued LucidFlex research: fixed plan before new strategy results

Date: 2026-10-25. User authorized continued strategy discovery after the first batch failed. Preserve the first batch and its failures. No trades, account purchases, or broker connections.

## Information boundaries

All old NQ/ES data through October9,2026 are now researcher-consumed history. Rolling train/validation/test rules below respect date order within the algorithm, but performance is **researcher-biased pseudo-out-of-sample**, not a fresh final holdout. Human diagnosis and prior failed searches influenced this design.

Reserve two new assessments until rules and current selections are frozen:
- Previously unused ES native3-minute history: 2024 and pre-June2025. A backward-time robustness challenge, not prospective live performance. No-volume VWAP strategies cannot be reproduced on that file.
- Actual MES/MNQ ten-second prices, October12–16,2026: five previously unseen full RTH sessions. Tiny historical sanity check, insufficient to prove an edge. Guarded loader excludes dates>=October10 by default. No selection changes after this check.

## Why change the search

The first candidate's fixed contract size let risk rise with volatility; 1R targets lost much of their edge after costs; a few large wins dominated returns. Do not memorize posthoc winning hour/range bins. Test distinct entry mechanisms, wider payoffs, causal regime filters and fixed cash risk. Raw drawdown alone is not a Lucid survival rule because the floor eventually stops trailing; run the actual floor accounting.

## Universe and fixed search grid

Primary data: old NQ Aug2024-Oct2026 priced as MNQ($2/point), old ES Jun2025-Oct2026 priced as MES($5/point). Full390-minute 09:30–15:59 NY RTH sessions, daily-reset features, no overnight exposure. No fabricated bars.

Ten families: opening-range30 breakout, failed opening-range30, breakout followed by a later retest, prior12-bar channel breakout, failed12-bar channel breakout, EMA9/21 pullback, EMA9/21 cross, VWAP trend reclaim, VWAP two-ATR reversion, prior20-close Bollinger reentry. Exact signal definitions live in engine_v2.py and must remain frozen before performance collection.

Per asset:10families ×3signal intervals(3,6,15minutes) ×3signal windows(10:00–11:29,11:30–13:29,13:30–14:59NY) ×2ATR5stop multipliers(1.5,2.5) ×3targets(1,1.5,2R) ×2maximum holds(30,90minutes) ×3contexts(none/trend/range) ×2directions(both/long only) =6,480 raw configurations. Two assets=12,960 new configurations. Report active/nonzero-trade counts separately; some long-lookback/time-window combinations cannot trade. These are highly correlated variants, not independent discoveries.

Context: completed-bar10-period efficiency ratio = absolute net price change / sum absolute price changes; trend>=0.35, range<=0.20. Stops round up0.25tick; reject NQ stops outside5..100points or ES outside1..20points. Integer contracts=floor(60/(stop*point_value+1.24+4ticks*point_value)), maximum10, skip if zero. Fixed$60 primary ex-ante risk budget, never increased after losses. Max2trades/session and one open position. Flatten15:55, or15:54 on native3-minute challenge data.

Fee assumption$1.24 per micro roundtrip. Primary selection uses stressed fills2ticks per side; report baseline1tick per side only as sensitivity. Same quantity rule in both cases. Next native bar open entry, stop-first ambiguous bars, adverse stop gaps fill at worse open, target slippage conservative. Native3-minute tests use actual3-minute bars and elapsed-clock exits, never upsampled1-minute bars.

## Predeclared selection algorithm

Collect stressed per-session PNL, gross winning/losing trade sums, counts and intraday lows for every configuration. Preserve all results.

Rolling folds per asset: preceding120sessions training, next30validation, following30test, advance30sessions; full windows only. At each fold:
1. Training eligibility: >=40trades, stressed PF>=1.05, net>0, average net per trade >=$2. No hard$800closed-drawdown veto.
2. Stability: at least60% of immediate stop/target/holding-period neighbor configurations have positive TRAINING stressed net. These are correlated sensitivity checks, not independent confirmations.
3. Rank by training net/max(training daily-closed drawdown,$180); keep top3 per family.
4. Validation gate: >=8trades, stressed net>0,PF>=1.05. Rank by the minimum of training and validation net/max(drawdown,$180). Keep at most1perfamily and at most3perasset.
5. Freeze this fold's configurations before computing its test portfolio. Zero selections means cash, not a forced trade.

For deployment research candidates, apply the identical procedure to the latest120+30sessions ending no laterOct9. Freeze all asset selections in JSON before the unused-data checks. No tuning after fresh checks. Report each selected rule, the adaptive algorithm's walk-forward outcome and the selected rule's broader consumed-history performance separately.

Fleet construction: collect selected chronological signals, at most one position across correlated instruments, at most2trades total per NY day; reject overlaps including opposing positions. Validation ranking determines tie priority, fixed before each fold. A current fleet may combine at most3candidates across both assets by validation score. No martingale, averaging, hedging or maximum-size prop gambling.

## Assessment

Report stressed/baseline net,PF,closed and intraday drawdown,profit concentration,trades,months and fold consistency. Run5-session block-bootstrap mean intervals. Run a shared-block max-statistic diagnostic across the FULL supplied grid on aligned common dates; this is a data-snooping diagnostic, not a proof or a way to restore untouched evidence. Every previous branch and human iteration remains a limitation.

Account replay: use official snapshot /workspace/lucid_rules.md; standard40%eval consistency,DLLoff,$1250target,$1000EODtrail floor initially24000,capped25100, intraday equity touch fails. Passed eval resets funded25000 next session. Funded payout cycles need5days>=100,positive cycle net; gross500/trader450. Primary waituntilaccountprofit1500, minimum1000sensitivityseparate. Continue after requests for up to3payouts and track20-session post-first-request survival/censoring. Replays use total-position PNL directly, no double quantity multiplication. Roll start every10sessions, complete120session horizons, plus latest available partial horizon labeled. Overlapping fractions are descriptive, not independent probability estimates. No verified evaluation/reset/hosting fees, no live approval or actual payouts.

## Decision language

Promising means a research candidate meriting forward simulation, not a verified winning bot. Favor positive stressed walk-forward outcomes, parameter stability and account-path survival over a peak backtest. A five-day fresh gain cannot validate a system; a loss is still reported. If no candidate meets meaningful evidence, retain the best leads with their failed gates rather than manufacture profitability. No automated live deployment in this task.
