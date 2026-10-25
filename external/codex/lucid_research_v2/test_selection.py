"""Independent selection and fleet-accounting boundary checks.

Synthetic values verify information boundaries, not strategy profitability.
No reserved market data are opened by these tests.
"""
import unittest
from datetime import date
import numpy as np
import pandas as pd
from search import configurations
from walkforward import select,neighbor_indices,merge_fleet,trade_metrics
from validation import rolling_folds


class SelectionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        all_configs=configurations('ES')
        cls.cs=[c for c in all_configs if c['family']==all_configs[0]['family']]
        cls.neighbors=neighbor_indices(cls.cs)

    def profitable_matrix(self):
        matrix=np.zeros((len(self.cs),180,5),dtype=np.float32)
        # net, winning sums, losing sums, count, intraday minimum.
        matrix[:,:,0]=3.;matrix[:,:,1]=3.;matrix[:,:,3]=1.
        matrix[:,:,4]=-1.
        return matrix

    def test_future_matrix_changes_cannot_change_selection(self):
        matrix=self.profitable_matrix()
        before,meta=select(self.cs,matrix,list(range(120)),list(range(120,150)),self.neighbors)
        self.assertEqual(len(before),1)
        mutated=matrix.copy()
        rng=np.random.default_rng(212)
        mutated[:,150:,:]=rng.normal(0,1e6,size=mutated[:,150:,:].shape)
        after,meta2=select(self.cs,mutated,list(range(120)),list(range(120,150)),self.neighbors)
        self.assertEqual(before,after)
        self.assertEqual(meta,meta2)

    def test_validation_failure_stays_cash_despite_future_winners(self):
        matrix=self.profitable_matrix()
        matrix[:,120:150,:]=0.
        matrix[:,150:,0]=1e6;matrix[:,150:,1]=1e6
        chosen,meta=select(self.cs,matrix,list(range(120)),list(range(120,150)),self.neighbors)
        self.assertEqual(chosen,[])
        self.assertEqual(meta['validated_variants'],0)
        self.assertGreater(meta['training_eligible'],0)

    def test_neighbor_support_does_not_borrow_future_returns(self):
        matrix=self.profitable_matrix()
        matrix[:,:120,0]=-3.;matrix[:,:120,1]=0.;matrix[:,:120,2]=3.
        chosen,meta=select(self.cs,matrix,list(range(120)),list(range(120,150)),self.neighbors)
        self.assertEqual(chosen,[])
        self.assertEqual(meta['training_eligible'],0)

    def test_fold_dates_are_ordered_and_tests_do_not_overlap(self):
        dates=pd.bdate_range('2024-01-02',periods=270)
        folds=rolling_folds(dates,120,30,30,30)
        self.assertEqual(len(folds),4)
        seen=set()
        for f in folds:
            self.assertLess(max(f.train_dates),min(f.validation_dates))
            self.assertLess(max(f.validation_dates),min(f.test_dates))
            self.assertFalse(set(f.test_dates)&seen)
            seen.update(f.test_dates)

    def test_fleet_no_overlap_cross_asset_limit_and_no_double_quantity(self):
        def trade(cid,asset,start,end,pnl,mae,qty,score):
            return dict(config_id=cid,asset=asset,
                entry_time=pd.Timestamp('2024-02-05 '+start,tz='UTC'),
                exit_time=pd.Timestamp('2024-02-05 '+end,tz='UTC'),
                session_date=date(2024,2,5),pnl_usd=pnl,mae_usd=mae,
                quantity=qty,selection_score=score,selection_priority=0)
        frame=pd.DataFrame([
            trade('weak_tie','ES','15:00','15:30',12,-20,4,.5),
            trade('strong_tie','NQ','15:00','15:10',40,-10,1,1.),
            trade('overlap','ES','15:05','15:08',1000,-10,9,10.),
            trade('same_time_as_exit','ES','15:10','15:20',1000,-10,9,10.),
            trade('next','ES','15:31','15:45',30,-12,6,.8),
            trade('third','NQ','16:00','16:10',1000,-10,9,10.),
        ])
        fleet=merge_fleet([frame])
        self.assertEqual(fleet.config_id.tolist(),['strong_tie','next'])
        self.assertTrue((fleet.entry_time>fleet.exit_time.shift()).iloc[1:].all())
        self.assertEqual(fleet.pnl_usd.sum(),70)
        # Twenty sessions make the bootstrap diagnostic well-defined; the
        # six-contract row's $30 already is total P&L, not $180.
        dates=pd.bdate_range('2024-02-05',periods=20).date
        stats=trade_metrics(fleet,dates)
        self.assertEqual(stats['net'],70)
        self.assertEqual(stats['trades'],2)
        self.assertEqual(stats['intraday_eod_dd'],10)


if __name__=='__main__':unittest.main()
