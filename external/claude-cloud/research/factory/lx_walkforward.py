"""Walk-forward test of the PROCESS: for each test year Y, run the gates and the fleet greedy on
sessions before Y only (validation = year Y-1, discovery = earlier), then trade year Y blind.
Uses the round-1 grid (25,062 specs) so no fold depends on a later fold's base selection.

    python -m factory.lx_walkforward nq20
"""
import json
import sys

import numpy as np

from . import data as D
from . import lx_run as R
from . import select as SEL
from .lucid import run_eval

FOLDS = (2023, 2024, 2025, 2026)
EVAL_LOCKS = (None, 600.0)


def _full(tag):
    """Per-day pnl/low/ntr for every spec over open + sealed + holdout sessions, date-sorted."""
    o = R.load_open(tag)
    z = np.load(D.DATA_DIR / f"lx_{tag}_sealed.npz", allow_pickle=False)
    dates = np.concatenate([o["dates"], z["sealed_dates"], z["holdout_dates"]]).astype("datetime64[D]")
    arr = {k: np.concatenate([o[k], z[f"sealed_{k}"], z[f"holdout_{k}"]], axis=1) for k in ("pnl", "low", "ntr")}
    order = np.argsort(dates, kind="stable")
    return o["meta"], dates[order], {k: v[:, order] for k, v in arr.items()}


def fold(meta, dates, arr, year, name):
    y0 = np.datetime64(f"{year}-01-01")
    yv = np.datetime64(f"{year - 1}-01-01")
    train = dates < y0
    test = (dates >= y0) & (dates < np.datetime64(f"{year + 1}-01-01"))
    sw = {"meta": meta, "dates": dates[train].astype(str), "is_disc": dates[train] < yv,
          "pnl": arr["pnl"][:, train], "low": arr["low"][:, train], "ntr": arr["ntr"][:, train]}
    rows, surv, _ = SEL.evaluate(sw, len(meta), gates=R.GATES_LX)
    if not surv:
        return {"year": year, "survivors": 0}
    # pool: one per cluster (rho 0.6), best min(disc, val) Sharpe first
    pnl, low = sw["pnl"][surv].astype(np.float64), sw["low"][surv].astype(np.float64)
    rob = np.array([min(rows[i]["disc"]["sharpe_ann"] or -9, rows[i]["val"]["sharpe_ann"] or -9) for i in surv])
    ok = np.where(low.min(axis=1) >= -2500.0)[0]
    _, lead = SEL.effective_trials(pnl, np.ones(pnl.shape[1], bool), ok[np.argsort(-rob[ok])], rho=0.6, min_active=30)
    pick = [surv[j] for j in lead[:150]]
    specs = [dict(meta[i], micros=1) for i in pick]
    mkt, mdates, F = R.market(name)
    tmask_train = np.isin(mdates, dates[train])
    tmask_test = np.isin(mdates, dates[test])
    pool = {"specs": specs}
    paths, pnls = [], []
    from . import lx_engine as LE, lx_strategies as LS
    for s in specs:
        r = LE.run(s["family"], mkt, s["params"], LS.day_mask(F, s["filter"]) & tmask_train, want_path=True)
        paths.append(r["path"][tmask_train].astype(np.float32))
        pnls.append(r["pnl"][tmask_train])
    paths, pnls = np.stack(paths), np.stack(pnls)
    out = {"year": year, "train": [str(dates[train][0]), str(dates[train][-1])],
           "test": [str(dates[test][0]), str(dates[test][-1])] if test.any() else None,
           "survivors": len(surv), "pool": len(specs)}
    fleets = {}
    for phase, cap, locks in (("eval", R.EVAL_CAP, EVAL_LOCKS), ("funded", R.FUNDED_CAP, (None,)),
                              ("journey", R.EVAL_CAP, EVAL_LOCKS)):
        best = None
        for lock in locks:
            m, v = R.greedy_overlay(paths, pnls, phase, cap, None, lock)
            if best is None or v > best[2]:
                best = (lock, m, v)
        lock, m, v = best
        sl = [dict(specs[j], micros=int(m[j])) for j in np.nonzero(m)[0]]
        fleets[phase] = {"lock": lock, "micros": int(m.sum()), "train_score": v, "sleeves": sl}
    res = {}
    for phase in ("eval", "funded"):
        f = fleets[phase]
        P, dpr, ts, _ = R.fleet_paths(f["sleeves"], mkt, F, tmask_test)
        dp, dl = R.overlay(P, dpr, None, f["lock"], f["micros"])
        n = len(dp)
        ie, iff = R._bidx(n, 20000, 10, 99), R._bidx(n, 20000, 21, 100)
        res[phase] = {"stats": R.stats(dp, dl), "lucid": R.lucid_metrics(dp, dl, ie, iff),
                      "wr": R.wr_rr(ts)[0], "rr": R.wr_rr(ts)[1], "micros": f["micros"], "lock": f["lock"],
                      "train_score": f["train_score"], "n_sleeves": len(f["sleeves"])}
        if phase == "eval":
            rng = np.random.default_rng(5)
            sgn = np.where(rng.random(n) < 0.5, -1.0, 1.0)
            dz, lz = R.overlay(P * sgn[:, None], dpr * sgn, None, f["lock"], f["micros"])
            res[phase]["zero_edge_pass_10"] = float(run_eval(dz[ie], R.RULES, low=lz[ie]).mean())
    Pe, de, _, _ = R.fleet_paths(fleets["eval"]["sleeves"], mkt, F, tmask_test)
    Pf, df_, _, _ = R.fleet_paths(fleets["funded"]["sleeves"], mkt, F, tmask_test)
    dpe, dle = R.overlay(Pe, de, None, fleets["eval"]["lock"], fleets["eval"]["micros"])
    dpf, dlf = R.overlay(Pf, df_, None, None, fleets["funded"]["micros"])
    res["journey"] = R.journey(dpe, dle, dpf, dlf)
    # the goal-1 fleet: one fleet chosen to maximise P(first payout within 15 sessions)
    fj = fleets["journey"]
    Pj, dj, tsj, _ = R.fleet_paths(fj["sleeves"], mkt, F, tmask_test)
    dpj, dlj = R.overlay(Pj, dj, None, fj["lock"], fj["micros"])
    res["fast_fleet"] = {"train_score": fj["train_score"], "micros": fj["micros"], "lock": fj["lock"],
                         "stats": R.stats(dpj, dlj), **R.journey(dpj, dlj, dpj, dlj)}
    out["test_results"] = res
    res["journey_63"] = R.journey(dpe, dle, dpf, dlf, horizon=63, seed=13)
    out["fleets"] = {ph: {"lock": fleets[ph]["lock"], "sleeves": [{k: s[k] for k in ("family", "filter", "knobs", "params", "micros")}
                                                                    for s in fleets[ph]["sleeves"]]} for ph in fleets}
    return out


