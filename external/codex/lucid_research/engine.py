"""Causal, bar-based MNQ research engine (not a live execution system).

Input is minute-start UTC OHLCV. All four signal rules use the close of a
completed bar; execution can first occur at the next minute's open. A signal
is never carried across a session. Complete regular sessions are required.

Conservative fill convention: stop wins when both stop and target occur in
one minute; adverse gaps are filled at the worse opening price; every entry
and exit pays adverse slippage, including targets. OHLC cannot resolve the
true intraminute path. No overnight holdings, pyramiding or position overlap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import weakref

try:
    from numba import njit
except ImportError:  # Correct but slower when numba is absent.
    def njit(*args, **kwargs):
        return lambda function: function

TICK = 0.25
POINT_VALUE = 2.0
TRADE_COLUMNS = [
    'entry_time', 'exit_time', 'session_date', 'direction', 'entry_price',
    'exit_price', 'stop_points', 'pnl_points', 'pnl_usd', 'mae_usd',
    'mfe_usd', 'exit_reason', 'bars_held',
]
_TF_CACHE = {}


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate prices and compute causal features once for a parameter search.

    A day must contain all 390 distinct minute-start RTH bars, 09:30--15:59 ET.
    Half days and sessions with missing bars are excluded. Features reset at
    the regular-session start. VWAP is cumulative typical-price * volume /
    cumulative volume, ATR is a 14-bar simple average of true range. EMAs use
    adjust=False and need 30 completed bars before pullback signals.
    """
    if df.attrs.get('lucid_prepared'):
        return df
    x = df.copy()
    x.columns = [str(c).lower() for c in x.columns]
    if not isinstance(x.index, pd.DatetimeIndex):
        raise TypeError('DataFrame must have a DatetimeIndex')
    if x.index.tz is None:
        raise ValueError('Timezone-aware timestamps required (convert to UTC)')
    x.index = x.index.tz_convert('UTC')
    if not x.index.is_monotonic_increasing or not x.index.is_unique:
        raise ValueError('Timestamps must be strictly increasing and unique')
    for col in ['open', 'high', 'low', 'close']:
        x[col] = pd.to_numeric(x[col], errors='coerce')
    if 'volume' not in x:
        x['volume'] = np.nan
    x['volume'] = pd.to_numeric(x.volume, errors='coerce')
    valid = (np.isfinite(x[['open','high','low','close']]).all(axis=1)
             & (x.high >= x[['open','close','low']].max(axis=1))
             & (x.low <= x[['open','close','high']].min(axis=1))
             & (x.low > 0))
    x = x.loc[valid].copy()
    et = x.index.tz_convert('America/New_York')
    x['minute'] = et.hour * 60 + et.minute
    x['session_date'] = et.date
    x = x.loc[(x.minute >= 570) & (x.minute < 960) & (et.dayofweek < 5)].copy()
    count = x.groupby('session_date').size()
    good_dates = count.index[count == 390]
    x = x.loc[x.session_date.isin(good_dates)].copy()
    # Given unique minute-aligned timestamps and the 390-minute window,
    # 390 bars establish continuity. Check seconds explicitly as well.
    invalid_seconds = (x.index.second != 0) | (x.index.microsecond != 0)
    if invalid_seconds.any():
        raise ValueError('Timestamps must identify minute-start bars')
    x['session_id'] = pd.factorize(x.session_date)[0]
    x['bar_in_session'] = x.minute - 570
    g = x.groupby('session_date', sort=False)
    prev_close = g.close.shift(1)
    tr = pd.concat([x.high-x.low, (x.high-prev_close).abs(),
                    (x.low-prev_close).abs()], axis=1).max(axis=1)
    x['atr'] = tr.groupby(x.session_date).transform(
        lambda s: s.rolling(14, min_periods=14).mean())
    # Every bar in a VWAP session must have observed nonnegative volume.
    volume_valid = (x.volume.notna() & (x.volume >= 0)).groupby(x.session_date).transform('all')
    typical = (x.high + x.low + x.close) / 3.0
    cv = x.volume.fillna(0).groupby(x.session_date).cumsum()
    cpv = (typical*x.volume.fillna(0)).groupby(x.session_date).cumsum()
    x['vwap'] = (cpv / cv.where(cv > 0)).where(volume_valid)
    for period in [9, 20, 21, 50, 100]:
        x[f'ema_{period}'] = g.close.transform(
            lambda s: s.ewm(span=period, adjust=False).mean())
    for minutes in [5, 15, 30, 60]:
        mask = x.bar_in_session < minutes
        # The range is only consumed once the opening interval has completed.
        # Masking prevents a future opening-range value being used early.
        rh = x.high.where(mask).groupby(x.session_date).transform('max')
        rl = x.low.where(mask).groupby(x.session_date).transform('min')
        x[f'or_high_{minutes}'] = rh.where(x.bar_in_session >= minutes)
        x[f'or_low_{minutes}'] = rl.where(x.bar_in_session >= minutes)
    x.attrs['lucid_prepared'] = True
    x.attrs['session_count'] = len(good_dates)
    x.attrs['rules'] = 'strict390_RTH_minute_start_close_signal_next_open'
    return x


