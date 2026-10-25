"""2020+ pipeline on the Lucid session: sweep -> gates -> round 2 -> fleet -> unseal.

Splits (SPLITS) live inside 2020+ only. Fleet scoring follows the account goals:
  goal 1  pass the LucidFlex 25K evaluation within 10 sessions (2 weeks), first payout fast
  goal 2  >= $1,000 owner payout per 21-session funded month, steadily
  goal 3  3:1 reward:risk at 60% win rate (reported per sleeve; it is a stretch goal)
using the sentra-fleet-engine rules: Rules() defaults are eval_sessions=10, funded_sessions=21,
owner_goal=$1,000, target $1,250, $1,000 EOD-trailing max loss, 50% consistency.

    python -m factory.lx_run prepare <dataset>
    python -m factory.lx_run rounds <dataset>
    python -m factory.lx_run fleet <dataset>
    python -m factory.lx_run unseal <dataset>
"""
import json
import sys
import time
from collections import Counter
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

from . import data as D
from . import lx_data as LD
from . import lx_engine as LE
from . import lx_features as LF
from . import lx_strategies as LS
from . import select as SEL
from .lucid import Rules, deflated_sharpe, run_eval, run_funded

SPLITS = {}          # dataset -> {"discovery": [(a, b), ...], "validation": [...], "sealed": [...], "holdout": [...]}
LOADERS = {}         # dataset -> callable returning a tz-aware 1-minute OHLCV DataFrame
GATES_LX = {"min_trades": 150, "years_pos": 0.66, "t_disc": 2.0, "t_val": 1.0}
RULES = Rules()      # 10-session evaluation, 21-session funded month
EVAL_CAP, FUNDED_CAP, PER_SLEEVE = 20, 10, 6
PATHS, SEED = 4000, 20261025


def _d(x):
    return np.datetime64(x, "D")


def register(name, loader, splits=None):
    LOADERS[name] = loader
    if splits:
        SPLITS[name] = {k: [tuple(_d(x) for x in ab) for ab in v] for k, v in splits.items()}


def _nq20():
    from . import lx_sources
    df, _, _ = lx_sources.build()
    return df


# 2020+ only; every period is real NQ futures.
register("nq20", _nq20, {
    "discovery": [("2020-01-01", "2023-12-31")],
    "validation": [("2024-01-01", "2024-12-31")],
    "sealed": [("2025-01-01", "2026-03-01")],
    "holdout": [("2026-03-02", "2026-10-23")],
})

# ---------------------------------------------------------------- markets
_MKT = {}


def sessions(name, rebuild=False):
    path = D.DATA_DIR / f"lx_{name}.npz"
    if path.exists() and not rebuild:
        return LD.load(path)
    s = LD.build(LOADERS[name](), name)
    D.DATA_DIR.mkdir(parents=True, exist_ok=True)
    LD.save(s, path)
    return s


def market(name):
    if name not in _MKT:
        s = sessions(name)
        F, vw, sig = LF.build(s)
        _MKT[name] = ((s.o, s.h, s.l, s.c, F, vw, sig, s.present), s.dates, F)
    return _MKT[name]


def period_masks(name):
    _, dates, F = market(name)
    valid = F[:, LF.VALID] > 0
    out = {}
    for k, ranges in SPLITS[name].items():
        m = np.zeros(len(dates), bool)
        for a, b in ranges:
            m |= (dates >= a) & (dates <= b)
        out[k] = valid & m
    return out


# ---------------------------------------------------------------- sweep
def _one(args):
    spec, name = args
    mkt, _, F = market(name)
    r = LE.run(spec["family"], mkt, spec["params"], LS.day_mask(F, spec["filter"]), inst=spec.get("inst", "nq"))
    return {k: r[k].astype(np.float32 if k in ("pnl", "low", "gw", "gl") else np.int16)
            for k in ("pnl", "low", "ntr", "nwin", "gw", "gl")}


