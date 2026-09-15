import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from bot import build_map_data
from bot.collectors import realtor

HEADER = ("month_date_yyyymm,cbsa_code,cbsa_title,HouseholdRank,median_listing_price,"
          "active_listing_count,median_days_on_market,price_reduced_count,total_listing_count,quality_flag")


# one line in the layout of the real file, blank strings for missing cells
def row(month, code, price, active, days, reduced, total, flag="0.0", title="Abilene, TX"):
    return f'{month},{code},"{title}",1,{price},{active},{days},{reduced},{total},{flag}'


# newest month first like the real file. 2024 is the only full year: month m
# has price 300000 + 1000m, 100 + m active, 40 + m days and m of 200 reduced.
# 2025-02 has no days value and a zero denominator, code 1234 has one month
def base_rows():
    rows = [
        row("202502", "10180", 330000.0, 160, "", 30.0, 0, "1.0"),
        row("202502", "1234", 90000.0, 5, 12.0, 1.0, 4, "", "Nowhere, TX"),
        row("202501", "10180", 320000.0, 150, 30.0, 20.0, 250),
    ]
    rows += [row(f"2024{m:02d}", "10180", 300000.0 + 1000 * m, 100 + m, 40.0 + m, float(m), 200)
             for m in range(12, 0, -1)]
    return rows


# crlf line endings and a trailing summary line with no month, as the real
# file has carried
BASE_TEXT = "\r\n".join([HEADER] + base_rows() + ['"Source: Realtor.com Economic Research"', ""])


# every 2024 month at price 100000, 10 active, 20 days, 10 of 100 reduced,
# except june with no denominator, plus a bogus repeat of january at the end
def edge_rows():
    rows = [row(f"2024{m:02d}", "10180", 100000.0, 10, 20.0, 10.0, "" if m == 6 else 100)
            for m in range(12, 0, -1)]
    rows.append(row("202401", "10180", 999999.0, 999, 99.0, 99.0, 100))
    return rows


EDGE_TEXT = "\n".join([HEADER] + edge_rows() + [""])


def lookup(df, code, metric):
    rows = df[(df.cbsa_code == code) & (df.metric == metric)]
    return dict(zip(rows.period, rows.value))


class TestParseHistory(unittest.TestCase):
    def test_columns_and_row_count(self):
        df = realtor.parse_history(BASE_TEXT)
        self.assertEqual(list(df.columns), ["cbsa_code", "period"] + realtor.METRICS + ["flagged"])
        self.assertEqual(len(df), 15)

    def test_summary_row_is_dropped(self):
        df = realtor.parse_history(BASE_TEXT)
        self.assertTrue(df.period.str.fullmatch(r"\d{4}-\d{2}").all())
        self.assertNotIn("Source: Realtor.com Economic Research", df.cbsa_code.tolist())

    # a summary line can also arrive as a full row of blanks or a label
    def test_other_summary_shapes_are_dropped(self):
        text = "\n".join([HEADER, row("202401", "10180", 1.0, 1, 1.0, 1.0, 1),
                          row("", "", "", "", "", "", "", ""),
                          row("Total", "US", 1.0, 1, 1.0, 1.0, 1), ""])
        df = realtor.parse_history(text)
        self.assertEqual(df.period.tolist(), ["2024-01"])

    def test_code_keeps_and_adds_leading_zeros(self):
        df = realtor.parse_history(BASE_TEXT)
        self.assertEqual(sorted(df.cbsa_code.unique()), ["01234", "10180"])
        self.assertTrue((df.cbsa_code.str.len() == 5).all())

    def test_month_becomes_yyyy_mm(self):
        df = realtor.parse_history(BASE_TEXT)
        self.assertEqual(df.period.iloc[0], "2025-02")
        self.assertEqual(df.period.min(), "2024-01")

    def test_metric_values_are_floats(self):
        df = realtor.parse_history(BASE_TEXT)
        for metric in realtor.METRICS:
            self.assertEqual(df[metric].dtype.kind, "f", metric)
        first = df[(df.cbsa_code == "10180") & (df.period == "2025-01")].iloc[0]
        self.assertEqual(first["median_listing_price"], 320000.0)
        self.assertEqual(first["active_listings"], 150.0)
        self.assertEqual(first["days_on_market"], 30.0)
        self.assertAlmostEqual(first["price_reduced_share"], 0.08)

    def test_blank_cell_is_missing(self):
        df = realtor.parse_history(BASE_TEXT)
        newest = df[(df.cbsa_code == "10180") & (df.period == "2025-02")].iloc[0]
        self.assertTrue(pd.isna(newest["days_on_market"]))
        self.assertEqual(newest["active_listings"], 160.0)

    def test_zero_denominator_gives_missing_share(self):
        df = realtor.parse_history(BASE_TEXT)
        newest = df[(df.cbsa_code == "10180") & (df.period == "2025-02")].iloc[0]
        self.assertTrue(pd.isna(newest["price_reduced_share"]))

    def test_missing_denominator_gives_missing_share(self):
        df = realtor.parse_history(EDGE_TEXT)
        june = df[df.period == "2024-06"].iloc[0]
        self.assertTrue(pd.isna(june["price_reduced_share"]))
        self.assertAlmostEqual(df[df.period == "2024-05"].iloc[0]["price_reduced_share"], 0.1)

    def test_share_is_count_over_total(self):
        df = realtor.parse_history(BASE_TEXT)
        nowhere = df[df.cbsa_code == "01234"].iloc[0]
        self.assertAlmostEqual(nowhere["price_reduced_share"], 0.25)

    def test_duplicate_month_keeps_the_first_row(self):
        df = realtor.parse_history(EDGE_TEXT)
        self.assertEqual(len(df), 12)
        self.assertEqual(df[df.period == "2024-01"].iloc[0]["median_listing_price"], 100000.0)

    def test_quality_flag_one_is_flagged_blank_and_zero_are_not(self):
        df = realtor.parse_history(BASE_TEXT)
        self.assertEqual(int(df.flagged.sum()), 1)
        self.assertTrue(df[(df.cbsa_code == "10180") & (df.period == "2025-02")].iloc[0]["flagged"])
        self.assertFalse(df[df.cbsa_code == "01234"].iloc[0]["flagged"])

    def test_header_only_gives_empty_frame(self):
        df = realtor.parse_history(HEADER + "\n")
        self.assertEqual(len(df), 0)
        self.assertEqual(list(df.columns), ["cbsa_code", "period"] + realtor.METRICS + ["flagged"])


