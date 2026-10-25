from pathlib import Path
import json
import pandas as pd
import study
from engine import run_backtest

OUT=Path(__file__).parent/'results_risk'
OUT.mkdir(exist_ok=True)
d=study.load();dev=study.split(d,'development');val=study.split(d,'validation')
vc=sorted(val.session_date.unique())
s=pd.read_csv(study.OUT/'development_all.csv')
for key in ['pnl','max_dd','avg_trade','intraday_dd','stress_pnl']:s[key]=s[key]/2
s['eligible']=(s.trades>=100)&(s.pf>=1.10)&(s.max_dd<=800)&(s.stress_pnl>0)&(s.positive_thirds>=2)
s.to_csv(OUT/'development_sizing.csv',index=False)
short=s[s.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(3)
cs={c['id']:c for c in study.configs()};rows=[]
for _,r in short.iterrows():
 c=cs[r.id];t=run_backtest(val,c);st=run_backtest(val,c,slip_ticks=2)
 m=study.metrics(t,vc,q=1);sm=study.metrics(st,vc,q=1)
 eligible=m['trades']>=30 and m['pf']>=1.05 and m['pnl']>0 and sm['pnl']>0 and m['max_dd']<=800
 rows.append(dict(id=c['id'],family=c['family'],**m,stress_pnl=sm['pnl'],stress_pf=sm['pf'],eligible=eligible,score=m['pnl']/max(m['max_dd'],100)))
v=pd.DataFrame(rows);v.to_csv(OUT/'validation_shortlist.csv',index=False)
chosen=v[v.eligible].sort_values('score',ascending=False).groupby('family',sort=False).head(1).head(3) if len(v) else pd.DataFrame()
freeze={'configs':[cs[i] for i in chosen.id] if len(chosen) else [],'quantity':1,'branch':'risk_sensitivity','tested_strategy_configurations':297,'holdout_inspected':False}
(OUT/'frozen_selection.json').write_text(json.dumps(freeze,indent=2))
print(v.to_string(index=False));print(json.dumps(freeze,indent=2))
