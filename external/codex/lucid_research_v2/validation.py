"""Validation and risk utilities for the second Lucid research batch.

These utilities do not make already-inspected dates fresh. Rolling tests on
previously seen history are pseudo-out-of-sample and retain researcher-level
selection bias. Bootstrap diagnostics require their own stationarity assumptions
and do not certify profitability, executable fills, or future payouts.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_dates: tuple[str, ...]
    validation_dates: tuple[str, ...]
    test_dates: tuple[str, ...]

    def as_dict(self, include_dates: bool = True) -> dict:
        if include_dates:
            return asdict(self)
        out = {"fold_id": self.fold_id}
        for label in ["train", "validation", "test"]:
            dates = getattr(self, f"{label}_dates")
            out[f"{label}_start"] = dates[0]
            out[f"{label}_end"] = dates[-1]
            out[f"{label}_sessions"] = len(dates)
        return out


def rolling_folds(session_dates: Iterable, train_sessions: int = 120,
                  validation_sessions: int = 30, test_sessions: int = 30,
                  step_sessions: int = 30,
                  min_train_sessions: int | None = None,
                  allow_overlapping_tests: bool = False) -> list[Fold]:
    """Chronological rolling train -> validation -> test session windows.

    Training uses at most ``train_sessions`` immediately preceding validation
    dates. ``min_train_sessions`` permits shorter initial training if explicitly
    chosen before research; omitted means a full fixed training window. Only
    complete test windows are returned. Different folds may reuse earlier test
    dates for later training, as a prospective rolling procedure would.
    """
    lengths = [train_sessions, validation_sessions, test_sessions, step_sessions]
    if any(not isinstance(v, (int, np.integer)) or v < 1 for v in lengths):
        raise ValueError("Window lengths must be positive integers")
    minimum = train_sessions if min_train_sessions is None else min_train_sessions
    if not isinstance(minimum, (int, np.integer)) or not 1 <= minimum <= train_sessions:
        raise ValueError("min_train_sessions must be in 1..train_sessions")
    if not allow_overlapping_tests and step_sessions < test_sessions:
        raise ValueError("Overlapping test windows require explicit opt-in")
    dates = sorted({pd.Timestamp(d).date().isoformat() for d in session_dates})
    out = []
    first_test = minimum + validation_sessions
    for start in range(first_test, len(dates) - test_sessions + 1, step_sessions):
        val_start = start - validation_sessions
        train_start = max(0, val_start - train_sessions)
        train = tuple(dates[train_start:val_start])
        val = tuple(dates[val_start:start])
        test = tuple(dates[start:start + test_sessions])
        assert train[-1] < val[0] <= val[-1] < test[0]
        out.append(Fold(len(out) + 1, train, val, test))
    return out


def risk_quantity(stop_points, point_value: float, risk_budget: float,
                  roundtrip_fee: float = 1.24, slippage_ticks: float = 2.,
                  tick_size: float = .25, max_contracts: int = 10):
    """Integer quantity from ex-ante stop risk plus conservative friction.

    This adds two adverse slippage allowances even when the execution model
    anchors its stop to the realized entry, intentionally reserving extra room.
    Budget is a fixed strategy input, not raised after losses. Quantity zero
    means skip: one micro already exceeds the budget. A 10-micro cap stays under
    the most restrictive LucidFlex25K funded tier; portfolio-wide exposure still
    needs a separate central limit and current account-floor checks.
    """
    if point_value <= 0 or risk_budget <= 0 or tick_size <= 0:
        raise ValueError("point_value, risk_budget and tick_size must be positive")
    if roundtrip_fee < 0 or slippage_ticks < 0:
        raise ValueError("Costs cannot be negative")
    if not isinstance(max_contracts, (int, np.integer)) or max_contracts < 1:
        raise ValueError("max_contracts must be a positive integer")
    s = np.asarray(stop_points, dtype=float)
    friction = roundtrip_fee + 2 * slippage_ticks * tick_size * point_value
    per_contract = s * point_value + friction
    valid = np.isfinite(s) & (s > 0)
    denominator = np.where(valid, per_contract, np.inf)
    qty = np.floor(risk_budget / denominator).clip(0, max_contracts).astype(np.int64)
    return int(qty) if qty.ndim == 0 else qty


def _block_indices(n: int, n_samples: int, block_length: int,
                   rng: np.random.Generator) -> np.ndarray:
    block = min(block_length, n)
    starts = rng.integers(0, n,
                          size=(n_samples, int(np.ceil(n / block))))
    return ((starts[:, :, None] + np.arange(block)) % n).reshape(n_samples, -1)[:, :n]


def moving_block_bootstrap_mean_ci(daily_pnl: Sequence[float],
                                  block_length: int = 5, n_boot: int = 2000,
                                  confidence: float = .95,
                                  seed: int = 20261025) -> dict:
    """Percentile mean interval and centered-null one-sided bootstrap p-value.

    Feed every observed trading session, including zero-trade days. Circular
    blocks preserve uniform marginal sampling. No missing rows or nonfinite
    values are accepted. At least20 observations and at least two block lengths
    are required, though far longer histories are preferable. This is a single-
    series diagnostic; it does not correct for searching thousands of configs.
    """
    x = np.asarray(daily_pnl, dtype=float)
    if block_length < 1 or n_boot < 1 or not 0 < confidence < 1:
        raise ValueError("Invalid bootstrap parameters")
    if x.ndim != 1 or len(x) < max(20, 2 * block_length) or not np.isfinite(x).all():
        raise ValueError("Need >=20 finite daily observations and >=2 full block lengths")
    rng = np.random.default_rng(seed)
    samples = x[_block_indices(len(x), n_boot, block_length, rng)].mean(axis=1)
    mean = float(x.mean())
    alpha = (1 - confidence) / 2
    lower, upper = np.quantile(samples, [alpha, 1 - alpha])
    # The residual series is centered at zero under a no-positive-mean null.
    null_means = samples - mean
    p = (1 + np.count_nonzero(null_means >= mean - 1e-12)) / (n_boot + 1)
    return {
        "sessions": len(x), "mean_daily_pnl": mean,
        "confidence": confidence, "ci_low": float(lower),
        "ci_high": float(upper), "centered_bootstrap_p_value": float(p),
        "block_length": min(block_length, len(x)), "bootstrap_samples": n_boot,
        "note": "Single-series stationary-block diagnostic; not search-adjusted or fresh holdout evidence."
    }


def shared_block_max_t_test(daily_pnl_matrix: np.ndarray,
                            block_length: int = 5, n_boot: int = 1000,
                            seed: int = 20261025, batch_size: int = 32) -> dict:
    """Exploratory data-snooping check over ALL searched candidate columns.

    Matrix is sessions x candidates, with aligned zero-trade days. The same
    sampled blocks are used across all columns to retain cross-strategy
    dependence. Candidate means are centered under the null. Studentization uses
    a Bartlett HAC standard error with lag block_length-1. Familywise p-values
    compare each observed t to the bootstrapped MAX t across the full grid.

    This is not a full implementation of White's Reality Check or Hansen SPA;
    it is a transparent max-statistic diagnostic. Including only a
    selected shortlist understates the search; history consumed through human
    iteration still invalidates claims of a fresh prospective test.
    """
    x = np.asarray(daily_pnl_matrix, dtype=float)
    if block_length < 1 or n_boot < 1 or batch_size < 1:
        raise ValueError("Bootstrap sizes must be positive")
    if x.ndim != 2 or x.shape[0] < max(20, 2 * block_length) or x.shape[1] < 1 or not np.isfinite(x).all():
        raise ValueError("Need an aligned matrix with >=20 finite sessions and >=2 full blocks")
    n, k = x.shape
    means = x.mean(axis=0)
    centered = x - means
    lags = min(block_length - 1, n - 1)
    variance = np.mean(centered * centered, axis=0)
    for lag in range(1, lags + 1):
        cov = np.mean(centered[lag:] * centered[:-lag], axis=0)
        variance += 2 * (1 - lag / (lags + 1)) * cov
    se = np.sqrt(np.maximum(variance, 0) / n)
    # An all-zero column has no edge and must not generate numerical evidence.
    zero_column = np.all(np.abs(x) <= 1e-12, axis=0)
    se = np.where(se > 1e-12, se, 1e-12)
    observed_t = means / se
    observed_t[zero_column] = 0
    rng = np.random.default_rng(seed)
    null_max = np.empty(n_boot)
    for first in range(0, n_boot, batch_size):
        b = min(batch_size, n_boot - first)
        indices = _block_indices(n, b, block_length, rng)
        counts = np.stack([np.bincount(row, minlength=n) for row in indices]) / n
        null_t = (counts @ centered) / se
        null_t[:, zero_column] = 0
        null_max[first:first + b] = np.maximum(0, null_t.max(axis=1))
    best_t = max(0., float(observed_t.max()))
    adjusted = (1 + (null_max[:, None] >= observed_t[None, :] - 1e-12).sum(axis=0)) / (n_boot + 1)
    global_p = (1 + np.count_nonzero(null_max >= best_t - 1e-12)) / (n_boot + 1)
    return {
        "sessions": n, "candidate_count": k,
        "best_candidate_index": int(np.argmax(observed_t)),
        "observed_t": observed_t.tolist(),
        "familywise_adjusted_p_values": adjusted.tolist(),
        "global_p_value": float(global_p), "bootstrap_samples": n_boot,
        "block_length": min(block_length, n),
        "note": "Exploratory shared-block max-t diagnostic over supplied candidates; not independent holdout proof."
    }


def family_plateau_support(scores: pd.DataFrame, configs: list[dict],
                           metric: str = "stress_net",
                           param_keys: Sequence[str] = (),
                           id_key: str = "id", family_key: str = "family",
                           positive_threshold: float = 0.,
                           ignore_keys: Sequence[str] = ("id", "source_config_id")) -> pd.DataFrame:
    """Local one-grid-step neighbor support, not independent replications.

    Neighbors match every other configuration field and differ in exactly one
    declared parameter by one adjacent grid value. Both higher and lower values
    count. Supply one score row per ID (aggregate folds before calling).
    Missing neighbor results are not silently counted as positive.
    """
    if id_key not in scores or metric not in scores:
        raise ValueError("scores must contain candidate ID and requested metric")
    if scores[id_key].duplicated().any():
        raise ValueError("Aggregate to one score row per candidate first")
    score_map = dict(zip(scores[id_key], pd.to_numeric(scores[metric], errors="coerce")))
    ignored = set(ignore_keys) | {id_key}
    keys = sorted(set().union(*(c.keys() for c in configs)) - ignored)
    def sig(c):
        return tuple((key, json.dumps(c.get(key), sort_keys=True)) for key in keys)
    lookup = {}
    for c in configs:
        lookup.setdefault(sig(c), []).append(c[id_key])
    axes = {}
    for c in configs:
        fam = c.get(family_key)
        for key in param_keys:
            if key in c:
                axes.setdefault((fam, key), set()).add(c[key])
    for axis, values in axes.items():
        try:
            axes[axis] = sorted(values)
        except TypeError:
            axes[axis] = sorted(values, key=lambda z: json.dumps(z, sort_keys=True))
    rows = []
    for c in configs:
        ids = set()
        for key in param_keys:
            if key not in c:
                continue
            vals = axes[(c.get(family_key), key)]
            loc = vals.index(c[key])
            for j in [loc - 1, loc + 1]:
                if 0 <= j < len(vals):
                    other = dict(c, **{key: vals[j]})
                    ids.update(lookup.get(sig(other), []))
        ids.discard(c[id_key])
        values = [float(score_map[i]) for i in ids if i in score_map and np.isfinite(score_map[i])]
        rows.append({
            id_key: c[id_key], family_key: c.get(family_key),
            "neighbor_configurations": len(ids), "neighbors_with_scores": len(values),
            "positive_neighbor_fraction": float(np.mean(np.array(values) > positive_threshold)) if values else np.nan,
            "median_neighbor_metric": float(np.median(values)) if values else np.nan,
            "lower_quartile_neighbor_metric": float(np.quantile(values, .25)) if values else np.nan,
            "note": "Correlated neighboring parameters; not independent confirmations."
        })
    return pd.DataFrame(rows)
