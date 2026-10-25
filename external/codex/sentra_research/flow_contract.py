"""Validate source-signed Trades/TBBO records. Never derive signing from OHLC."""
import pandas as pd

def summarize_source_trades(df):
 required={'ts_event','instrument_id','symbol','action','side','size','price'}
 if not required<=set(df):raise ValueError('Need genuine contract-identified signed trade records; OHLCV is insufficient')
 x=df.loc[df.action=='T'].copy()
 if not x.side.isin(['B','A','N']).all():raise ValueError('Unsupported source side; no inferred signing allowed')
 times=pd.to_datetime(x.ts_event,utc=True,errors='raise')
 if not times.is_monotonic_increasing:raise ValueError('Explicit timestamp/sequence reconciliation required')
 if (pd.to_numeric(x['size'])<=0).any():raise ValueError('Trade size must be positive')
 rows=[]
 for (contract,instrument),g in x.groupby(['symbol','instrument_id']):
  buy=float(g.loc[g.side=='B','size'].sum());sell=float(g.loc[g.side=='A','size'].sum());unknown=float(g.loc[g.side=='N','size'].sum());known=buy+sell
  rows.append(dict(contract=contract,instrument_id=int(instrument),buy_volume=buy,sell_volume=sell,unknown_volume=unknown,source_signed_net=buy-sell,known_side_fraction=known/(known+unknown),imbalance_known_only=(buy-sell)/known if known else None))
 return rows