def sweep(specs, tag, name, procs=4, chunk=4000):
    """Streams results chunk by chunk into preallocated arrays (a full sweep can be 100k specs)."""
    t0 = time.time()
    pm = period_masks(name)
    _, dates, _ = market(name)
    oc = pm["discovery"] | pm["validation"]
    pers = [p for p in ("sealed", "holdout") if p in pm]
    n = len(specs)
    arr = {"pnl": np.zeros((n, oc.sum()), np.float32), "low": np.zeros((n, oc.sum()), np.float32),
           "ntr": np.zeros((n, oc.sum()), np.int16)}
    for p in pers:
        for k, dt in (("pnl", np.float32), ("low", np.float32), ("ntr", np.int16)):
            arr[f"{p}_{k}"] = np.zeros((n, pm[p].sum()), dt)
    ts = {k: np.zeros((n, 4)) for k in ["disc", "val"] + pers}
    tcols = {"disc": pm["discovery"], "val": pm["validation"], **{p: pm[p] for p in pers}}
    with Pool(procs) as pool:
        for a in range(0, n, chunk):
            res = pool.map(_one, [(sp, name) for sp in specs[a:a + chunk]], chunksize=32)
            for j, r in enumerate(res):
                q = a + j
                for k in ("pnl", "low", "ntr"):
                    arr[k][q] = r[k][oc]
                    for p in pers:
                        arr[f"{p}_{k}"][q] = r[k][pm[p]]
                for key, cols in tcols.items():
                    ts[key][q] = [r["ntr"][cols].sum(), r["nwin"][cols].sum(), r["gw"][cols].sum(),
                                  r["gl"][cols].sum()]
            del res
    meta = json.dumps([{k: sp.get(k) for k in ("id", "family", "params", "filter", "knobs", "inst")} for sp in specs],
                      default=float)
    ids = np.array([sp["id"] for sp in specs])
    np.savez(D.DATA_DIR / f"lx_{tag}_open.npz", ids=ids, meta=np.array(meta), dates=dates[oc].astype(str),
             is_disc=pm["discovery"][oc], pnl=arr["pnl"], low=arr["low"], ntr=arr["ntr"],
             ts_disc=ts["disc"], ts_val=ts["val"])
    sealed = {"ids": ids}
    for p in pers:
        sealed.update({f"{p}_dates": dates[pm[p]].astype(str), f"{p}_pnl": arr[f"{p}_pnl"],
                       f"{p}_low": arr[f"{p}_low"], f"{p}_ntr": arr[f"{p}_ntr"], f"{p}_ts": ts[p]})
    np.savez(D.DATA_DIR / f"lx_{tag}_sealed.npz", **sealed)
    print(f"sweep {tag}: {n} specs in {time.time() - t0:.0f}s")


def load_open(tag):
    z = np.load(D.DATA_DIR / f"lx_{tag}_open.npz", allow_pickle=False)
    return {k: z[k] for k in z.files} | {"meta": json.loads(str(z["meta"]))}


def wr_rr(ts):
    trades, wins, gw, gl = ts
    losses = trades - wins
    wr = wins / trades if trades else None
    rr = (gw / wins) / (gl / losses) if wins and losses and gl > 0 else None
    return wr, rr


# ---------------------------------------------------------------- rounds
def rounds(name, resweep_r1=True):
    r1 = LS.round1()
    if resweep_r1:
        sweep(r1, f"{name}_r1", name)
    sw1 = load_open(f"{name}_r1")
    rows1, _, _ = SEL.evaluate(sw1, len(r1), gates=GATES_LX, log_path=D.DATA_DIR / f"lx_trials_{name}_r1.jsonl.gz")
    passers = [k for k, r in enumerate(rows1) if r["stopped_at"] in ("survived", "validation")]
    # one base per near-duplicate cluster (rho > 0.9 on discovery P&L), best discovery t first
    tb = np.array([rows1[k]["disc"]["t"] or 0 for k in passers])
    _, lead = SEL.effective_trials(sw1["pnl"][passers], sw1["is_disc"], np.argsort(-tb), rho=0.9, min_active=30)
    bases = [dict(id=rows1[passers[j]]["id"], family=rows1[passers[j]]["family"],
                  params=rows1[passers[j]]["params"], knobs=rows1[passers[j]]["knobs"], inst="nq") for j in lead]
    print(f"{len(passers)} discovery-gate passers -> {len(bases)} distinct bases (rho 0.9)")
    r2 = LS.round2(bases)
    print(f"round 1: {len(r1)} specs, {len(bases)} discovery-gate passers -> round 2: {len(r2)} specs")
    rows2, sw2 = [], None
    if r2:
        sweep(r2, f"{name}_r2", name)
        sw2 = load_open(f"{name}_r2")
        rows2, _, _ = SEL.evaluate(sw2, len(r1) + len(r2), gates=GATES_LX,
                                   log_path=D.DATA_DIR / f"lx_trials_{name}_r2.jsonl.gz")
    pnl = sw1["pnl"] if sw2 is None else np.vstack([sw1["pnl"], sw2["pnl"]])
    tsd = sw1["ts_disc"] if sw2 is None else np.vstack([sw1["ts_disc"], sw2["ts_disc"]])
    tsv = sw1["ts_val"] if sw2 is None else np.vstack([sw1["ts_val"], sw2["ts_val"]])
    rows = rows1 + rows2
    t_all = np.array([r["disc"]["t"] or 0 for r in rows])
    n_eff, _ = SEL.effective_trials(pnl, sw1["is_disc"], np.argsort(-t_all))
    p = pnl.astype(np.float64)
    sd = p.std(axis=1, ddof=1)
    var = float(np.nanvar(p.mean(axis=1) / np.where(sd > 0, sd, np.nan)))
    # a round-2 variant counts only if ITS OWN base passed validation unfiltered in round 1:
    # re-testing ~40 filtered variants of a base that failed validation lets chance passes in
    r1_surv = {r["id"] for r in rows1 if r["stopped_at"] == "survived"}
    base_of = {sp["id"]: sp["base"] for sp in r2}
    cands = []
    for k, r in enumerate(rows):
        if r["stopped_at"] != "survived":
            continue
        rnd = 1 if k < len(rows1) else 2
        wd, rd = wr_rr(tsd[k])
        wv, rv = wr_rr(tsv[k])
        cands.append(dict(r, row=k, round=rnd, admissible=rnd == 1 or base_of.get(r["id"]) in r1_surv,
                          dsr=float(deflated_sharpe(p[k], n_eff, var)),
                          wr_disc=wd, rr_disc=rd, wr_val=wv, rr_val=rv))
    summary = {"trials": {"round1": len(r1), "round2": len(r2), "effective": n_eff, "var_sharpe_daily": var},
               "funnel_r1": SEL.funnel(rows1), "funnel_r2": SEL.funnel(rows2) if rows2 else {},
               "survivors": len(cands), "admissible": sum(c["admissible"] for c in cands),
               "families": dict(Counter(c["family"] for c in cands if c["admissible"]))}
    (D.DATA_DIR / f"lx_candidates_{name}.json").write_text(json.dumps({"summary": summary, "candidates": cands},
                                                                      default=float))
    return summary


