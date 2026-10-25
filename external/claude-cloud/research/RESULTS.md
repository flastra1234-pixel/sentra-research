# Strategy factory results: LucidFlex 25K fleet (2026-10-25)

Copying the "I backtested 10,000 strategies" process (mass variations, then "add features"),
with the checks the videos don't show: costs, a sealed period, parameter plateaus,
deflation against every trial, and scoring against the LucidFlex rules instead of profit.
Research only. Not financial advice, and nothing here places orders.

## Bottom line
- **175,310 strategy variants** on 4 instruments (NQ, RTY, gold, crude), about 2,958
  effectively independent tests after correlation clustering.
- **5,500 cleared every gate (3.1%).** All of them are intraday momentum: opening-range
  breakouts, noise-area momentum, last-30-minute momentum, overnight-range breakouts and
  opening drive. Mean reversion (VWAP, RSI(2), gap fade, time-of-day) failed everywhere.
  So did crude, and gold only "passed" after filters were added (rejected, see lessons).
- **Fleet v1: 7 NQ sleeves, 1 MNQ each.** Frozen on 2008-2018, then run once on data it had
  never seen:

| period | sessions | annual Sharpe | $/day | max DD | worst intraday | Lucid pass (bootstrap / replays) | paid >= $1k in 2 funded months |
|---|---|---|---|---|---|---|---|
| in-sample 2008-18 | 2,645 | 2.60 | 56.9 | -$4,808 | -$998 | 54% / 57% | 35% |
| **sealed 2019 to 2020-05** | 337 | **1.65** (t 1.91, p 0.022) | 36.1 | -$3,147 | -$1,161 | **44% / 47%** | 25% |
| real NQ futures Aug-Oct 2026 | 60 | 0.68 (t 0.33) | 17.4 | -$3,061 | -$585 | 28% / 18% | 12% |

Pass = $1,250 target before the $1,000 EOD-trailing floor, 50% consistency, within 60
sessions; intraday breach uses the measured worst mark of each day. At 40% consistency,
pass drops about 5 points (sealed 39%). Replays start an evaluation on every session.

**Verdict: a real but modest edge, not a winner yet.** The sealed 2019-20 test was
profitable in both years, including the 2020 crash, and significant at p 0.022. The
fleet-engine verdict is "consistent" (not "confirmed": Sharpe minus 2 SE is just below 0).
The most recent 60 sessions of real futures were weak (choppy, about 0.6% overnight gaps),
and 60 sessions is too short to separate a regime from noise (SE of annual Sharpe about 2).

Rough economics per evaluation bought (P(pass) x mean owner payout over 2 funded months,
before the one-time fee of about $89-149): in-sample $448, sealed $271, 2026 $104. That is
positive in 2019-20 conditions and about break-even in the 2026 sample.

## The fleet (v1, 7 micros, no daily stop)
Times are ET. The OR (opening range) is the high/low from 09:30. Trend = prior close vs its 20-day
average. ATR = 14-day average true range (regular session) as a % of price. "Gap day" =
|open - prior close| >= 0.25 ATR. NR7/inside = prior session was the narrowest of 7 or an
inside day. One trade per sleeve per day unless noted. Stops and targets are resting orders.

| # | sleeve | trade only when | entry | stop / exit | sharpe in / sealed / 2026 |
|---|---|---|---|---|---|
| 1 | ORB-15 counter-trend | gap day, ATR <= 2.0% | stop order at 15-min OR high/low until 13:30, only against the trend | 0.15 ATR stop, 3R target, breakeven after a 1R close, out 15:55 | 1.63 / 0.83 / -1.76 |
| 2 | ORB-30 short | after NR7/inside, ATR <= 2.5% | sell stop at 30-min OR low until 12:00 | stop 0.5 x OR width, 1R target, out 12:00 | 1.37 / -0.08 / -0.73 |
| 3 | ORB-15 long | after NR7/inside | buy stop at 15-min OR high until 11:00 | 0.15 ATR stop, 3R target, breakeven after 1R, out 12:00 | 1.25 / 1.44 / 0.92 |
| 4 | Noise-area momentum | gap day, ATR <= 2.0% | at 10:30, 11:30 ... 15:30: close beyond open x (1 +/- 0.6 x 20-day avg move-from-open at that minute), with the trend | exit when a 1-min close crosses VWAP, re-entry allowed, flat 16:00 | 1.24 / 0.87 / 1.36 |
| 5 | ORB-60 | every day | stop orders at 60-min OR high/low until 13:30 | 0.15 ATR stop, 3R target, breakeven after 1R, out 15:55 | 1.13 / 0.73 / 1.16 |
| 6 | ORB-5 long counter-trend | ATR5/ATR50 >= 0.9, ATR <= 1.5%, trend down | buy stop at 5-min OR high until 12:00 | 0.15 ATR stop, breakeven after 1R, out 12:00 | 1.12 / 0.70 / 1.56 |
| 7 | Last-30-min momentum | not Monday, ATR <= 1.5% | 15:30, in the direction of prior close to 10:00 if it agrees with the trend | 0.3 ATR stop, out 16:00 | 1.06 / 0.68 / -1.11 |

