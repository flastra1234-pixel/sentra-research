import unittest
import numpy as np
import pandas as pd
from engine_v2 import build_market,config_signals,backtest,_execute,_retest,FAMILIES,COL


def synthetic(days=2,asset='ES'):
    frames=[]
    rng=np.random.default_rng(412)
    for date in pd.bdate_range('2024-02-05',periods=days):
        idx=pd.date_range(str(date.date())+' 09:30',periods=390,freq='min',tz='America/New_York').tz_convert('UTC')
        step=rng.normal(0,.55,390)+np.sin(np.arange(390)/33)*.07
        close=5000+np.cumsum(step)
        op=np.r_[close[0],close[:-1]]
        high=np.maximum(op,close)+rng.uniform(.25,.75,390)
        low=np.minimum(op,close)-rng.uniform(.25,.75,390)
        frames.append(pd.DataFrame(dict(open=op,high=high,low=low,close=close,volume=rng.integers(5,100,390)),index=idx))
    return pd.concat(frames)


def execute(op,high,low,minute,signal_idx,stop=4.,side=1,hold=30,slip=.25,pv=5.,budget=60.,flat=955,target_mode=0):
    n=len(op)
    return _execute(np.array(op,float),np.array(high,float),np.array(low,float),np.array(op,float),
        np.array(minute,np.int64),np.zeros(n,np.int64),np.array(signal_idx,np.int64),
        np.full(len(signal_idx),side,np.int64),np.full(len(signal_idx),stop,float),
        pv,1.,hold,955,slip,1.24,budget,10,2,flat,target_mode)