def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Return close-of-bar directions and entry stop distances.

    Config families:
      orb: close crosses the completed opening range in breakout direction.
      failed_orb: bar pierces a range boundary and closes back inside it.
      vwap_reversion: previous close beyond band_atr*previous ATR from previous
        VWAP, followed by a directional reversal close; enters toward VWAP,
        with a fixed R target (it does not use a future VWAP as target).
      ema_pullback: EMA fast > slow, rising fast over five bars, and close
        crosses upward through fast EMA (mirror image for shorts).
    """
    x = prepare_data(df)
    if 'signal_minutes' in config:
        return higher_tf_signals(x, config)
    family = config.get('family', 'orb')
    g = x.groupby('session_date', sort=False)
    pc = g.close.shift(1)
    direction = pd.Series(0, index=x.index, dtype=np.int8)
    if family in ['orb', 'failed_orb']:
        minutes = int(config.get('or_minutes', 30))
        if f'or_high_{minutes}' not in x:
            raise ValueError('or_minutes must be one of 5,15,30,60')
        hi, lo = x[f'or_high_{minutes}'], x[f'or_low_{minutes}']
        if family == 'orb':
            long = (x.close > hi) & (pc <= hi)
            short = (x.close < lo) & (pc >= lo)
        else:
            inside = (x.close >= lo) & (x.close <= hi)
            long = (x.low < lo) & inside & (x.high <= hi)
            short = (x.high > hi) & inside & (x.low >= lo)
    elif family == 'vwap_reversion':
        band = float(config.get('band_atr', 1.5))
        pv = g.vwap.shift(1)
        pa = g.atr.shift(1)
        long = (pc < pv-band*pa) & (x.close > pc)
        short = (pc > pv+band*pa) & (x.close < pc)
    elif family == 'ema_pullback':
        fast = int(config.get('ema_fast', 9))
        slow = int(config.get('ema_slow', 50))
        ef, es = x[f'ema_{fast}'], x[f'ema_{slow}']
        pef = ef.groupby(x.session_date).shift(1)
        lag = ef.groupby(x.session_date).shift(5)
        long = (ef > es) & (ef > lag) & (pc <= pef) & (x.close > ef)
        short = (ef < es) & (ef < lag) & (pc >= pef) & (x.close < ef)
    else:
        raise ValueError(f'Unknown family: {family}')
    direction.loc[long & ~short] = 1
    direction.loc[short & ~long] = -1
    start = config.get('start_minute')
    if start is None:
        start = 600
    end = int(config.get('end_minute', 690))
    allowed = (x.minute >= int(start)) & (x.minute < end)
    if family == 'ema_pullback':
        allowed &= x.bar_in_session >= 30
    direction.loc[~allowed] = 0
    stops = np.ceil((x.atr * float(config.get('stop_atr', 1.5))) / TICK)*TICK
    valid_stop = (stops >= float(config.get('min_stop', 5.0))) & (stops <= float(config.get('max_stop', 60.0)))
    direction.loc[~valid_stop] = 0
    return pd.DataFrame({'direction': direction, 'stop_points': stops}, index=x.index)


def _aggregate_features(x: pd.DataFrame, minutes: int, atr_period: int) -> pd.DataFrame:
    """Aggregate daily-reset complete bars, labeled by final minute-start.

    A 09:30--09:34 five-minute bar is labeled09:34. Its OHLC is only known
    at09:35, which is the next-minute execution time in the minute engine.
    Thirteen complete30-minute bars cover a regular session exactly.
    """
    if minutes not in [1, 5, 15, 30]:
        raise ValueError('signal_minutes must be one of1,5,15,30')
    if atr_period < 1:
        raise ValueError('atr_period must be positive')
    key = (id(x), minutes, atr_period)
    cached = _TF_CACHE.get(key)
    if cached is not None and cached[0]() is x:
        return cached[1]
    y = x[['open','high','low','close','volume','minute','session_date','bar_in_session']].copy()
    y['_timestamp'] = y.index
    y['_bucket'] = y.bar_in_session // minutes
    a = y.groupby(['session_date','_bucket'], sort=False).agg(
        open=('open','first'), high=('high','max'), low=('low','min'),
        close=('close','last'), volume=('volume',lambda z:z.sum(min_count=1)),
        minute=('minute','last'), timestamp=('_timestamp','last'), count=('close','size'))
    a = a.loc[a['count'] == minutes].reset_index().set_index('timestamp')
    a.index.name = x.index.name
    g = a.groupby('session_date', sort=False)
    pc = g.close.shift(1)
    tr = pd.concat([a.high-a.low,(a.high-pc).abs(),(a.low-pc).abs()],axis=1).max(axis=1)
    a['atr'] = tr.groupby(a.session_date).transform(
        lambda z:z.rolling(atr_period,min_periods=atr_period).mean())
    # A partially missing source-volume day cannot create a valid VWAP.
    good_volume = (x.volume.notna() & (x.volume >= 0)).groupby(x.session_date).all()
    a.loc[~a.session_date.map(good_volume), 'volume'] = np.nan
    typical = (a.high+a.low+a.close)/3
    cv = a.volume.fillna(0).groupby(a.session_date).cumsum()
    cpv = (typical*a.volume.fillna(0)).groupby(a.session_date).cumsum()
    a['vwap'] = (cpv/cv.where(cv > 0)).where(a.session_date.map(good_volume))
    # Higher-timeframe VWAP uses aggregate typical prices, a stated OHLCV
    # approximation; it is not the exact volume-weighted trade-price VWAP.
    for period in [5,9,20,21,50,100]:
        a[f'ema_{period}'] = g.close.transform(lambda z:z.ewm(span=period,adjust=False).mean())
    a['agg_bar'] = g.cumcount()
    for opening in [5,15,30,60]:
        a[f'or_high_{opening}'] = x[f'or_high_{opening}'].reindex(a.index)
        a[f'or_low_{opening}'] = x[f'or_low_{opening}'].reindex(a.index)
    _TF_CACHE[key] = (weakref.ref(x), a)
    return a


def higher_tf_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Completed higher-timeframe signals executed on original minute bars.

    Expansion-only options: explicit signal_minutes1/5/15/30, atr_period5/14,
    stop_mode='atr' or 'or_fraction', stop_fraction=.25/.5/1. Structural
    stops are a fraction of completed opening-range width. Out-of-range
    stops are rejected, never clamped. EMA warmup defaults max(3,fast);
    EMA is seeded at each day's first aggregate close. VWAP requires3bars.
    """
    x = prepare_data(df)
    minutes = int(config.get('signal_minutes',5))
    a = _aggregate_features(x,minutes,int(config.get('atr_period',5)))
    g = a.groupby('session_date',sort=False)
    pc = g.close.shift(1)
    family = config.get('family','orb')
    direction = pd.Series(0,index=a.index,dtype=np.int8)
    opening = int(config.get('or_minutes',30))
    hi,lo = a[f'or_high_{opening}'], a[f'or_low_{opening}']
    if family == 'orb':
        long = (a.close > hi) & (pc <= hi)
        short = (a.close < lo) & (pc >= lo)
    elif family == 'failed_orb':
        inside = (a.close >= lo) & (a.close <= hi)
        long = (a.low < lo) & inside & (a.high <= hi)
        short = (a.high > hi) & inside & (a.low >= lo)
    elif family == 'vwap_reversion':
        band = float(config.get('band_atr',1.5))
        pv,pa = g.vwap.shift(1),g.atr.shift(1)
        long = (pc < pv-band*pa) & (a.close > pc)
        short = (pc > pv+band*pa) & (a.close < pc)
        warm = a.agg_bar+1 >= int(config.get('min_agg_bars',3))
        long &= warm
        short &= warm
    elif family == 'ema_pullback':
        fast,slow = int(config.get('ema_fast',5)),int(config.get('ema_slow',20))
        ef,es = a[f'ema_{fast}'],a[f'ema_{slow}']
        pef = ef.groupby(a.session_date).shift(1)
        lag = ef.groupby(a.session_date).shift(int(config.get('ema_slope_bars',2)))
        warm = a.agg_bar+1 >= int(config.get('warmup_bars',max(3,fast)))
        long = (ef > es) & (ef > lag) & (pc <= pef) & (a.close > ef) & warm
        short = (ef < es) & (ef < lag) & (pc >= pef) & (a.close < ef) & warm
    elif family == 'time_entry':
        if minutes != 1:
            raise ValueError('time_entry requires signal_minutes=1')
        at_time = a.minute == int(config.get('entry_minute',600))-1
        mode = config.get('direction_mode','opening_momentum')
        if mode == 'long':
            long,short = at_time,pd.Series(False,index=a.index)
        elif mode == 'short':
            long,short = pd.Series(False,index=a.index),at_time
        elif mode == 'opening_momentum':
            opening_price = g.open.transform('first')
            long = at_time & (a.close > opening_price)
            short = at_time & (a.close < opening_price)
        else:
            raise ValueError('direction_mode must be long,short,opening_momentum')
    else:
        raise ValueError(f'Unknown family: {family}')
    direction.loc[long & ~short] = 1
    direction.loc[short & ~long] = -1
    start = int(config.get('start_minute',585))
    end = int(config.get('end_minute',720))
    direction.loc[(a.minute < start) | (a.minute >= end)] = 0
    mode = config.get('stop_mode','atr')
    if mode == 'or_fraction':
        raw_stop = (hi-lo)*float(config.get('stop_fraction',.5))
    elif mode == 'atr':
        raw_stop = a.atr*float(config.get('stop_atr',1.5))
    else:
        raise ValueError('stop_mode must be atr or or_fraction')
    stops = np.ceil(raw_stop/TICK)*TICK
    valid = (stops >= float(config.get('min_stop',5))) & (stops <= float(config.get('max_stop',100)))
    direction.loc[~valid] = 0
    signals = pd.DataFrame({'direction':direction,'stop_points':stops},index=a.index)
    out = signals.reindex(x.index)
    out['direction'] = out.direction.fillna(0).astype(np.int8)
    return out


