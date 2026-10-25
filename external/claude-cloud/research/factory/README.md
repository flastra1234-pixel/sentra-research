# Strategy factory (LucidFlex 25K)

Mass-generates intraday MNQ strategy variants, backtests them on 1-minute data, gates them,
learns from the failures, builds a fleet for one LucidFlex 25K account and judges it on
data it never saw. It is the upstream of `ucmyg/sentra-fleet-engine`: the LucidFlex rule
engine (`run_eval`, `run_funded`) and deflated Sharpe are imported from there, not copied.

Research only. Nothing here places, modifies or cancels an order.

## Data (not committed)
| set | source | span | role |
|---|---|---|---|
| NAS100 CFD 1m | Oanda via github.com/FutureSharks/financial-data | 2005-01 .. 2020-05 | discovery 2008-16, validation 2017-18, sealed test 2019 .. 2020-05 |
| NQ=F futures 1m | Yahoo via github.com/Chief-rich/nasdaq100-data | 2026-07-02 .. 2026-10-23 | final holdout (real futures) |
| US2000 / XAU / WTICO CFD 1m | Oanda, same repo as NAS100 | 2005/06 .. 2020-05 | RTY / gold / crude sleeves (SPX500 too sparse) |

The CFD tracks the Nasdaq-100 cash index, so percent moves match NQ but levels do not.
Every trade is priced at today's level (`REF_PRICE` 29,000, $2/pt, 1 micro): a 1% move in
2010 is charged as a 1% move of a 29,000 contract. Costs: $2.00 round trip + 1 tick per
fill + 1 more tick on stop exits. Fills are conservative (next-bar open on close signals,
stop wins when a bar touches stop and target, entry bar checked against the stop).

## Pipeline
```
python -m factory.data        # build session caches (FACTORY_DATA_DIR, default ../sentra-data)
python -m factory.rounds      # round 1 grid -> gates -> round 2 "add features" -> candidates.json
python -m factory.fleet       # v1 fleet: greedy micros, J = P(pass 60) x P(paid >= $1k in 42)
python -m factory.fleet --phased   # v1.1: separate eval / funded fleets (no eval deadline)
python -m factory.unseal [--phased]  # sealed 2019-20 + NQ 2026, exact intraday lows
python -m factory.data us2000 xau wti     # other instruments (Oanda CFDs, 2005-2020)
python -m factory.rounds rty gc cl        # their round 1 + 2
python -m factory.rounds --combine nq rty gc cl   # deflate everyone against all trials
python -m factory.fleet nq rty [--phased]         # cross-instrument pool
python -m pytest -q tests     # engine arithmetic, stops, marks, no lookahead
```
Paths: `NAS100_SRC`, `NQ2026_SRC`, `FLEET_ENGINE_DIR`, `FACTORY_DATA_DIR` (defaults are
sibling folders of this repo).

| file | role |
|---|---|
| `data.py` | 1m bars -> 390-bar ET sessions + overnight range |
| `features.py` | decision-time daily features, VWAP, noise-area sigma |
| `engine.py` | numba families: ORB, noise-area momentum, intraday momentum, gap, VWAP reversion, prior-day/overnight levels, time-of-day, opening drive, 5m RSI(2) |
| `strategies.py` | round-1 grid, day filters, round-2 generator, stable spec ids |
| `sweep.py` | runs specs; sealed/holdout results go to a separate file only `unseal.py` reads |
| `select.py` | gates, parameter-plateau check, validation, effective trial count, trial log |
| `fleet.py` | pool (one per correlation cluster), greedy fleet with LucidFlex scoring |
| `unseal.py` | one-shot evaluation on sealed + holdout, replays from every start date |

## Gates (discovery unless noted)
200+ trades; t >= 2.0; profit factor >= 1.10; avg trade >= $5; 6 of 9 years positive and
both halves positive; median t of one-step parameter neighbours >= 1.0 with 60% positive;
2017-18 t >= 1.0 and mean > 0. Deflation N = number of correlation clusters (rho > 0.5)
over all trials ever run, not the raw count.

Results: `research/results/` and `research/RESULTS.md` (v1, 2005-2020 CFD data).

