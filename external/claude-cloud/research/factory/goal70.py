"""The account goal: net $100-150 on >= 70% of eligible trading days, the LucidFlex 25K account
surviving, and >= $1,000 of funded payouts a month. Tools to measure any daily P&L series
against it with the sentra-fleet-engine rules (via lx_run.journey / lucid.run_funded).

"Eligible" days are the days a strategy's ex-ante rules allow it to trade; hit rates are
reported both on eligible days and on all sessions.
"""
from dataclasses import replace

import numpy as np

from .lucid import Rules, run_funded

RULES = Rules()
HIT = 100.0                  # the goal's lower bound for a "hit" day, $ net


def streaks(x):
    """Longest run of True in a boolean array."""
    best = cur = 0
    for v in x:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def day_profile(dp, eligible=None, hit=HIT):
    dp = np.asarray(dp, float)
    el = np.ones(len(dp), bool) if eligible is None else np.asarray(eligible, bool)
    d = dp[el]
    if not len(d):
        return {}
    cum = np.cumsum(dp)
    return {
        "sessions": int(len(dp)), "eligible": int(el.sum()), "eligible_share": float(el.mean()),
        "hit_rate_eligible": float(np.mean(d >= hit)), "hit_rate_all": float(np.mean(dp >= hit)),
        "hit_150_eligible": float(np.mean(d >= 150)),
        "mean_day": float(dp.mean()), "mean_eligible_day": float(d.mean()),
        "mean_hit_day": float(d[d >= hit].mean()) if (d >= hit).any() else None,
        "mean_miss_day": float(d[d < hit].mean()) if (d < hit).any() else None,
        "worst_day": float(dp.min()),
        "losing_streak_max": int(streaks(d < 0)), "miss_streak_max": int(streaks(d < hit)),
        "max_drawdown": float((cum - np.maximum.accumulate(np.maximum(cum, 0))).min()),
        "sharpe_ann": float(dp.mean() / dp.std(ddof=1) * np.sqrt(252)) if dp.std(ddof=1) > 0 else 0.0,
    }


def boot_idx(n, paths, sessions, seed, mean_block=5.0):
    rng = np.random.default_rng(seed)
    idx = np.empty((paths, sessions), int)
    idx[:, 0] = rng.integers(0, n, paths)
    restart = rng.random((paths, sessions)) < 1.0 / mean_block
    fresh = rng.integers(0, n, (paths, sessions))
    for t in range(1, sessions):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def funded_life(dp, dl, months=12, paths=20000, seed=3):
    """A fresh funded account traded for `months` x 21 sessions: survival and payouts."""
    n_s = 21 * months
    rules = replace(RULES, funded_sessions=n_s)
    idx = boot_idx(len(dp), paths, n_s, seed)
    owner, qd, pays = run_funded(np.asarray(dp)[idx], rules, low=np.asarray(dl)[idx])
    # survival: rerun bookkeeping cheaply by checking whether the account was still alive at the
    # end (run_funded does not return it), via a funded run whose owner_goal tracks breaches
    alive = _alive(np.asarray(dp)[idx], np.asarray(dl)[idx], rules)
    return {"months": months, "owner_per_month": float(owner.mean() / months),
            "owner_median_total": float(np.median(owner)), "p_survive": float(alive.mean()),
            "payouts_per_month": float(pays.mean() / months),
            "p_owner_ge_1k_per_month_avg": float(np.mean(owner / months >= 1000.0))}


def _alive(pnl, low, rules):
    """Mirror of fleet_engine run_funded breach logic, returning survival at the horizon."""
    paths, T = pnl.shape
    locked_floor = rules.start + rules.lock_offset
    bal = np.full(paths, rules.start); high = bal.copy(); locked = np.zeros(paths, bool)
    alive = np.ones(paths, bool); qd = np.zeros(paths, int); cycle = np.zeros(paths)
    for t in range(T):
        floor = np.where(locked, locked_floor, np.minimum(high - rules.max_loss, locked_floor))
        x1 = bal + pnl[:, t]
        alive &= ~(alive & ((bal + low[:, t] <= floor) | (x1 <= floor)))
        day = np.where(alive, pnl[:, t], 0.0)
        bal = np.where(alive, x1, bal)
        high = np.where(alive, np.maximum(high, bal), high)
        qd += alive & (day >= rules.qual_pnl)
        cycle += day
        prof = bal - rules.start
        req = np.minimum(rules.max_request, rules.payout_frac * prof)
        ok = alive & (qd >= rules.qual_days) & (cycle > 0) & (req >= rules.min_request) & (bal - req > locked_floor)
        bal = np.where(ok, bal - req, bal)
        qd = np.where(ok, 0, qd); cycle = np.where(ok, 0.0, cycle); locked |= ok
    return alive