class TestFullYears(unittest.TestCase):
    def test_only_twelve_month_years_count(self):
        periods = [f"2024-{m:02d}" for m in range(1, 13)] + ["2025-01", "2025-02"]
        self.assertEqual(realtor.full_years(periods), [2024])

    def test_repeated_months_count_once(self):
        self.assertEqual(realtor.full_years(["2024-01"] * 12), [])

    def test_gap_year_is_absent(self):
        periods = [f"2023-{m:02d}" for m in range(1, 13)] + ["2025-01"]
        self.assertEqual(realtor.full_years(periods), [2023])

    def test_empty(self):
        self.assertEqual(realtor.full_years([]), [])

    def test_sorted_ints(self):
        periods = [f"{y}-{m:02d}" for y in (2019, 2017) for m in range(1, 13)]
        self.assertEqual(realtor.full_years(periods), [2017, 2019])


class TestSummarize(unittest.TestCase):
    def setUp(self):
        self.out = realtor.summarize(realtor.parse_history(BASE_TEXT))

    def test_map_contract_columns(self):
        self.assertEqual(list(self.out.columns), realtor.COLUMNS)
        self.assertTrue(self.out.period.str.fullmatch(r"\d{4}(-\d{2})?").all())
        self.assertFalse(self.out.value.isna().any())
        self.assertEqual(self.out.value.dtype.kind, "f")

    # month m of 2024 carries 300000 + 1000m, so the mean sits at m = 6.5
    def test_annual_means_exact(self):
        self.assertEqual(lookup(self.out, "10180", "median_listing_price")["2024"], 306500.0)
        self.assertEqual(lookup(self.out, "10180", "active_listings")["2024"], 106.5)
        self.assertEqual(lookup(self.out, "10180", "days_on_market")["2024"], 46.5)
        self.assertAlmostEqual(lookup(self.out, "10180", "price_reduced_share")["2024"], 0.0325)

    def test_partial_year_has_no_annual_row(self):
        self.assertNotIn("2025", set(self.out.period))
        self.assertNotIn("2016", set(self.out.period))

    def test_newest_month_per_metric(self):
        price = lookup(self.out, "10180", "median_listing_price")
        active = lookup(self.out, "10180", "active_listings")
        self.assertEqual(price["2025-02"], 330000.0)
        self.assertEqual(active["2025-02"], 160.0)
        self.assertEqual(len(price), 2)

    # a metric with no value in the newest month falls back to its own newest
    def test_missing_value_falls_back_to_the_previous_month(self):
        days = lookup(self.out, "10180", "days_on_market")
        self.assertEqual(days, {"2024": 46.5, "2025-01": 30.0})

    def test_zero_denominator_falls_back_to_the_previous_month(self):
        share = lookup(self.out, "10180", "price_reduced_share")
        self.assertEqual(set(share), {"2024", "2025-01"})
        self.assertAlmostEqual(share["2025-01"], 0.08)

    def test_code_without_a_full_year_has_newest_rows_only(self):
        nowhere = self.out[self.out.cbsa_code == "01234"]
        self.assertEqual(nowhere.period.tolist(), ["2025-02"] * 4)
        self.assertEqual(lookup(self.out, "01234", "price_reduced_share"), {"2025-02": 0.25})

    def test_row_count(self):
        self.assertEqual(len(self.out), 12)

    def test_duplicate_month_does_not_skew_the_mean(self):
        out = realtor.summarize(realtor.parse_history(EDGE_TEXT))
        self.assertEqual(lookup(out, "10180", "median_listing_price"), {"2024": 100000.0, "2024-12": 100000.0})
        self.assertEqual(lookup(out, "10180", "active_listings")["2024"], 10.0)

    # the june share is missing, so the mean runs over eleven months of 0.1
    def test_missing_month_is_left_out_of_the_mean(self):
        out = realtor.summarize(realtor.parse_history(EDGE_TEXT))
        self.assertAlmostEqual(lookup(out, "10180", "price_reduced_share")["2024"], 0.1)

    def test_year_with_no_data_for_a_code_gets_no_row(self):
        text = "\n".join([HEADER] + [row(f"2023{m:02d}", "10180", 1.0, 1, 1.0, 1.0, 1) for m in range(1, 13)]
                         + [row("202301", "1234", 2.0, 2, 2.0, 1.0, 2), ""])
        out = realtor.summarize(realtor.parse_history(text))
        self.assertEqual(lookup(out, "10180", "median_listing_price"), {"2023": 1.0, "2023-12": 1.0})
        self.assertEqual(lookup(out, "01234", "median_listing_price"), {"2023": 2.0, "2023-01": 2.0})

    def test_row_order_in_the_file_does_not_matter(self):
        reversed_text = "\n".join([HEADER] + list(reversed(base_rows())) + [""])
        out = realtor.summarize(realtor.parse_history(reversed_text))
        pd.testing.assert_frame_equal(out, self.out)

    def test_empty_frame(self):
        out = realtor.summarize(realtor.parse_history(HEADER + "\n"))
        self.assertEqual(list(out.columns), realtor.COLUMNS)
        self.assertEqual(len(out), 0)

    def test_metric_names_are_not_reserved(self):
        self.assertEqual(set(realtor.METRICS) & build_map_data.RESERVED, set())
        for metric in realtor.METRICS:
            self.assertRegex(metric, r"^[a-z][a-z0-9_]*$")


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.content = BASE_TEXT.encode()

    def tearDown(self):
        self.tmp.cleanup()

    def run_collect(self):
        response = Mock(content=self.content)
        with patch("bot.collectors.realtor.fetch", return_value=response) as fetched, \
                patch.object(realtor, "OUT_DIR", self.folder), \
                patch.object(realtor, "OUT_FILE", self.folder / "metrics.csv"):
            path = realtor.collect()
        fetched.assert_called_once_with(realtor.URL)
        return path

    def test_writes_metrics_and_manifest_only(self):
        path = self.run_collect()
        self.assertEqual(path, self.folder / "metrics.csv")
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["download_manifest.json", "metrics.csv"])
        written = pd.read_csv(path, dtype={"cbsa_code": str, "period": str})
        self.assertEqual(list(written.columns), realtor.COLUMNS)
        self.assertEqual(len(written), 12)
        self.assertIn("01234", set(written.cbsa_code))

    def test_manifest_describes_the_source_file(self):
        self.run_collect()
        entry = json.loads((self.folder / "download_manifest.json").read_text())[0]
        self.assertEqual(entry["filename"], "metrics.csv")
        self.assertEqual(entry["source"]["endpoint"], realtor.URL)
        self.assertEqual(entry["source"]["access_method"], "Direct HTTP download")
        self.assertEqual(entry["version"], "through 2025-02")
        self.assertEqual(entry["integrity"]["row_count"], 12)
        notes = entry["notes"]
        self.assertEqual(notes["attribution"], "Realtor.com Economic Research, realtor.com/research/data")
        self.assertEqual(notes["source_sha256"], hashlib.sha256(self.content).hexdigest())
        self.assertEqual(notes["source_size_kb"], round(len(self.content) / 1024, 1))
        self.assertEqual(notes["source_rows"], 15)
        self.assertEqual(notes["source_newest_month"], "2025-02")
        self.assertEqual(notes["full_years"], [2024])
        self.assertEqual(notes["quality_flagged_rows"], 1)

    # the builder's own loader must accept what collect writes
    def test_builder_reads_the_output(self):
        path = self.run_collect()
        source = build_map_data.load_enrichment(path)
        self.assertEqual(source["metrics"], sorted(realtor.METRICS))
        annual, latest = build_map_data.enrich_values(source["groups"]["10180"])
        self.assertEqual(annual[("median_listing_price", 2024)], 306500.0)
        self.assertEqual(latest["median_listing_price"], ("2025-02", 330000.0))
        self.assertEqual(latest["days_on_market"], ("2025-01", 30.0))

    def test_empty_source_raises(self):
        self.content = (HEADER + "\n").encode()
        with self.assertRaises(RuntimeError):
            self.run_collect()
        self.assertFalse((self.folder / "metrics.csv").exists())


if __name__ == "__main__":
    unittest.main()