## 2020+ on the Lucid session (`lx_*`)
Lucid trades Sunday-Friday 18:00-16:45 ET and allows no position through 16:45, so v2 lays
every day out as one 1,365-bar session (18:00 ET the evening before through 16:44) and every
strategy is flat by the 16:44 bar. Only 2020+ data is used.

| file | role |
|---|---|
| `lx_sources.py` | NQ 1m 2020-01 .. 2026-10 from public GitHub copies, spliced on overlapping bars, quarterly rolls detected as a calm one-minute gap and back-adjusted, overnight bad prints clamped |
| `lx_data.py` | 18:00-16:44 sessions; halt days and half days kept; fills only on real prints |
| `lx_features.py` | decision-time features, each with the bar it becomes available (gap / overnight range only from 09:30) |
| `lx_engine.py` | breakouts / fades of any window (cash open, overnight, Asia->London, London, pre-08:30), noise-area momentum, end-of-day momentum, timed holds (incl. overnight drift), drives, 09:30 gap; win/loss tallies |
| `lx_strategies.py` | grids, availability-checked filters, round-2 generator |
| `lx_run.py` | sweeps, gates, fleets scored on the account goals, daily stop / profit-lock overlays on exact minute paths, `journey()` (evaluation then funded, time to first payout), unseal |
| `lx_walkforward.py` | the process test: select on years before Y, trade Y blind, for Y = 2023..2026 |

```
python -m factory.lx_run prepare nq20      # sessions (needs FACTORY_RAW_DIR with the source files)
python -m factory.lx_run rounds nq20       # round 1 + round 2, gates, candidates
python -m factory.lx_run fleet2 nq20       # eval / funded fleets with overlays (2020-2024 only)
python -m factory.lx_run unseal2 nq20      # sealed 2025-01..2026-02 and holdout 2026-03..10
python -m factory.lx_walkforward nq20      # walk-forward, 2023-2026
```
Splits: discovery 2020-2023, validation 2024, sealed 2025-01-02..2026-02-27, holdout
2026-03-02..2026-10-23 (2026-07..10 was already looked at by v1). Results:
`research/RESULTS_2020plus.md`.

## The "70% of days" account goal (`goal70`, `lx_diag`, `lx_newinfo`, `lx_prereg`)
Can any strategy deliver net $100-150 on 70% of days with LucidFlex 25K survival and $1,000+ a
month? What does that need, why did the 2020-2024 edge fade, and does any new information
(10:00 ET features, VIX, CPI/NFP/FOMC calendar, SPY 1-minute) predict better days?

| file | role |
|---|---|
| `goal70.py` | daily profile on eligible / all days (hit rates, streaks, drawdown), funded simulator with a payout buffer (reproduces fleet_engine `run_funded` at buffer 0), lock/stop frontier |
| `lx_diag.py` | per-session market structure (trend days, variance ratios, opening-range follow-through, gap fills) |
| `lx_newinfo.py` | 10:00 ET features and labels, chronological feature scans (year-stratified AUC, within-year permutation, Holm) |
| `lx_prereg.py`, `lx_prereg2.py` | the tests in `research/PREREGISTRATION.md` and `PREREGISTRATION_round2.md`, and the single 2025-26 look (runs only for qualified hypotheses) |
| `goal70_report.py` | regenerates every table into `research/results/goal70.json` |
| `forward.py` | frozen forward test on sessions after 2026-10-23 (`research/PREREGISTRATION_forward.md`); writes `research/results/forward.json` |

```
PYTHONPATH=. python3 -m factory.goal70_report [feasibility existing overlays walkforward diagnostics newinfo canonical scorecard prereg prereg2]
```
External data (not committed, under `FACTORY_RAW_DIR/ext`, each folder with a manifest of
sources and hashes): `vix/` (VIX, VIX9D, VIX3M, VVIX, VXN daily), `calendar/` (CPI, NFP,
FOMC, PPI, PCE, GDP, retail sales with release times, 2020-2026), `etf1m/` (SPY and QQQ
consolidated-tape 1-minute bars). Results: `research/RESULTS_goal70.md`.
