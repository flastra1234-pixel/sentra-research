# Pre-registration: new predictive information for the "70% of days" account goal

Written 2026-10-25 before any event-calendar or cross-asset result was computed. Committed to
git so its timestamp precedes the analyses it governs.

## Goal under test
Net +$100 to +$150 on at least 70% of eligible trading days. The LucidFlex 25K account
must survive, and funded payouts must reach $1,000+ a month. Rules come from
sentra-fleet-engine (`fleet_engine/rules.py`).

## What has already been examined (and is therefore not a clean test set)
- **2025-01-02 .. 2026-10-23 NQ sessions.** These were unsealed for the earlier fleets,
  the walk-forward, the family-by-year tables and the trend-day diagnostics in
  `RESULTS_2020plus.md` and `RESULTS_goal70.md`. Hypotheses below were partly motivated by
  those diagnostics, especially the decline in trend days. A 2025-26 result can therefore
  never count as fully independent evidence.
- **2020-2024 design data, examined in this round:**
  - feature scans for rest-of-day trend days and for momentum profit days (16 NQ features
    plus VIX);
  - filter rules R1 (trailing 20-day strategy P&L > 0) and R2 (VIX rose the prior day).
  - Result: nothing survived Holm correction on traded days, and R1/R2 *reduced*
    expectancy in 2021-24. Both are rejected and will not be tested on 2025-26.

## Hypotheses (design-period test, 2020-2024 only)
The strategy is always the canonical noise-area momentum spec (`lx_newinfo.CANON_NOISE`) at
1 MNQ.
- **E1.** Its expectancy per session is higher on scheduled 08:30 ET release days (CPI or NFP)
  than on other days.
- **E2.** Its expectancy differs on FOMC statement days (14:00 ET) from other days
  (two-sided).
- **E3.** The rest-of-day trend frequency (label `trend_rest`) is higher on CPI/NFP/FOMC days.
- **X1** (only if SPY 1-minute data is available for 2020-2024). Its expectancy is higher on
  days when SPY's 09:30-10:00 return has the same sign as NQ's.

**Qualification to advance**, all required:
1. Holm-adjusted permutation p < 0.05 across the hypotheses actually run (session labels
   permuted within year).
2. The same sign of effect in at least 4 of 5 design years.
3. Effect of at least $25 per traded day at 1 MNQ (E1, E2, X1), or at least 5 percentage
   points (E3).

## Single look at 2025-2026 (only for qualified hypotheses)
- **Rule.** Trade the canonical strategy on the qualified day type. Code and parameters are
  frozen in a commit before the run. One run, no iteration.
- **Success requires all of:**
  1. One-sided paired session-block bootstrap p < 0.05 that the rule beats trading every day
     on mean $ per session.
  2. Positive mean $ per traded day net of costs.
  3. Account metrics (`goal70.funded_life_policy`, $1,000 buffer) better than the
     every-day baseline.
- **If nothing qualifies,** 2025-2026 is not touched for these hypotheses.

## What would count as convincing evidence for buying an evaluation
None of the above alone. It also requires a live forward test (paper or sim) on sessions
after 2026-10-23 of at least 60 sessions. The frozen rule must beat its zero-edge baseline,
and its daily profile must be consistent with the account goal.

## Erratum (added 2026-10-25, after the design tests ran; the hypotheses and criteria above are unchanged)
The opening sentence says this file was written "before any event-calendar or cross-asset
result was computed". That holds for the calendar and SPY tests. It does not hold for VIX: the
VIX-level scans and the R1/R2 filter, both listed above as examined, had already been run.