@njit(cache=True)
def _execute(op, hi, lo, close, minute, session, signal, stop_size,
             reward_r, max_hold, max_trades, end_minute, slip, commission):
    n = len(op)
    # entry_idx,exit_idx,direction,entry,exit,stop,pnlpoints,pnldollars,
    # mae,mfe,reason,bars. Max possible trade count <= n.
    rows = np.empty((n, 12), dtype=np.float64)
    count = 0
    i = 0
    last_session = -1
    today_trades = 0
    while i < n-1:
        if session[i] != last_session:
            last_session = session[i]
            today_trades = 0
        if (signal[i] == 0 or today_trades >= max_trades
                or session[i+1] != session[i] or minute[i+1] > end_minute
                or minute[i+1] >= 955):
            i += 1
            continue
        side = signal[i]
        ei = i+1
        ep = op[ei]+side*slip
        risk = stop_size[i]
        stop = ep-side*risk
        reward = np.ceil(risk*reward_r/TICK)*TICK
        target = ep+side*reward
        worst = -slip
        best = 0.0
        reason = 2  # time/flat
        j = ei
        xp = ep
        while j < n and session[j] == session[ei]:
            if j-ei >= max_hold or minute[j] >= 955:
                xp = op[j]-side*slip
                excursion = side*(op[j]-ep)
                worst = min(worst, excursion-slip)
                best = max(best, excursion)
                reason = 2
                break
            if side == 1:
                hit_stop = lo[j] <= stop
                hit_target = hi[j] >= target
                if hit_stop:
                    raw = min(stop, op[j])
                    xp = raw-slip
                    worst = min(worst, xp-ep)
                    # The order within a stop bar is unknowable: for MFE,
                    # use opening price only rather than post-exit extrema.
                    best = max(best, op[j]-ep)
                    reason = 0
                    break
                worst = min(worst, lo[j]-ep-slip)
                if hit_target:
                    xp = target-slip
                    best = max(best, target-ep)
                    reason = 1
                    break
                best = max(best, hi[j]-ep)
            else:
                hit_stop = hi[j] >= stop
                hit_target = lo[j] <= target
                if hit_stop:
                    raw = max(stop, op[j])
                    xp = raw+slip
                    worst = min(worst, ep-xp)
                    best = max(best, ep-op[j])
                    reason = 0
                    break
                worst = min(worst, ep-hi[j]-slip)
                if hit_target:
                    xp = target+slip
                    best = max(best, ep-target)
                    reason = 1
                    break
                best = max(best, ep-lo[j])
            j += 1
        if j >= n or session[min(j,n-1)] != session[ei]:
            j -= 1
            xp = close[j]-side*slip
            reason = 2
        points = side*(xp-ep)
        rows[count,0] = ei
        rows[count,1] = j
        rows[count,2] = side
        rows[count,3] = ep
        rows[count,4] = xp
        rows[count,5] = risk
        rows[count,6] = points
        rows[count,7] = points*POINT_VALUE-commission
        rows[count,8] = worst*POINT_VALUE-commission
        rows[count,9] = best*POINT_VALUE-commission
        rows[count,10] = reason
        rows[count,11] = j-ei
        count += 1
        today_trades += 1
        # Exit bar close may generate the next signal, entering next open.
        i = max(j, ei)
    return rows[:count]


