"""Strategy grid on the Lucid session (absolute bar indices, see lx_data.T).

Round 1: window breakouts and fades (cash-open ORB, overnight range into the cash session,
Asia range into London, London ORB, pre-08:30 range), noise-area momentum from 09:30,
end-of-day momentum, timed holds between session landmarks (incl. the overnight drift
18:00 -> 09:30, which Lucid's 18:00-16:45 day allows), drives after an anchor, 09:30 gap.
Round 2 adds day filters, but only filters whose inputs exist before the strategy's first
possible entry (lx_features.AVAILABLE_AT)."""
import hashlib
import itertools
import json

import numpy as np

from . import lx_features as X

TF = (0, 1, 2)
LANDMARKS = (0, 120, 360, 480, 540, 720, 840, 870, 930, 960, 1080, 1200, 1260, 1290, 1320)
LAST = 1364


def _grid(**axes):
    keys = list(axes)
    for vals in itertools.product(*(axes[k] for k in keys)):
        yield dict(zip(keys, vals))


BRK_WINDOWS = (
    [("orb", 930, rb, cut, tx) for rb in (935, 945, 960, 990) for cut in (1020, 1170)
     for tx in (1080, 1315, 1364) if cut < tx]
    + [("on_rth", 0, 930, cut, tx) for cut in (1020, 1170) for tx in (1315, 1364)]
    + [("asia_ldn", ra, 540, cut, tx) for ra in (0, 120) for cut in (660, 900) for tx in (929, 1364)]
    + [("ldn_orb", 540, rb, cut, tx) for rb in (570, 600) for cut in (720, 900) for tx in (929, 1364)]
    + [("pre_data", 810, 870, cut, tx) for cut in (900, 960) for tx in (1080, 1364)]
)


def brk():
    for (name, ra, rb, cut, tx), g in itertools.product(BRK_WINDOWS, _grid(
            dir_mode=(0, 1, 2), stop=((0, 0.0), (1, 0.5), (2, 0.1), (2, 0.2)),
            target_r=(0, 1, 2, 3), be_r=(0, 1), tf=TF)):
        sm, sv = g["stop"]
        k = dict(g, window=name, ra=ra, rb=rb, cut=cut, tx=tx)
        yield [ra, rb, cut, g["dir_mode"], sm, sv, g["target_r"], tx, g["be_r"], g["tf"], 1], k


FADE_WINDOWS = ([("on_rth", 0, 930, 1170, tx) for tx in (1315, 1364)]
                + [("asia_ldn", 0, 540, 900, tx) for tx in (929, 1364)]
                + [("orb", 930, rb, 1170, 1315) for rb in (960, 990)])


def fade():
    for (name, ra, rb, cut, tx), g in itertools.product(FADE_WINDOWS, _grid(
            dir_mode=(0, 1, 2), stop=(0.1, 0.2, 0.4), target=(0, 1, 2), tf=TF)):
        k = dict(g, window=name, ra=ra, rb=rb, cut=cut, tx=tx)
        yield [ra, rb, cut, g["dir_mode"], g["stop"], g["target"], tx, g["tf"]], k


def noise():
    for g in _grid(lb=(0, 1, 2), mult=(0.6, 0.8, 1.0, 1.2, 1.5), freq=(15, 30, 60),
                   first_t=(30, 60), stop_mode=(0, 1, 2), every=(0, 1), reentry=(0, 1),
                   gap_adj=(0, 1), tf=(0, 1)):
        yield [g["lb"], g["mult"], g["freq"], g["first_t"], g["stop_mode"], g["every"],
               g["reentry"], g["gap_adj"], g["tf"], 0.0, 1319], g


def imom():
    for g in _grid(sig_mode=(0, 1, 2, 3), te=(1260, 1290, 1320), k=(0.0, 0.1, 0.25, 0.5),
                   follow=(1, 0), stop=(0.0, 0.3), tf=TF, tx=(1319, 1364)):
        if g["tx"] <= g["te"]:
            continue
        yield [g["sig_mode"], g["te"], g["k"], g["follow"], g["stop"], g["tf"], g["tx"]], g


def hold():
    exits = sorted({t - 1 for t in LANDMARKS if t > 0} | {LAST})
    for te in LANDMARKS:
        for tx in exits:
            if tx <= te:
                continue
            for g in _grid(d=(1, -1), stop=(0.0, 0.5), tf=TF):
                yield [te, tx, g["d"], g["stop"], g["tf"]], dict(g, te=te, tx=tx)


DRIVE_EXITS = {0: (539, 929), 540: (929, 1364), 870: (1080, 1364), 930: (1080, 1315)}


def drive():
    for ta, txs in DRIVE_EXITS.items():
        for g in _grid(t1=(15, 30, 60), k=(0.1, 0.2, 0.3), follow=(1, 0), stop=(0.15, 0.3),
                       target_r=(0, 2), tx=txs, tf=TF):
            yield [ta, g["t1"], g["k"], g["follow"], g["stop"], g["target_r"], g["tx"], g["tf"]], dict(g, anchor=ta)