# ---------------------------------------------------------------- fleet
def _bidx(n, paths, sessions_, seed, mean_block=5.0):
    rng = np.random.default_rng(seed)
    idx = np.empty((paths, sessions_), int)
    idx[:, 0] = rng.integers(0, n, paths)
    restart = rng.random((paths, sessions_)) < 1.0 / mean_block
    fresh = rng.integers(0, n, (paths, sessions_))
    for t in range(1, sessions_):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def lucid_metrics(dp, dl, ie, iff, rules=RULES):
    passed = run_eval(dp[ie], rules, low=dl[ie])
    owner, qd, pays = run_funded(dp[iff], rules, low=dl[iff])
    return {"pass_10": float(passed.mean()), "ppmc_1k": float((owner >= rules.owner_goal).mean()),
            "any_payout_21": float((pays > 0).mean()), "owner_mean_21": float(owner.mean())}


def load_pool(name, pool_size=80, rho=0.6, worst_low=-900.0):
    c = json.loads((D.DATA_DIR / f"lx_candidates_{name}.json").read_text())["candidates"]
    sw1 = load_open(f"{name}_r1")
    parts = [sw1]
    try:
        parts.append(load_open(f"{name}_r2"))
    except FileNotFoundError:
        pass
    pnl = np.vstack([q["pnl"] for q in parts]).astype(np.float64)
    low = np.vstack([q["low"] for q in parts]).astype(np.float64)
    c = [x for x in c if x["admissible"]]
    rows = np.array([x["row"] for x in c])
    if not len(rows):
        return None
    wl = low[rows].min(axis=1)
    rob = np.array([min(x["disc"]["sharpe_ann"], x["val"]["sharpe_ann"]) for x in c])
    ok = np.where(wl >= worst_low)[0]
    order = ok[np.argsort(-rob[ok])]
    _, leaders = SEL.effective_trials(pnl[rows], np.ones(pnl.shape[1], bool), order, rho=rho, min_active=30)
    pick = leaders[:pool_size]
    return {"specs": [c[i] for i in pick], "pnl": pnl[rows[pick]], "low": low[rows[pick]], "dates": sw1["dates"]}


def greedy(pool, phase, cap, stop=None):
    pnl, low = pool["pnl"], pool["low"]
    k, n = pnl.shape
    idx = _bidx(n, PATHS, RULES.eval_sessions if phase == "eval" else RULES.funded_sessions,
                SEED + (0 if phase == "eval" else 1))

    def score(m):
        dp, dl = m @ pnl, m @ low
        if stop is not None:
            hit = dl <= -stop
            dp = np.where(hit, -stop - m.sum(), dp)
            dl = np.where(hit, np.minimum(dl, -stop - m.sum()), dl)
        if phase == "eval":
            return float(run_eval(dp[idx], RULES, low=dl[idx]).mean())
        owner, _, _ = run_funded(dp[idx], RULES, low=dl[idx])
        return float((owner >= RULES.owner_goal).mean())

    m = np.zeros(k)
    best = 0.0
    while m.sum() < cap:
        arg, cand = None, best
        for j in range(k):
            if m[j] >= PER_SLEEVE:
                continue
            m[j] += 1
            v = score(m)
            if v > cand + 0.002:
                cand, arg = v, j
            m[j] -= 1
        if arg is None:
            break
        m[arg] += 1
        best = cand
    return m, best