def run_backtest(df: pd.DataFrame, config: dict, commission: float = 1.24,
                 slip_ticks: float = 1) -> pd.DataFrame:
    """Return one-MNQ trades, including conservative marked-to-exit MAE.

    Costs are dollars per complete round trip per micro contract. Slippage
    is ticks per side. MAE includes a possible adverse exit and round-trip
    fee and is therefore conservative for an intraday equity-floor check.
    It is not reconstructed tick equity. Scaling contracts is done outside.
    """
    x = prepare_data(df)
    sig = generate_signals(x, config)
    args = [x[col].to_numpy(dtype=np.float64) for col in ['open','high','low','close']]
    rows = _execute(*args, x.minute.to_numpy(dtype=np.int64),
                    x.session_id.to_numpy(dtype=np.int64),
                    sig.direction.to_numpy(dtype=np.int64),
                    sig.stop_points.to_numpy(dtype=np.float64),
                    float(config.get('reward_r', 1.5)),
                    int(config.get('max_hold', 60)),
                    int(config.get('max_trades', 2)),
                    int(config.get('end_minute', 690)),
                    float(slip_ticks)*TICK, float(commission))
    if len(rows) == 0:
        return pd.DataFrame(columns=TRADE_COLUMNS)
    entry_idx, exit_idx = rows[:,0].astype(int), rows[:,1].astype(int)
    out = pd.DataFrame({
        'entry_time': x.index[entry_idx], 'exit_time': x.index[exit_idx],
        'session_date': x.session_date.to_numpy()[entry_idx],
        'direction': rows[:,2].astype(int), 'entry_price': rows[:,3],
        'exit_price': rows[:,4], 'stop_points': rows[:,5],
        'pnl_points': rows[:,6], 'pnl_usd': rows[:,7],
        'mae_usd': rows[:,8], 'mfe_usd': rows[:,9],
        'exit_reason': np.array(['stop','target','time'])[rows[:,10].astype(int)],
        'bars_held': rows[:,11].astype(int),
    })
    out.attrs['config'] = dict(config)
    out.attrs['commission'] = commission
    out.attrs['slip_ticks_per_side'] = slip_ticks
    out.attrs['complete_sessions'] = len(x.session_date.unique())
    return out


