import unittest

import numpy as np
import pandas as pd

from loop import spec


def small_panel():
    rows = []
    for code, start in (("10001", 100.0), ("10002", 200.0)):
        for i, q in enumerate(pd.period_range("2015Q1", "2016Q4", freq="Q")):
            rows.append({"cbsa_code": code, "quarter": str(q), "log_hpi": np.log(start * (1.01 ** i))})
    return pd.DataFrame(rows)


class TestQuarters(unittest.TestCase):
    def test_shift_crosses_years(self):
        self.assertEqual(spec.shift_quarter("2024Q3", 2), "2025Q1")
        self.assertEqual(spec.shift_quarter("2024Q1", -1), "2023Q4")

    def test_quarter_end_and_back(self):
        end = spec.quarter_end("2026Q2")
        self.assertEqual(str(end.date()), "2026-06-30")
        self.assertEqual(spec.quarter_of(end), "2026Q2")


class TestTarget(unittest.TestCase):
    def test_growth_is_log_difference_ahead(self):
        panel = small_panel()
        y = spec.target(panel, 4)
        first = panel[(panel.cbsa_code == "10001") & (panel.quarter == "2015Q1")].index[0]
        self.assertAlmostEqual(y[first], 4 * np.log(1.01))
        self.assertAlmostEqual(spec.pct(y[first]), 100 * (1.01 ** 4 - 1), places=6)

    def test_missing_quarter_gives_null_not_a_wrong_pair(self):
        panel = small_panel()
        panel = panel[panel.quarter != "2015Q3"].reset_index(drop=True)
        y = spec.target(panel, 1)
        row = panel[(panel.cbsa_code == "10001") & (panel.quarter == "2015Q2")].index[0]
        self.assertTrue(np.isnan(y[row]))

    def test_last_quarters_have_no_target(self):
        panel = small_panel()
        y = spec.target(panel, 2)
        tail = panel[panel.quarter.isin(["2016Q3", "2016Q4"])].index
        self.assertTrue(y[tail].isna().all())


class TestBlocks(unittest.TestCase):
    def test_outcome_decides_the_block(self):
        self.assertEqual(spec.block("2015Q4", 8), "train")
        self.assertIsNone(spec.block("2016Q1", 8))
        self.assertEqual(spec.block("2018Q1", 8), "cal")
        self.assertIsNone(spec.block("2020Q1", 8))
        self.assertEqual(spec.block("2022Q1", 8), "test")
        self.assertEqual(spec.block("2021Q4", 1), None)
        self.assertEqual(spec.block("2017Q3", 1), "train")


class TestMeasures(unittest.TestCase):
    def test_relative_mae_of_no_change_is_one(self):
        y = np.array([0.02, -0.01, 0.05, 0.0])
        self.assertAlmostEqual(spec.relative_mae(y, np.zeros(4)), 1.0)

    def test_pinball_penalises_the_right_side(self):
        y = np.array([1.0])
        self.assertAlmostEqual(spec.pinball(y, np.array([0.0]), 0.9), 0.9)
        self.assertAlmostEqual(spec.pinball(y, np.array([2.0]), 0.9), 0.1)

    def test_coverage_and_width_skip_nulls(self):
        y = np.array([0.0, 1.0, np.nan, 3.0])
        lo = np.array([-1.0, 2.0, 0.0, 2.0])
        hi = np.array([1.0, 3.0, 1.0, 4.0])
        self.assertAlmostEqual(spec.coverage(y, lo, hi), 2 / 3)
        self.assertAlmostEqual(spec.mean_width(lo, hi), 1.5)

    def test_conformal_margin_reaches_nominal_coverage(self):
        rng = np.random.default_rng(spec.SEED)
        y = rng.normal(size=2000)
        lo, hi = np.full(2000, -0.5), np.full(2000, 0.5)
        m = spec.conformal_margin(y, lo, hi, alpha=0.1)
        self.assertGreater(m, 0)
        self.assertGreaterEqual(spec.coverage(y, lo - m, hi + m), 0.9)

    def test_conformal_margin_can_shrink_a_wide_band(self):
        y = np.zeros(50)
        m = spec.conformal_margin(y, np.full(50, -2.0), np.full(50, 2.0))
        self.assertLess(m, 0)


if __name__ == "__main__":
    unittest.main()
