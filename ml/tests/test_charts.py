import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from loop import charts


class TestCharts(unittest.TestCase):
    def test_figure_saves_a_png_in_the_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(charts, "FIGURES_DIR", charts.FIGURES_DIR.__class__(tmp)):
                fig, ax = charts.figure("title", "subtitle")
                x = np.arange(10)
                ax.plot(x, x * 2.0)
                charts.label_end(ax, 9, 18.0, "end", charts.SERIES[0])
                charts.pct_axis(ax)
                path = charts.save(fig, "check")
                self.assertTrue(os.path.exists(path))
                self.assertGreater(os.path.getsize(path), 1000)

    def test_palettes_are_hex_and_fixed_order(self):
        self.assertEqual(charts.SERIES[0], "#2a78d6")
        self.assertEqual(len(charts.SEQUENTIAL), 7)
        self.assertEqual(charts.DIVERGING[3], "#f0efec")
        self.assertTrue(all(c.startswith("#") and len(c) == 7 for c in charts.SERIES + charts.SEQUENTIAL + charts.DIVERGING))
        self.assertIsNotNone(charts.sequential_cmap())
        self.assertIsNotNone(charts.diverging_cmap())


if __name__ == "__main__":
    unittest.main()