def daily_equity(trades: pd.DataFrame, dates=None) -> pd.DataFrame:
    """Daily net PNL and conservative intra-day low/high of closed+open PNL.

    Suitable for an EOD-trailing drawdown model whose floor is still enforced
    intraday. Sum-before-trade plus MAE preserves trade ordering within a day.
    """
    if trades.empty:
        return pd.DataFrame(index=pd.Index([] if dates is None else dates, name='session_date'),
                            columns=['pnl_usd','min_equity_usd','max_equity_usd','trades']).fillna(0)
    t = trades.sort_values('entry_time').copy()
    t['before'] = t.groupby('session_date').pnl_usd.cumsum()-t.pnl_usd
    t['low'] = t.before+t.mae_usd
    t['high'] = t.before+t.mfe_usd
    d = t.groupby('session_date').agg(pnl_usd=('pnl_usd','sum'),
                                      min_equity_usd=('low','min'),
                                      max_equity_usd=('high','max'),
                                      trades=('pnl_usd','size'))
    d.min_equity_usd = np.minimum(d.min_equity_usd, 0)
    d.max_equity_usd = np.maximum(np.maximum(d.max_equity_usd, d.pnl_usd), 0)
    if dates is not None:
        d = d.reindex(pd.Index(dates,name='session_date')).fillna(0)
    return d
