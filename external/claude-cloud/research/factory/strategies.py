"""The strategy grid. A spec is (family, params, filter); its id is a stable hash of all three,
so the trial log counts every distinct thing ever tested exactly once.

Round 1 = base families x parameters x trend-alignment (tf: 0 any, 1 with the 20-day trend,
2 against it). Day filters (volatility regime, weekday, gap size, NR7) are the round-2
"add a feature" step and are listed in FILTERS."""
import hashlib
import itertools
import json

import numpy as np

from . import features as X

TF = (0, 1, 2)


def _grid(**axes):
    keys = list(axes)
    for vals in itertools.product(*(axes[k] for k in keys)):
        yield dict(zip(keys, vals))


def orb():
    for g in _grid(or_len=(5, 15, 30, 60), cutoff=(90, 240), dir_mode=(0, 1, 2),
                   stop=((0, 0.0), (1, 0.5), (2, 0.15), (2, 0.3)), target_r=(0, 1, 1.5, 2, 3),
                   tx=(150, 385), be_r=(0, 1), tf=TF):
        if g["cutoff"] <= g["or_len"]:
            continue
        sm, sv = g["stop"]
        yield [g["or_len"], g["cutoff"], g["dir_mode"], sm, sv, g["target_r"], g["tx"],
               g["be_r"], 1, g["tf"]], g


def noise():
    for g in _grid(lb=(0, 1, 2), mult=(0.6, 0.8, 1.0, 1.2, 1.5), freq=(15, 30, 60),
                   first_t=(30, 60), stop_mode=(0, 1, 2), every=(0, 1), reentry=(0, 1),
                   gap_adj=(0, 1), tf=(0, 1)):
        yield [g["lb"], g["mult"], g["freq"], g["first_t"], g["stop_mode"], g["every"],
               g["reentry"], g["gap_adj"], g["tf"], 0.0], g


def imom():
    for g in _grid(sig_mode=(0, 1, 2), te=(300, 330, 360), k=(0.0, 0.1, 0.25, 0.5),
                   follow=(1, 0), stop=(0.0, 0.3), tf=TF):
        yield [g["sig_mode"], g["te"], g["k"], g["follow"], g["stop"], g["tf"]], g


def gap():
    for g in _grid(gmin=(0.1, 0.2, 0.3, 0.5), gmax=(0.6, 1.0, 3.0), mode=(0, 1),
                   delay=(0, 5, 15, 30), stop=(0.25, 0.5, 1.0), tgt=(0.5, 1.0),
                   tx=(60, 120, 389), tf=(0, 1)):
        if g["gmin"] >= g["gmax"]:
            continue
        tgt = g["tgt"] if g["mode"] == 0 else g["tgt"] * 2      # go mode: 1R / 2R
        yield [g["gmin"], g["gmax"], g["mode"], g["delay"], g["stop"], tgt, g["tx"], g["tf"]], g


def vwap():
    for g in _grid(k=(0.25, 0.4, 0.6, 0.8, 1.0), t_start=(30, 60), t_end=(300, 360),
                   stop=(0.25, 0.5, 1.0), tgt_mode=(0, 1), max_trades=(1, 3), tf=TF):
        yield [g["k"], g["t_start"], g["t_end"], g["stop"], g["tgt_mode"], g["max_trades"],
               g["tf"]], g


def level():
    for g in _grid(level=(0, 1), mode=(0, 1), dir_mode=(0, 1, 2), stop=(0.15, 0.3, 0.5),
                   target_r=(0, 1, 2, 3), tx=(150, 389), cutoff=(120, 330), tf=TF):
        if g["cutoff"] >= g["tx"]:
            continue
        yield [g["level"], g["mode"], g["dir_mode"], g["stop"], g["target_r"], g["tx"],
               g["cutoff"], g["tf"]], g


def tod():
    for g in _grid(te=(0, 30, 60, 120, 180, 240, 300, 330, 360), hold=(30, 60, 0),
                   d=(1, -1), stop=(0.0, 0.5), tf=TF):
        if g["hold"] and g["te"] + g["hold"] > 390:
            continue
        yield [g["te"], g["hold"], g["d"], g["stop"], g["tf"]], g


def drive():
    for g in _grid(t1=(29, 59, 89), k=(0.1, 0.2, 0.3, 0.5), follow=(1, 0),
                   stop=(0.25, 0.5, 1.0), target_r=(0, 1, 2), tx=(240, 389), tf=TF):
        yield [g["t1"], g["k"], g["follow"], g["stop"], g["target_r"], g["tx"], g["tf"]], g


