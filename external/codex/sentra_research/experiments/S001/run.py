from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
sys.path.insert(0,'/workspace/market_data_v2')
from load_micro import load_micro_1min
R=Path(__file__).parent
results={}
for asset in ['MES','MNQ']:
 d=load_micro_1min(asset); et=d.index.tz_convert('America/New_York');d=d.copy();d.index=et
 rt=d.between_time('09:30','15:59');counts=rt.groupby(rt.index.date).size();full=counts[counts==390].index
 events=[];missing=0
 for day in full:
  date=pd.Timestamp(day,tz='America/New_York');a=date-pd.Timedelta(hours=6);b=date+pd.Timedelta(hours=9,minutes=30)
  on=d.loc[(d.index>=a)&(d.index<b)]
  if len(on)!=930:missing+=1;continue
  opening=rt.loc[rt.index.date==day].iloc[:15];hi=on.high.max();lo=on.low.min();last=opening.close.iloc[-1]
  long=bool(opening.low.min()<lo and last>lo);short=bool(opening.high.max()>hi and last<hi)
  prev=(pd.Timestamp(day)-pd.offsets.BDay()).date();prevbar=d.loc[(d.index.date==prev)&(d.index.hour==15)&(d.index.minute==59)]
  gap=np.nan;gap_event=None
  if len(prevbar)==1 and hi>lo:
   gap=float(opening.open.iloc[0]-prevbar.close.iloc[0]);gap_event=bool(abs(gap)>=.25*(hi-lo) and ((gap>0 and short and not long)or(gap<0 and long and not short)))
  events.append(dict(date=str(day),long_failure=long,short_failure=short,any_failure=long or short,one_sided=long!=short,gap=gap,gap_event=gap_event))
 x=pd.DataFrame(events);x.to_csv(R/f'{asset}_events.csv',index=False)
 n=len(x);known=x.gap_event.notna()
 results[asset]=dict(full_rth_sessions=len(full),overnight_incomplete_excluded=missing,eligible_sessions=n,
  one_sided_events=int(x.one_sided.sum()),any_failure_events=int(x.any_failure.sum()),ambiguous_both=int((x.long_failure&x.short_failure).sum()),
  one_sided_coverage=float(x.one_sided.mean()),generous_any_failure_upper_bound=float(x.any_failure.mean()),
  missing_previous_businessday_close=int((~known).sum()),gap_eligible=int(known.sum()),gap_events=int(x.loc[known,'gap_event'].sum()),
  gap_event_coverage=float(x.loc[known,'gap_event'].mean()),
  standalone_target_feasible_even_perfect_prediction=bool(x.any_failure.mean()>=.7))
out={'experiment':'S001','status':'coverage_only_not_predictive_validation','reserved_data_accessed':False,'preregistration_sha256':hashlib.sha256((R/'PREREGISTRATION.md').read_bytes()).hexdigest(),'results':results}
(R/'results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
