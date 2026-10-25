"""Frozen forward test (research/PREREGISTRATION_forward.md) for sessions after 2026-10-23.

    PYTHONPATH=. python3 -m factory.forward             # after the session cache has new data

Candidates: C0 canonical noise-area momentum every eligible session; C1 = N3 and not N1;
C2 = C1 and N2 (flags exactly as lx_prereg2.hypotheses). E-goal at 60 forward sessions,
E-improve at 250. Interim runs report progress only."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import goal70 as G
from . import lx_features as X
from . import lx_prereg as P1
from . import lx_prereg2 as P2
from . import lx_run as R

START = np.datetime64("2026-10-24")          # first session after the research data ends
N_DRAWS = 20000
OUT = Path(__file__).resolve().parents[1] / "results" / "forward.json"


def candidate_flags(mkt, F, dates):
    h = P2.hypotheses(mkt, F, dates)
    n1, n2, n3 = h["N1"][1], h["N2"][1], h["N3"][1]
    have_vix = h["N1"][3]
    have_qqq = h["N2"][3]
    c0 = np.ones(len(dates), bool)
    c1 = n3 & ~n1 & have_vix
    c2 = c1 & n2 & have_qqq
    return {"C0": c0, "C1": c1, "C2": c2}


def zero_edge_p(dp, seed=1):
    """One-sided p that mean(dp) > 0 against random daily sign flips."""
    rng = np.random.default_rng(seed)
    obs = dp.mean()
    sgn = np.where(rng.random((N_DRAWS, len(dp))) < 0.5, -1.0, 1.0)
    null = (sgn * dp).mean(axis=1)
    return float((np.sum(null >= obs) + 1) / (N_DRAWS + 1))


def e_goal(dp, dl, eligible, weeks):
    """The five E-goal criteria on forward days in order."""
    el = eligible
    owner, alive, pays, first = G.funded_sim(dp[None, :], dl[None, :], buffer=1000.0)
    res = {"sessions": int(len(dp)), "eligible": int(el.sum()),
           "eligible_per_week": float(el.sum() / max(weeks, 1e-9)),
           "hit_rate_eligible": float(np.mean(dp[el] >= 100)) if el.any() else 0.0,
           "mean_per_session": float(dp.mean()), "worst_day": float(dp.min()),
           "funded_sim_alive": bool(alive[0]), "funded_sim_owner": float(owner[0]),
           "p_zero_edge": zero_edge_p(dp)}
    res["pass"] = bool(res["hit_rate_eligible"] >= 0.70 and res["eligible_per_week"] >= 3
                       and res["mean_per_session"] >= 40 and res["worst_day"] >= -150
                       and res["funded_sim_alive"] and res["p_zero_edge"] < 0.05)
    return res


def sharpe(x):
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


def e_improve(dp_c, dl_c, dp_0, dl_0, seed=2):
    idx = G.boot_idx(len(dp_c), N_DRAWS, len(dp_c), seed)
    a, b = dp_c[idx], dp_0[idx]
    diff = (a.mean(1) / np.maximum(a.std(1, ddof=1), 1e-9) - b.mean(1) / np.maximum(b.std(1, ddof=1), 1e-9)) * np.sqrt(252)
    p = float((np.sum(diff <= 0) + 1) / (N_DRAWS + 1))
    lc = G.funded_life_policy(dp_c, dl_c, paths=6000, buffer=1000.0)
    l0 = G.funded_life_policy(dp_0, dl_0, paths=6000, buffer=1000.0)
    return {"sharpe_candidate": sharpe(dp_c), "sharpe_c0": sharpe(dp_0), "p_boot": p,
            "life_candidate": lc, "life_c0": l0,
            "account_ok": bool(lc["p_survive"] >= l0["p_survive"] and lc["owner_per_month"] >= l0["owner_per_month"])}


def run():
    mkt, dates, F = R.market("nq20")
    fwd = (F[:, X.VALID] > 0) & (dates >= START)
    n = int(fwd.sum())
    out = {"forward_sessions": n, "first": str(dates[fwd][0]) if n else None,
           "last": str(dates[fwd][-1]) if n else None, "milestones": {"e_goal": 60, "e_improve": 250}}
    if n == 0:
        out["status"] = "no forward sessions yet"
        return out
    canon, _, _ = P1._base(mkt, F, dates)
    flags = candidate_flags(mkt, F, dates)
    fd = dates[fwd]
    series = {}
    for k, f in flags.items():
        dp = np.where(f, canon["pnl"], 0.0)[fwd]
        dl = np.where(f, canon["low"], 0.0)[fwd]
        series[k] = (dp, dl, f[fwd])            # eligible = sessions the rules allow trading
    out["progress"] = {k: G.day_profile(v[0], v[2]) for k, v in series.items()}
    if n >= 60:
        first60 = slice(0, 60)
        weeks60 = ((fd[59] - fd[0]).astype("timedelta64[D]").astype(int) + 1) / 7.0
        out["e_goal"] = {k: e_goal(v[0][first60], v[1][first60], v[2][first60], weeks60)
                         for k, v in series.items()}
    if n >= 250:
        w = slice(0, 250)
        res = {k: e_improve(series[k][0][w], series[k][1][w], series["C0"][0][w], series["C0"][1][w])
               for k in ("C1", "C2")}
        adj = P1._holm(np.array([res["C1"]["p_boot"], res["C2"]["p_boot"]]))
        for (k, r), a in zip(res.items(), adj):
            r["p_holm"] = float(a)
            r["verified_improvement"] = bool(a < 0.05 and r["account_ok"])
        out["e_improve"] = res
    out["status"] = "complete" if n >= 250 else "in progress"
    return out


if __name__ == "__main__":
    res = run()
    OUT.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("forward_sessions", "status")}, indent=1))