Exact parameters: `research/results/fleet.json`; code: `research/factory/engine.py`.
Risk note: the worst single day reached -$998 (in-sample) and -$1,161 (sealed) intraday at
7 micros, about the whole $1,000 cushion. A fleet daily stop of $600 cost little in-sample
(J 0.150 vs 0.162) and is the safer way to run it.

## What the failures taught, and what each lesson changed
1. **Momentum works, fading doesn't.** In every family, following the move beat fading it, and
   trading with the 20-day trend beat trading against it. That narrowed round 2 to momentum.
2. **The best discovery scores were luck.** Of the 70 strategies with discovery t-stat
   above 3.5 (57 of them 60-minute ORB variants), 64 died in 2017-18 validation. That is why
   there is a parameter-plateau gate and a separate validation period.
3. **Crash days kill prop accounts.** Survivors' median worst intraday mark was -$1,164 per
   micro (2008-style days at today's NQ price), more than the whole $1,000 drawdown. Round 2
   added ATR caps (skip sessions when ATR > 1.5 / 2.0 / 2.5%), and the fleet pool requires a
   worst mark above -$900.
4. **Gap days and narrow-range days carry the ORB edge.** These filters survived validation
   most often (`gap_large`, `nr7_or_inside`).
5. **Features can't rescue a failed idea.** Gold had zero round-1 survivors, then 93 appeared
   once filters were tried (only 1.1% of discovery passers held in validation, against about
   16% expected by chance). Rule adopted before unsealing: a round-2 variant counts only if its
   base family passed validation on that instrument in round 1.
6. **Pass rate is capped by Sharpe.** Under a $1,000 trailing drawdown, a daily Sharpe of
   0.10-0.16 tops out around 45-55% pass. Sizing per phase (smaller in the evaluation, since
   Lucid has no deadline, and bigger when funded) lifted in-sample pass to 74%, but it
   **did not survive** the sealed test (sealed 48%; 2026 replays 2%). So it is reported, not recommended.
7. **More markets didn't diversify.** RTY ideas were the same momentum bet as NQ (the fleet
   took one RTY sleeve and J did not improve: 0.155 vs 0.162). Crude: nothing survived. ES:
   the free CFD data is too sparse (often 10-30% of cash-session minutes missing) to test.

## Funnel
| instrument | round 1 | round 2 | survived | effective tests |
|---|---|---|---|---|
| NQ (MNQ) | 17,808 (228 pass) | 70,809 | 5,321 | 1,398 |
| RTY (M2K) | 17,808 (16 pass) | 9,617 | 86 | 635 |
| Gold (MGC) | 17,808 (0 pass) | 23,652 | 93 (rejected, lesson 5) | 594 |
| Crude (MCL) | 17,808 (0 pass) | none | 0 | 331 |

No single strategy clears a deflated Sharpe of 0.95 against all trials (best NQ 0.895).
The evidence rests on the fleet's out-of-sample record above.

## Data and assumptions (read before trading anything)
- In-sample/sealed data is the Oanda NAS100 CFD (tracks the cash index, not futures). Only
  the 2026 holdout is real NQ futures, and it is just 60 usable sessions.
- Every move is priced at NQ 29,000 ($58k per MNQ). Costs: $2.00 round trip + 1 tick per
  fill + 1 extra tick on stops. Fills are conservative (stop wins ties; signals fill at the next bar).
- RTY/gold/crude price levels are assumptions for late 2026 (no 2026 data here).
- Lucid terms vary across third-party reviews (consistency 40% vs 50%, contract tiers).
  Both consistency readings are reported; check the current terms on Lucid's site.
- The sealed period has now been looked at twice (v1, then v1.1). Nothing remains untouched
  except live forward data.

## Next steps that would actually move the needle
1. **Forward-test v1 on a Lucid sim or paper account** for 40-60 sessions. That is the only clean test left.
2. **Run the factory on your own MNQ export** (`~/fleet-data`, 2012-24 futures with measured
   costs) and on 2021-2025 data, which is missing here. 2021-22 was a very different regime.
3. **Look for uncorrelated edges, not more ORB variants.** Pass rate is capped by fleet Sharpe,
   and every survivor here is the same momentum bet. Candidates are other sessions (overnight /
   Europe open) and event-driven setups (CPI/FOMC days), tested with the same gates.
