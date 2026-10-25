# Pre-registration: forward test on sessions after 2026-10-23

Written 2026-10-25, a Sunday, before any session after 2026-10-23 exists. The first new Lucid
session opens at 18:00 ET tonight. The code (`factory/forward.py`) and these rules are frozen in
the same commit. Paper or simulation only: no orders and no evaluation purchase.

## Candidates (all canonical noise-area momentum, `lx_newinfo.CANON_NOISE`, 1 MNQ)
| id | trade on | source |
|---|---|---|
| C0 | every eligible session | baseline |
| C1 | sessions where NQ's 16:00 → 09:30 move has the same sign as its 09:30-10:00 move (N3), skipping sessions after a prior-close VIX9D / VIX ≥ 1 (not N1) | round 2: N3 near miss; N1 opposite direction |
| C2 | C1, and also QQQ's beta-adjusted 09:30-10:00 lead agrees with NQ (N2) | round 2: N2 near miss |

The flags are computed exactly as in `lx_prereg2.hypotheses`. All of them are known by 10:00 ET.

## Evaluations
Each evaluation is run once, at its milestone. Interim checks are monitoring only and cannot
change the rules.

**E-goal: the account goal**, at 60 forward sessions, for C0, C1 and C2. All of these must
hold:
1. At least 70% of eligible days are ≥ +$100. Eligible days are the sessions the candidate's
   rules allow trading, and there must be at least 3 a week on average.
2. The mean is ≥ $40 per session over all sessions.
3. The worst day is ≥ -$150.
4. A LucidFlex funded simulation (`goal70.funded_sim`, $1,000 buffer) on the forward days in
   order never breaches.
5. The mean beats a zero-edge baseline at one-sided p < 0.05. The baseline flips each day's sign
   at random, with 20,000 draws.

The research so far predicts that no candidate will pass E-goal.

**E-improve: does a filter improve the strategy?** Run at 250 forward sessions, for C1 and C2
against C0. Success requires both of:
1. A stationary block bootstrap (mean block 5, 20,000 draws) gives one-sided p < 0.05 that the
   candidate's annualised Sharpe exceeds C0's on the same days.
2. The candidate's 12-month funded survival and owner $/month, with the $1,000 buffer and days
   bootstrapped from the forward sessions, are both at least C0's.

The two comparisons are Holm-corrected. Only a pass here would count as a verified economic
improvement.

## Data
New NQ 1-minute bars must come from the same kind of source and session construction as
`lx_sources` / `lx_data` (18:00-16:44 ET sessions). QQQ, SPY and VIX for the new dates come from
equivalent public sources, with provenance recorded. Execution in a paper or sim account should
be logged as well. Its fills are compared with the model: the average slippage must be within 1
tick per fill. If execution logs are missing, the results count only as a backtest on new data.
