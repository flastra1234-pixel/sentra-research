# Reproduce the LucidFlex 25K research

Outcome: **no strategy passed final screening**. Read `REPORT.md` first. This is offline research code; it cannot place orders and is not a live trading adapter.

The download bundle contains sibling `lucid_research/` and `market_data/` directories, plus `lucid_rules.md`. Keep that layout when extracting. Python 3.12 was used.

```bash
cd lucid_research
python -m pip install -r requirements.txt
python -m unittest discover -p 'test_*.py' -v
```

The saved raw data are pinned by SHA256 in `market_data/DATA_PROVENANCE.md`. Do not refresh or overwrite them when reproducing historical results.

To rerun searches, in order:

```bash
python study.py search
python risk_sensitivity.py
python higher_tf_study.py
python time_entry_study.py
python es_study.py
python final_assessment.py
```

These commands overwrite corresponding result files. Work on a copy if preserving the original run is important. Final assessment consumes the frozen selections rather than searching the final period. The saved plans describe the original staged research, including expansions after validation failures; rerunning after knowing the results cannot recreate the original information barrier.

Optional independent accounting and minimum-payout-policy check:

```bash
python audit_final_accounting.py
```

`results_es/micro_check/` contains the unchanged strategy's actual-MES feed comparison. The micro-check script's original `/workspace` paths may require adjustment if running outside that location; the main search/final pipeline uses the sibling directory layout.

## Important model conventions

- Completed-bar signals enter at next-minute open; stops and targets anchor to the modeled fill.
- Tick size 0.25. NQ-derived MNQ uses $2/point; ES-derived MES uses $5/point.
- Round-trip fee assumption $1.24 per micro, adverse slippage one tick each side baseline / two ticks stress.
- Stop-first when one bar hits both stop and target; adverse gaps fill worse.
- Complete RTH sessions only; all indicators reset daily; no overnight exposure.
- Study P&L continues through the sample even after a hypothetical account might fail. The separate prop simulator terminates individual account paths at breaches.
- No tests here establish future profitability. Synthetic unit tests verify execution/accounting behavior only.

No API credentials, brokerage adapters, purchases, evaluations or funded accounts are part of this bundle.