def gap():
    for g in _grid(gmin=(0.1, 0.2, 0.3, 0.5), gmax=(0.6, 1.0, 3.0), mode=(0, 1),
                   delay=(0, 5, 15, 30), stop=(0.25, 0.5, 1.0), tgt=(0.5, 1.0),
                   tx=(990, 1050, 1315), tf=(0, 1)):
        if g["gmin"] >= g["gmax"]:
            continue
        tgt = g["tgt"] if g["mode"] == 0 else g["tgt"] * 2
        yield [g["gmin"], g["gmax"], g["mode"], g["delay"], g["stop"], tgt, g["tx"], g["tf"]], g


GENERATORS = {"brk": brk, "fade": fade, "noise": noise, "imom": imom, "hold": hold,
              "drive": drive, "gap": gap}


def entry_from(family, p):
    """First bar a spec could trade; filters must be known by then."""
    return {"brk": lambda: p[1], "fade": lambda: p[1], "noise": lambda: 930 + p[3],
            "imom": lambda: p[1], "hold": lambda: p[0], "drive": lambda: p[0] + p[1],
            "gap": lambda: 930 + p[3]}[family]()


# name -> (availability index, mask function)
FILTERS = {
    "all": (0, lambda F: np.ones(len(F), bool)),
    "vol_low": (0, lambda F: F[:, X.VOLR] < 0.9),
    "vol_mid": (0, lambda F: (F[:, X.VOLR] >= 0.9) & (F[:, X.VOLR] <= 1.2)),
    "vol_high": (0, lambda F: F[:, X.VOLR] > 1.2),
    "vol_not_high": (0, lambda F: F[:, X.VOLR] <= 1.2),
    "vol_not_low": (0, lambda F: F[:, X.VOLR] >= 0.9),
    "no_mon": (0, lambda F: F[:, X.DOW] != 0),
    "no_fri": (0, lambda F: F[:, X.DOW] != 4),
    "tue_thu": (0, lambda F: (F[:, X.DOW] >= 1) & (F[:, X.DOW] <= 3)),
    "nr7_or_inside": (0, lambda F: (F[:, X.NR7] > 0) | (F[:, X.INSIDE] > 0)),
    "not_nr7": (0, lambda F: (F[:, X.NR7] == 0) & (F[:, X.INSIDE] == 0)),
    # ATR here is the full 18:00-16:45 session's true range (higher than cash-session ATR)
    "atr_le_20": (0, lambda F: F[:, X.ATR14] <= 0.020),
    "atr_le_25": (0, lambda F: F[:, X.ATR14] <= 0.025),
    "atr_le_30": (0, lambda F: F[:, X.ATR14] <= 0.030),
    "gap_small": (930, lambda F: np.abs(F[:, X.GAP_ATR]) < 0.25),
    "gap_large": (930, lambda F: np.abs(F[:, X.GAP_ATR]) >= 0.25),
    "on_quiet": (930, lambda F: F[:, X.ON_RANGE_ATR] < 0.4),
    "on_wide": (930, lambda F: F[:, X.ON_RANGE_ATR] >= 0.4),
}
CAPS = ("atr_le_20", "atr_le_25", "atr_le_30")


def day_mask(F, filt):
    m = F[:, X.VALID] > 0
    for part in filt.split("+"):
        m &= FILTERS[part][1](F)
    return m


def filter_ok(family, params, filt):
    t0 = entry_from(family, params)
    return all(FILTERS[p][0] <= t0 for p in filt.split("+"))


def spec_id(family, params, filt, inst="nq"):
    raw = json.dumps(["lx", inst, family, [round(float(p), 6) for p in params], filt])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def round1(inst="nq"):
    return [{"id": spec_id(f, p, "all", inst), "family": f, "params": p, "filter": "all",
             "knobs": k, "inst": inst} for f, gen in GENERATORS.items() for p, k in gen()]


def round2(bases):
    singles = [f for f in FILTERS if f != "all"]
    combos = singles + [f"{f}+{c}" for f in singles if not f.startswith("atr") for c in CAPS]
    out, seen = [], set()
    for b in bases:
        inst = b.get("inst", "nq")
        variants = [(b["params"], b["knobs"], False)]
        if b["family"] == "noise":
            for hs in (0.3, 0.5):
                p = list(b["params"]); p[9] = hs
                variants.append((p, dict(b["knobs"], hard_stop=hs), True))
        for params, knobs, fresh in variants:
            for filt in (["all"] if fresh else []) + combos:
                if not filter_ok(b["family"], params, filt):
                    continue
                sid = spec_id(b["family"], params, filt, inst)
                if sid in seen:
                    continue
                seen.add(sid)
                out.append({"id": sid, "family": b["family"], "params": params, "filter": filt,
                            "knobs": knobs, "base": b["id"], "inst": inst})
    return out


if __name__ == "__main__":
    from collections import Counter
    s = round1()
    print(len(s), Counter(x["family"] for x in s))
