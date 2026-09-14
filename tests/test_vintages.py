import os
import sys
import unittest
from pathlib import Path

# scripts/ is not a package, so put it on the path before importing
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import download_census as dc


class TestWindow(unittest.TestCase):
    # the fencepost. 2010 through 2014 inclusive is five years, not six
    def test_window_is_inclusive(self):
        self.assertEqual(dc.window(2014), (2010, 2014))
        self.assertEqual(dc.window(2024), (2020, 2024))

    def test_window_length_matches_span(self):
        start, end = dc.window(2019)
        self.assertEqual(end - start + 1, dc.SPAN)


class TestBatches(unittest.TestCase):
    def test_known_batches(self):
        self.assertEqual(dc.acs_batches(2024), [2024, 2019, 2014])

    def test_newest_first(self):
        years = dc.acs_batches(2024)
        self.assertEqual(years, sorted(years, reverse=True))

    # 15 years of coverage means the oldest start is latest - 14, not latest - 15
    def test_total_coverage_is_fifteen_years(self):
        years = dc.acs_batches(2024)
        oldest_start = dc.window(years[-1])[0]
        self.assertEqual(oldest_start, 2024 - 14)
        self.assertEqual(2024 - oldest_start + 1, dc.SPAN * dc.N_BATCHES)

    # the methodology claim in the readme: no respondent counted twice
    def test_windows_do_not_overlap(self):
        windows = sorted(dc.window(y) for y in dc.acs_batches(2024))
        for earlier, later in zip(windows, windows[1:]):
            self.assertGreater(later[0], earlier[1])

    def test_respects_batch_count(self):
        self.assertEqual(dc.acs_batches(2024, n_batches=2), [2024, 2019])

    # the floor is on the end year because that is the endpoint we request
    def test_floor_guard_raises(self):
        with self.assertRaises(ValueError):
            dc.acs_batches(2024, n_batches=4)
        with self.assertRaises(ValueError):
            dc.acs_batches(2016)

    def test_oldest_allowed_latest_passes(self):
        self.assertEqual(dc.acs_batches(2022), [2022, 2017, 2012])


class TestLatestVintage(unittest.TestCase):
    CATALOG = {
        "dataset": [
            {"c_dataset": ["acs", "acs5"], "c_vintage": 2019},
            {"c_dataset": ["acs", "acs5"], "c_vintage": 2024},
            {"c_dataset": ["acs", "acs1"], "c_vintage": 2030},
            {"c_dataset": ["timeseries", "eits"]},
        ]
    }

    def test_picks_max_for_the_right_dataset(self):
        self.assertEqual(dc.latest_vintage(self.CATALOG), 2024)

    def test_raises_when_dataset_absent(self):
        with self.assertRaises(RuntimeError):
            dc.latest_vintage(self.CATALOG, dataset=("acs", "acs9"))


class TestApiKey(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.pop("CENSUS_API_KEY", None)
        os.environ.pop("CENSUS_ENV_FILE", None)

    def tearDown(self):
        if self.saved is not None:
            os.environ["CENSUS_API_KEY"] = self.saved

    def test_reads_environment(self):
        os.environ["CENSUS_API_KEY"] = "  abc123  "
        self.assertEqual(dc.load_api_key(), "abc123")

    def test_raises_when_missing(self):
        with self.assertRaises(RuntimeError):
            dc.load_api_key()

    # comments, blanks and quoted values are where dotenv parsers break
    def test_reads_dotenv_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text('# a comment\n\nOTHER=1\nCENSUS_API_KEY="abc123"\n')
            self.assertEqual(dc.load_api_key(env_file=str(path)), "abc123")

    def test_redact_removes_the_key(self):
        self.assertEqual(dc.redact("url?key=abc123", "abc123"), "url?key=***")
        self.assertEqual(dc.redact("nothing", ""), "nothing")


if __name__ == "__main__":
    unittest.main()
