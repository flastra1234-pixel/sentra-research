from pathlib import Path
from itertools import product
import json
import numpy as np
import pandas as pd
import study
from engine import run_backtest

OUT=Path(__file__).parent/'results_higher_tf'
OUT.mkdir(exist_ok=True)

def configs():
 cs=[]
 for f in ['orb','failed_orb','vwap_reversion','ema_pullback']:
  for tf,v,stop,r,hold,end in product([5,15],[15,30] if f in ['orb','failed_orb'] else ([1,2] if f=='vwap_reversion' else [5,9]),[.25,.5] if f in ['orb','failed_orb'] else [1.5,2.5],[1,2],[60,120],[720,900]):
   c=dict(family=f,signal_minutes=tf,atr_period=5,start_minute=585,end_minute=end,max_hold=hold,max_trades=1,min_stop=5,max_stop=100,reward_r=r)
   if f in ['orb','failed_orb']:c.update(or_minutes=v,stop_mode='or_fraction',stop_fraction=stop)
   elif f=='vwap_reversion':c.update(band_atr=v,stop_atr=stop,min_agg_bars=3)
   else:c.update(ema_fast=v,ema_slow=20,stop_atr=stop,warmup_bars=max(3,v))
   c['id']=f'H{len(cs)+1:03d}';cs.append(c)
 assert len(cs)==256
 return cs

def main():
 d=study.load();dev=study.split(d,'development');val=study.split(d,'validation')
 dc=sorted(dev.session_date.unique());vc=sorted(val.session_date.unique())
 cs=configs();(OUT/'all_configs.json').write_text(json.dumps(cs,indent=2))
 rows=[]
 for j,c in enumerate(cs):
  t=run_backtest(dev,c);st=run_backtest(dev,c,slip_ticks=2)
  m=study.metrics(t,dc,q=1);sm=study.metrics(st,dc,q=1)
  pos=sum(t.loc[t.session_date.isin(g),'pnl_usd'].sum()>0 for g in np.array_split(np.array(dc,dtype=object),3))
  eligible=m['trades']>=50 and m['pf']>=1.10 and m['max_dd']<=800 and sm['pnl']>0 and pos>=2
  rows.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],positive_thirds=pos,eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
  if (j+1)%50==0:print('Slower development',j+1,'/256',flush=True)
 s=pd.DataFrame(rows);s.to_csv(OUT/'development_all.csv',index=False)
 short=s[s.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(2)
 byid={c['id']:c for c in cs};vr=[]
 for _,row in short.iterrows():
  c=byid[row.id];t=run_backtest(val,c);st=run_backtest(val,c,slip_ticks=2)
  m=study.metrics(t,vc,q=1);sm=study.metrics(st,vc,q=1)
  eligible=m['trades']>=20 and m['pf']>=1.05 and m['pnl']>0 and sm['pnl']>0 and m['max_dd']<=800
  vr.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
 v=pd.DataFrame(vr);v.to_csv(OUT/'validation_shortlist.csv',index=False)
 chosen=v[v.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(1).head(3) if len(v) else pd.DataFrame()
 freeze={'configs':[byid[i] for i in chosen.id] if len(chosen) else [],'quantity':1,'branch':'higher_timeframe','tested_configs':256,'holdout_inspected':False}
 (OUT/'frozen_selection.json').write_text(json.dumps(freeze,indent=2))
 print('Development eligible',int(s.eligible.sum()),'shortlist',len(short));print(v.to_string(index=False));print(json.dumps(freeze,indent=2))

if __name__=='__main__':main()
