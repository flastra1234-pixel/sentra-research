"""Fleet construction for one LucidFlex 25K account, on discovery + validation days only.

Pool: gate survivors whose worst intraday mark at 1 micro stayed above POOL_WORST_LOW,
one representative per correlation cluster (best min(discovery, validation) Sharpe first).
Greedy: add one micro at a time to whichever sleeve most raises
    J = P(pass eval within EVAL_SESSIONS) x P(owner >= $1,000 within FUNDED_SESSIONS)
measured with the sentra-fleet-engine LucidFlex rules on a stationary block bootstrap of
whole days (common random numbers for every move). Optional fleet daily stop: flatten when
the day's mark reaches -L.

The day low of a fleet is approximated here as the SUM of sleeve lows (never better than the
truth); unseal.py recomputes it exactly from minute paths."""
import json
from dataclasses import replace

import numpy as np

from . import data as D
from . import select as SEL
from . import sweep as W
from .lucid import Rules, run_eval, run_funded

POOL_WORST_LOW = -900.0
POOL_SIZE = 80
CLUSTER_RHO = 0.6
MAX_PER_SLEEVE = 3
MAX_TOTAL = 10                 # 1 mini equivalent, inside every LucidFlex 25K size tier
EVAL_SESSIONS = 60
FUNDED_SESSIONS = 42
PATHS = 4000
SEED = 20261025
DAILY_STOPS = (None, 300.0, 450.0, 600.0)
STOP_SLIP_PER_MICRO = 1.0      # extra ticks paid when the fleet stop flattens everything
RULES = Rules(eval_sessions=EVAL_SESSIONS, funded_sessions=FUNDED_SESSIONS)


def load_pool():
    cand = json.loads((D.DATA_DIR / "candidates.json").read_text())
    sw1, sw2 = W.load_open("r1"), W.load_open("r2")
    pnl = np.vstack([sw1["pnl"], sw2["pnl"]]).astype(np.float64)
    low = np.vstack([sw1["low"], sw2["low"]]).astype(np.float64)
    c = cand["candidates"]
    rows = np.array([x["row"] for x in c])
    wl = low[rows].min(axis=1)
    rob = np.array([min(x["disc"]["sharpe_ann"], x["val"]["sharpe_ann"]) for x in c])
    ok = np.where(wl >= POOL_WORST_LOW)[0]
    order = ok[np.argsort(-rob[ok])]
    _, leaders = SEL.effective_trials(pnl[rows], np.ones(pnl.shape[1], bool), order,
                                      rho=CLUSTER_RHO, min_active=50)
    pick = leaders[:POOL_SIZE]
    return {"specs": [c[i] for i in pick], "pnl": pnl[rows[pick]], "low": low[rows[pick]],
            "dates": sw1["dates"], "summary": cand["summary"]}


POOL_PER_INST = {"nq": 60, "rty": 30, "gc": 30, "cl": 30}


def admissible(c, r1_families):
    """Round-2 variants only count when their (instrument, family) passed validation in
    round 1 with no added feature: a filter cannot rescue an idea that failed on its own."""
    return c["round"] == 1 or (c.get("inst", "nq"), c["family"]) in r1_families


def load_pool_multi(insts=("nq", "rty")):
    """Pool across instruments on the union of their open-period sessions (a session an
    instrument has no data for counts as flat for its sleeves)."""
    from .rounds import cand_path, load_rows
    per = {}
    for i in insts:
        c = json.loads(cand_path(i).read_text())["candidates"]
        per[i] = (c, load_rows(i))
    r1_fam = {(i, x["family"]) for i, (c, _) in per.items() for x in c if x["round"] == 1}
    union = np.unique(np.concatenate([rows["dates"] for _, rows in per.values()]))
    specs, P, L = [], [], []
    for i, (c, rows) in per.items():
        idx = np.searchsorted(union, rows["dates"])
        keep = [k for k, x in enumerate(c) if admissible(x, r1_fam)]
        if not keep:
            continue
        rr = np.array([c[k]["row"] for k in keep])
        wl = rows["low"][rr].min(axis=1)
        rob = np.array([min(c[k]["disc"]["sharpe_ann"], c[k]["val"]["sharpe_ann"]) for k in keep])
        ok = np.where(wl >= POOL_WORST_LOW)[0]
        order = ok[np.argsort(-rob[ok])]
        _, leaders = SEL.effective_trials(rows["pnl"][rr], np.ones(len(rows["dates"]), bool), order,
                                          rho=CLUSTER_RHO, min_active=50)
        for j in leaders[:POOL_PER_INST.get(i, 30)]:
            x = dict(c[keep[j]], inst=i)
            p = np.zeros(len(union)); lo = np.zeros(len(union))
            p[idx] = rows["pnl"][x["row"]]; lo[idx] = rows["low"][x["row"]]
            specs.append(x); P.append(p); L.append(lo)
    allsum = json.loads((D.DATA_DIR / "candidates_all.json").read_text())["summary"]
    return {"specs": specs, "pnl": np.array(P), "low": np.array(L), "dates": union.astype(str),
            "summary": {"trials": {"total": allsum["trials_total"], "effective": allsum["effective_total"]}},
            "insts": list(insts)}


