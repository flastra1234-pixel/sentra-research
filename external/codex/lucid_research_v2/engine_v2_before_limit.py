"""Fast, causal, intraday futures research engine; no order placement.

Signals use completed 3/5/15-minute candles anchored to 09:30 New York and
execute at the following one-minute open. Indicators reset every day. Only
complete 390-minute RTH sessions are retained (an offline data-quality filter).

All dollar trade fields represent the TOTAL position, including its integer
quantity. They must not be multiplied by quantity again in account replays.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd
from numba import njit

TICK = 0.25
FEE = 1.24
WINDOWS = {'AM': (600, 690), 'mid': (690, 810), 'PM': (810, 900)}
FAMILIES = (
    'orb30', 'failed_orb30', 'orb_retest30', 'donchian_breakout12',
    'donchian_failed12', 'ema_pullback9_21', 'ema_cross9_21',
    'vwap_trend_reclaim', 'vwap_reversion', 'bollinger_reversion',
)
COMPACT_COLUMNS = [
    'entry_idx', 'exit_idx', 'session_id', 'pnl_usd', 'mae_usd',
    'quantity', 'stop_points', 'direction', 'entry_price', 'exit_price',
    'mfe_usd', 'exit_reason', 'bars_held', 'pnl_points',
]
COL = {name: i for i, name in enumerate(COMPACT_COLUMNS)}


@dataclass
class Market:
    asset: str
    point_value: float
    min_stop: float
    max_stop: float
    index: pd.DatetimeIndex
    session_id: np.ndarray
    session_dates: np.ndarray
    minute: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    bar_minutes: int = 1
    flat_minute: int = 955
    aggregates: dict[int, dict[str, Any]] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)


def _normalize(df: pd.DataFrame, bar_minutes: int=1) -> pd.DataFrame:
    x = df.copy()
    x.columns = [str(c).lower() for c in x.columns]
    if not isinstance(x.index, pd.DatetimeIndex):
        if 'datetime' not in x:
            raise TypeError('Expected UTC-aware DatetimeIndex or datetime column')
        x.index = pd.to_datetime(x.pop('datetime'), utc=True)
    if x.index.tz is None:
        raise ValueError('Timezone-aware timestamps are required')
    x.index = x.index.tz_convert('UTC')
    if not x.index.is_unique or not x.index.is_monotonic_increasing:
        raise ValueError('Timestamp index must be unique and sorted')
    if (x.index.second != 0).any() or (x.index.microsecond != 0).any():
        raise ValueError('Input must be native interval-start bars')
    if 'volume' not in x:
        x['volume'] = np.nan
    for c in ['open', 'high', 'low', 'close', 'volume']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    valid = (np.isfinite(x[['open', 'high', 'low', 'close']]).all(axis=1)
             & (x.high >= x[['open', 'close', 'low']].max(axis=1))
             & (x.low <= x[['open', 'close', 'high']].min(axis=1))
             & (x.low > 0))
    x = x.loc[valid].copy()
    et = x.index.tz_convert('America/New_York')
    x['minute'] = et.hour * 60 + et.minute
    x['session_date'] = et.date
    x = x.loc[(x.minute >= 570) & (x.minute < 960) & (et.dayofweek < 5)].copy()
    if ((x.minute-570) % bar_minutes != 0).any():
        raise ValueError('Input bars do not align to native interval from09:30')
    counts = x.groupby('session_date').size()
    good = counts.index[counts == 390//bar_minutes]
    x = x.loc[x.session_date.isin(good)].copy()
    x['session_id'] = pd.factorize(x.session_date)[0]
    x['bar'] = x.minute - 570
    return x


def build_market(df: pd.DataFrame, asset: str, bar_minutes: int=1) -> Market:
    """Prepare all common features once; performs no strategy backtests."""
    asset = asset.upper()
    aliases = {'MNQ': 'NQ', 'MES': 'ES'}
    asset = aliases.get(asset, asset)
    if asset not in ['NQ', 'ES']:
        raise ValueError('This registered engine supports NQ/MNQ and ES/MES only')
    if bar_minutes not in [1,3]:raise ValueError('Native bar_minutes must be1or3')
    x = _normalize(df,bar_minutes)
    if x.empty:
        raise ValueError('No complete RTH sessions in input')
    pv, minimum, maximum = (2.0, 5.0, 100.0) if asset == 'NQ' else (5.0, 1.0, 20.0)
    market = Market(
        asset, pv, minimum, maximum, x.index,
        x.session_id.to_numpy(np.int64), x.session_date.unique(),
        x.minute.to_numpy(np.int64),
        *[x[c].to_numpy(np.float64) for c in ['open','high','low','close','volume']],
        bar_minutes=bar_minutes,flat_minute=(955 if bar_minutes==1 else 954),
    )
    market.quality = {'input_rows': len(df), 'retained_rows': len(x),
                      'complete_sessions': len(market.session_dates),
                      'strict_full_RTH': True,'native_bar_minutes':bar_minutes,
                      'bar_label': 'interval_start_assumed'}
    for tf in [3,5,6,15]:
        if tf % bar_minutes == 0:
            market.aggregates[tf] = _features(x, tf,bar_minutes)
    return market


def _features(x: pd.DataFrame, tf: int,bar_minutes: int=1) -> dict[str, Any]:
    y = x[['open','high','low','close','volume','minute','session_id','bar']].copy()
    y['minute_idx'] = np.arange(len(y))
    y['bucket'] = y.bar // tf
    a = y.groupby(['session_id','bucket'], sort=False).agg(
        open=('open','first'), high=('high','max'), low=('low','min'),
        close=('close','last'), volume=('volume',lambda z:z.sum(min_count=1)),
        minute=('minute','last'), minute_idx=('minute_idx','last'),
        count=('close','size')).reset_index()
    a = a.loc[a['count'] == tf//bar_minutes].copy()
    g = a.groupby('session_id', sort=False)
    pc = g.close.shift(1)
    tr = pd.concat([a.high-a.low, (a.high-pc).abs(), (a.low-pc).abs()],axis=1).max(axis=1)
    a['atr'] = tr.groupby(a.session_id).transform(lambda z:z.rolling(5,min_periods=5).mean())
    for period in [9,21]:
        a[f'ema{period}'] = g.close.transform(lambda z:z.ewm(span=period,adjust=False).mean())
    e9 = a.ema9; e21 = a.ema21
    pe9 = e9.groupby(a.session_id).shift(1)
    pe21 = e21.groupby(a.session_id).shift(1)
    slope = e9-e9.groupby(a.session_id).shift(2)
    diff = g.close.diff().abs()
    path = diff.groupby(a.session_id).transform(lambda z:z.rolling(10,min_periods=10).sum())
    a['er'] = ((a.close-g.close.shift(10)).abs()/path.where(path>0))
    ch = g.high.transform(lambda z:z.shift(1).rolling(12,min_periods=12).max())
    cl = g.low.transform(lambda z:z.shift(1).rolling(12,min_periods=12).min())
    mean = g.close.transform(lambda z:z.shift(1).rolling(20,min_periods=20).mean())
    std = g.close.transform(lambda z:z.shift(1).rolling(20,min_periods=20).std(ddof=0))
    upper,lower = mean+2*std,mean-2*std
    good_vol = (x.volume.notna() & (x.volume>=0)).groupby(x.session_id).all()
    cv = a.volume.fillna(0).groupby(a.session_id).cumsum()
    typical = (a.high+a.low+a.close)/3
    cvp = (typical*a.volume.fillna(0)).groupby(a.session_id).cumsum()
    vw = (cvp/cv.where(cv>0)).where(a.session_id.map(good_vol))
    pvw = vw.groupby(a.session_id).shift(1)
    pat = a.atr.groupby(a.session_id).shift(1)
    # Opening-range values are only consumed by aggregate candles entirely
    # AFTER 10:00. Their highs/lows cannot borrow later session prices.
    hh = x.high.where(x.bar<30).groupby(x.session_id).max()
    ll = x.low.where(x.bar<30).groupby(x.session_id).min()
    hi = a.session_id.map(hh).where(a.minute>=600)
    lo = a.session_id.map(ll).where(a.minute>=600)
    sig = {}
    def put(name, long, short):
        signal = np.zeros(len(a),dtype=np.int8)
        signal[np.asarray(long & ~short).astype(bool)] = 1
        signal[np.asarray(short & ~long).astype(bool)] = -1
        sig[name] = signal
    put('orb30',(a.close>hi)&(pc<=hi),(a.close<lo)&(pc>=lo))
    inside = (a.close>=lo)&(a.close<=hi)
    put('failed_orb30',(a.low<lo)&inside&(a.high<=hi),(a.high>hi)&inside&(a.low>=lo))
    sig['orb_retest30'] = _retest(a.session_id.to_numpy(np.int64),
        a.close.to_numpy(),a.high.to_numpy(),a.low.to_numpy(),
        hi.to_numpy(),lo.to_numpy())
    put('donchian_breakout12',a.close>ch,a.close<cl)
    channel_inside = (a.close>=cl)&(a.close<=ch)
    put('donchian_failed12',(a.low<cl)&channel_inside&(a.high<=ch),
        (a.high>ch)&channel_inside&(a.low>=cl))
    put('ema_pullback9_21',(e9>e21)&(slope>0)&(pc<=pe9)&(a.close>e9),
        (e9<e21)&(slope<0)&(pc>=pe9)&(a.close<e9))
    put('ema_cross9_21',(e9>e21)&(pe9<=pe21),(e9<e21)&(pe9>=pe21))
    put('vwap_trend_reclaim',(e9>e21)&(pc<=pvw)&(a.close>vw),
        (e9<e21)&(pc>=pvw)&(a.close<vw))
    put('vwap_reversion',(pc<pvw-2*pat)&(a.close>pc),
        (pc>pvw+2*pat)&(a.close<pc))
    # Current thresholds use ONLY the prior20closes; crossing is evaluated
    # against those fixed, already-known bands.
    put('bollinger_reversion',(pc<lower)&(a.close>=lower),
        (pc>upper)&(a.close<=upper))
    return {'minute_idx':a.minute_idx.to_numpy(np.int64),
            'minute':a.minute.to_numpy(np.int64),'session_id':a.session_id.to_numpy(np.int64),
            'atr':a.atr.to_numpy(np.float64),'er':a.er.to_numpy(np.float64),
            'signals':sig}


@njit(cache=True)
def _retest(session, close, high, low, upper, lower):
    n=len(close);out=np.zeros(n,np.int8)
    armed_long=False;armed_short=False;last=-1
    for i in range(n):
        if session[i]!=last:
            armed_long=False;armed_short=False;last=session[i]
        if not np.isfinite(upper[i]) or not np.isfinite(lower[i]):
            continue
        # A breakout cannot simultaneously count as its own later retest.
        if armed_long and low[i]<=upper[i] and close[i]>upper[i]:
            out[i]=1;armed_long=False
        elif armed_short and high[i]>=lower[i] and close[i]<lower[i]:
            out[i]=-1;armed_short=False
        if close[i]<upper[i]:armed_long=False
        if close[i]>lower[i]:armed_short=False
        if i>0 and session[i-1]==session[i]:
            if close[i]>upper[i] and close[i-1]<=upper[i]:armed_long=True
            if close[i]<lower[i] and close[i-1]>=lower[i]:armed_short=True
    return out


def _sparse_signals(market: Market, config: dict):
    family = config['family']
    # Aliases allow drivers to use short family names without another grid.
    aliases={'orb':'orb30','failed_orb':'failed_orb30','orb_retest':'orb_retest30',
             'donchian_breakout':'donchian_breakout12','donchian_failed':'donchian_failed12',
             'ema_pullback':'ema_pullback9_21','ema_cross':'ema_cross9_21'}
    family=aliases.get(family,family)
    if family not in FAMILIES:raise ValueError(f'Unknown family:{family}')
    tf=int(config['tf']);a=market.aggregates[tf]
    direction=a['signals'][family].copy()
    window=config.get('window','AM')
    if isinstance(window,str):
        # Accept case-insensitive canonical labels.
        window={'am':'AM','mid':'mid','pm':'PM'}.get(window.lower(),window)
        start,end=WINDOWS[window]
    else:start,end=window
    allowed=(a['minute']>=start)&(a['minute']<end)
    context=config.get('context','none')
    if context=='trend':allowed &= a['er']>=.35
    elif context=='range':allowed &= a['er']<=.20
    elif context!='none':raise ValueError('context must be none/trend/range')
    mode=config.get('direction','both')
    if mode=='long':allowed &= direction>0
    elif mode=='short':allowed &= direction<0
    elif mode!='both':raise ValueError('direction must be both/long/short')
    stops=np.ceil(a['atr']*float(config.get('stop_atr',1.5))/TICK)*TICK
    allowed &= np.isfinite(stops)&(stops>=market.min_stop)&(stops<=market.max_stop)&(direction!=0)
    return (a['minute_idx'][allowed],direction[allowed].astype(np.int64),stops[allowed],int(end))


def config_signals(market: Market, config: dict):
    """Return full minute-indexed direction and stop arrays for inspection."""
    idx,d,s,_ = _sparse_signals(market,config)
    directions=np.zeros(len(market.index),np.int8)
    stops=np.full(len(market.index),np.nan)
    directions[idx]=d;stops[idx]=s
    return directions,stops


@njit(cache=True)
def _execute(op,high,low,close,minute,session,signal_idx,signal_side,signal_stop,
             point_value,reward_r,max_hold,end_minute,slip,fee,budget,max_contracts,max_trades,
             flat_minute):
    n=len(op);rows=np.empty((len(signal_idx),14),np.float64);count=0
    last_session=-1;today=0;last_exit=-1
    for k in range(len(signal_idx)):
        i=signal_idx[k]
        if session[i]!=last_session:
            last_session=session[i];today=0
        if i<last_exit or today>=max_trades or i+1>=n:
            continue
        ei=i+1
        if session[ei]!=session[i] or minute[ei]>end_minute or minute[ei]>=flat_minute:
            continue
        risk=signal_stop[k]
        # Same integer sizing under both cost cases; four ticks is the full
        # two-per-side stressed friction allowance, plus round-trip fees.
        q=int(np.floor(budget/(risk*point_value+fee+4*TICK*point_value)))
        if q>max_contracts:q=max_contracts
        if q<1:continue
        side=signal_side[k];ep=op[ei]+side*slip
        stop=ep-side*risk
        target=ep+side*np.ceil(risk*reward_r/TICK)*TICK
        worst=-slip;best=0.;reason=2;j=ei;xp=ep
        while j<n and session[j]==session[ei]:
            if minute[j]-minute[ei]>=max_hold or minute[j]>=flat_minute:
                xp=op[j]-side*slip
                excursion=side*(op[j]-ep)
                worst=min(worst,excursion-slip);best=max(best,excursion)
                break
            if side==1:
                if low[j]<=stop:
                    xp=min(stop,op[j])-slip
                    worst=min(worst,xp-ep);best=max(best,op[j]-ep)
                    reason=0;break
                worst=min(worst,low[j]-ep-slip)
                if high[j]>=target:
                    xp=target-slip;best=max(best,target-ep);reason=1;break
                best=max(best,high[j]-ep)
            else:
                if high[j]>=stop:
                    xp=max(stop,op[j])+slip
                    worst=min(worst,ep-xp);best=max(best,ep-op[j])
                    reason=0;break
                worst=min(worst,ep-high[j]-slip)
                if low[j]<=target:
                    xp=target+slip;best=max(best,ep-target);reason=1;break
                best=max(best,ep-low[j])
            j+=1
        if j>=n or session[min(j,n-1)]!=session[ei]:
            j-=1;xp=close[j]-side*slip;reason=2
        points=side*(xp-ep)
        pnl=(points*point_value-fee)*q
        mae=min(worst*point_value-fee,points*point_value-fee,0.)*q
        rows[count,0]=ei;rows[count,1]=j;rows[count,2]=session[ei]
        rows[count,3]=pnl;rows[count,4]=mae;rows[count,5]=q
        rows[count,6]=risk;rows[count,7]=side;rows[count,8]=ep;rows[count,9]=xp
        rows[count,10]=(best*point_value-fee)*q
        rows[count,11]=reason;rows[count,12]=j-ei;rows[count,13]=points
        count+=1;today+=1;last_exit=j
    return rows[:count]


def backtest(market: Market, config: dict, slip_ticks: float=2,
             risk_budget: float=60, return_frame: bool=True,
             commission: float=FEE, max_contracts: int=10,
             max_trades: int=2):
    """Execute a config. Compact columns are COMPACT_COLUMNS; dollars TOTAL.

    Risk sizing is fixed to the stressed4tick friction allowance regardless
    of chosen fill stress, so the cost comparison does not optimize size.
    """
    if risk_budget<=0 or commission<0 or slip_ticks<0:
        raise ValueError('Invalid risk/cost assumptions')
    if not 1<=max_contracts<=10:raise ValueError('max_contracts must be1..10')
    idx,side,stop,end=_sparse_signals(market,config)
    rows=_execute(market.open,market.high,market.low,market.close,
        market.minute,market.session_id,idx,side,stop,market.point_value,
        float(config.get('reward_r',1.5)),int(config.get('max_hold',90)),end,
        float(slip_ticks)*TICK,float(commission),float(risk_budget),
        int(max_contracts),int(max_trades),int(market.flat_minute))
    if not return_frame:return rows
    return to_frame(market,rows,config)


def to_frame(market: Market, rows: np.ndarray, config: dict|None=None) -> pd.DataFrame:
    """Convert compact rows to chronological, account-replay-compatible logs."""
    out=pd.DataFrame(rows,columns=COMPACT_COLUMNS)
    if len(out):
        ei=out.entry_idx.to_numpy(np.int64);xi=out.exit_idx.to_numpy(np.int64)
        si=out.session_id.to_numpy(np.int64)
        out['entry_time']=market.index[ei];out['exit_time']=market.index[xi]
        out['session_date']=market.session_dates[si]
        for col in ['entry_idx','exit_idx','session_id','quantity','direction','bars_held']:
            out[col]=out[col].astype(np.int64)
        out['exit_reason']=np.array(['stop','target','time'])[out.exit_reason.to_numpy(np.int64)]
    else:
        for col in ['entry_time','exit_time','session_date']:out[col]=pd.Series(dtype=object)
    out.attrs.update(asset=market.asset,point_value=market.point_value,
                     dollar_fields_are_total_position=True,
                     replay_quantity=1,config=dict(config or {}))
    return out
