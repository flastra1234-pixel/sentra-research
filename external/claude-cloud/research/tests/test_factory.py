"""Synthetic checks for the factory engine: P&L arithmetic, stops, marks, no lookahead."""
import numpy as np
import pytest

from factory import engine as E
from factory import features as X
from factory import strategies as S
from factory.data import Sessions


def _market(n=60, seed=0, drift=0.0):
    rng = np.random.default_rng(seed)
    base = 10_000.0
    o = np.zeros((n, 390)); h = np.zeros_like(o); l = np.zeros_like(o); c = np.zeros_like(o)
    px = base
    for i in range(n):
        for t in range(390):
            op = px
            px = px * (1 + drift + 0.0008 * rng.standard_normal())
            o[i, t] = op; c[i, t] = px
            h[i, t] = max(op, px) * (1 + 0.0002 * rng.random())
            l[i, t] = min(op, px) * (1 - 0.0002 * rng.random())
    dates = np.arange(np.datetime64("2015-01-05"), np.datetime64("2015-01-05") + np.timedelta64(n, "D")).astype("datetime64[D]")
    s = Sessions(dates, o, h, l, c, np.ones_like(o), h.max(axis=1), l.min(axis=1), "synthetic")
    F, vw, sig = X.build(s)
    return s, (o, h, l, c, F, vw, sig)


def test_tod_open_to_close_arithmetic():
    s, m = _market()
    F = m[4]
    mask = F[:, X.VALID] > 0
    pnl, low, ntr, _ = E.run("tod", m, [0, 0, 1, 0.0, 0], mask)
    o0, cl = s.o[:, 0], s.c[:, -1]
    exp = (cl - o0) * E.REF_PRICE / o0 * E.USD_PER_PT - E.ENTRY_COST - E.EXIT_COST
    assert np.allclose(pnl[mask], exp[mask])
    assert (ntr[mask] == 1).all() and (ntr[~mask] == 0).all()
    assert (low <= 0).all() and (low <= pnl + 1e-9).all()


def test_stop_caps_loss():
    s, m = _market(seed=3)
    F = m[4]
    mask = F[:, X.VALID] > 0
    pnl, low, ntr, _ = E.run("tod", m, [0, 0, 1, 0.5, 0], mask)
    # loss per trade is bounded by the stop distance plus costs (and a gap through the stop)
    bound = 0.5 * F[:, X.ATR14] * E.REF_PRICE * E.USD_PER_PT + E.ENTRY_COST + E.EXIT_COST + E.STOP_COST
    assert (pnl[mask] >= -bound[mask] * 1.05).all()


@pytest.mark.parametrize("fam", list(S.GENERATORS))
def test_path_matches_low_and_close(fam):
    s, m = _market(seed=5)
    F = m[4]
    mask = F[:, X.VALID] > 0
    params, _ = next(iter(S.GENERATORS[fam]()))
    pnl, low, ntr, path = E.run(fam, m, params, mask, want_path=True)
    assert np.allclose(np.minimum(path.min(axis=1), 0.0), low, atol=1e-6)
    assert (low <= 1e-9).all()


@pytest.mark.parametrize("fam", list(S.GENERATORS))
def test_no_lookahead_into_next_session(fam):
    """Changing the last session must not change any earlier session's result."""
    s, m = _market(seed=7)
    F = m[4]
    mask = F[:, X.VALID] > 0
    for params, _ in list(S.GENERATORS[fam]())[:25]:
        a = E.run(fam, m, params, mask)[0]
        s2, _ = _market(seed=7)
        s2.c[-1] *= 1.03; s2.h[-1] *= 1.03; s2.l[-1] *= 1.03; s2.o[-1, 1:] *= 1.03
        F2, vw2, sig2 = X.build(s2)
        b = E.run(fam, (s2.o, s2.h, s2.l, s2.c, F2, vw2, sig2), params, mask)[0]
        assert np.allclose(a[:-1], b[:-1])


def test_daily_features_use_only_the_open_of_today():
    s, _ = _market(seed=9)
    F = X.daily_features(s)
    s.c[30, 1:] *= 1.05; s.h[30, 1:] *= 1.05; s.l[30, 1:] *= 1.05
    G = X.daily_features(s)
    assert np.allclose(F[:31], G[:31], equal_nan=True)


def test_spec_ids_unique():
    specs = S.round1()
    assert len({sp["id"] for sp in specs}) == len(specs)
