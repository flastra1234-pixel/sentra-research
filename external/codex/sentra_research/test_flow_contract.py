import unittest
from pathlib import Path
import pandas as pd
from flow_contract import summarize_source_trades
class FlowChecks(unittest.TestCase):
 def setUp(self):self.x=pd.read_csv(Path(__file__).parent/'data/test_data.trades.dbn.zst.decoded.csv')
 def test_official_fixture(self):
  r=summarize_source_trades(self.x)[0];self.assertEqual(r['source_signed_net'],2);self.assertEqual(r['known_side_fraction'],1)
 def test_unknown_not_invented(self):
  self.x.loc[0,'side']='N';r=summarize_source_trades(self.x)[0];self.assertEqual(r['unknown_volume'],1);self.assertEqual(r['known_side_fraction'],.75)
 def test_bars_rejected(self):
  with self.assertRaises(ValueError):summarize_source_trades(pd.DataFrame({'open':[1],'close':[2],'volume':[100]}))
 def test_passive_events_not_signed_trades(self):
  extra=self.x.iloc[[-1]].copy();extra['action']='A';extra['size']=1000;r=summarize_source_trades(pd.concat([self.x,extra]))[0];self.assertEqual(r['source_signed_net'],2)
if __name__=='__main__':unittest.main()