def two_point(p_hit, win, loss, n=4000, seed=1):
    """Synthetic days: exactly round(p_hit * n) days of +win, the rest -loss, in random order
    (intraday low = day P&L on losing days, 0 on winning days)."""
    rng = np.random.default_rng(seed)
    w = rng.permutation(np.arange(n) < round(p_hit * n))
    dp = np.where(w, win, -loss).astype(float)
    dl = np.where(w, 0.0, -loss).astype(float)
    return dp, dl


def required_table():
    rows = []
    for win in (100.0, 125.0, 150.0):
        for p in (0.6, 0.7, 0.8):
            for loss in (100.0, 150.0, 200.0, 250.0, 300.0, 400.0):
                dp, dl = two_point(p, win, loss)
                mean = p * win - (1 - p) * loss
                life = funded_life(dp, dl, months=12, paths=4000)
                rows.append({"p_hit": p, "win": win, "loss": loss, "mean_day": mean,
                             "sharpe_ann": mean / (np.sqrt(p * (1 - p)) * (win + loss)) * np.sqrt(252),
                             **life})
    return rows


def funded_sim(pnl, low, rules=RULES, buffer=0.0):
    """Funded account with a payout policy: request min($1,000, 50% of profit, amount that keeps
    the balance >= locked floor + buffer). buffer=0 reproduces fleet_engine run_funded (request
    as soon as allowed). Returns owner $, survival flag, payouts, session of first payout."""
    paths, T = pnl.shape
    locked_floor = rules.start + rules.lock_offset
    bal = np.full(paths, rules.start); high = bal.copy(); locked = np.zeros(paths, bool)
    alive = np.ones(paths, bool); qd = np.zeros(paths, int); cycle = np.zeros(paths)
    owner = np.zeros(paths); pays = np.zeros(paths, int); first = np.full(paths, -1)
    for t in range(T):
        floor = np.where(locked, locked_floor, np.minimum(high - rules.max_loss, locked_floor))
        x1 = bal + pnl[:, t]
        alive &= ~(alive & ((bal + low[:, t] <= floor) | (x1 <= floor)))
        day = np.where(alive, pnl[:, t], 0.0)
        bal = np.where(alive, x1, bal)
        high = np.where(alive, np.maximum(high, bal), high)
        qd += alive & (day >= rules.qual_pnl)
        cycle += day
        prof = bal - rules.start
        req = np.minimum(np.minimum(rules.max_request, rules.payout_frac * prof),
                         bal - (locked_floor + buffer))
        ok = (alive & (qd >= rules.qual_days) & (cycle > 0) & (req >= rules.min_request)
              & (bal - req > locked_floor))
        bal = np.where(ok, bal - req, bal)
        owner += np.where(ok, rules.split * req, 0.0)
        pays += ok
        first = np.where(ok & (first < 0), t, first)
        qd = np.where(ok, 0, qd); cycle = np.where(ok, 0.0, cycle); locked |= ok
    return owner, alive, pays, first


def funded_life_policy(dp, dl, months=12, paths=10000, seed=3, buffer=0.0):
    n_s = 21 * months
    idx = boot_idx(len(dp), paths, n_s, seed)
    owner, alive, pays, first = funded_sim(np.asarray(dp)[idx], np.asarray(dl)[idx], buffer=buffer)
    return {"buffer": buffer, "p_survive": float(alive.mean()), "owner_per_month": float(owner.mean() / months),
            "p_avg_ge_900_per_month": float(np.mean(owner / months >= 900.0)),
            "median_first_payout_session": float(np.median(first[first >= 0] + 1)) if (first >= 0).any() else None}


def lock_stop_frontier(P, dpr, micros, locks=(100.0, 125.0, 150.0, 200.0), stops=(100.0, 150.0, 200.0, 300.0, None),
                       eligible=None, months=12, paths=4000, buffer=1000.0, seed=3):
    """Hit rate / expectancy / survival for every daily profit-lock x daily-stop pair applied to a
    fleet's exact minute path P (sessions x 1365) and day P&L dpr. Uses lx_run.overlay."""
    from .lx_run import overlay
    rows = []
    for lock in locks:
        for stop in stops:
            dp, dl = overlay(P, dpr, stop, lock, micros)
            prof = day_profile(dp, eligible)
            life = funded_life_policy(dp, dl, months=months, paths=paths, seed=seed, buffer=buffer)
            rows.append({"lock": lock, "stop": stop, **{k: prof[k] for k in ("hit_rate_all", "hit_rate_eligible",
                         "mean_day", "losing_streak_max", "max_drawdown")}, **life})
    return rows
