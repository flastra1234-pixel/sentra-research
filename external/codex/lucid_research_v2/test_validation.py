import unittest
import numpy as np
import pandas as pd

from validation import (rolling_folds, risk_quantity,
                        moving_block_bootstrap_mean_ci,
                        shared_block_max_t_test, family_plateau_support)


class ValidationTests(unittest.TestCase):
    def test_rolling_folds_chronological_and_disjoint_tests(self):
        dates = pd.bdate_range("2024-01-01", periods=200)
        folds = rolling_folds(dates, 60, 20, 30, 30)
        self.assertEqual(len(folds), 4)
        tests = []
        for f in folds:
            self.assertEqual(len(f.train_dates), 60)
            self.assertEqual(len(f.validation_dates), 20)
            self.assertEqual(len(f.test_dates), 30)
            self.assertLess(f.train_dates[-1], f.validation_dates[0])
            self.assertLess(f.validation_dates[-1], f.test_dates[0])
            tests.extend(f.test_dates)
        self.assertEqual(len(tests), len(set(tests)))

    def test_overlapping_tests_must_be_explicit(self):
        with self.assertRaises(ValueError):
            rolling_folds(pd.bdate_range("2024-01-01", periods=100), 40, 10, 20, 10)

    def test_risk_sizing_respects_costs_caps_and_skips(self):
        # MES stop10points: $50 + fee1.24 + conservative slippage5 =56.24.
        self.assertEqual(risk_quantity(10, 5, 100), 1)
        self.assertEqual(risk_quantity(10, 5, 50), 0)
        self.assertEqual(risk_quantity(.25, 2, 1000), 10)
        np.testing.assert_array_equal(risk_quantity([10, np.nan, -1], 5, 100), [1, 0, 0])

    def test_zero_bootstrap_does_not_manufacture_an_edge(self):
        r = moving_block_bootstrap_mean_ci(np.zeros(40), n_boot=100)
        self.assertEqual(r["ci_low"], 0)
        self.assertEqual(r["ci_high"], 0)
        self.assertEqual(r["centered_bootstrap_p_value"], 1)
        m = shared_block_max_t_test(np.zeros((40, 10)), n_boot=100)
        self.assertEqual(m["global_p_value"], 1)
        self.assertTrue(all(p == 1 for p in m["familywise_adjusted_p_values"]))

    def test_max_statistic_adjustment_is_never_weaker_than_single_column(self):
        rng = np.random.default_rng(9)
        x = rng.normal(size=(120, 30))
        # One signal with clear positive mean; other columns are noisy alternatives.
        x[:, 0] += .7
        r = shared_block_max_t_test(x, n_boot=200)
        one = shared_block_max_t_test(x[:, :1], n_boot=200)
        self.assertGreaterEqual(r["familywise_adjusted_p_values"][0], one["global_p_value"])
        self.assertLess(r["global_p_value"], .05)

    def test_plateau_checks_local_neighbors_and_preserves_asset_context(self):
        cs = [{"id": f"A{i}", "family": "orb", "asset": "MES", "reward": i}
              for i in [1, 2, 3]]
        cs += [{"id": "N2", "family": "orb", "asset": "MNQ", "reward": 2}]
        scores = pd.DataFrame({"id": ["A1", "A2", "A3", "N2"],
                               "stress_net": [-10, 1000, 20, 9999]})
        out = family_plateau_support(scores, cs, param_keys=["reward"]).set_index("id")
        self.assertEqual(out.loc["A2", "neighbor_configurations"], 2)
        self.assertEqual(out.loc["A2", "positive_neighbor_fraction"], .5)
        self.assertEqual(out.loc["A2", "median_neighbor_metric"], 5)
        self.assertEqual(out.loc["N2", "neighbor_configurations"], 0)


if __name__ == "__main__":
    unittest.main()
