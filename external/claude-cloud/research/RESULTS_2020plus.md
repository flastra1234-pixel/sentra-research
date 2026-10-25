# 2020+ results: LucidFlex 25K on the real Lucid trading day (2026-10-25)

Research only, not financial advice. Nothing here places orders.

## Bottom line
- **Data.** Real NQ futures, 1-minute bars, Jan 2020 to Oct 23 2026. Each day is one Lucid
  session, 18:00 ET to 16:44 ET, flat by 16:45 (1,751 sessions, halt days and half days
  included). The main file was cross-checked against an independent vendor: 1-minute return
  correlation 0.993, daily correlation 0.9997.
- **Search.** 111,960 strategy variants, including overnight, Asia, London and pre-08:30 setups.
  These cluster into about 1,182 independent tests.
- **2020-2024: a real edge.** Noise-area momentum from the 09:30 open, plus opening-range
  breakouts, was profitable in nearly every variant.
- **2025-2026: the edge faded and turned negative.** A walk-forward test retrains each year on
  all earlier years and then trades the next year blind. It made money in 2023 and 2024. It lost
  in 2025 and 2026, and retraining on 2025 did not fix 2026.
- **Your three goals** (out-of-sample figures):

| goal | what it takes | best result here (out of sample) |
|---|---|---|
| 1. any payout within 2 weeks | pass in 5 sessions or fewer, then 5 straight funded days of $100+ that add up to $1,000+ profit | **0.2-0.7%** chance, even for a fleet built only for this goal |
| 2. ~$1,000 per month per account | a daily Sharpe around 0.6 (about 9.5 a year) to make it 80% likely in a given month | **9-11%** of months in 2023-24, **4-5%** in 2025-26 |
| 3. 3:1 reward:risk at 60% win rate | +1.4R per trade, about an 11 annual Sharpe | **none** of 111,960 variants; 3:1 setups win about 31% of the time |

**Do not run these fleets with real evaluation money.** Their edge is gone in the current
market. The useful outputs are below: the math on what Lucid's rules make possible, a factory
that can be re-run on new data, and where to look next.

## Why goals 1 and 2 are so hard under LucidFlex rules
This comes from the account rules, not from the strategies.
- **Earliest possible payout.** The evaluation needs at least 2 good days, because no day may
  be more than 50% of profit. A funded payout needs 5 days of $100+, a positive cycle, and a
  $500 minimum request, which is 50% of profit, so profit must be at least $1,000. That means
  no payout before about session 7. A payout within 10 sessions needs a pass in 5 sessions or
  fewer and then 5 straight qualifying days.
- **What Sharpe buys.** From the sentra-fleet-engine grid (normal daily P&L, best sizing):

| daily Sharpe (annual) | P(pass within 10 sessions) | P(>= $1,000 owner payout in a 21-session month) |
|---|---|---|
| 0.00 (0) | 18% | 8% |
| 0.10 (1.6) | 26% | 16% |
| 0.20 (3.2) | 36% | 27% |
| 0.40 (6.3) | 56% | 55% |
| 0.60 (9.5) | 76% | 80% |

- **Passing fast is mostly sizing, not edge.** A zero-edge version of the evaluation fleet is
  the same fleet with each day's P&L sign flipped at random, keeping its volatility, intraday
  lows and $600 daily profit lock. It passes within 10 sessions 15-36% of the time, depending
  on the year's volatility. The real fleet beat that by about 10 points in 2023-24 and
  trailed it in 2025-26. Getting *paid* is where edge matters.

## Walk-forward: does the process work going forward?
Each year Y is selected on all sessions before Y (gates, pool, fleets) and then traded blind.
Only the round-1 grid of 25,062 specs is used, so no fold leans on a later fold's choices.

| test year | eval fleet $/day (Sharpe) | P(pass in 10): fleet vs zero-edge | funded fleet $/day (Sharpe) | P($1k month) | P(payout within 10 / 21 sessions of buying) |
|---|---|---|---|---|---|
| 2023 | +$25 (1.09) | 27% vs 16% | +$58 (1.78) | 9% | 0.5% / 8.5% |
| 2024 | +$33 (1.35) | 26% vs 15% | +$22 (0.64) | 11% | 0.4% / 8.0% |
| 2025 | -$7 (-0.23) | 22% vs 36% | -$10 (-0.22) | 4% | 0.4% / 4.4% |
| 2026 (to Oct 23) | -$50 (-1.76) | 17% vs 22% | -$24 (-0.91) | 5% | 0.1% / 4.7% |

Goal-1 fleet: one fleet chosen to maximise P(first payout within 15 sessions). It scored
7-11% in-sample. Out of sample it paid within 10 sessions 0.2-0.7% of the time, within 15
sessions 1.7-3.5%, and within 21 sessions 3-9%.

**Economics per evaluation bought.** Walk-forward fleets, 63 sessions (3 months) from buying
the evaluation: trade the eval fleet until it passes, then the funded fleet.

