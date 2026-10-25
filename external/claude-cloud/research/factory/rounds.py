"""Round 1 (base grid) -> learn -> round 2 (add features to discovery-gate passers), per
instrument, with every trial logged and the deflation N taken from the effective count.

    python -m factory.rounds                 # NQ (writes DATA_DIR/candidates.json)
    python -m factory.rounds rty gc cl       # other instruments -> candidates_<inst>.json
    python -m factory.rounds --combine nq rty gc cl   # re-deflate everyone against all trials
"""
import json
import sys
from collections import Counter

import numpy as np

from . import data as D
from . import select as SEL
from . import strategies as S
from . import sweep as W


def tags(inst):
    return ("r1", "r2") if inst == "nq" else (f"r1_{inst}", f"r2_{inst}")


def cand_path(inst):
    return D.DATA_DIR / ("candidates.json" if inst == "nq" else f"candidates_{inst}.json")


def _evaluate(tag, n_trials):
    sw = W.load_open(tag)
    rows, surv, info = SEL.evaluate(sw, n_trials, log_path=D.DATA_DIR / f"trials_{tag}.jsonl.gz")
    return sw, rows, surv, info


def _sharpe_rows(pnl):
    p = pnl.astype(np.float64)
    sd = p.std(axis=1, ddof=1)
    return p.mean(axis=1) / np.where(sd > 0, sd, np.nan)


def run_instrument(inst="nq", resweep=True):
    t1, t2 = tags(inst)
    r1 = S.round1(inst)
    if resweep:
        W.run(r1, t1)
    sw1, rows1, _, _ = _evaluate(t1, len(r1))
    bases = [{"id": r["id"], "family": r["family"], "params": r["params"], "knobs": r["knobs"],
              "inst": inst} for r in rows1 if r["stopped_at"] in ("survived", "validation")]
    r2 = S.round2(bases)
    if r2:
        if resweep:
            W.run(r2, t2)
        sw2, rows2, _, _ = _evaluate(t2, len(r1) + len(r2))
        pnl = np.vstack([sw1["pnl"], sw2["pnl"]])
    else:
        rows2, pnl = [], sw1["pnl"]
    rows = rows1 + rows2
    t_all = np.array([r["disc"]["t"] or 0 for r in rows])
    n_eff, _ = SEL.effective_trials(pnl, sw1["is_disc"], np.argsort(-t_all))
    var_trials = float(np.nanvar(_sharpe_rows(pnl)))
    cands = []
    for k, r in enumerate(rows):
        if r["stopped_at"] != "survived":
            continue
        r = dict(r, inst=inst, round=1 if k < len(rows1) else 2, row=k)
        r["dsr_eff"] = float(SEL.deflated_sharpe(pnl[k].astype(np.float64), n_eff, var_trials))
        cands.append(r)
    summary = {
        "inst": inst,
        "trials": {"round1": len(r1), "round2": len(r2), "total": len(r1) + len(r2),
                   "effective": n_eff, "var_sharpe_daily": var_trials},
        "funnel_r1": SEL.funnel(rows1), "funnel_r2": SEL.funnel(rows2) if rows2 else {},
        "survivors": len(cands),
        "survivor_families": dict(Counter(c["family"] for c in cands)),
    }
    out = {"summary": summary, "candidates": cands}
    cand_path(inst).write_text(json.dumps(out, default=float))
    return out


def load_rows(inst):
    """Stacked open-period pnl/low for an instrument's r1 + r2 sweeps (row = candidate['row'])."""
    t1, t2 = tags(inst)
    sw1 = W.load_open(t1)
    parts = [sw1]
    try:
        parts.append(W.load_open(t2))
    except FileNotFoundError:
        pass
    return {"pnl": np.vstack([p["pnl"] for p in parts]), "low": np.vstack([p["low"] for p in parts]),
            "dates": sw1["dates"], "is_disc": sw1["is_disc"]}


def combine(insts):
    """Deflate every survivor against the effective trial count summed over instruments
    (cross-instrument correlation is ignored, which only makes N larger: conservative)."""
    per = {i: json.loads(cand_path(i).read_text()) for i in insts}
    n_eff = sum(p["summary"]["trials"]["effective"] for p in per.values())
    var = max(p["summary"]["trials"]["var_sharpe_daily"] for p in per.values())
    total = sum(p["summary"]["trials"]["total"] for p in per.values())
    allc = []
    for i, p in per.items():
        rows = load_rows(i)
        for c in p["candidates"]:
            c = dict(c)
            c["dsr_all"] = float(SEL.deflated_sharpe(rows["pnl"][c["row"]].astype(np.float64), n_eff, var))
            allc.append(c)
    summary = {"instruments": list(insts), "trials_total": total, "effective_total": n_eff,
               "var_sharpe_daily": var, "per_instrument": {i: p["summary"] for i, p in per.items()},
               "survivors": len(allc)}
    out = {"summary": summary, "candidates": allc}
    (D.DATA_DIR / "candidates_all.json").write_text(json.dumps(out, default=float))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--combine":
        o = combine(args[1:])
        s = o["summary"]
        print("trials", s["trials_total"], "effective", s["effective_total"], "survivors", s["survivors"])
        for i, ps in s["per_instrument"].items():
            print(i, ps["trials"], ps["survivor_families"])
        raise SystemExit
    for inst in (args or ["nq"]):
        o = run_instrument(inst, resweep=inst != "nq" or "--resweep" in args)
        print(inst, json.dumps(o["summary"]["trials"]), o["summary"]["survivor_families"])
        print("  r1", o["summary"]["funnel_r1"].get("ALL"))
        print("  r2", o["summary"]["funnel_r2"].get("ALL"))
