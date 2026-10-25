"""Execution and causality checks; synthetic bars are never performance evidence."""
import unittest
import numpy as np
import pandas as pd
from engine import prepare_data, generate_signals, _execute, daily_equity


def regular_session():
    ix = pd.date_range('2025-02-03 09:30', periods=390, freq='min',
                       tz='America/New_York').tz_convert('UTC')
    p = 20000 + np.sin(np.arange(390)*.3)*10 + np.arange(390)*.05
    return pd.DataFrame({'open':p,'high':p+2,'low':p-2,
                         'close':p+.25,'volume':100.0}, index=ix)


class EngineChecks(unittest.TestCase):
    def test_missing_minute_excludes_entire_session(self):
        x = regular_session()
        self.assertEqual(len(prepare_data(x)), 390)
        self.assertEqual(len(prepare_data(x.drop(x.index[100]))), 0)

    def test_future_prices_cannot_change_earlier_signals(self):
        x = regular_session()
        y = x.copy()
        y.iloc[180:, y.columns.get_indexer(['open','high','low','close'])] += 123
        y.iloc[180:, y.columns.get_loc('volume')] *= 7
        for family in ['orb','failed_orb','ema_pullback','vwap_reversion']:
            a = generate_signals(x, {'family':family})
            b = generate_signals(y, {'family':family})
            pd.testing.assert_frame_equal(a.iloc[:180], b.iloc[:180])

    def test_missing_volume_disables_only_vwap(self):
        x = regular_session()
        x.volume = np.nan
        prepared = prepare_data(x)
        self.assertEqual(len(prepared), 390)
        self.assertTrue(prepared.vwap.isna().all())
        self.assertTrue((generate_signals(prepared, {'family':'vwap_reversion'}).direction == 0).all())

    def test_higher_timeframe_is_causal_and_only_signals_completed_bars(self):
        x = regular_session()
        y = x.copy()
        y.iloc[181:, y.columns.get_indexer(['open','high','low','close'])] += 123
        for tf in [1,5,15,30]:
            for family in ['orb','failed_orb','ema_pullback','vwap_reversion']:
                cfg = {'family':family,'signal_minutes':tf,'atr_period':5,
                       'min_stop':.25,'max_stop':1000,'end_minute':900,
                       'ema_fast':5,'ema_slow':20}
                a = generate_signals(x,cfg)
                b = generate_signals(y,cfg)
                pd.testing.assert_frame_equal(a.iloc[:181],b.iloc[:181])
                nonzero = np.flatnonzero(a.direction.to_numpy())
                self.assertTrue(np.all(nonzero % tf == tf-1))

    def test_structural_stop_is_fraction_of_completed_original_range(self):
        x = regular_session()
        cfg = {'family':'orb','signal_minutes':5,'stop_mode':'or_fraction',
               'or_minutes':30,'stop_fraction':.5,'min_stop':.25,'max_stop':1000}
        a = generate_signals(x,cfg)
        expected = np.ceil((x.high.iloc[:30].max()-x.low.iloc[:30].min())*.5/.25)*.25
        self.assertEqual(a.stop_points.iloc[34],expected)
        self.assertTrue(a.stop_points.iloc[:30].isna().all())

    def test_time_entry_timestamp_direction_and_causality(self):
        x = regular_session()
        cfg = {'family':'time_entry','signal_minutes':1,'entry_minute':600,
               'stop_mode':'or_fraction','or_minutes':15,'stop_fraction':.5,
               'min_stop':.25,'max_stop':1000,'start_minute':585,'end_minute':900}
        for mode,expected in [('long',1),('short',-1),('opening_momentum',int(np.sign(x.close.iloc[29]-x.open.iloc[0])))]:
            c = {**cfg,'direction_mode':mode}
            a = generate_signals(x,c)
            self.assertEqual(np.flatnonzero(a.direction.to_numpy()).tolist(),[29])
            self.assertEqual(a.direction.iloc[29],expected)
            y = x.copy()
            y.iloc[30:,y.columns.get_indexer(['open','high','low','close'])] += 500
            b = generate_signals(y,c)
            pd.testing.assert_frame_equal(a.iloc[:30],b.iloc[:30])

    def execute_case(self, open2=100.0):
        op = np.array([100.0,open2,100.0,100.0])
        high = np.array([100.0,104.0,100.0,100.0])
        low = np.array([100.0,96.0,100.0,100.0])
        return _execute(op,high,low,op,np.arange(600,604),np.zeros(4,dtype=np.int64),
                        np.array([1,0,0,0]),np.ones(4),1.0,60,2,690,.25,1.24)

    def test_next_open_and_stop_first_with_both_boundaries_hit(self):
        row = self.execute_case()[0]
        self.assertEqual(row[0], 1)  # never signal-bar entry
        self.assertEqual(row[3], 100.25)
        self.assertEqual(row[4], 99.0)
        self.assertEqual(row[10], 0)
        self.assertAlmostEqual(row[7], -3.74)
        # Do not charge the full low beyond a protective stop as MAE.
        self.assertAlmostEqual(row[8], -3.74)

    def test_adverse_gap_stop_uses_worse_open(self):
        op = np.array([100.,100.,97.,100.])
        hi = np.array([100.,100.5,98.,100.])
        lo = np.array([100.,100.,96.,100.])
        rows = _execute(op,hi,lo,op,np.arange(600,604),np.zeros(4,dtype=np.int64),
                         np.array([1,0,0,0]),np.ones(4),1.,60,2,690,.25,1.24)
        self.assertEqual(rows[0,1], 2)
        self.assertEqual(rows[0,4], 96.75)

    def test_daily_low_preserves_previous_trade_loss(self):
        t = pd.DataFrame({'entry_time':pd.to_datetime(['2025-02-03T15:00Z','2025-02-03T16:00Z']),
                          'session_date':['2025-02-03']*2,'pnl_usd':[-30,50],
                          'mae_usd':[-30,-20],'mfe_usd':[5,60]})
        d = daily_equity(t)
        self.assertEqual(d.iloc[0].pnl_usd,20)
        self.assertEqual(d.iloc[0].min_equity_usd,-50)


if __name__ == '__main__':
    unittest.main()