def fleet(name):
    pool = load_pool(name)
    if pool is None:
        return {"error": "no admissible survivors"}
    out = {}
    for phase, cap in (("eval", EVAL_CAP), ("funded", FUNDED_CAP)):
        res = [(stop, *greedy(pool, phase, cap, stop)) for stop in (None, 400.0, 600.0)]
        stop, m, v = max(res, key=lambda r: r[2])
        out[phase] = {"stop": stop, "score": v, "micros": int(m.sum()),
                      "sleeves": [dict(micros=int(m[j]), **{q: pool["specs"][j].get(q) for q in
                                  ("id", "family", "filter", "knobs", "params", "disc", "val", "dsr",
                                   "wr_disc", "rr_disc", "wr_val", "rr_val")}) for j in np.nonzero(m)[0]],
                      "by_stop": [{"stop": r[0], "score": r[2], "micros": int(r[1].sum())} for r in res]}
    (D.DATA_DIR / f"lx_fleet_{name}.json").write_text(json.dumps(out, default=float, indent=1))
    return out


# ---------------------------------------------------------------- unseal
def fleet_days(sleeves, mkt, F, mask, stop=None):
    n = len(F)
    tot = np.zeros(n)
    path = np.zeros((n, LD.NB))
    ts = np.zeros(4)
    per = []
    for s in sleeves:
        r = LE.run(s["family"], mkt, s["params"], LS.day_mask(F, s["filter"]) & mask, want_path=True)
        tot += s["micros"] * r["pnl"]
        path += s["micros"] * r["path"]
        st = np.array([r["ntr"][mask].sum(), r["nwin"][mask].sum(), r["gw"][mask].sum(), r["gl"][mask].sum()])
        ts += st * [1, 1, s["micros"], s["micros"]]
        per.append({"id": s["id"], "sharpe_ann": _sh(r["pnl"][mask]), "total_1micro": float(r["pnl"][mask].sum()),
                    "wr": wr_rr(st)[0], "rr": wr_rr(st)[1], "trades": int(st[0])})
    low = np.minimum(path.min(axis=1), 0.0)
    dp, dl = tot[mask], low[mask]
    if stop is not None:
        micros = sum(s["micros"] for s in sleeves)
        hit_t = np.argmax(path[mask] <= -stop, axis=1)
        hit = (path[mask] <= -stop).any(axis=1)
        dp = np.where(hit, -stop - micros, dp)
        dl = np.where(hit, np.minimum(dl, -stop - micros), dl)
    return dp, dl, ts, per


