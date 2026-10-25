"""Gates, plateau check, validation, deflation and the trial log. Reads only the open
(discovery + validation) sweep files; the sealed file is never opened here."""
import gzip
import json
from collections import defaultdict

import numpy as np

from . import data as D
from .lucid import deflated_sharpe

GATES = {
    "min_trades": 200,          # discovery trades (~22 a year)
    "t_disc": 2.0,              # t-stat of daily P&L, discovery
    "pf": 1.10,                 # profit factor of daily P&L
    "years_pos": 6,             # of 9 discovery years
    "avg_trade": 5.0,           # $ per micro per trade after costs (slippage headroom)
    "plateau_t": 1.0,           # median discovery t of one-step parameter neighbours
    "plateau_pos": 0.6,         # share of neighbours with positive t
    "t_val": 1.0,               # validation (2017-18) t-stat
}


def metrics(pnl, low, ntr, cols, dates):
    """Vectorised over specs. pnl/low/ntr: specs x sessions; cols: bool session mask."""
    p = pnl[:, cols].astype(np.float64)
    n = p.shape[1]
    mean = p.mean(axis=1)
    sd = p.std(axis=1, ddof=1)
    sd = np.where(sd > 0, sd, np.nan)
    t = mean / sd * np.sqrt(n)
    pos = np.where(p > 0, p, 0).sum(axis=1)
    neg = -np.where(p < 0, p, 0).sum(axis=1)
    trades = ntr[:, cols].sum(axis=1).astype(np.float64)
    yrs = dates[cols].astype("datetime64[Y]")
    uy = np.unique(yrs)
    yearly = np.stack([p[:, yrs == y].sum(axis=1) for y in uy], axis=1)
    half = len(uy) // 2
    cum = np.cumsum(p, axis=1)
    dd = (cum - np.maximum.accumulate(np.maximum(cum, 0), axis=1)).min(axis=1)
    return {
        "mean": mean, "sd": sd, "t": t, "sharpe_ann": mean / sd * np.sqrt(252),
        "pf": np.where(neg > 0, pos / np.where(neg > 0, neg, 1), np.inf),
        "trades": trades, "traded_days": (ntr[:, cols] > 0).sum(axis=1),
        "avg_trade": np.where(trades > 0, p.sum(axis=1) / np.maximum(trades, 1), 0.0),
        "years_pos": (yearly > 0).sum(axis=1), "n_years": len(uy),
        "first_half": yearly[:, :half].sum(axis=1), "second_half": yearly[:, half:].sum(axis=1),
        "max_dd": dd, "worst_low": low[:, cols].min(axis=1).astype(np.float64),
        "yearly": yearly, "years": [str(y) for y in uy],
    }


def metrics_chunked(pnl, low, ntr, cols, dates, chunk=20000):
    """metrics() over row chunks (a sweep can hold several hundred thousand specs)."""
    parts = [metrics(pnl[a:a + chunk], low[a:a + chunk], ntr[a:a + chunk], cols, dates)
             for a in range(0, len(pnl), chunk)]
    out = {}
    for k, v in parts[0].items():
        out[k] = np.concatenate([p[k] for p in parts]) if isinstance(v, np.ndarray) else v
    return out


def _hashable(v):
    return tuple(v) if isinstance(v, list) else v


def neighbours(meta):
    """index -> list of indices that differ in exactly one knob by one grid step."""
    axes = defaultdict(lambda: defaultdict(set))
    for m in meta:
        for k, v in m["knobs"].items():
            axes[(m["family"], m["filter"])][k].add(_hashable(v))
    order = {fk: {k: sorted(vs) for k, vs in ax.items()} for fk, ax in axes.items()}
    index = {}
    for i, m in enumerate(meta):
        key = (m["family"], m["filter"], tuple(sorted((k, _hashable(v)) for k, v in m["knobs"].items())))
        index[key] = i
    out = []
    for m in meta:
        fk = (m["family"], m["filter"])
        kn = {k: _hashable(v) for k, v in m["knobs"].items()}
        nb = []
        for k, v in kn.items():
            vals = order[fk][k]
            j = vals.index(v)
            for jj in (j - 1, j + 1):
                if 0 <= jj < len(vals):
                    alt = dict(kn)
                    alt[k] = vals[jj]
                    key = (m["family"], m["filter"], tuple(sorted(alt.items())))
                    if key in index:
                        nb.append(index[key])
        out.append(nb)
    return out