def main(name):
    meta, dates, arr = _full(f"{name}_r1")
    out = []
    for y in FOLDS:
        r = fold(meta, dates, arr, y, name)
        out.append(r)
        t = r.get("test_results", {})
        if t:
            print(y, "train", r["train"], "test", r["test"], "survivors", r["survivors"])
            for ph in ("eval", "funded"):
                x = t[ph]
                print("   ", ph, "train score", round(x["train_score"], 3), "| test mean/day", round(x["stats"]["mean_day"], 1),
                      "sharpe", round(x["stats"]["sharpe_ann"], 2), "| pass10", round(x["lucid"]["pass_10"], 3),
                      "ppmc", round(x["lucid"]["ppmc_1k"], 3), "WR", x["wr"] and round(x["wr"], 2), "RR", x["rr"] and round(x["rr"], 2),
                      ("zero-edge pass10 %.3f" % x["zero_edge_pass_10"]) if "zero_edge_pass_10" in x else "")
            print("    journey", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in t["journey"].items()})
            ff = t["fast_fleet"]
            print("    fast fleet (goal 1)", "train p15", round(ff["train_score"], 4), "micros", ff["micros"], "lock", ff["lock"],
                  "| test p10", round(ff["p_payout_within_10"], 4), "p15", round(ff["p_payout_within_15"], 4),
                  "p21", round(ff["p_payout_within_21"], 4), "mean/day", round(ff["stats"]["mean_day"], 1))
    (D.DATA_DIR / f"lx_walkforward_{name}.json").write_text(json.dumps(out, default=float, indent=1))
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "nq20")