| test year | P(any payout within 42 sessions) | mean $ paid to you per evaluation | minus a $89-149 fee |
|---|---|---|---|
| 2023 | 11.7% | $220 | +$71 to +$131 |
| 2024 | 10.4% | $148 | -$1 to +$59 |
| 2025 | 5.3% | $67 | -$22 to -$82 |
| 2026 | 5.5% | $75 | -$14 to -$74 |

Even in the good years the median outcome is $0: most evaluations either fail or breach before
the first payout. A small minority of accounts carry the average.

## What changed in 2025-2026
Median annual Sharpe of every variant in each family, by year (share of variants positive):

| family | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| noise-area momentum (4,320) | +0.05 (53%) | +0.80 (87%) | +1.84 (100%) | +0.96 (89%) | +1.41 (100%) | +0.33 (66%) | -0.13 (43%) |
| cash-open ORB (5,760) | -0.12 (46%) | +0.13 (54%) | +0.38 (66%) | -0.31 (39%) | +0.76 (79%) | -0.12 (45%) | -0.56 (21%) |
| overnight range -> cash session (1,152) | +0.30 | +0.32 | +0.38 | -0.16 | +0.13 | +0.19 | -0.48 |
| Asia/London breakouts (4,608) | +0.03 | +0.11 | -0.05 | -0.02 | -0.18 | -0.60 | +0.14 |
| pre-08:30 range breakout (1,152) | +0.14 | +0.56 | +0.94 | -0.16 | -0.32 | -0.19 | -0.56 |
| fades, end-of-day momentum, timed holds, drives, 09:30 gap | about 0 or negative every year | | | | | | |

The intraday momentum that carried 2021-2024 weakened in 2025 and is negative in 2026. No
family in the grid shows a clear 2026 edge, mean reversion included. One plausible cause is
crowding: this momentum style was widely published and copied in 2024. Other explanations
can't be ruled out.

## The final fleets (frozen on 2020-2024)
Selected on 2020-2024 only. The sealed and holdout figures below are a **second look**: an
earlier version of these fleets, built before the review fixes, was unsealed once and failed
the same way. Use them as confirmation, not as an independent test; the walk-forward above is
the clean evidence.

| | eval fleet $/day | P(pass in 10): fleet vs zero-edge | funded fleet $/day (Sharpe) | P($1k month) | P(payout within 10 sessions of buying) |
|---|---|---|---|---|---|
| in-sample 2020-2024 | +$23 | 33% vs 29% | +$125 (2.63) | 17.7% | 1.2% |
| sealed 2025-01 .. 2026-02 | -$24 | 21% vs 33% | -$12 (-0.29) | 5.0% | 0.2% |
| holdout 2026-03 .. 2026-10 | -$56 | 15% vs 27% | -$33 (-0.70) | 2.9% | 0.07% |
| of which never seen (2026-03 .. 2026-07) | -$19 | 19% vs 26% | +$42 (0.84) | 7.3% | 0.06% |

Times below are ET. "Trend" means the prior session close vs its 20-day average. "ATR" is the
14-day average true range of the full Lucid session. Every position is flat by 16:44.

**Evaluation fleet: 5 MNQ, plus a daily profit lock (flatten everything at +$600).** The lock
keeps every day below the 50% consistency limit.

| sleeve | rules | Sharpe in / sealed / holdout | win rate, reward:risk (in-sample) |
|---|---|---|---|
| noise-area momentum | bands = 09:30 open (gap-adjusted) +/- 0.8 x 10-day average move-from-open at that minute; check 10:00, 11:00, ... 15:00; long above / short below; exit when a 1-minute close crosses VWAP; re-entries allowed; 0.3 ATR hard stop; flat 16:00 | 1.89 / 0.25 / 1.03 | 41%, 2.1:1 |
| noise-area momentum, with trend | same, checks every 30 min from 10:00, only with the trend, skip days when 5-day ATR > 1.2x 50-day ATR | 1.88 / -0.32 / 1.13 | 43%, 2.3:1 |
| 60-min ORB long, with trend | buy stop above the 09:30-10:29 high until 13:30, only in up-trends, skip high-vol days; 0.2 ATR stop, breakeven after +1R, out 16:44 | 1.52 / 0.27 / 0.72 | 42%, 2.3:1 |
| opening drive | if 09:30-10:29 moved >= 0.1 ATR, enter its way at 10:30; 0.3 ATR stop, 2R target, out 15:55; small-gap days, ATR <= 2% | 1.20 / 0.86 / -1.73 | 51%, 1.4:1 |
| 30-min ORB | stop orders at the 09:30-09:59 high/low until 11:00; 0.2 ATR stop, 3R target, out 15:55 | 1.21 / -0.25 / -1.92 | 40%, 1.9:1 |

**Funded fleet: 8 MNQ, no overlay.**