def bootstrap_idx(n_days, paths, sessions, seed, mean_block=5.0):
    rng = np.random.default_rng(seed)
    idx = np.empty((paths, sessions), int)
    idx[:, 0] = rng.integers(0, n_days, paths)
    restart = rng.random((paths, sessions)) < 1.0 / mean_block
    fresh = rng.integers(0, n_days, (paths, sessions))
    for t in range(1, sessions):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n_days)
    return idx


def apply_stop(day_pnl, day_low, stop, micros):
    if stop is None:
        return day_pnl, day_low
    hit = day_low <= -stop
    cut = -stop - STOP_SLIP_PER_MICRO * micros
    return np.where(hit, cut, day_pnl), np.where(hit, np.minimum(day_low, cut), day_low)


def lucid_scores(day_pnl, day_low, idx_e, idx_f, rules=RULES):
    pe, le = day_pnl[idx_e], day_low[idx_e]
    passed = run_eval(pe, rules, low=le)
    pf, lf = day_pnl[idx_f], day_low[idx_f]
    owner, qd, payouts = run_funded(pf, rules, low=lf)
    return {"pass": float(passed.mean()), "paid_1k": float((owner >= rules.owner_goal).mean()),
            "owner_mean": float(owner.mean()), "payouts_mean": float(payouts.mean())}


def objective(s):
    return s["pass"] * s["paid_1k"]


def fleet_series(m, pnl, low, stop):
    micros = int(m.sum())
    dp = m @ pnl
    dl = m @ low
    return apply_stop(dp, dl, stop, micros)


def greedy(pool, stop, paths=PATHS, seed=SEED, log=None):
    pnl, low = pool["pnl"], pool["low"]
    k, n = pnl.shape
    idx_e = bootstrap_idx(n, paths, EVAL_SESSIONS, seed)
    idx_f = bootstrap_idx(n, paths, FUNDED_SESSIONS, seed + 1)
    m = np.zeros(k)
    best = {"pass": 0.0, "paid_1k": 0.0}
    best_j = 0.0
    history = []
    while m.sum() < MAX_TOTAL:
        trial_best, arg = best_j, None
        for j in range(k):
            if m[j] >= MAX_PER_SLEEVE:
                continue
            m[j] += 1
            dp, dl = fleet_series(m, pnl, low, stop)
            s = lucid_scores(dp, dl, idx_e, idx_f)
            jv = objective(s)
            if jv > trial_best + 0.002:
                trial_best, arg, arg_s = jv, j, s
            m[j] -= 1
        if arg is None:
            break
        m[arg] += 1
        best_j, best = trial_best, arg_s
        history.append({"add": pool["specs"][arg]["id"], "J": best_j, **best})
        if log:
            log(f"stop={stop} +{pool['specs'][arg]['family']}:{pool['specs'][arg]['id']} "
                f"J={best_j:.3f} pass={best['pass']:.3f} paid1k={best['paid_1k']:.3f}")
    return m, best_j, best, history


# ---------------------------------------------------------------- v1.1: size each phase on its own
# LucidFlex has no evaluation deadline, so the evaluation is sized to maximise the chance of
# passing at all (bounded at EVAL_LONG sessions), and the funded account is sized to maximise
# expected owner payouts over FUNDED_LONG sessions (fleet-engine's sigma_eval / sigma_funded).
EVAL_LONG = 120
FUNDED_LONG = 63
RULES_PHASE = Rules(eval_sessions=EVAL_LONG, funded_sessions=FUNDED_LONG)


def greedy_phase(pool, stop, phase, paths=PATHS, seed=SEED, log=None):
    pnl, low = pool["pnl"], pool["low"]
    k, n = pnl.shape
    sessions = EVAL_LONG if phase == "eval" else FUNDED_LONG
    idx = bootstrap_idx(n, paths, sessions, seed + (0 if phase == "eval" else 7))

    def score(m):
        dp, dl = fleet_series(m, pnl, low, stop)
        if phase == "eval":
            return float(run_eval(dp[idx], RULES_PHASE, low=dl[idx]).mean())
        owner, _, _ = run_funded(dp[idx], RULES_PHASE, low=dl[idx])
        return float(owner.mean())

    tol = 0.002 if phase == "eval" else 5.0
    m = np.zeros(k)
    best = 0.0
    while m.sum() < MAX_TOTAL:
        arg, cand = None, best
        for j in range(k):
            if m[j] >= MAX_PER_SLEEVE:
                continue
            m[j] += 1
            v = score(m)
            if v > cand + tol:
                cand, arg = v, j
            m[j] -= 1
        if arg is None:
            break
        m[arg] += 1
        best = cand
        if log:
            log(f"{phase} stop={stop} +{pool['specs'][arg]['family']}:{pool['specs'][arg]['id']} -> {best:.3f}")
    return m, best


