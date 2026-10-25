"""Continued predeclared grid. All old history is researcher-consumed."""
from pathlib import Path
from itertools import product
import sys,json,hashlib,time
import numpy as np
import pandas as pd
from numba import njit
from engine_v2 import build_market,backtest,FAMILIES

ROOT=Path(__file__).parent
OUT=ROOT/'results'
OUT.mkdir(exist_ok=True)

def configurations(asset):
 rows=[]
 for f,tf,w,s,r,h,c,d in product(FAMILIES,[3,6,15],['AM','mid','PM'],[1.5,2.5],[1,1.5,2],[30,90],['none','trend','range'],['both','long']):
  rows.append(dict(id=f'{asset}_{len(rows)+1:05d}',asset=asset,family=f,tf=tf,window=w,stop_atr=s,reward_r=r,max_hold=h,context=c,direction=d))
 assert len(rows)==6480
 return rows

def load_primary(asset):
 path=ROOT.parent/'market_data'/('NQ_1min_continuous.csv.gz' if asset=='NQ' else 'ES_1min_stitched.csv')
 d=pd.read_csv(path);d.index=pd.to_datetime(d.pop('datetime'),utc=True)
 dates=d.index.tz_convert('America/New_York').strftime('%Y-%m-%d')
 d=d.loc[(dates>='2024-08-05')&(dates<'2026-10-10')]
 return build_market(d[['open','high','low','close','volume']],asset)

@njit(cache=True)
def daily_summary(rows,n):
 # net,grosswinning,grosslosing,tradecount,conservative intraday minimum
 out=np.zeros((n,5),np.float64)
 for j in range(len(rows)):
  sid=int(rows[j,2]);p=rows[j,3];m=rows[j,4]
  out[sid,4]=min(out[sid,4],out[sid,0]+m)
  out[sid,0]+=p
  if p>0:out[sid,1]+=p
  else:out[sid,2]-=p
  out[sid,3]+=1
 return out

def collect(asset):
 cs=configurations(asset);market=load_primary(asset);start=time.monotonic()
 directory=OUT/asset;directory.mkdir(exist_ok=True)
 (directory/'configs.json').write_text(json.dumps(cs,indent=2))
 manifest={'plan_sha256':hashlib.sha256((ROOT/'PLAN.md').read_bytes()).hexdigest(),
           'engine_sha256':hashlib.sha256((ROOT/'engine_v2.py').read_bytes()).hexdigest(),
           'asset':asset,'sessions':[str(x) for x in market.session_dates],
           'quality':market.quality,'cost':'2ticks_each_side','risk_budget':60,
           'history_is_researcher_consumed':True}
 (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
 matrix=np.empty((len(cs),len(market.session_dates),5),np.float32)
 for i,c in enumerate(cs):
  rows=backtest(market,c,slip_ticks=2,return_frame=False)
  matrix[i]=daily_summary(rows,len(market.session_dates))
  if (i+1)%500==0:print(asset,i+1,'/6480',round(time.monotonic()-start,1),'sec',flush=True)
 np.savez_compressed(directory/'daily_stressed.npz',daily=matrix)
 n=matrix[:,:,3].sum(axis=1);net=matrix[:,:,0].sum(axis=1,dtype=np.float64)
 win=matrix[:,:,1].sum(axis=1,dtype=np.float64);loss=matrix[:,:,2].sum(axis=1,dtype=np.float64)
 stats=pd.DataFrame({'id':[c['id'] for c in cs],'family':[c['family'] for c in cs],
                     'trades':n.astype(int),'stress_net':net,'stress_pf':np.divide(win,loss,out=np.full_like(win,999),where=loss>0)})
 stats.to_csv(directory/'all_config_metrics.csv',index=False)
 print(asset,'COMPLETE',len(cs),'active',int((n>0).sum()),'netpositive',int((net>0).sum()),'seconds',round(time.monotonic()-start,1),flush=True)

if __name__=='__main__':collect(sys.argv[1])
