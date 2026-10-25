# Lucid $25K V2 — NO VERIFIED IMPROVEMENT

Assessment date: October 25, 2026 (America/New_York).

## Decision and evidence boundary

No candidate qualifies for the requested $100–$150 net on at least70% of eligible days, sustainable positive owner cash, and $1,000+ monthly owner withdrawals. No position sizes were increased and no money was spent or live trading enabled. All previously examined2026 data remain spent for selection. Rolling results below respect chronological algorithm windows but retain researcher-level selection bias; they are not prospective validation.

The still-unused2024 native-three-minute ES history and October12–16 actual-micro sessions remain UNOPENED for strategy assessment.2024 would be a backward historical check, not prospective evidence. No finalist passed the existing evidence gates, so those reserved observations were not consumed to rescue a weak selection. A future experiment must freeze code, selection, sizing and pass/fail thresholds before using them.

## Completed grid and robustness work

12,960 configurations,6,480 per market;9,024 generated trades. Inactive configurations remain counted separately. These are correlated variants, not independent strategies.

Rolling procedure:120training sessions,30validation,30test, advance30. Training requires40trades, stressedPF>=1.05, positive net, average net/trade>=$2 and60% positive neighboring parameters. Top3perfamily advance; validation requires8trades, positive stressed net andPF>=1.05. Selection uses only past train/validation data. Portfolio permits one position and at most two trades/day. Risk remains the originally registered$60 ex-ante cash budget with integer micros and no loss-driven increases.

| Chronological rolling fleet | Baseline | Stress |
|---|---:|---:|
| All eligible complete sessions |390|390|
| Trades |174|173|
| Net trading P&L |-$1,025.60|-$1,179.87|
| Profit factor |0.766|0.734|
| Maximum closed-trade drawdown |$1,442.82|$1,562.07|
| Days net >=$100 |4/390 (1.03%)|3/390 (0.77%)|
| Days net >=$150 |1/390 (0.26%)|1/390 (0.26%)|
| Losing days |73|73|
| Inactive days |269|269|

Eligible days include losing and inactive complete sessions; they are not redefined after observing profit. Short/holiday/data-incomplete sessions excluded by the original quality rule are not represented. Baseline assumes1tick adverse slippage per side; stress2ticks; fee$1.24 per micro roundtrip. Dollar logs already contain total-position quantities, never multiplied twice.

Even the highest full-sample individual stressed daily target rates were only7.38% (NQ) and8.90% (ES) for$100;1.85% and3.37% for$150. These maxima are selected historical statistics, not validated recommendations. Zero of12,960 configurations attained70% for either threshold.

The strict broader-history screen found zero configurations with BOTH stressedPF>=1.20 and>=150trades. Smaller positive samples lacked strong parameter plateaus. Recent-window developmental selections ES_03981 and NQ_05339 had negative whole-history stressed P&L and do not qualify as finalists. Selecting them because their recent results look better would not establish improvement.

## Uncertainty, search adjustment and zero-edge comparisons

Five-session block-bootstrap95% interval for rolling mean daily net: baseline[-$6.57,+$1.19],stress[-$7.04,+$0.84]. For stressed fraction of$100days the interval is[0%,1.79%]; for$150days[0%,0.77%]. These approximate stationary-block intervals are not multiple-search-adjusted confirmations.

Search-wide centered block-bootstrap max-statistic diagnostic used1,000 shared resamples across all12,960 columns on325common dates. Global adjustedp=1.000; separate full-history NQp=0.998,ESp=0.987. No positive edge was established against this zero-mean null. This exploratory method is not a full White Reality Check/Hansen SPA and does not correct human iteration or prove no edge could exist.

Cash/no trade has$0 net market P&L and beats this negative rolling fleet. A hypothetical zero-gross-edge benchmark charging only observed commission quantities would lose$235.60baseline/$233.12stress before any slippage; that is an illustrative fee-only benchmark, not an independently executable randomized strategy. The centered search-wide null is the statistical zero-edge comparison. No result supports a positive owner-cash claim.

## E028 execution audit

