# Sentra external research snapshot

**NO VERIFIED IMPROVEMENT. Research and simulation only.**

This snapshot is prepared for private repository `flastra1234-pixel/sentra-external-research`, under `codex/sentra-snapshot-20261025/`. Repository access returned HTTP404 through both connected GitHub and CLI. Preparing a local commit is not a successful remote transfer. No default branch or other researcher's files were changed.

Start here:

- `STATUS.md` and `CHECKPOINT.json`: current mission/recovery state.
- `lucid_research/REPORT.md`: first completed strategy study and exact E028 rules/results.
- `lucid_research_v2/ASSESSMENT.md`: 12,960-configuration assessment, owner daily targets, E028 execution audit and account lifecycles.
- `sentra_research/experiments/`: preregistrations, scripts, results and derived trade logs for subsequent mechanism experiments.
- `sentra_research/DATA_ACCESS_AUDIT.md`: exact signed-flow data requirements, available data and genuine access blocker.
- `sentra_research/experiments/S006/RESULT.md`: latest completed cross-index experiment.
- `EXPORT_MANIFEST.json`: file hashes and export screening.

## Data and confidentiality

No vendor raw bars, tick/quote files, third-party decoded trade fixtures, credentials, secret stores, private account exports or T1 local files are included. Research-generated signals, simulated fills and P&L logs are included. Public-source provenance/hashes are included so an authorized reviewer can obtain matching inputs independently; inclusion of a public URL is not a grant of redistribution or access rights.

Reproduction is conditional on lawful access to the stated input data. This is not a self-contained raw-data archive. No script should purchase data or bypass entitlement checks. Four-record SDK fixtures test decoding only and cannot support trading conclusions.

## Reproduction

The original environment was Python3.12. Extract/copy the research directories into `/workspace/` preserving names, or adjust the documented absolute workspace paths before running. Install `sentra_research/requirements.txt`. Original raw inputs belong in `/workspace/market_data/` and `/workspace/market_data_v2/` with the pinned filenames/hashes; do not refresh them silently.

Once authorized inputs are in place:

```bash
cd /workspace/lucid_research_v2
python -m unittest discover -p 'test_*.py' -q
python complete_assessment.py

cd /workspace/sentra_research
python experiments/S001/run.py
python experiments/S003/run.py
python experiments/S004/run.py
OPENBLAS_NUM_THREADS=2 python experiments/S006/run.py
```

These commands overwrite their own derived results; run on a copy to preserve the committed evidence. Reserved HFD dates at/after2026-10-10 stay excluded by `load_micro.py`; do not set `allow_fresh=True` merely to reproduce spent-history work. Native ES2024 robustness samples remain unexamined.

Flow parser tests additionally need the official public Databento SDK fixture download and offline decoding described in `DATA_ACCESS_AUDIT.md`. The excluded fixture source manifest contains two provider URLs, and the audit records their hashes. Unknown trade side must remain unknown; passive order updates must not be signed as trades.

## Evidence limits

Previously examined2026 observations are researcher-consumed. Rolling chronological splits do not undo human selection. Cash gains in a diagnostic are not owner withdrawals. Evaluation/reset/hosting fees are not assumed known. No independently verified profitable strategy has been established and no claim of continued background execution is made.
