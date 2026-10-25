"""Reproducible pre-registered search. Run search before finalize."""
from pathlib import Path
from itertools import product
import json, sys
import numpy as np
import pandas as pd
from engine import prepare_data, run_backtest, daily_equity

ROOT=Path(__file__).parent
OUT=ROOT/'results'
OUT.mkdir(exist_ok=True)

def load():
    d=pd.read_csv(ROOT.parent/'market_data'/'NQ_1min_continuous.csv.gz')
    d.index=pd.to_datetime(d.pop('datetime'), utc=True)
    d=d.loc[d.index >= '2024-08-05']
    return prepare_data(d[['open','high','low','close','volume']])

def split(d, part):
    ranges={'development':('2024-08-05','2025-07-01'),
            'validation':('2025-07-01','2026-01-01'),
            'holdout':('2026-01-01','2027-01-01')}
    a,b=ranges[part]
    # Select by New York session date, not UTC calendar boundary.
    ds=d.session_date.astype(str)
    x=d.loc[(ds>=a)&(ds<b)].copy()
    x.attrs.update(d.attrs)
    return x

def configs():
    rows=[]
    for family in ['orb','failed_orb','vwap_reversion','ema_pullback']:
        values=[15,30,60] if family in ['orb','failed_orb'] else ([1,1.5,2] if family=='vwap_reversion' else [9,20])
        key='or_minutes' if family in ['orb','failed_orb'] else ('band_atr' if family=='vwap_reversion' else 'ema_fast')
        for v,stop,r,hold in product(values,[1.5,2.5,4],[1,1.5,2],[30,60,90]):
            c={'family':family,key:v,'stop_atr':stop,'reward_r':r,'max_hold':hold,
               'start_minute':600,'end_minute':690,'max_trades':2,'min_stop':5,'max_stop':60}
            if family=='ema_pullback':c['ema_slow']=50
            c['id']=f'C{len(rows)+1:03d}'
            rows.append(c)
    return rows

def metrics(t, dates, q=2):
    if len(t)==0:return dict(trades=0,pnl=0,pf=0,max_dd=0,win_rate=0,avg_trade=0,avg_r=0,positive_months=0,months=0,intraday_dd=0)
    p=t.pnl_usd.to_numpy()*q
    eq=np.r_[0,np.cumsum(p)]
    dd=np.maximum.accumulate(eq)-eq
    wins=p[p>0].sum(); losses=-p[p<0].sum()
    daily=daily_equity(t, dates)*q
    de=daily.pnl_usd.cumsum()
    # Prior day's high-water cash vs conservative daily marked low.
    prior=de.shift(1,fill_value=0)
    high=np.maximum.accumulate(np.r_[0,de.to_numpy()])[:-1]
    intradd=np.max(high-(prior+daily.min_equity_usd).to_numpy())
    monthly=daily.pnl_usd.groupby(pd.to_datetime(daily.index).to_period('M')).sum()
    return dict(trades=len(t),pnl=float(p.sum()),pf=float(wins/losses) if losses else 999,
                max_dd=float(dd.max()),win_rate=float((p>0).mean()),avg_trade=float(p.mean()),
                avg_r=float((t.pnl_usd/(t.stop_points*2)).mean()),
                positive_months=int((monthly>0).sum()),months=len(monthly),intraday_dd=float(intradd))

