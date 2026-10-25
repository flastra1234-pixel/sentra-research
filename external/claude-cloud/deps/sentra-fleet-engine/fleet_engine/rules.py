"""LucidFlex 25K rule engine, vectorised over paths. Shared by both simulation engines.

Intraday breach: either a measured intraday low per session (bootstrap engine), or the
Brownian-bridge probability with the session's sigma (exact for one step per session,
since the floor only moves at the close)."""
from dataclasses import dataclass, replace

import numpy as np


@dataclass(frozen=True)
class Rules:
    start: float = 25_000.0
    max_loss: float = 1_000.0          # D, trails the highest close
    lock_offset: float = 100.0         # floor never above start + 100
    target: float = 1_250.0            # T (run 1,250 and 1,500)
    consistency: float = 0.50          # largest win <= this share of profit (help center: 0.40 w/o add-on)
    eval_sessions: int = 10
    qual_pnl: float = 100.0
    qual_days: int = 5
    max_request: float = 1_000.0
    min_request: float = 500.0
    payout_frac: float = 0.50          # of profit above the starting balance (default reading)
    split: float = 0.90
    funded_sessions: int = 21
    owner_goal: float = 1_000.0

    def with_target(self, t: float) -> "Rules":
        return replace(self, target=t)


def _breached(x0, x1, floor, sig, low, u):
    if low is not None:
        return (x0 + low <= floor) | (x1 <= floor)
    a = np.clip(x0 - floor, 0.0, None)
    b = np.clip(x1 - floor, 0.0, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(sig > 0, np.exp(-2.0 * a * b / np.square(np.where(sig > 0, sig, 1.0))), 0.0)
    return (x1 <= floor) | (u < p)


def _col(arr, t):
    return None if arr is None else arr[:, t]


def run_eval(pnl, rules: Rules, sig=None, low=None, u=None) -> np.ndarray:
    """Boolean pass per path within rules.eval_sessions. pnl: paths x sessions."""
    paths = pnl.shape[0]
    bal = np.full(paths, rules.start)
    high = bal.copy()
    alive = np.ones(paths, bool)
    passed = np.zeros(paths, bool)
    max_win = np.zeros(paths)
    for t in range(min(rules.eval_sessions, pnl.shape[1])):
        floor = np.minimum(high - rules.max_loss, rules.start + rules.lock_offset)
        x1 = bal + pnl[:, t]
        live = alive & ~passed
        alive &= ~(live & _breached(bal, x1, floor, _col(sig, t), _col(low, t), _col(u, t)))
        act = alive & ~passed
        bal = np.where(act, x1, bal)
        high = np.where(act, np.maximum(high, bal), high)
        max_win = np.where(act, np.maximum(max_win, pnl[:, t]), max_win)
        profit = bal - rules.start
        passed |= act & (profit >= rules.target) & (max_win <= rules.consistency * profit)
    return passed


def run_funded(pnl, rules: Rules, sig=None, low=None, u=None, cushioned: bool = False):
    """One funded month. Returns (owner_net, qualifying_days, payouts) per path.
    Fresh: balance at start, floor start - D. Cushioned: floor locked, balance floor + D.
    First approved payout locks the floor at start + lock_offset (harsher reading)."""
    paths = pnl.shape[0]
    locked_floor = rules.start + rules.lock_offset
    bal = np.full(paths, locked_floor + rules.max_loss if cushioned else rules.start)
    high = bal.copy()
    locked = np.full(paths, cushioned)
    alive = np.ones(paths, bool)
    qd = np.zeros(paths, int)
    qd_total = np.zeros(paths, int)
    cycle = np.zeros(paths)
    owner = np.zeros(paths)
    payouts = np.zeros(paths, int)
    for t in range(min(rules.funded_sessions, pnl.shape[1])):
        floor = np.where(locked, locked_floor,
                         np.minimum(high - rules.max_loss, locked_floor))
        x1 = bal + pnl[:, t]
        alive &= ~(alive & _breached(bal, x1, floor, _col(sig, t), _col(low, t), _col(u, t)))
        day = np.where(alive, pnl[:, t], 0.0)
        bal = np.where(alive, x1, bal)
        high = np.where(alive, np.maximum(high, bal), high)
        good = alive & (day >= rules.qual_pnl)
        qd += good
        qd_total += good
        cycle += day
        profit = bal - rules.start
        req = np.minimum(rules.max_request, rules.payout_frac * profit)
        ok = (alive & (qd >= rules.qual_days) & (cycle > 0) & (req >= rules.min_request)
              & (bal - req > locked_floor))
        bal = np.where(ok, bal - req, bal)
        owner = owner + np.where(ok, rules.split * req, 0.0)
        payouts += ok
        qd = np.where(ok, 0, qd)
        cycle = np.where(ok, 0.0, cycle)
        locked |= ok
    return owner, qd_total, payouts


def prop1_ceiling(mu: float, sigma: float, rules: Rules) -> float:
    """P(reach T before a drawdown of D), no deadline: exp(-(T/D) h(gamma D))."""
    x = 2.0 * mu / (sigma * sigma) * rules.max_loss
    h = 1.0 if abs(x) < 1e-12 else x / np.expm1(x)
    return float(np.exp(-(rules.target / rules.max_loss) * h))
