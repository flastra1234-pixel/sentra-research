# Independent pre-reserved-assessment audit

Audit date: 2026-10-25. Reviewed `PLAN.md`, `search.py`, `walkforward.py`, `validation.py` and `engine_v2.py`. No reserved ES2024 or October12–16 strategy performance was opened by this audit. No running driver or engine was modified.

## Findings

No major selection lookahead or dollar-quantity accounting defect was found.

- Grid summaries store actual TOTAL-position P&L and excursion. Integer contract size is already incorporated by the engine. Search aggregation and walk-forward metrics correctly sum those dollar amounts without multiplying again. Account replay must use quantity1 for these logs.
- Each fold's training gates, neighbor support and training shortlist use training indices only. Validation uses only the next validation block. Test observations cannot change the selected list. Current selection uses the last120training and30validation sessions, all before reserved dates.
- Recomputing selected strategy logs on the full primary history before test-date filtering does not introduce future trading decisions: indicators reset daily, there are no overnight positions, and within-day prices are consumed causally apart from the quality-filter caveat below.
- Walk-forward tests do not overlap within an asset. Different assets can have different fold boundaries; each has past-only selections when its signals enter the common chronological fleet.
- Fleet decisions use previously established validation scores, deterministic tie-breaking, one position across assets, and at most two trades per session. Simultaneous or overlapping opposite positions are rejected. Reentry exactly at an earlier exit timestamp is also rejected, conservatively.
- Native3-minute bars are not upsampled. The first30minutes comprise ten native bars, including the09:57 bar completed at10:00. First subsequent3-minute OR signals are completed at10:03 and execute at that next native open. Holding exits use elapsed clock minutes; forced flatten is15:54.
- EMA9/21 values reset at each session and seed from that day's first completed aggregate close. This is causal, but differs from conventional continuously seeded multi-session EMA. ATR5 imposes five-bar minimum stop availability; there is no extra21-bar EMA warmup.

## Offline-quality caveat

Complete-session retention and full-day volume-validity gating are offline data-quality filters. A late missing bar can exclude earlier trades from that day; a late missing volume value can disable the entire day's earlier VWAP signals. This uses future data availability, though not future price direction. It must not be described as a fully causal live data-recovery policy. A live adapter should track coverage and validity prospectively and should be tested separately. All-missing volume correctly disables VWAP strategies on the reserved ES3-minute source.

The primary NQ/ES RTH rows within the registered date bounds were checked independently: both have zero missing or negative volume values. Thus the whole-day volume-validity check does not select among primary sessions on this run; the general live-policy caveat remains.

## Small-sample API caveat

At review time, `walkforward.trade_metrics` attempted a bootstrap for any sample longer than one session while the bootstrap utility requires at least20. The parent was notified to guard small reserved samples or mark the diagnostic unavailable. This does not affect the long-history search or walk-forward selection.

## Additional tests

`python -m unittest test_selection.py -v` passes five independent synthetic tests:

1. Arbitrarily perturbing future test matrices does not alter frozen selections.
2. Failed validation produces cash even when future returns are enormous.
3. Future positive returns cannot repair failed training/neighbor support.
4. Train/validation/test blocks are chronological and test blocks do not overlap.
5. Fleet overlap and daily trade limits work across assets, and dollar metrics do not double-count quantity.

These tests validate information flow and accounting behavior, not profitability, broker fills or prospective robustness. Previously examined2026 history remains researcher-consumed pseudo-out-of-sample, as the plan states.
