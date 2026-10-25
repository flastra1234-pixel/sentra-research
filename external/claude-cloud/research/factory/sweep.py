"""Run a list of specs (all on one instrument) over its dataset. Results for discovery +
validation sessions go to sweep_<tag>_open.npz; results for the sealed test period (and, for
NQ, the 2026 futures holdout) go to sweep_<tag>_sealed.npz, which only unseal.py reads."""
import json
import time
from multiprocessing import Pool

import numpy as np

from . import data as D
from . import engine as E
from . import features as X
from . import strategies as S

DISCOVERY = (np.datetime64("2008-01-01"), np.datetime64("2016-12-31"))
VALIDATION = (np.datetime64("2017-01-01"), np.datetime64("2018-12-31"))
SEALED = (np.datetime64("2019-01-01"), np.datetime64("2020-05-31"))
WARMUP_FROM = np.datetime64("2007-09-01")
HOLDOUT = {"nq": "nq2026"}

_MKT = {}


def market(dataset):
    """(market tuple, dates, F) for a dataset; built once per process."""
    if dataset not in _MKT:
        s = D.load(dataset)
        if dataset != "nq2026":
            s = s.slice(s.dates >= WARMUP_FROM)
        F, vw, sig = X.build(s)
        _MKT[dataset] = ((s.o, s.h, s.l, s.c, F, vw, sig), s.dates, F)
    return _MKT[dataset]


def markets():
    """Back-compat: the NQ research set and its holdout."""
    return {"nas100": market("nas100"), "nq2026": market("nq2026")}


def period_masks(dataset="nas100"):
    _, dates, F = market(dataset)
    valid = F[:, X.VALID] > 0
    def m(a, b):
        return valid & (dates >= a) & (dates <= b)
    return {"discovery": m(*DISCOVERY), "validation": m(*VALIDATION), "sealed": m(*SEALED)}


def _run_one(spec):
    inst = spec.get("inst", "nq")
    out = {}
    for name in [E.INSTRUMENTS[inst].dataset] + ([HOLDOUT[inst]] if inst in HOLDOUT else []):
        mkt, _, F = market(name)
        mask = S.day_mask(F, spec["filter"])
        pnl, low, ntr, _ = E.run(spec["family"], mkt, spec["params"], mask, inst=inst)
        out[name] = (pnl.astype(np.float32), low.astype(np.float32), ntr.astype(np.int16))
    return out


def run(specs, tag, procs=4):
    t0 = time.time()
    insts = {s.get("inst", "nq") for s in specs}
    if len(insts) != 1:
        raise ValueError(f"one instrument per sweep, got {insts}")
    inst = insts.pop()
    ds = E.INSTRUMENTS[inst].dataset
    pm = period_masks(ds)
    open_cols = pm["discovery"] | pm["validation"]
    with Pool(procs) as pool:
        res = pool.map(_run_one, specs, chunksize=64)
    _, dates, _ = market(ds)

    def stack(name, k, cols=None):
        a = np.stack([r[name][k] for r in res])
        return a if cols is None else a[:, cols]
    ids = np.array([s["id"] for s in specs])
    meta = json.dumps([{k: s.get(k, "nq") for k in ("id", "family", "params", "filter", "knobs", "inst")}
                       for s in specs], default=float)
    D.DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(D.DATA_DIR / f"sweep_{tag}_open.npz", ids=ids, meta=np.array(meta),
             dates=dates[open_cols].astype(str), is_disc=pm["discovery"][open_cols],
             pnl=stack(ds, 0, open_cols), low=stack(ds, 1, open_cols), ntr=stack(ds, 2, open_cols))
    sc = pm["sealed"]
    sealed = dict(ids=ids, dates=dates[sc].astype(str), pnl=stack(ds, 0, sc), low=stack(ds, 1, sc),
                  ntr=stack(ds, 2, sc))
    if inst in HOLDOUT:
        _, qdates, Fq = market(HOLDOUT[inst])
        sealed.update(q_dates=qdates.astype(str), q_valid=Fq[:, X.VALID] > 0,
                      q_pnl=stack(HOLDOUT[inst], 0), q_low=stack(HOLDOUT[inst], 1),
                      q_ntr=stack(HOLDOUT[inst], 2))
    np.savez(D.DATA_DIR / f"sweep_{tag}_sealed.npz", **sealed)
    print(f"sweep {tag}: {len(specs)} specs in {time.time() - t0:.0f}s")


def load_open(tag):
    z = np.load(D.DATA_DIR / f"sweep_{tag}_open.npz", allow_pickle=False)
    return {k: z[k] for k in z.files} | {"meta": json.loads(str(z["meta"]))}


if __name__ == "__main__":
    run(S.round1(), "r1")