def build_phased(log=print, pool=None, suffix=""):
    pool = pool or load_pool()
    out = {}
    for phase in ("eval", "funded"):
        res = [(stop, *greedy_phase(pool, stop, phase, log=log)) for stop in DAILY_STOPS]
        stop, m, v = max(res, key=lambda r: r[2])
        out[phase] = {"stop": stop, "score": v, "sleeves": [
            {"micros": int(m[j]), "inst": pool["specs"][j].get("inst", "nq"),
             **{k: pool["specs"][j].get(k) for k in
                ("id", "family", "filter", "knobs", "params", "disc", "val", "dsr_eff", "round")}}
            for j in np.nonzero(m)[0]],
            "all_stops": [{"stop": r[0], "score": r[2], "micros": int(r[1].sum())} for r in res]}
    out["trials"] = pool["summary"]["trials"]
    out["pool_size"] = len(pool["specs"])
    (D.DATA_DIR / f"fleet_phased{suffix}.json").write_text(json.dumps(out, default=float, indent=1))
    return out


def build(log=print, pool=None, suffix=""):
    pool = pool or load_pool()
    results = []
    for stop in DAILY_STOPS:
        m, j, s, hist = greedy(pool, stop, log=log)
        results.append({"stop": stop, "micros": m, "J": j, "scores": s, "history": hist})
    best = max(results, key=lambda r: r["J"])
    # re-score the winner on fresh bootstrap draws (the greedy's own draws flatter it)
    n = pool["pnl"].shape[1]
    ie = bootstrap_idx(n, 20000, EVAL_SESSIONS, SEED + 99)
    iff = bootstrap_idx(n, 20000, FUNDED_SESSIONS, SEED + 100)
    dp, dl = fleet_series(best["micros"], pool["pnl"], pool["low"], best["stop"])
    best["fresh_scores"] = lucid_scores(dp, dl, ie, iff)
    best["fresh_scores_c40"] = lucid_scores(dp, dl, ie, iff, replace(RULES, consistency=0.40))
    sleeves = [{"micros": int(best["micros"][j]), "inst": pool["specs"][j].get("inst", "nq"),
                **{k: pool["specs"][j].get(k) for k in
                   ("id", "family", "filter", "knobs", "params", "disc", "val", "dsr_eff", "round")}}
               for j in np.nonzero(best["micros"])[0]]
    fleet = {"stop": best["stop"], "sleeves": sleeves, "J_greedy": best["J"],
             "scores_greedy": best["scores"], "scores_fresh": best["fresh_scores"],
             "scores_fresh_c40": best["fresh_scores_c40"],
             "all_stops": [{"stop": r["stop"], "J": r["J"], "micros": int(r["micros"].sum()),
                            "n_sleeves": int((r["micros"] > 0).sum())} for r in results],
             "history": best["history"], "trials": pool["summary"]["trials"],
             "pool_size": len(pool["specs"])}
    (D.DATA_DIR / f"fleet{suffix}.json").write_text(json.dumps(fleet, default=float, indent=1))
    return fleet, pool


if __name__ == "__main__":
    import sys
    multi = [a for a in sys.argv[1:] if not a.startswith("--")]
    pool, suffix = (load_pool_multi(multi), "_" + "_".join(multi)) if multi else (None, "")
    if "--phased" in sys.argv:
        o = build_phased(pool=pool, suffix=suffix)
        for ph in ("eval", "funded"):
            print(ph, o[ph]["stop"], o[ph]["score"], o[ph]["all_stops"])
            for s in o[ph]["sleeves"]:
                print("  ", s["micros"], s["inst"], s["family"], s["filter"], s["knobs"])
        raise SystemExit
    f, _ = build(pool=pool, suffix=suffix)
    print(json.dumps({k: f[k] for k in ("stop", "J_greedy", "scores_greedy", "scores_fresh",
                                         "scores_fresh_c40", "all_stops")}, indent=1, default=float))
    for s in f["sleeves"]:
        print(s["micros"], s["inst"], s["family"], s["filter"], s["knobs"])
