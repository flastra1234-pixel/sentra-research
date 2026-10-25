"""Stage 5: deflated Sharpe (Bailey & Lopez de Prado), verdicts, trial log."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import kurtosis, norm, skew

EULER_GAMMA = 0.5772156649


def expected_max_sharpe(n_trials: int, var_trials: float) -> float:
    """SR0 = sqrt(V) [(1-g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e))]."""
    if n_trials < 2:
        return 0.0
    g = EULER_GAMMA
    return float(np.sqrt(var_trials) * ((1 - g) * norm.ppf(1 - 1 / n_trials)
                                        + g * norm.ppf(1 - 1 / (n_trials * np.e))))


def deflated_sharpe(pnl, n_trials: int, var_trials: float) -> float:
    p = np.asarray(pnl, float)
    n = len(p)
    s = p.mean() / p.std(ddof=1)
    sk = skew(p)
    ku = kurtosis(p, fisher=False)          # normal = 3
    sr0 = expected_max_sharpe(n_trials, var_trials)
    denom = np.sqrt(1 - sk * s + (ku - 1) / 4 * s * s)
    return float(norm.cdf((s - sr0) * np.sqrt(n - 1) / denom))


def verdict(s_oos: float, se_oos: float, s_oof: float, beats_best_single: bool) -> str:
    if s_oos - 2 * se_oos > 0 and beats_best_single:
        return "confirmed"
    if s_oos < s_oof - 2 * se_oos:
        return "contradicted"
    return "consistent"


class TrialLog:
    """Append-only JSONL. Every candidate, the stage it stopped at, and why."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, candidate_id: str, spec: dict, stage: str, reason: str, **metrics) -> None:
        row = {"ts": datetime.now(timezone.utc).isoformat(), "id": candidate_id,
               "spec": spec, "stopped_at": stage, "reason": reason, **metrics}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=float) + "\n")

    def rows(self):
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x]

    def n_trials(self) -> int:
        return len({r["id"] for r in self.rows()})