def rsi():
    for g in _grid(lo=(5, 10, 20), ex=(50, 65), max_bars=(6, 12), stop=(0.2, 0.4, 0.8),
                   max_trades=(2, 4), tf=TF):
        yield [g["lo"], g["ex"], g["max_bars"], g["stop"], g["max_trades"], g["tf"]], g


GENERATORS = {"orb": orb, "noise": noise, "imom": imom, "gap": gap, "vwap": vwap,
              "level": level, "tod": tod, "drive": drive, "rsi": rsi}

# ---------------------------------------------------------------- day filters (decision-time)
FILTERS = {
    "all": lambda F: np.ones(len(F), bool),
    "vol_low": lambda F: F[:, X.VOLR] < 0.9,
    "vol_mid": lambda F: (F[:, X.VOLR] >= 0.9) & (F[:, X.VOLR] <= 1.2),
    "vol_high": lambda F: F[:, X.VOLR] > 1.2,
    "vol_not_high": lambda F: F[:, X.VOLR] <= 1.2,
    "vol_not_low": lambda F: F[:, X.VOLR] >= 0.9,
    "no_mon": lambda F: F[:, X.DOW] != 0,
    "no_fri": lambda F: F[:, X.DOW] != 4,
    "tue_thu": lambda F: (F[:, X.DOW] >= 1) & (F[:, X.DOW] <= 3),
    "gap_small": lambda F: np.abs(F[:, X.GAP_ATR]) < 0.25,
    "gap_large": lambda F: np.abs(F[:, X.GAP_ATR]) >= 0.25,
    "nr7_or_inside": lambda F: (F[:, X.NR7] > 0) | (F[:, X.INSIDE] > 0),
    "not_nr7": lambda F: (F[:, X.NR7] == 0) & (F[:, X.INSIDE] == 0),
    "atr_high": lambda F: F[:, X.ATR14] > 0.012,
    "atr_low": lambda F: F[:, X.ATR14] <= 0.012,
    # prop-risk caps: skip sessions whose prior 14-day ATR says one micro risks too much
    "atr_le_15": lambda F: F[:, X.ATR14] <= 0.015,
    "atr_le_20": lambda F: F[:, X.ATR14] <= 0.020,
    "atr_le_25": lambda F: F[:, X.ATR14] <= 0.025,
}


def day_mask(F, filt: str) -> np.ndarray:
    base = F[:, X.VALID] > 0
    for part in filt.split("+"):
        base &= FILTERS[part](F)
    return base


def spec_id(family, params, filt, inst="nq") -> str:
    body = [family, [round(float(p), 6) for p in params], filt]
    raw = json.dumps(body if inst == "nq" else [inst] + body)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def round1(inst="nq"):
    out = []
    for fam, gen in GENERATORS.items():
        for params, g in gen():
            out.append({"id": spec_id(fam, params, "all", inst), "family": fam, "params": params,
                        "filter": "all", "knobs": g, "inst": inst})
    return out


def round2(bases):
    """Part-2 step: every base that cleared the discovery gates gets each day filter, alone
    and combined with an ATR cap; noise-area bases also get hard stops (they have none)."""
    caps = ("atr_le_15", "atr_le_20", "atr_le_25")
    singles = [f for f in FILTERS if f != "all"]
    combos = singles + [f"{f}+{c}" for f in singles if not f.startswith("atr") for c in caps]
    out, seen = [], set()
    for b in bases:
        inst = b.get("inst", "nq")
        variants = [(b["params"], b["knobs"])]
        if b["family"] == "noise":
            for hs in (0.3, 0.5):
                p = list(b["params"]); p[9] = hs
                variants.append((p, dict(b["knobs"], hard_stop=hs)))
        for params, knobs in variants:
            for filt in (["all"] if params is not b["params"] else []) + combos:
                sid = spec_id(b["family"], params, filt, inst)
                if sid in seen:
                    continue
                seen.add(sid)
                out.append({"id": sid, "family": b["family"], "params": params, "filter": filt,
                            "knobs": knobs, "base": b["id"], "inst": inst})
    return out


if __name__ == "__main__":
    specs = round1()
    from collections import Counter
    print(len(specs), Counter(s["family"] for s in specs))