| sleeve | rules | Sharpe in / sealed / holdout | win rate, reward:risk |
|---|---|---|---|
| opening drive, wide overnight | 60-min drive >= 0.1 ATR, 0.3 ATR stop, 2R, out 15:55; overnight range >= 0.4 ATR, ATR <= 2.5% | 1.81 / 0.32 / 0.20 | 52%, 1.4:1 |
| opening drive, 15 min, with trend | 09:30-09:44 drive >= 0.1 ATR with the trend, 0.3 ATR stop, 2R, out 15:55; no Mondays | 1.73 / 0.13 / -0.42 | 53%, 1.6:1 |
| 60-min ORB, with trend | stop half the range, 1R target, breakeven after 1R, out 16:44 | 1.47 / 0.89 / -1.41 | 58%, 1.0:1 |
| noise-area momentum on NR7/inside days | 14-day bands x 1.0, every 30 min, tighter of band/VWAP exit, 0.5 ATR hard stop | 1.34 / -1.34 / -0.24 | 33%, 4.0:1 |
| 60-min ORB | 0.2 ATR stop, 2R, out 15:55 | 1.22 / -0.19 / -0.76 | 45%, 1.5:1 |
| 60-min ORB, low-vol days | same, only when 5-day ATR < 0.9x 50-day and ATR <= 2% | 1.24 / -1.54 / 0.16 | 48%, 1.6:1 |
| Asia -> London breakout, with trend (2 MNQ) | range 18:00-02:59, stop orders 03:00-05:00, stop half the range, 1R, out by 16:44 | 1.10 / -0.57 / -0.26 | 56%, 1.05:1 |

Full parameters: `research/results/lx_fleet2_nq20.json`.

## Funnel (2020-2023 discovery, 2024 validation)
| | specs | survived every gate |
|---|---|---|
| round 1 (base grid) | 25,062 | 1,627 (6.5%): 1,472 noise-area momentum, 121 cash-open ORB, 34 drives |
| round 2 (filters on 614 distinct bases) | 86,898 | 15,738 (14,557 admissible: their own base passed validation unfiltered) |

- **Deflation.** No single strategy clears a deflated Sharpe of 0.95 against 1,182 independent
  tests (best 0.86).
- **Win rate and reward:risk.** Survivors win 41% of the time at 2.2:1 (median). Only 4 reach
  50% at 2:1 or better. The 3,828 survivors with 3:1 or better win 31% (median).

## What the adversarial review caught (all fixed before the final numbers)
Five reviewers each hunted one kind of bias, and two skeptics tried to refute every serious
finding.
- **Major: payout timing.** Goal 1 had no metric. The 21-session "any payout" figure looked
  10-300x better than reality. Fixed by `journey()`, which runs the evaluation and then the
  funded account and records the session of the first approved payout.
- **Major: round-2 leakage.** Round 2 re-tested filtered variants of bases that had already
  failed 2024 validation, so chance passes got in. Now a variant counts only if its own base
  passed.
- **Major (also fixed): dropped tail days.** Sessions were dropped when bars were missing
  later in the day. That threw away the March 2020 circuit-breaker days and the Sep 2022 FOMC
  day. Halt days and half days are now kept, and orders never fill on bars without a print.
- **Minor:**
  - stop entries paid no extra slippage;
  - per-sleeve equity paths stuck after a re-entry, which mis-fired the daily profit lock;
  - pre-open minutes were back-filled with a future close;
  - zero-volume tick rows overwrote real 2026 bars;
  - 44 overnight bad prints were not filtered (now clamped);
  - the roll-detector's time unit was wrong, and the June 2022 roll was not adjusted;
  - pass-rate replays were biased at the end of the data.

  Every one of these is fixed and covered by tests (43 passing).

## Data (all 2020+, public GitHub copies)
| span | source | check |
|---|---|---|
| 2020-01 .. 2026-03 | `okmantz/T58-QUANT-ALGO-BACKTESTER` futures_NQ.F_1m.parquet (continuous front month) | vs `hindsight-finance/Silver-Bullet-AM-Session` nq_1m: 1.85M overlapping minutes, return corr 0.993 |
| 2026-03 .. 2026-09 | `chi2tseng/nq-replay-trainer` NQ_db_1m.json | same contract as NQ.F at the splice (ratio 1.0000) |
| 2026-09 .. 2026-10-23 | `Chief-rich/nasdaq100-data` nq_1m (Yahoo NQ=F) | identical to chi2tseng where they overlap |

Quarterly rolls are detected as a calm one-minute gap of about 1% and back-adjusted. Prices are
scaled to NQ 29,000 ($58k per MNQ). Costs: $2.00 round trip, plus 1 tick per fill, plus 1 more
tick on stop orders.

## What would actually move the needle
1. **Do not buy evaluations for these fleets.** With no edge, a pass is a 15-36% lottery
   ticket, and the funded account rarely pays (P($1k month) about 8% at zero edge).
2. **Forward-test before any money.** The only clean test left is live paper trading. Run
   the walk-forward selection each quarter on new data and act only if a fleet beats its
   zero-edge baseline for a full quarter.
3. **Look for an edge that isn't 2024's crowded momentum:**
   - order-flow and bid/ask features (`mbytes21/MNQ_DATA` has MNQ bid/ask 1m, 2019-2026);
   - other instruments for diversification (`chi2tseng/nq-replay-trainer` also has ES 1m,
     2023-2026);
   - regime filters that switch momentum off when it stops working;
   - event-day playbooks (CPI/FOMC).

   Then re-run the same factory and walk-forward unchanged.