def search():
    d=load(); dev=split(d,'development'); val=split(d,'validation')
    dc=sorted(dev.session_date.unique()); vc=sorted(val.session_date.unique())
    cs=configs(); assert len(cs)==297
    (OUT/'all_configs.json').write_text(json.dumps(cs,indent=2))
    rows=[]
    for j,c in enumerate(cs):
        t=run_backtest(dev,c); st=run_backtest(dev,c,slip_ticks=2)
        m=metrics(t,dc); sm=metrics(st,dc)
        thirds=np.array_split(np.array(dc,dtype=object),3)
        pos=sum(t.loc[t.session_date.isin(g),'pnl_usd'].sum()>0 for g in thirds)
        eligible=m['trades']>=100 and m['pf']>=1.10 and m['max_dd']<=1000 and sm['pnl']>0 and pos>=2
        rows.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],positive_thirds=pos,eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
        if (j+1)%50==0:print('Development',j+1,'/',len(cs),flush=True)
    scores=pd.DataFrame(rows);scores.to_csv(OUT/'development_all.csv',index=False)
    shortlist=scores[scores.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(3)
    byid={c['id']:c for c in cs}; vr=[]
    for _,s in shortlist.iterrows():
        c=byid[s.id];t=run_backtest(val,c);st=run_backtest(val,c,slip_ticks=2)
        m=metrics(t,vc);sm=metrics(st,vc)
        eligible=m['trades']>=30 and m['pnl']>0 and sm['pnl']>0 and m['pf']>=1.05
        vr.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
    vs=pd.DataFrame(vr)
    vs.to_csv(OUT/'validation_shortlist.csv',index=False)
    frozen=[]
    if len(vs):
        final=vs[vs.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(1).head(3)
        frozen=[byid[i] for i in final.id]
    freeze={'configs':frozen,'selection':'pre-registered development gates, top3/family, validation gates, top1/family max3',
            'development_sessions':len(dc),'validation_sessions':len(vc),'tested_configs':len(cs)}
    (OUT/'frozen_selection.json').write_text(json.dumps(freeze,indent=2))
    print('Development eligible',int(scores.eligible.sum()),'shortlist',len(shortlist))
    print(vs.to_string(index=False));print(json.dumps(freeze,indent=2))

def merge_fleet(logs, dates):
    # A single position, max2trades/day, validation order breaks ties.
    if not logs:return pd.DataFrame()
    x=pd.concat([t.assign(priority=i) for i,t in enumerate(logs)]).sort_values(['entry_time','priority'])
    accepted=[];last=None;counts={}
    for i,row in x.iterrows():
        date=row.session_date
        if counts.get(date,0)>=2 or (last is not None and row.entry_time<=last):continue
        accepted.append(row);last=row.exit_time;counts[date]=counts.get(date,0)+1
    return pd.DataFrame(accepted).reset_index(drop=True)

def block_ci(t,dates,q=2,n=3000):
    a=daily_equity(t,dates).pnl_usd.to_numpy()*q
    if len(a)<5:return [None,None]
    rng=np.random.default_rng(20261025)
    inds=rng.integers(0,len(a),size=(n,int(np.ceil(len(a)/5))))
    take=(inds[:,:,None]+np.arange(5))%len(a)
    samples=a[take.reshape(n,-1)[:,:len(a)]].mean(axis=1)
    return [float(x) for x in np.quantile(samples,[.025,.975])]

def finalize():
    frozen=json.loads((OUT/'frozen_selection.json').read_text())
    if not frozen['configs']:
        print('No candidate survived. Holdout not opened.');return
    d=load();logs={};rows=[]
    for part in ['development','validation','holdout']:
        x=split(d,part);dates=sorted(x.session_date.unique())
        base=[];stress=[]
        for c in frozen['configs']:
            t=run_backtest(x,c);st=run_backtest(x,c,slip_ticks=2)
            t.to_csv(OUT/f'{c["id"]}_{part}_trades.csv',index=False)
            st.to_csv(OUT/f'{c["id"]}_{part}_stress_trades.csv',index=False)
            base.append(t.assign(strategy=c['id']));stress.append(st.assign(strategy=c['id']))
            for label,tt in [('baseline',t),('stress',st)]:
                m=metrics(tt,dates);ci=block_ci(tt,dates)
                rows.append(dict(id=c['id'],family=c['family'],split=part,cost=label,quantity=2,sessions=len(dates),**m,daily_mean_ci_low=ci[0],daily_mean_ci_high=ci[1]))
        if len(base)>1:
            for label,ls in [('baseline',base),('stress',stress)]:
                ft=merge_fleet(ls,dates)
                ft.to_csv(OUT/f'fleet_{part}_{label}_trades.csv',index=False)
                m=metrics(ft,dates,q=1);ci=block_ci(ft,dates,q=1)
                rows.append(dict(id='fleet',family='nonoverlap_equal1MNQ',split=part,cost=label,quantity=1,sessions=len(dates),**m,daily_mean_ci_low=ci[0],daily_mean_ci_high=ci[1]))
    out=pd.DataFrame(rows);out.to_csv(OUT/'split_metrics.csv',index=False)
    print(out.to_string(index=False))

if __name__=='__main__':
    {'search':search,'finalize':finalize}[sys.argv[1]]()
