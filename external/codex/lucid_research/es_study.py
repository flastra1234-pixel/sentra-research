"""Preregistered ES-price / 2MES research branch; search never opens 2026."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from engine import prepare_data, run_backtest as mnq_backtest, daily_equity
from higher_tf_study import configs as higher_configs

ROOT=Path(__file__).parent
OUT=ROOT/'results_es'
OUT.mkdir(exist_ok=True)
DATA=ROOT.parent/'market_data'/'ES_1min_stitched.csv'
COMMISSION=1.24
POINT_VALUE=5.0
QUANTITY=2


def configs():
    cs=higher_configs()
    for i,c in enumerate(cs,1):
        c['source_config_id']=c['id']
        c.update(id=f'E{i:03d}',min_stop=1,max_stop=20)
    assert len(cs)==256
    return cs


def load(include_holdout=False):
    d=pd.read_csv(DATA)
    d.index=pd.to_datetime(d.pop('datetime'),utc=True)
    dates=d.index.tz_convert('America/New_York').strftime('%Y-%m-%d')
    if not include_holdout:
        d=d.loc[(dates>='2025-06-20') & (dates<'2026-01-01')].copy()
    return prepare_data(d[['open','high','low','close','volume']])


def split(d,part):
    ranges={'development':('2025-06-20','2025-10-01'),
            'validation':('2025-10-01','2026-01-01'),
            'holdout':('2026-01-01','2027-01-01')}
    a,b=ranges[part]
    dates=d.session_date.astype(str)
    x=d.loc[(dates>=a)&(dates<b)].copy()
    x.attrs.update(d.attrs)
    return x


def convert_mes(t,commission=COMMISSION):
    t=t.copy()
    if len(t):
        t['pnl_usd']=t.pnl_points*POINT_VALUE-commission
        for col in ['mae_usd','mfe_usd']:
            t[col]=(t[col]+commission)*(POINT_VALUE/2.0)-commission
    t.attrs['instrument_pnl']='MES priced from ES bars'
    t.attrs['point_value']=POINT_VALUE
    return t


def run_backtest(d,c,commission=COMMISSION,slip_ticks=1):
    return convert_mes(mnq_backtest(d,c,commission=commission,slip_ticks=slip_ticks),commission)


def metrics(t,dates,q=QUANTITY):
    if len(t)==0:
        return dict(trades=0,pnl=0,pf=0,max_dd=0,win_rate=0,avg_trade=0,avg_r=0,positive_months=0,months=0,intraday_dd=0)
    p=t.pnl_usd.to_numpy()*q
    eq=np.r_[0,np.cumsum(p)]
    dd=np.maximum.accumulate(eq)-eq
    wins=p[p>0].sum();losses=-p[p<0].sum()
    daily=daily_equity(t,dates)*q
    de=daily.pnl_usd.cumsum();prior=de.shift(1,fill_value=0)
    high=np.maximum.accumulate(np.r_[0,de.to_numpy()])[:-1]
    intradd=np.max(high-(prior+daily.min_equity_usd).to_numpy())
    monthly=daily.pnl_usd.groupby(pd.to_datetime(daily.index).to_period('M')).sum()
    return dict(trades=len(t),pnl=float(p.sum()),pf=float(wins/losses) if losses else 999,
                max_dd=float(dd.max()),win_rate=float((p>0).mean()),avg_trade=float(p.mean()),
                avg_r=float((t.pnl_usd/(t.stop_points*POINT_VALUE)).mean()),
                positive_months=int((monthly>0).sum()),months=len(monthly),intraday_dd=float(intradd))


def main():
    assert (ROOT/'es_plan.md').exists(),'Plan must precede run'
    cs=configs()
    (OUT/'all_configs.json').write_text(json.dumps(cs,indent=2))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'es_plan.md',ROOT/'es_study.py',ROOT/'engine.py',ROOT/'higher_tf_study.py',DATA]}
    (OUT/'run_provenance.json').write_text(json.dumps({'sha256':hashes,'holdout_inspected':False},indent=2))
    # Unit check conversion independently of the strategy engine.
    fake=pd.DataFrame({'pnl_points':[2.,-3.], 'pnl_usd':[2.76,-7.24],
                       'mae_usd':[-3.24,-7.24], 'mfe_usd':[3.76,-1.24]})
    converted=convert_mes(fake)
    assert np.allclose(converted.pnl_usd,[8.76,-16.24])
    assert np.allclose(converted.mae_usd,[-6.24,-16.24])
    assert np.allclose(converted.mfe_usd,[11.26,-1.24])
    d=load();dev=split(d,'development');val=split(d,'validation')
    assert not any(str(z)>='2026-01-01' for z in d.session_date.unique())
    dc=sorted(dev.session_date.unique());vc=sorted(val.session_date.unique())
    sessions={'development':len(dc),'validation':len(vc),'development_first':str(dc[0]),'development_last':str(dc[-1]),'validation_first':str(vc[0]),'validation_last':str(vc[-1]),'holdout_inspected':False}
    (OUT/'sessions.json').write_text(json.dumps(sessions,indent=2))
    rows=[]
    for j,c in enumerate(cs):
        t=run_backtest(dev,c);st=run_backtest(dev,c,slip_ticks=2)
        m=metrics(t,dc);sm=metrics(st,dc)
        pos=sum(t.loc[t.session_date.isin(g),'pnl_usd'].sum()>0 for g in np.array_split(np.array(dc,dtype=object),3))
        eligible=m['trades']>=30 and m['pf']>=1.15 and m['max_dd']<=600 and sm['pnl']>0 and pos>=2
        rows.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],positive_thirds=pos,eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
        if (j+1)%50==0:print('ES development',j+1,'/256',flush=True)
    s=pd.DataFrame(rows);s.to_csv(OUT/'development_all.csv',index=False)
    short=s[s.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(2)
    byid={c['id']:c for c in cs};vr=[]
    for _,row in short.iterrows():
        c=byid[row.id];t=run_backtest(val,c);st=run_backtest(val,c,slip_ticks=2)
        m=metrics(t,vc);sm=metrics(st,vc)
        eligible=m['trades']>=20 and m['pf']>=1.05 and m['pnl']>0 and sm['pnl']>0 and m['max_dd']<=800
        vr.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
    columns=['id','family','trades','pnl','pf','max_dd','win_rate','avg_trade','avg_r','positive_months','months','intraday_dd','stress_pnl','stress_pf','eligible','score']
    v=pd.DataFrame(vr,columns=columns);v.to_csv(OUT/'validation_shortlist.csv',index=False)
    chosen=v[v.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(1).head(3) if len(v) else pd.DataFrame()
    freeze={'configs':[byid[i] for i in chosen.id] if len(chosen) else [],'quantity':QUANTITY,'instrument':'MES','price_proxy':'ES','point_value':POINT_VALUE,'branch':'es_higher_timeframe','tested_configs':len(cs),'holdout_inspected':False,'selection':'development gates top2 per family; validation gates top1 per family max3','sessions':sessions}
    (OUT/'frozen_selection.json').write_text(json.dumps(freeze,indent=2))
    print('Development eligible',int(s.eligible.sum()),'shortlist',len(short),flush=True)
    print(v.to_string(index=False),flush=True)
    print(json.dumps(freeze,indent=2),flush=True)

if __name__=='__main__':main()
