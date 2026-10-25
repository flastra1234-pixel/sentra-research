"""Small synthetic tests of rules/accounting, never used as market evidence."""
import unittest
import pandas as pd
from prop_sim import simulate_trial, rolling_trials


def rows(pnl,mae=None):
    days=pd.bdate_range('2026-01-05',periods=len(pnl))
    trades=pd.DataFrame({'session_date':days.date,'pnl_usd':pnl,
                         'mae_usd':mae if mae is not None else [-1.]*len(pnl)})
    return trades,days


class TestPropSim(unittest.TestCase):
    def test_eod_ratchet_not_intraday(self):
        # Day1 +500 moves next-day floor24500; next-day dip to24400 breaches
        t,d=rows([500,200],[-1,-1100])
        r=simulate_trial(t,d,quantity=1)
        self.assertEqual(r['outcome'],'evaluation_breach')
        self.assertEqual(r['ending_floor'],24500)

    def test_intraday_low_before_recovery_breaches(self):
        t,d=rows([300],[-1000])
        r=simulate_trial(t,d,quantity=1)
        self.assertEqual(r['outcome'],'evaluation_breach')
        self.assertEqual(r['minimum_headroom'],0)

    def test_consistency_blocks_concentrated_profit(self):
        t,d=rows([900,350],[-1,-1])
        r=simulate_trial(t,d,quantity=1)
        self.assertEqual(r['outcome'],'evaluation_pending')
        self.assertEqual(r['eval_status'],'pending')

    def test_eval_then_fresh_funded_and_payout(self):
        # Eval3days then funded5days, no carry-forward of1250+ eval profit
        t,d=rows([450,450,450]+[300]*5)
        r=simulate_trial(t,d,quantity=1)
        self.assertEqual(r['eval_status'],'passed')
        self.assertEqual(r['eval_days'],3)
        self.assertEqual(r['funded_days'],5)
        self.assertEqual(r['outcome'],'payout')
        self.assertEqual(r['trader_net_payout'],450)
        self.assertEqual(r['ending_balance'],26000)
        self.assertEqual(r['ending_floor'],25100)
        self.assertEqual(r['payout_after_headroom'],900)

    def test_exact_target_40_percent(self):
        t,d=rows([500,500,250])
        r=simulate_trial(t,d,quantity=1)
        self.assertEqual(r['eval_status'],'passed')
        self.assertEqual(r['outcome'],'funded_pending')
        self.assertEqual(r['ending_balance'],25000)

    def test_floor_caps(self):
        t,d=rows([1200,-50])
        r=simulate_trial(t,d,quantity=1,stage='funded')
        self.assertEqual(r['ending_floor'],25100)

    def test_funded_no_consistency(self):
        t,d=rows([1000,125,125,125,125])
        r=simulate_trial(t,d,quantity=1,stage='funded')
        self.assertEqual(r['outcome'],'payout')
        self.assertEqual(r['funded_days'],5)

    def test_minimum_payout_restricts_lowprofit(self):
        t,d=rows([100]*5)
        r=simulate_trial(t,d,quantity=1,stage='funded',payout_profit=0)
        self.assertEqual(r['outcome'],'funded_pending')
        self.assertEqual(r['funded_qualifying_days'],5)

    def test_positive_mae_is_also_loss_magnitude(self):
        t,d=rows([300],[1000])
        self.assertEqual(simulate_trial(t,d,quantity=1)['outcome'],'evaluation_breach')

    def test_full_rolling_horizon_only(self):
        t,d=rows([10]*12)
        r=rolling_trials(t,d,quantity=1,horizon=10,stride=2)
        self.assertEqual(len(r),2)
        self.assertEqual(set(r['horizon_sessions']),{10})

    def test_30_calendar_day_inactivity(self):
        d=pd.bdate_range('2026-01-05',periods=30)
        t=pd.DataFrame(columns=['session_date','pnl_usd','mae_usd'])
        r=simulate_trial(t,d,quantity=1)
        self.assertEqual(r['outcome'],'evaluation_inactivity')

    def test_overlapping_trades_rejected(self):
        t,d=rows([1,2])
        t['entry_time']=pd.to_datetime(['2026-01-05T14:31Z','2026-01-05T14:32Z'])
        t['exit_time']=pd.to_datetime(['2026-01-05T14:33Z','2026-01-05T14:34Z'])
        with self.assertRaises(ValueError):
            simulate_trial(t,d,quantity=1)

if __name__=='__main__':
    unittest.main()
