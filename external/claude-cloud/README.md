# Claude Cloud research snapshot: LucidFlex 25K intraday NQ research

Research only. Nothing here places, modifies or cancels orders. It is for review before any
integration into Sentra. No deployment and no real-money trading.

## Provenance
| part | source |
|---|---|
| `research/` | `ucmyg/sentra`, branch `claude/loving-pasteur-l8jz7t`, commit `6c9ce8d`; folder `research/`, git-tracked files only |
| `deps/sentra-fleet-engine/fleet_engine/` | `ucmyg/sentra-fleet-engine` at `55cb989`. Three files only: the LucidFlex rule engine (`rules.py`) and deflated Sharpe (`deflate.py`), which the factory imports (`research/factory/lucid.py`) |
| `data-provenance/` | manifests (sources, pinned commits, hashes, checks) for the external datasets used in the goal70 round. The data itself is **not** included |

`SHA256SUMS` lists a hash for every file in this folder.

## Reports, newest first
1. **`research/RESULTS_goal70.md`**: the current goal, "net $100-150 on 70% of eligible days with
   sustainable LucidFlex 25K payouts". It covers:
   - what the goal costs under the actual rules;
   - whether any tested strategy or fleet approaches it;
   - why the 2020-2024 edge faded in 2025-2026;
   - pre-registered tests of new information: CPI/NFP/FOMC days and SPY confirmation;
   - per-evaluation payout economics;
   - verified results listed separately from preliminary ones.
2. **`research/PREREGISTRATION.md`** and **`research/PREREGISTRATION_round2.md`**: hypotheses and
   pass criteria for the two rounds of new-information tests, each committed before its tests
   were run.
3. **`research/PREREGISTRATION_forward.md`**: the frozen forward test (`factory/forward.py`) on
   sessions after 2026-10-23. It was committed before any of those sessions existed.
4. **`research/RESULTS_2020plus.md`**: 2020+ NQ on the real Lucid session (18:00-16:44 ET).
   Covers the 111,960-variant search, the walk-forward process test, fleets and unsealing.
5. **`research/RESULTS.md`**: v1, NAS100 CFD 2005-2020 (superseded by the 2020+ work).

**Bottom line.** No strategy tested reaches the 70%-of-days goal, even in-sample. The goal needs
an annualised Sharpe of about 6-10 with losing days capped near $100-150. The best edge found
was about 1.2-2.3, and it faded in 2025-2026. Seven pre-registered hypotheses, in two rounds,
were tested on 2020-2024. None qualified, so 2025-2026 was not used for them. Two came close
(QQQ leadership and overnight agreement, p 0.018 and 0.027) and are listed as preliminary
forward-test candidates. The report recommends **not**
buying an evaluation, and gives a forward-test protocol.

## Layout
```
research/
  factory/            strategy factory, Lucid-session engine, fleets, walk-forward, goal70 tools
  tests/              55 unit tests (synthetic data; no market data needed)
  results/            result JSONs behind every report table (goal70.json = RESULTS_goal70.md)
  *.md                reports and the pre-registration
deps/sentra-fleet-engine/fleet_engine/   LucidFlex rules + deflated Sharpe (imported, not modified)
data-provenance/      external-data manifests (VIX, economic calendar, SPY/QQQ 1-minute)
```

## Run the tests (no data needed)
```
cd external/claude-cloud/research
pip install numpy pandas scipy numba pytest pyarrow
FLEET_ENGINE_DIR=../deps/sentra-fleet-engine python -m pytest -q tests
```

## Reproduce the reports (data needed, not included)
Market data is not committed. The code expects these locations:
- **Session caches:** `FACTORY_DATA_DIR`, default `../sentra-data`. They are built from the
  public GitHub copies of NQ 1-minute bars listed in `research/factory/lx_sources.py` and
  `RESULTS_2020plus.md`.
- **External sets:** `/home/user/sentra-data/raw/ext/{vix,calendar,etf1m}`.
  `data-provenance/` lists every source and hash for them.

Then:
```
cd external/claude-cloud/research
FLEET_ENGINE_DIR=../deps/sentra-fleet-engine PYTHONPATH=. python -m factory.goal70_report
```
That regenerates `results/goal70.json`. The pipeline commands for the earlier reports are in
`research/factory/README.md`.

## Validation conventions
- **Chronological splits.** Design is 2020-2024. 2025-2026 had already been examined in
  `RESULTS_2020plus.md`, so it is never used to select or tune anything.
- **Costs.** $2 round trip, plus 1 tick per fill, plus 1 extra tick on stops. Every trade is
  priced at NQ 29,000.
- **Rules.** Accounts are simulated with the sentra-fleet-engine LucidFlex rules: $1,000
  end-of-day trailing drawdown with intraday breach, the floor lock, 5 qualifying days, the
  $500 minimum request and the 90% split.
- **Multiple testing.** Holm correction, within-year permutation tests, effective trial counts
  and deflated Sharpe.

## Data policy
This folder contains no credentials, raw market data or vendor files. It holds code, derived
statistics and source manifests only.
