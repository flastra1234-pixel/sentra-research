from pathlib import Path
from itertools import product
import json
import numpy as np
import pandas as pd
import study
from engine import run_backtest

OUT=Path(__file__).parent/'results_time'
OUT.mkdir(exist_ok=True)

def configs():
 cs=[]
 for entry,mode,fraction,reward,hold in product([600,630,660,840],['long','short','opening_momentum'],[.25,.5,1],[1,2],[30,60,120]):
  cs.append(dict(id=f'T{len(cs)+1:03d}',family='time_entry',signal_minutes=1,entry_minute=entry,direction_mode=mode,or_minutes=15,stop_mode='or_fraction',stop_fraction=fraction,reward_r=reward,max_hold=hold,max_trades=1,min_stop=5,max_stop=100,start_minute=585,end_minute=900,atr_period=5))
 assert len(cs)==216
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
  rows.append(dict(id=c['id'],family=c['family'],direction_mode=c['direction_mode'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],positive_thirds=pos,eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
  if (j+1)%50==0:print('Time development',j+1,'/216',flush=True)
 s=pd.DataFrame(rows);s.to_csv(OUT/'development_all.csv',index=False)
 short=s[s.eligible].sort_values('score',ascending=False).groupby('direction_mode',sort=False).head(2)
 byid={c['id']:c for c in cs};vr=[]
 for _,row in short.iterrows():
  c=byid[row.id];t=run_backtest(val,c);st=run_backtest(val,c,slip_ticks=2)
  m=study.metrics(t,vc,q=1);sm=study.metrics(st,vc,q=1)
  eligible=m['trades']>=20 and m['pf']>=1.05 and m['pnl']>0 and sm['pnl']>0 and m['max_dd']<=800
  vr.append(dict(id=c['id'],family=c['family'],direction_mode=c['direction_mode'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
 v=pd.DataFrame(vr);v.to_csv(OUT/'validation_shortlist.csv',index=False)
 chosen=v[v.eligible].sort_values('score',ascending=False).groupby('direction_mode',sort=False).head(1).head(3) if len(v) else pd.DataFrame()
 freeze={'configs':[byid[i] for i in chosen.id] if len(chosen) else [],'quantity':1,'asset':'MNQ','branch':'time_entry','tested_configs':216,'holdout_inspected':False}
 (OUT/'frozen_selection.json').write_text(json.dumps(freeze,indent=2))
 print('Development eligible',int(s.eligible.sum()),'shortlist',len(short));print(v.to_string(index=False));print(json.dumps(freeze,indent=2))

if __name__=='__main__':main()