class EngineV2Tests(unittest.TestCase):
    def test_future_changes_do_not_change_any_earlier_signal(self):
        x=synthetic(1)
        altered=x.copy();cut=220
        for c in ['open','high','low','close']:altered.iloc[cut:,altered.columns.get_loc(c)]+=100
        a,b=build_market(x,'ES'),build_market(altered,'ES')
        for tf in [3,5,6,15]:
            for family in FAMILIES:
                c=dict(tf=tf,family=family,window=(570,955),context='none',direction='both',stop_atr=1.5)
                aa,ast=config_signals(a,c);bb,bst=config_signals(b,c)
                np.testing.assert_array_equal(aa[:cut],bb[:cut],err_msg=f'{tf}/{family}')
                np.testing.assert_allclose(ast[:cut],bst[:cut],equal_nan=True)

    def test_only_completed_aggregate_bar_can_signal(self):
        m=build_market(synthetic(1),'ES')
        for tf in [3,5,6,15]:
            for family in FAMILIES:
                c=dict(tf=tf,family=family,window=(570,955),stop_atr=1.5)
                directions,_=config_signals(m,c)
                idx=np.flatnonzero(directions)
                self.assertTrue(np.all((m.minute[idx]-570+1)%tf==0))

    def test_fixed_stressed_risk_quantity_and_total_dollars(self):
        op=np.full(4,5000.);hi=op+.2;lo=op-.2
        lo[1]=4990 # entry5000.25 stop4996.25 =>stopfill4996
        t=execute(op,hi,lo,[599,600,601,602],[0],stop=4)
        self.assertEqual(int(t[0,COL['quantity']]),2)
        self.assertLessEqual(2*(4*5+1.24+4*.25*5),60)
        self.assertAlmostEqual(t[0,COL['pnl_usd']],2*(-4.25*5-1.24))
        self.assertLessEqual(t[0,COL['mae_usd']],t[0,COL['pnl_usd']])
        too_wide=execute(op,hi,lo,[599,600,601,602],[0],stop=20)
        self.assertEqual(len(too_wide),0)

    def test_next_open_stop_first_and_gap_fill(self):
        op=np.array([5000,5002,5000,5000.])
        high=op+.1;low=op-.1
        high[1]=5010;low[1]=4990
        t=execute(op,high,low,[599,600,601,602],[0],stop=4)
        self.assertEqual(t[0,COL['entry_idx']],1)
        self.assertAlmostEqual(t[0,COL['entry_price']],5002.25)
        self.assertEqual(t[0,COL['exit_reason']],0)
        # First bar benign; second bar gaps below stop.
        op=np.array([5000,5000,4980,4980.]);high=op+.1;low=op-.1
        t=execute(op,high,low,[599,600,601,602],[0],stop=4)
        self.assertAlmostEqual(t[0,COL['exit_price']],4979.75)

    def test_retest_requires_a_later_candle(self):
        s=np.zeros(5,np.int64);upper=np.full(5,101.);lower=np.full(5,99.)
        c=np.array([100.,102.,102.,100.,102.]);h=c+1;l=np.array([99.5,100.5,100.8,99.,100.5])
        d=_retest(s,c,h,l,upper,lower)
        self.assertEqual(d[1],0)
        self.assertEqual(d[2],1)
        self.assertEqual(d[4],0)

    def test_missing_bar_rejects_day_missing_volume_disables_vwap(self):
        x=synthetic(2);x=x.drop(x.index[50]);m=build_market(x,'ES')
        self.assertEqual(len(m.session_dates),1)
        x=synthetic(1);x.iloc[200,x.columns.get_loc('volume')]=np.nan
        m=build_market(x,'ES')
        for tf in [3,5,6,15]:
            for family in ['vwap_trend_reclaim','vwap_reversion']:
                self.assertEqual(np.count_nonzero(m.aggregates[tf]['signals'][family]),0)

    def test_native_three_minute_no_upsampling_and_clock_exit(self):
        x=synthetic(1);native=x.groupby(np.arange(len(x))//3).agg(
            open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'))
        native.index=x.index[::3]
        m=build_market(native,'ES',bar_minutes=3)
        self.assertEqual(len(m.index),130)
        self.assertEqual(m.flat_minute,954)
        self.assertNotIn(5,m.aggregates)
        op=np.full(25,5000.);hi=op+.1;lo=op-.1
        t=execute(op,hi,lo,np.arange(597,672,3),[0],stop=4,hold=30,flat=954)
        self.assertEqual(t[0,COL['exit_idx']]-t[0,COL['entry_idx']],10)
        self.assertEqual(t[0,COL['exit_reason']],2)
        minute=np.arange(897,960,3);op=np.full(len(minute),5000.)
        t=execute(op,op+.1,op-.1,minute,[0],stop=4,hold=90,flat=954)
        self.assertEqual(minute[int(t[0,COL['exit_idx']])],954)

    def test_frame_and_compact_agree_and_no_overlap(self):
        m=build_market(synthetic(2),'ES')
        c=dict(family='ema_cross9_21',tf=3,window=(570,955),stop_atr=1.5,reward_r=1.5,max_hold=30)
        r=backtest(m,c,return_frame=False)
        t=backtest(m,c,return_frame=True)
        self.assertEqual(len(t),len(r));self.assertGreater(len(t),0)
        np.testing.assert_allclose(t.pnl_usd,r[:,COL['pnl_usd']])
        self.assertTrue((t.groupby('session_date').size()<=2).all())
        self.assertFalse((t.entry_time<t.exit_time.shift()).fillna(False).any())
        self.assertTrue(t.attrs['dollar_fields_are_total_position'])

    def test_limit_target_touch_is_not_fill_for_long_or_short(self):
        for side in [1,-1]:
            op=np.full(4,5000.);high=op+1;low=op-1
            target=5000+side*.25+side*4
            if side==1:high[1]=target
            else:low[1]=target
            minute=[599,600,601,602]
            limit=execute(op,high,low,minute,[0],side=side,hold=1,target_mode=1)
            market=execute(op,high,low,minute,[0],side=side,hold=1,target_mode=0)
            self.assertEqual(limit[0,COL['exit_reason']],2)
            self.assertEqual(limit[0,COL['exit_idx']],2)
            self.assertEqual(market[0,COL['exit_reason']],1)

    def test_limit_trade_through_fills_at_target_without_exit_slip(self):
        for side in [1,-1]:
            op=np.full(4,5000.);high=op+1;low=op-1
            target=5000+side*.25+side*4
            if side==1:high[1]=target+.25
            else:low[1]=target-.25
            t=execute(op,high,low,[599,600,601,602],[0],side=side,target_mode=1)
            self.assertEqual(t[0,COL['exit_reason']],1)
            self.assertAlmostEqual(t[0,COL['exit_price']],target)
            self.assertAlmostEqual(t[0,COL['pnl_points']],4)
            self.assertAlmostEqual(t[0,COL['pnl_usd']],2*(4*5-1.24))

    def test_limit_target_keeps_stop_first_ambiguity(self):
        op=np.full(4,5000.);high=op+10;low=op-10
        t=execute(op,high,low,[599,600,601,602],[0],target_mode=1)
        self.assertEqual(t[0,COL['exit_reason']],0)
        self.assertAlmostEqual(t[0,COL['exit_price']],4996.)

    def test_default_market_target_matches_preserved_engine(self):
        import engine_v2_before_limit as original
        x=synthetic(2)
        new_market=build_market(x,'ES');old_market=original.build_market(x,'ES')
        for family in FAMILIES:
            c=dict(family=family,tf=3,window=(570,955),stop_atr=1.5,reward_r=1.5,max_hold=30)
            old=original.backtest(old_market,c,return_frame=False)
            new=backtest(new_market,c,return_frame=False)
            explicit=backtest(new_market,dict(c,target_order='market'),return_frame=False)
            np.testing.assert_array_equal(old,new,err_msg=family)
            np.testing.assert_array_equal(new,explicit,err_msg=family)


if __name__=='__main__':unittest.main()