def _sh(p):
    p = np.asarray(p, float)
    sd = p.std(ddof=1)
    return float(p.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


def stats(p, low):
    p = np.asarray(p, float)
    cum = np.cumsum(p)
    s = p.mean() / p.std(ddof=1) if p.std(ddof=1) > 0 else 0.0
    return {"sessions": len(p), "mean_day": float(p.mean()), "sd_day": float(p.std(ddof=1)),
            "sharpe_ann": float(s * np.sqrt(252)), "t": float(s * np.sqrt(len(p))),
            "max_dd": float((cum - np.maximum.accumulate(np.maximum(cum, 0))).min()),
            "worst_day": float(p.min()), "worst_intraday": float(np.min(low)),
            "pct_days_ge_100": float(np.mean(p >= 100)), "pct_up_days": float(np.mean(p > 0)),
            "total": float(p.sum())}


def replays(dp, dl, rules=RULES):
    """Every start date: does the evaluation pass within rules.eval_sessions?"""
    n = len(dp)
    res = Counter()
    days = []
    for d in range(n - rules.eval_sessions + 1):    # full windows only (no end-of-data bias)
        bal = high = rules.start
        mx = 0.0
        outcome = "open"
        for t in range(rules.eval_sessions):
            floor = min(high - rules.max_loss, rules.start + rules.lock_offset)
            if bal + dl[d + t] <= floor or bal + dp[d + t] <= floor:
                outcome = "breached"
                break
            bal += dp[d + t]
            high = max(high, bal)
            mx = max(mx, dp[d + t])
            prof = bal - rules.start
            if prof >= rules.target and mx <= rules.consistency * prof:
                outcome = "passed"
                days.append(t + 1)
                break
        res[outcome] += 1
    full = res["passed"] + res["breached"] + res["open"]
    return {**res, "pass_rate_10": res["passed"] / full if full else None,
            "median_days_to_pass": float(np.median(days)) if days else None}


def unseal(name):
    fl = json.loads((D.DATA_DIR / f"lx_fleet_{name}.json").read_text())
    mkt, dates, F = market(name)
    pm = period_masks(name)
    periods = {"in_sample": (mkt, F, pm["discovery"] | pm["validation"], dates),
               "sealed": (mkt, F, pm["sealed"], dates),
               "holdout": (mkt, F, pm.get("holdout", np.zeros(len(dates), bool)), dates)}
    out = {"fleet": fl}
    for pname, (m, FF, mask, dd) in periods.items():
        if not mask.any():
            continue
        blk = {"dates": [str(dd[mask][0]), str(dd[mask][-1])]}
        for phase in ("eval", "funded"):
            f = fl[phase]
            dp, dl, ts, per = fleet_days(f["sleeves"], m, FF, mask, f["stop"])
            n = len(dp)
            ie, iff = _bidx(n, 20000, RULES.eval_sessions, 99), _bidx(n, 20000, RULES.funded_sessions, 100)
            blk[phase] = {"stats": stats(dp, dl), "lucid": lucid_metrics(dp, dl, ie, iff),
                          "lucid_c40": lucid_metrics(dp, dl, ie, iff, replace(RULES, consistency=0.40)),
                          "replays": replays(dp, dl), "wr": wr_rr(ts)[0], "rr": wr_rr(ts)[1],
                          "trades": int(ts[0]), "sleeves": per}
        out[pname] = blk
    (D.DATA_DIR / f"lx_unseal_{name}.json").write_text(json.dumps(out, default=float, indent=1))
    return out


# ---------------------------------------------------------------- v2: overlays on exact minute paths
STOPS = (None, 300.0, 500.0)
LOCKS = (None, 150.0, 250.0, 400.0, 600.0)
FUNDED_LIFE = 126          # ~6 months of funded sessions for lifetime economics
EVAL_FEE = (89.0, 149.0)   # one-time LucidFlex 25K evaluation fee range seen in reviews


def pool_paths(pool, name):
    """Per-sleeve minute paths (running worst mark, $ per micro) on the open period."""
    mkt, dates, F = market(name)
    pm = period_masks(name)
    oc = pm["discovery"] | pm["validation"]
    paths, pnls = [], []
    for s in pool["specs"]:
        r = LE.run(s["family"], mkt, s["params"], LS.day_mask(F, s["filter"]) & oc, want_path=True)
        paths.append(r["path"][oc].astype(np.float32))
        pnls.append(r["pnl"][oc])
    return np.stack(paths), np.stack(pnls)


def overlay(P, day_pnl, stop, lock, micros):
    """Fleet day P&L / low after a daily stop and profit lock, from the fleet minute path P
    (worst marks: triggers the stop no later and the lock no earlier than reality)."""
    n, nb = P.shape
    big = nb + 1
    t_stop = np.where((P <= -stop).any(axis=1), np.argmax(P <= -stop, axis=1), big) if stop else np.full(n, big)
    t_lock = np.where((P >= lock).any(axis=1), np.argmax(P >= lock, axis=1), big) if lock else np.full(n, big)
    dp = day_pnl.copy()
    low = np.minimum(P.min(axis=1), 0.0)
    slip = float(micros)                       # ~2 ticks of MNQ per micro to flatten everything
    s_hit = t_stop < t_lock
    l_hit = t_lock < t_stop
    if stop:
        dp[s_hit] = -stop - slip
        low[s_hit] = -stop - slip
    if lock:
        dp[l_hit] = lock - slip
        cm = np.minimum.accumulate(np.minimum(P, 0.0), axis=1)
        low[l_hit] = cm[l_hit, t_lock[l_hit]]
    return dp, low


def greedy_overlay(paths, pnls, phase, cap, stop, lock, paths_n=PATHS):
    k, n, nb = paths.shape
    sessions_ = RULES.eval_sessions if phase == "eval" else RULES.funded_sessions
    idx = _bidx(n, paths_n, sessions_, SEED + (0 if phase == "eval" else 1))

    def score(P, dpnl, micros):
        dp, dl = overlay(P, dpnl, stop, lock, micros)
        if phase == "eval":
            return float(run_eval(dp[idx], RULES, low=dl[idx]).mean())
        if phase == "journey":            # goal 1: first payout within 15 sessions of buying the eval
            return journey(dp, dl, dp, dl, n_paths=paths_n, horizon=15, seed=SEED + 2)["p_payout_within_15"]
        owner, _, _ = run_funded(dp[idx], RULES, low=dl[idx])
        return float((owner >= RULES.owner_goal).mean())

    m = np.zeros(k)
    P = np.zeros((n, nb), np.float32)
    dpnl = np.zeros(n)
    best = 0.0
    while m.sum() < cap:
        arg, cand = None, best
        for j in range(k):
            if m[j] >= PER_SLEEVE:
                continue
            v = score(P + paths[j], dpnl + pnls[j], m.sum() + 1)
            if v > cand + 0.002:
                cand, arg = v, j
        if arg is None:
            break
        m[arg] += 1
        P += paths[arg]
        dpnl += pnls[arg]
        best = cand
    return m, best


def lifetime(dp, dl, seed=7, n_paths=20000):
    """Fresh funded account over FUNDED_LIFE sessions: owner payouts and survival."""
    rules = replace(RULES, funded_sessions=FUNDED_LIFE)
    idx = _bidx(len(dp), n_paths, FUNDED_LIFE, seed)
    owner, qd, pays = run_funded(dp[idx], rules, low=dl[idx])
    return {"owner_mean_6m": float(owner.mean()), "owner_median_6m": float(np.median(owner)),
            "payouts_mean_6m": float(pays.mean()), "p_any_payout_6m": float((pays > 0).mean())}


def fleet_v2(name, pool_size=150, worst_low=-2500.0, log=print):
    pool = load_pool(name, pool_size=pool_size, worst_low=worst_low)
    paths, pnls = pool_paths(pool, name)
    out = {"pool_size": len(pool["specs"])}
    for phase, cap in (("eval", EVAL_CAP), ("funded", FUNDED_CAP)):
        grid = []
        for stop in STOPS:
            for lock in LOCKS:
                m, v = greedy_overlay(paths, pnls, phase, cap, stop, lock)
                grid.append((stop, lock, m, v))
                log(f"{phase} stop={stop} lock={lock}: {v:.3f} with {int(m.sum())} micros")
        stop, lock, m, v = max(grid, key=lambda g: g[3])
        P = np.tensordot(m, paths, axes=1)
        dp, dl = overlay(P, m @ pnls, stop, lock, m.sum())
        out[phase] = {"stop": stop, "lock": lock, "score": v, "micros": int(m.sum()),
                      "in_sample": {**stats(dp, dl), **lifetime(dp, dl)},
                      "grid": [{"stop": g[0], "lock": g[1], "score": g[3], "micros": int(g[2].sum())} for g in grid],
                      "sleeves": [dict(micros=int(m[j]), **{q: pool["specs"][j].get(q) for q in
                                  ("id", "family", "filter", "knobs", "params", "disc", "val", "dsr",
                                   "wr_disc", "rr_disc", "wr_val", "rr_val")}) for j in np.nonzero(m)[0]]}
    (D.DATA_DIR / f"lx_fleet2_{name}.json").write_text(json.dumps(out, default=float, indent=1))
    return out




def fleet_paths(sleeves, mkt, F, mask, mark="worst"):
    """Exact fleet minute path and day P&L on a period (sum over sleeves x micros).
    mark="best" returns favourable-extreme marks (see lx_engine.run)."""
    n = len(F)
    P = np.zeros((n, LD.NB))
    dp = np.zeros(n)
    ts = np.zeros(4)
    per = []
    for s in sleeves:
        r = LE.run(s["family"], mkt, s["params"], LS.day_mask(F, s["filter"]) & mask, want_path=True, mark=mark)
        P += s["micros"] * r["path"]
        dp += s["micros"] * r["pnl"]
        st = np.array([r["ntr"][mask].sum(), r["nwin"][mask].sum(), r["gw"][mask].sum(), r["gl"][mask].sum()])
        ts += st * [1, 1, s["micros"], s["micros"]]
        per.append({"id": s["id"], "family": s["family"], "filter": s["filter"],
                    "sharpe_ann": _sh(r["pnl"][mask]), "total_1micro": float(r["pnl"][mask].sum()),
                    "wr": wr_rr(st)[0], "rr": wr_rr(st)[1], "trades": int(st[0])})
    return P[mask], dp[mask], ts, per


def unseal_v2(name):
    """One-shot evaluation of the frozen v2 fleets on the sealed period and the 2026 holdout."""
    fl = json.loads((D.DATA_DIR / f"lx_fleet2_{name}.json").read_text())
    mkt, dates, F = market(name)
    pm = period_masks(name)
    out = {"fleet": {ph: {k: fl[ph][k] for k in ("stop", "lock", "micros", "sleeves")} for ph in ("eval", "funded")}}
    fresh = pm["holdout"] & (dates <= np.datetime64("2026-07-01"))
    for pname, mask in (("in_sample", pm["discovery"] | pm["validation"]), ("sealed", pm["sealed"]),
                        ("holdout", pm["holdout"]), ("holdout_never_seen", fresh),
                        ("holdout_seen_in_v1", pm["holdout"] & ~fresh)):
        blk = {"dates": [str(dates[mask][0]), str(dates[mask][-1])], "sessions": int(mask.sum())}
        for ph in ("eval", "funded"):
            f = fl[ph]
            P, dpr, ts, per = fleet_paths(f["sleeves"], mkt, F, mask)
            dp, dl = overlay(P, dpr, f["stop"], f["lock"], f["micros"])
            n = len(dp)
            ie, iff = _bidx(n, 20000, RULES.eval_sessions, 99), _bidx(n, 20000, RULES.funded_sessions, 100)
            blk[ph] = {"stats": stats(dp, dl), "lucid": lucid_metrics(dp, dl, ie, iff),
                       "lucid_c40": lucid_metrics(dp, dl, ie, iff, replace(RULES, consistency=0.40)),
                       "replays": replays(dp, dl), "lifetime": lifetime(dp, dl),
                       "wr": wr_rr(ts)[0], "rr": wr_rr(ts)[1], "trades": int(ts[0]), "sleeves": per}
            if ph == "eval":
                ie60 = _bidx(n, 20000, 60, 101)
                blk[ph]["pass_60"] = float(run_eval(dp[ie60], replace(RULES, eval_sessions=60), low=dl[ie60]).mean())
        Pe, dpe_r, _, _ = fleet_paths(fl["eval"]["sleeves"], mkt, F, mask)
        Pf, dpf_r, _, _ = fleet_paths(fl["funded"]["sleeves"], mkt, F, mask)
        dpe, dle = overlay(Pe, dpe_r, fl["eval"]["stop"], fl["eval"]["lock"], fl["eval"]["micros"])
        dpf, dlf = overlay(Pf, dpf_r, fl["funded"]["stop"], fl["funded"]["lock"], fl["funded"]["micros"])
        blk["journey"] = journey(dpe, dle, dpf, dlf)
        blk["journey_63"] = journey(dpe, dle, dpf, dlf, horizon=63, seed=13)
        blk["funded"]["payout_within_10_funded"] = payout_within_funded(dpf, dlf)
        # zero-edge baseline: same days, each day's whole path flipped in sign at random (keeps
        # volatility, lows and the overlay mechanics; removes the edge)
        rng = np.random.default_rng(5)
        sgn = np.where(rng.random(len(dpe)) < 0.5, -1.0, 1.0)
        Pz = Pe * sgn[:, None]
        dpz, dlz = overlay(Pz, dpe_r * sgn, fl["eval"]["stop"], fl["eval"]["lock"], fl["eval"]["micros"])
        n = len(dpz)
        blk["eval_zero_edge_pass_10"] = float(run_eval(dpz[_bidx(n, 20000, 10, 99)], RULES,
                                                       low=dlz[_bidx(n, 20000, 10, 99)]).mean())
        out[pname] = blk
    (D.DATA_DIR / f"lx_unseal2_{name}.json").write_text(json.dumps(out, default=float, indent=1))
    return out


def journey(dp_e, dl_e, dp_f, dl_f, n_paths=20000, horizon=42, seed=11, rules=RULES):
    """Goal 1: buy an evaluation, trade the eval fleet until it passes, then the funded fleet
    from the next session; when does the first payout get approved? Same session index for
    both fleets (one calendar). Mirrors fleet_engine.rules run_eval / run_funded (fresh)."""
    idx = _bidx(len(dp_e), n_paths, horizon, seed)
    pe, le, pf, lf = dp_e[idx], dl_e[idx], dp_f[idx], dl_f[idx]
    n = n_paths
    phase = np.zeros(n, int)                      # 0 eval, 1 funded, 2 failed
    bal = np.full(n, rules.start); high = bal.copy(); max_win = np.zeros(n)
    locked = np.zeros(n, bool); qd = np.zeros(n, int); cycle = np.zeros(n)
    passed_at = np.full(n, -1); first_pay = np.full(n, -1); owner = np.zeros(n)
    locked_floor = rules.start + rules.lock_offset
    for t in range(horizon):
        ev = phase == 0
        fu = phase == 1
        # evaluation step
        floor = np.minimum(high - rules.max_loss, locked_floor)
        x1 = bal + pe[:, t]
        br = ev & ((bal + le[:, t] <= floor) | (x1 <= floor))
        phase[br] = 2
        ok_e = ev & ~br
        bal = np.where(ok_e, x1, bal)
        high = np.where(ok_e, np.maximum(high, bal), high)
        max_win = np.where(ok_e, np.maximum(max_win, pe[:, t]), max_win)
        prof = bal - rules.start
        pas = ok_e & (prof >= rules.target) & (max_win <= rules.consistency * prof)
        passed_at[pas] = t
        # fresh funded account from the next session
        bal = np.where(pas, rules.start, bal); high = np.where(pas, rules.start, high)
        qd[pas] = 0; cycle[pas] = 0.0; locked[pas] = False
        # funded step (accounts funded before this session)
        floor_f = np.where(locked, locked_floor, np.minimum(high - rules.max_loss, locked_floor))
        x1f = bal + pf[:, t]
        brf = fu & ((bal + lf[:, t] <= floor_f) | (x1f <= floor_f))
        phase[brf] = 2
        alive = fu & ~brf
        day = np.where(alive, pf[:, t], 0.0)
        bal = np.where(alive, x1f, bal)
        high = np.where(alive, np.maximum(high, bal), high)
        qd += alive & (day >= rules.qual_pnl)
        cycle += day
        prof = bal - rules.start
        req = np.minimum(rules.max_request, rules.payout_frac * prof)
        okp = alive & (qd >= rules.qual_days) & (cycle > 0) & (req >= rules.min_request) & (bal - req > locked_floor)
        first_pay = np.where(okp & (first_pay < 0), t, first_pay)
        owner += np.where(okp, rules.split * req, 0.0)
        bal = np.where(okp, bal - req, bal)
        qd = np.where(okp, 0, qd); cycle = np.where(okp, 0.0, cycle); locked |= okp
        phase[pas] = 1
    paid = first_pay >= 0
    out = {f"p_payout_within_{k}": float(np.mean(paid & (first_pay < k))) for k in (10, 15, 21, 42)}
    out["p_pass_within_10"] = float(np.mean((passed_at >= 0) & (passed_at < 10)))
    out["median_sessions_to_first_payout"] = float(np.median(first_pay[paid] + 1)) if paid.any() else None
    out[f"owner_mean_within_{horizon}"] = float(owner.mean())     # $ paid to the trader per evaluation bought
    return out


def payout_within_funded(dp, dl, k=10, seed=12, n_paths=20000):
    idx = _bidx(len(dp), n_paths, k, seed)
    _, _, pays = run_funded(dp[idx], replace(RULES, funded_sessions=k), low=dl[idx])
    return float((pays > 0).mean())



if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "prepare":
        s = sessions(name, rebuild=True)
        yrs = Counter(s.dates.astype("datetime64[Y]").astype(str))
        print(name, len(s), s.dates[0], s.dates[-1], dict(sorted(yrs.items())))
    elif cmd == "rounds":
        print(json.dumps(rounds(name, resweep_r1="--no-r1" not in sys.argv), indent=1, default=float))
    elif cmd == "fleet":
        print(json.dumps(fleet(name), indent=1, default=float))
    elif cmd == "unseal":
        print(json.dumps(unseal(name), indent=1, default=float)[:20000])
    elif cmd == "unseal2":
        o = unseal_v2(name)
        for pn in ("in_sample", "sealed", "holdout", "holdout_never_seen", "holdout_seen_in_v1"):
            b = o[pn]
            print("==", pn, b["dates"], b["sessions"], "sessions")
            for ph in ("eval", "funded"):
                x = b[ph]
                print("  ", ph, {k: round(v, 3) for k, v in x["stats"].items() if k in
                       ("mean_day", "sd_day", "sharpe_ann", "t", "max_dd", "worst_intraday", "pct_days_ge_100")},
                      "WR", x["wr"] and round(x["wr"], 2), "RR", x["rr"] and round(x["rr"], 2))
                print("      lucid", {k: round(v, 3) for k, v in x["lucid"].items()}, "c40 pass", round(x["lucid_c40"]["pass_10"], 3),
                      "| replays", x["replays"], "| 6m", {k: round(v, 2) for k, v in x["lifetime"].items()},
                      ("| pass_60 %.3f" % x["pass_60"]) if "pass_60" in x else "")
            print("   journey (goal 1):", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in b["journey"].items()},
                  "| payout within 10 funded sessions", round(b["funded"]["payout_within_10_funded"], 3),
                  "| zero-edge eval pass_10", round(b["eval_zero_edge_pass_10"], 3))
    elif cmd == "fleet2":
        o = fleet_v2(name)
        for ph in ("eval", "funded"):
            f = o[ph]
            print(ph, "stop", f["stop"], "lock", f["lock"], "score", round(f["score"], 3), "micros", f["micros"])
            print("   in-sample", {k: round(v, 3) for k, v in f["in_sample"].items()})
            for sl in f["sleeves"]:
                print("   ", sl["micros"], sl["family"], sl["filter"], sl["knobs"])
