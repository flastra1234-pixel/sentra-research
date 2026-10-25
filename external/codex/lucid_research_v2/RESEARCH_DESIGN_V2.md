# Continuation design after the first failed study

This is independent design advice, recorded before the second batch's results. It is not a claim that any new strategy works.

## What changes and what does not

The first study searched only a few mechanisms and often used fixed contract counts. Continuing with additional economic hypotheses is reasonable. The count of configurations is not evidence: 10,000 correlated variants can be 10,000 opportunities to fit noise.

All 2026 results already examined must now be labeled researcher-consumed history. A subsequently discovered rule that does well there is a research result, even if the program computes it through chronological folds. New downloaded periods may remain an assessment set only if no one uses their strategy outcomes to choose the next rules. An untouched earlier period is a useful reverse-time replication, not a future forward test.

Retain every grid definition, result and research amendment. Configuration IDs should include instrument, family, entry/exit parameters and risk policy. Do not inflate the count by treating baseline and stressed execution or duplicate quantities as independent strategies.

## Predeclared rolling procedure

One practical default is 120 observed trading sessions for training, the following30 for validation, and the following30 for deployment/test; step forward30 sessions and repeat. Train precedes validation, which precedes test. The next fold may train on prior fold test data, just as a prospective monthly procedure would. Tests do not overlap.

The 326-session ES dataset permits approximately five complete such test windows. NQ permits more. If shorter initial training is desired, decide that now rather than after seeing which initial folds lose. Use `validation.rolling_folds` to write explicit session-date manifests.

Within each fold:

1. Compute all predefined strategies on training with fixed execution assumptions.
2. Apply training gates and rank within each economic family, retaining only a small fixed count.
3. Check shortlisted variants on the subsequent validation window. Require positive stressed net results and adequate trade count, without searching new filters after seeing that window.
4. Choose a fixed number of survivors and fixed risk allocation before the test window begins. If none pass, hold cash.
5. Concatenate only these prospective selections' test logs. Report the no-trade periods, fold failures and turnover as well as total P&L.

The whole procedure—including its candidate universe, gates and tie-breaking—is the strategy being evaluated. Selecting the best configuration by all-period test profits is another search and must be labeled as such.

## Use dollars at risk rather than fixed quantity

Test a small, predefined risk-budget set such as $40/$60/$80 per position. Size from the stop that is known at entry:

`q = floor(budget / (stop_points * point_value + roundtrip_fee + adverse_slippage_allowance))`

Cap q at10 micros to remain below the initial funded tier; skip if even one micro exceeds the budget. Use the same rule during training, validation and test. Increasing quantity because the account lost is excluded. A predefined cap based on remaining distance to the active account floor may reduce risk, never increase the budget after losses.

Budget60 with a1R target often cannot produce a $100 qualifying day from one trade. Targets1.5–3R, or up to two independently justified nonoverlapping signals daily, can address this constraint through payoff structure. This is different from selecting rules solely for a high win rate. Fees and execution affect the actual qualifying-day amount.

The supplied `risk_quantity` utility reserves two-sided stressed slippage in addition to commission. If the trade engine anchors the protective stop to the realized fill, that reserve is deliberately conservative.

## Account objective and risk gates

Raw maximum drawdown under$800 is an imperfect proxy for Lucid survival. Lucid's floor stops trailing at$25,100. A path may accumulate substantial retained profit and later experience more than$1,000 peak-to-trough drawdown without touching the floor. Conversely, small closed-trade drawdown can conceal an intratrade floor violation.

Use the exact account replay as the main feasibility check: prior-EOD high-water floor, intraday equity/MAE floor touch, fresh funded balance after evaluation, consistency during evaluation only, qualifying funded days, payout lock and gross withdrawal deduction. Retain max drawdown as an informative metric rather than declaring that every drawdown>$1,000 is automatically a breach.

Report both evaluation-to-payout and already-funded scenarios. Use multiple nonoverlapping starts when feasible; overlapping rolling starts are descriptive scenarios, not independent probability samples. Keep pending outcomes distinct from breaches. Show sensitivity to $1,000 versus$1,500 funded profit before the first$500 request; do not choose the policy by whichever looks best in the final data.

Extend replay beyond first payout—at least another20–60 sessions, or a second payout cycle. A policy that quickly withdraws$500 but leaves only$400 above the locked floor may have weak durability. Current evaluation/reset/hosting costs are necessary before claiming economic profitability. Without verified fees, report trader payouts and breaches separately.

## Stability, uncertainty and multiple comparisons

Require more than one profitable month or fold. Useful diagnostics are median stressed test-fold return, number of profitable/non-trading folds, worst fold, minimum account headroom and trade counts. A few outlier trades or one favorable quarter should not dominate the claim.

Parameter-neighbor support can distinguish a broad plateau from a single isolated optimum. The supplied utility compares configurations that match every other field and differ by one adjacent parameter-grid step. Neighboring results are correlated and are not independent replications.

`moving_block_bootstrap_mean_ci` estimates a daily-mean interval with serial dependence retained in circular blocks. Feed zero-trade sessions as zeros, not missing rows. The function also reports a centered-null one-sided p-value; it is a single-series diagnostic, not a correction for selecting from10,000 alternatives.

`shared_block_max_t_test` is an optional exploratory data-snooping check. Feed an aligned sessions-by-candidates matrix covering the whole searched universe, not just the winners. It centers each strategy's mean under a null, uses the same resampled blocks for all candidates and compares observed studentized means with bootstrap maximum statistics. Its familywise-adjusted p-values depend on approximate stationarity and the specified universe; they do not erase human research iteration or create a fresh holdout. It is deliberately not named a full White Reality Check or Hansen SPA implementation.

## Fleet construction

Select different economic families using training/validation information. Set allocation and priority before each test window. Centralize orders, net opposing signals, limit total contract count and total stop risk, and reject overlapping positions if the execution model cannot simulate a multi-position book faithfully. Do not fit portfolio weights to the period used to report performance.

A fleet deserves the same stressed execution and actual account-floor replay as a single strategy. Low sample correlation alone is insufficient; two strategies may both fail during the same volatility episode. Broader assets can help only when data provenance, session schedules, tick values and fills are handled correctly.

## Utility verification

`validation.py` provides fold manifests, ex-ante risk quantity, block mean intervals, shared-block max-t diagnostics and parameter-plateau support. Six tests verify chronological/nonoverlapping folds, explicit overlapping-window opt-in, friction-aware sizing and skip logic, zero-edge bootstrap behavior, max-statistic adjustment and asset-preserving parameter adjacency. Synthetic tests establish implementation behavior, not trading profitability.
