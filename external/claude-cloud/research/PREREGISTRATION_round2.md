# Pre-registration, round 2: more day-level information for the canonical momentum strategy

Written 2026-10-25, after round 1 (`PREREGISTRATION.md`, where nothing qualified) and before any
round-2 result was computed. It is committed to git before the analysis code is run.

## Why a second round, and what it costs
In round 1, the 18-feature scan, CPI/NFP/FOMC days and SPY confirmation all failed. Round 2
tests three day-level signals with an independent rationale. None of them is in the earlier
scans:
- **N1. VIX term structure.** Prior-close VIX9D / VIX ≥ 1, i.e. short-dated stress. Intraday
  momentum has been reported to be stronger in high or rising volatility. The VIX *level* and
  its daily change were already scanned and failed. The term-structure slope was not scanned
  as a day filter. A monthly correlation with trend-day share of 0.12 was seen, which does not
  select a direction.
- **N2. Tech leadership.** The sign of QQQ's minus SPY's 09:30-10:00 return equals the sign of
  NQ's 09:30-10:00 move. The idea is that Nasdaq-specific flow pushing the same way as NQ
  trends persist. This differs from X1, which compared SPY with NQ and did not use relative
  strength.
- **N3. Overnight-to-open agreement.** The sign of NQ's prior 16:00 close → 09:30 move equals
  the sign of its 09:30-10:00 move.

Each extra round makes a chance "hit" more likely. So round 2 is corrected within the round
(Holm over N1-N3), and also across both rounds (Holm over all 7 hypotheses). A hypothesis is
reported as a success only if it passes both.

**Amendment, made before any outcome was computed.** As first written, N2 used the raw QQQ
minus SPY return. A coverage check, which counted flag frequency only, showed that this sign
agrees with NQ's direction on 81% of days. That is a beta effect: QQQ moves more than SPY.
Leadership is therefore redefined as QQQ's return beyond beta x SPY, with beta taken from the
previous 60 sessions that have both returns. No P&L had been looked at when this change was
made.

## Design-period tests (2020-2024 only)
- **Strategy.** The canonical noise-area momentum spec (`lx_newinfo.CANON_NOISE`), 1 MNQ, net of
  costs.
- **N1-N3 statistic.** Mean $ per session on flagged days minus other days. One-sided: flagged
  days are higher.
- **N2 sample.** QQQ data starts 2020-07-13, so N2 uses 2020-07..2024 sessions with both QQQ and
  SPY data.
- **p-values and qualification.** The p-values, the permutation scheme (labels shuffled within
  year, 20,000 draws) and the qualification rules are the same as round 1. To qualify, a
  hypothesis needs all of:
  - Holm p < 0.05 within the round *and* across all 7 hypotheses;
  - the same sign in at least 4 of 5 design years;
  - an effect of at least $25 per traded day, with the same sign as the per-session effect.

## Single 2025-2026 look (qualified hypotheses only)
This uses the same frozen rule and the same success criteria as round 1:
`lx_prereg.look_stats`, with the stricter same-direction check.
- For N2, the look covers sessions with QQQ and SPY data, which run to 2026-09-30.
- If nothing qualifies, 2025-2026 is not touched.

## What would still be required
This is the same as round 1. A forward test on sessions after 2026-10-23 must pass before any
evaluation purchase is considered.

## Erratum (added 2026-10-25, after the design tests ran; the hypotheses and criteria above are unchanged)
The N1 rationale says the monthly correlation of 0.12 between VIX9D/VIX and trend-day share
"does not select a direction". That correlation is positive, the same direction N1 registered,
and it was computed on months that include 2025-2026. N1 failed in the registered direction.