Verified every saved trade: MES=$5/point/contract; two contracts; one-contract net = pnl_points*$5-$1.24; then multiply by2. Tick=0.25point. No multiplier or fee mismatch found.158entries match one-to-one between baseline and stress.

- Baseline net: +$715.66.
- Stress net: -$526.84.
- Exact deterioration: -$1,242.50.
- Fees unchanged.
- Five exit reasons and22exit timestamps changed.
- Matched trades with changed reason/time contributed-$880.00; unchanged reason/time contributed-$362.50.

A naive fixed-path additional-two-sided-tick charge gives-$790, but is not the execution simulation. Stops/targets anchor to slipped entry prices; changes alter which thresholds fill and when. The saved entry/exit fill-by-fill ledger reconciles the full-$1,242.50. Stop-first ambiguous bars and adverse gap fills were audited. Targets in this experiment are market-style adverse-slip exits, NOT resting limit orders; a limit-target model requires its own preregistered fill assumptions and trade-through/missed-fill tests. An opt-in extension in code is not a completed performance result and is not included in the12,960 results.

See assessment/E028_fill_reconciliation.csv for the complete matched ledger. This resolves the discrepancy without replacing stress outcomes with an arithmetic fee subtraction.

## Evaluation-to-payout and owner cash

Replayed28overlapping full120-session starting windows per cost scenario, separately from evaluation and already-funded starts. Official snapshot:25K start,$1,250eval target,40%consistency,$1,000EODtrailing allowance, capped$25,100floor, intraday floor enforcement,30-calendar-day inactivity; funded5days>=$100,positive cycle net,$500gross request/$450trader net. Primary$1,500profit reserve policy and minimum$1,000 sensitivity are separate. Simulator continues after requests and supports three cycles/20-session post-request checks; no actual requests occurred here.

With inactivity enforced, all28windows per scenario expired for inactivity before completing their objectives. There were zero evaluation passes and zero simulated payout requests under either reserve policy. Inactivity is a failure of operational suitability, not a drawdown breach.

For diagnosis only, disabling inactivity produced one baseline and two stressed floor-breach paths out of28; remaining paths stayed pending/alive without any payout requests. This sensitivity is NOT a compliant account model. Actual valid-rule results must not be replaced by the relaxed scenario.

No simulated owner receipts occurred. Actual evaluation/reset/platform/hosting costs were not verified and are excluded, so sustainable positive NET owner cash is not demonstrated and would be worse with positive costs. $1,000+ monthly withdrawals are unsupported. First-payout eligibility is not proof of approval; the model does not establish the later live-account regime after sim payout limits. No post-payout survival percentage can be estimated with zero requests.

## Next genuinely distinct market hypothesis

Investigate **overnight inventory imbalance and cash-open failed-auction reversion confirmed by signed trade flow**, not another EMA/ATR parameter search. Hypothesis: unusually one-sided overnight positioning followed by failed cash-open price discovery and opposing aggressive order flow predicts a move toward prior-session fair value.

Requires contract-identified overnight prices and trade/quote or reliable aggressor-side data, plus a predeclared scheduled-news treatment. The present session-reset OHLC studies did not test that information. Validate data and roll handling first; freeze economic event definitions, sizing unchanged, transaction costs, chronological periods and daily/owner-cash targets before performance. No purchase is authorized or needed to claim it as an untested hypothesis. Do not use the five reserved days as tuning material.

## Artifacts

- assessment/metrics.json: daily attainment, every-grid maxima, E028 audit, account summaries.
- assessment/*daily_targets.csv: all12,960 denominator-inclusive daily metrics.
- assessment/*lifecycles.csv: compliant rolling account paths.
- assessment/DIAGNOSTIC_ignore_inactivity*: clearly separated rule-relaxation diagnostics.
- results/walkforward_selection.json: chronological selections and boundaries.
- results/searchwide_max_t.json and SEARCHWIDE_DIAGNOSTIC.md: full search adjustment and neighborhood findings.
- complete_assessment.py: reproduction using saved results only.

37execution,accounting,selection andvalidation tests pass. None of these synthetic checks establishes trading profitability.