def evaluate(sw, n_trials_total, var_trials=None, log_path=None, gates=None):
    """Run every gate. Returns (table of per-spec results, list of survivors' indices).
    gates overrides GATES; years_pos may be given as a fraction (<= 1) of discovery years."""
    G = dict(GATES, **(gates or {}))
    meta = sw["meta"]
    dates = sw["dates"].astype("datetime64[D]")
    disc = sw["is_disc"]
    val = ~disc
    md = metrics_chunked(sw["pnl"], sw["low"], sw["ntr"], disc, dates)
    mv = metrics_chunked(sw["pnl"], sw["low"], sw["ntr"], val, dates)
    nbs = neighbours(meta)
    tdisc = np.nan_to_num(md["t"], nan=0.0)
    plateau = np.array([np.median(tdisc[nb]) if nb else 0.0 for nb in nbs])
    plateau_pos = np.array([np.mean(tdisc[nb] > 0) if nb else 0.0 for nb in nbs])
    # deflation over disc+val combined, against every trial ever run
    both = disc | val
    p_all = sw["pnl"][:, both]
    if var_trials is None:
        sr_all = np.concatenate([(lambda q: q.mean(axis=1) / np.where(q.std(axis=1, ddof=1) > 0,
                                                                       q.std(axis=1, ddof=1), np.nan))(
            p_all[a:a + 20000].astype(np.float64)) for a in range(0, len(p_all), 20000)])
        var_trials = float(np.nanvar(sr_all))
    rows, survivors = [], []
    for i, m in enumerate(meta):
        r = {"id": m["id"], "family": m["family"], "filter": m["filter"], "knobs": m["knobs"],
             "params": m["params"],
             "disc": {k: _f(md[k][i]) for k in ("mean", "t", "sharpe_ann", "pf", "trades",
                                                 "avg_trade", "years_pos", "max_dd", "worst_low")},
             "val": {k: _f(mv[k][i]) for k in ("mean", "t", "sharpe_ann", "pf", "trades", "max_dd")},
             "plateau_t": _f(plateau[i]), "plateau_pos": _f(plateau_pos[i])}
        stop = None
        if md["trades"][i] < G["min_trades"]:
            stop = ("activity", f"{int(md['trades'][i])} trades < {G['min_trades']}")
        elif not (md["t"][i] >= G["t_disc"]):
            stop = ("edge", f"discovery t {md['t'][i]:.2f} < {G['t_disc']}")
        elif md["pf"][i] < G["pf"]:
            stop = ("edge", f"profit factor {md['pf'][i]:.2f} < {G['pf']}")
        elif md["avg_trade"][i] < G["avg_trade"]:
            stop = ("costs", f"avg trade ${md['avg_trade'][i]:.2f} < ${G['avg_trade']}")
        elif md["years_pos"][i] < (G["years_pos"] * md["n_years"] if G["years_pos"] <= 1 else G["years_pos"]) or md["first_half"][i] <= 0 or md["second_half"][i] <= 0:
            stop = ("stability", f"{int(md['years_pos'][i])}/{md['n_years']} years positive, halves "
                                 f"{md['first_half'][i]:.0f}/{md['second_half'][i]:.0f}")
        elif plateau[i] < G["plateau_t"] or plateau_pos[i] < G["plateau_pos"]:
            stop = ("plateau", f"neighbour median t {plateau[i]:.2f}, {plateau_pos[i]:.0%} positive")
        elif not (mv["t"][i] >= G["t_val"]) or mv["mean"][i] <= 0:
            stop = ("validation", f"2017-18 t {mv['t'][i]:.2f}, mean ${mv['mean'][i]:.2f}/day")
        if stop is None:
            dsr = deflated_sharpe(p_all[i].astype(np.float64), n_trials_total, var_trials)
            r["dsr"] = _f(dsr)
            survivors.append(i)
            r["stopped_at"], r["reason"] = "survived", f"DSR {dsr:.3f} over {n_trials_total} trials"
        else:
            r["stopped_at"], r["reason"] = stop
        rows.append(r)
    if log_path is not None:
        with gzip.open(log_path, "wt", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, default=float) + "\n")
    return rows, survivors, {"var_trials": var_trials, "md": md, "mv": mv}


def effective_trials(pnl, cols, order, rho=0.5, min_active=50):
    """Greedy leader clustering on daily P&L correlation: walk trials best-first, join the
    first leader correlated above rho, else start a new cluster. Returns cluster count,
    the deflation's N (near-duplicate variants are not independent tests)."""
    p = pnl[:, cols].astype(np.float32)
    active = (p != 0).sum(axis=1) >= min_active
    z = p - p.mean(axis=1, keepdims=True)
    nrm = np.linalg.norm(z, axis=1)
    z = np.where(nrm[:, None] > 0, z / np.where(nrm > 0, nrm, 1)[:, None], 0)
    leaders = []
    L = np.zeros((0, z.shape[1]), np.float32)
    for i in order:
        if not active[i]:
            continue
        if len(leaders) and (L @ z[i]).max() > rho:
            continue
        leaders.append(i)
        L = np.vstack([L, z[i]])
    return len(leaders), leaders


def _f(x):
    x = float(x)
    return round(x, 4) if np.isfinite(x) else None


def funnel(rows):
    order = ["activity", "edge", "costs", "stability", "plateau", "validation", "survived"]
    by_fam = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_fam[r["family"]][r["stopped_at"]] += 1
        by_fam["ALL"][r["stopped_at"]] += 1
    return {fam: {k: d.get(k, 0) for k in order} for fam, d in by_fam.items()}


def knob_lift(rows, family, gate_ok=lambda r: r["disc"]["t"] is not None):
    """Mean discovery t by knob value inside a family: what the failures say."""
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["family"] != family or not gate_ok(r):
            continue
        for k, v in r["knobs"].items():
            acc[k][json.dumps(v)].append(r["disc"]["t"] or 0.0)
    return {k: {v: (round(float(np.mean(ts)), 2), len(ts)) for v, ts in sorted(d.items())}
            for k, d in acc.items()}
