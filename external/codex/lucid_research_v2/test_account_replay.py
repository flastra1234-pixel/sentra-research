"""Synthetic accounting/rule tests; never evidence of strategy performance."""
import unittest,json
import pandas as pd
from account_replay import simulate_trial,rolling_trials,recent_trial,summarize_trials,normalize_trades


def data(pnl,mae=None,q=1):
    dates=pd.bdate_range('2026-01-05',periods=len(pnl))
    return pd.DataFrame({'session_date':dates.date,'pnl_usd':pnl,
                         'mae_usd':[-1]*len(pnl) if mae is None else mae,
                         'quantity':q}),dates


class AccountReplayChecks(unittest.TestCase):
    def test_total_position_pnl_is_not_rescaled(self):
        t,d=data([200],q=8)
        self.assertEqual(simulate_trial(t,d)['ending_balance'],25200)

    def test_intraday_floor_touch_before_winning_exit(self):
        t,d=data([200],[-1000])
        r=simulate_trial(t,d)
        self.assertEqual(r['outcome'],'funded_breach')
        self.assertEqual(r['minimum_headroom'],0)

    def test_eval_consistency_and_fresh_funded_reset(self):
        t,d=data([500,500,250,200])
        r=simulate_trial(t,d,stage='evaluation')
        self.assertEqual(r['eval_days'],3)
        self.assertEqual(r['funded_days'],1)
        self.assertEqual(r['eval_status'],'passed')
        self.assertEqual(r['ending_balance'],25200)
        self.assertEqual(r['simulated_payout_requests'],0)

    def test_consistency_blocks_large_single_day(self):
        t,d=data([900,350])
        self.assertEqual(simulate_trial(t,d,stage='evaluation')['eval_status'],'pending')

    def test_requests_reset_cycle_and_trading_continues(self):
        t,d=data([300]*10)
        r=simulate_trial(t,d)
        self.assertEqual(r['simulated_payout_requests'],2)
        self.assertEqual(r['funded_days'],10)
        self.assertEqual(r['simulated_trader_net_total'],900)
        self.assertEqual(r['ending_balance'],27000)
        events=json.loads(r['request_events_json'])
        self.assertEqual([e['qualifying_days'] for e in events],[5,5])
        self.assertEqual([e['cycle_trading_profit'] for e in events],[1500,1500])

    def test_minimum_policy_floor_stays_locked_after_request(self):
        t,d=data([200]*5+[0])
        r=simulate_trial(t,d,payout_profit=1000)
        self.assertEqual(r['simulated_payout_requests'],1)
        self.assertEqual(r['ending_balance'],25500)
        self.assertEqual(r['ending_floor'],25100)
        self.assertEqual(r['first_request_headroom'],400)

    def test_failure_after_request_is_not_reported_success(self):
        t,d=data([300]*5+[-1000],[-1]*5+[-1000])
        r=simulate_trial(t,d)
        self.assertEqual(r['simulated_payout_requests'],1)
        self.assertEqual(r['outcome'],'funded_breach_after_request')
        self.assertFalse(r['account_survived_horizon'])
        self.assertFalse(r['survived_20_sessions_after_first_request'])

    def test_twenty_session_survival_and_censoring(self):
        t,d=data([300]*5+[0]*20)
        r=simulate_trial(t,d)
        self.assertTrue(r['survived_20_sessions_after_first_request'])
        t,d=data([300]*5+[0]*10)
        self.assertIsNone(simulate_trial(t,d)['survived_20_sessions_after_first_request'])

    def test_three_request_cap_does_not_stop_trading(self):
        t,d=data([300]*25)
        r=simulate_trial(t,d)
        self.assertEqual(r['simulated_payout_requests'],3)
        self.assertEqual(r['funded_days'],25)
        self.assertEqual(r['ending_balance'],31000)

    def test_eod_only_trail_and_post_payout_floor(self):
        t,d=data([500,200],[-1,-1100])
        r=simulate_trial(t,d)
        self.assertEqual(r['outcome'],'funded_breach')
        self.assertEqual(r['ending_floor'],24500)

    def test_size_limit_uses_prior_eod_profit(self):
        t,d=data([1500],q=11)
        self.assertEqual(simulate_trial(t,d)['outcome'],'funded_size_violation')
        t,d=data([1000,100],q=10);t.loc[1,'quantity']=11
        self.assertNotIn('size_violation',simulate_trial(t,d)['outcome'])

    def test_inactivity(self):
        dates=pd.bdate_range('2026-01-05',periods=30)
        r=simulate_trial(pd.DataFrame(),dates)
        self.assertEqual(r['outcome'],'funded_inactivity')

    def test_overlap_rejected(self):
        t,d=data([1,2]);t['session_date']=[d[0].date()]*2
        t['entry_time']=['2026-01-05T14:31Z','2026-01-05T14:32Z']
        t['exit_time']=['2026-01-05T14:33Z','2026-01-05T14:34Z']
        with self.assertRaises(ValueError):normalize_trades(t)

    def test_rolling_and_short_recent_summary(self):
        t,d=data([10]*12)
        x=rolling_trials(t,d,horizon=10,stride=2)
        self.assertEqual(len(x),2)
        self.assertEqual(len(recent_trial(t,d,lookback_sessions=20)),1)
        self.assertTrue(recent_trial(t,d,lookback_sessions=20).iloc[0].short_horizon)
        self.assertTrue(recent_trial(t,d,lookback_sessions=20,allow_short=False).empty)
        self.assertEqual(summarize_trials(x)['paths_with_request'],0)


if __name__=='__main__':unittest.main()
