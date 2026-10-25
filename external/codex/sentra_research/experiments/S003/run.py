from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
sys.path.insert(0,'/workspace/market_data_v2');from load_micro import load_micro_1min
sys.path.insert(0,'/workspace/lucid_research_v2');from validation import moving_block_bootstrap_mean_ci
r=Path(__file__).parent;results={}
for asset,pv in [('MES',5),('MNQ',2)]:
 d=load_micro_1min(asset);d.index=d.index.tz_convert('America/New_York');rows=[]
 for day,g in d.groupby(d.index.date):
  if pd.Timestamp(day).dayofweek>=5:continue
  h=g.between_time('02:00','02:59');end=g.between_time('03:00','03:00')
  if len(h)!=60 or len(end)!=1:continue
  points=float(end.open.iloc[0]-h.open.iloc[0]);rows.append(dict(date=str(day),gross_points=points,net_one_micro=points*pv-1.24-pv))
 x=pd.DataFrame(rows);x.to_csv(r/f'{asset}_markouts.csv',index=False);p=x.net_one_micro.to_numpy();parts=np.array_split(p,2)
 b=moving_block_bootstrap_mean_ci(p,n_boot=3000)
 results[asset]=dict(eligible_days=len(x),hypothetical_net=float(p.sum()),mean_net=float(p.mean()),median_net=float(np.median(p)),worst_net=float(p.min()),days100=int((p>=100).sum()),days150=int((p>=150).sum()),chronological_half_nets=[float(a.sum()) for a in parts],bootstrap=b)
ps=sorted([(v['bootstrap']['centered_bootstrap_p_value'],k) for k,v in results.items()]);running=0
for i,(p,k) in enumerate(ps):running=max(running,min(1,p*(2-i)));results[k]['holm_adjusted_p']=running
out={'diagnostic_only':True,'reserved_data_accessed':False,'preregistration_sha256':hashlib.sha256((r/'PREREGISTRATION.md').read_bytes()).hexdigest(),'results':results};(r/'results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
