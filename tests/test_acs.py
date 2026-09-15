import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from bot import build_map_data
from bot.collectors import acs

# scripts/ is not a package, so put it on the path before importing
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import download_census as dc

# one full row of the variables, chosen so every metric is a clean number
ABILENE = {
    "NAME": "Abilene, TX Metro Area",
    "B25064_001E": "950",
    "B25070_001E": "20000", "B25070_007E": "2000", "B25070_008E": "1500",
    "B25070_009E": "1300", "B25070_010E": "3200", "B25070_011E": "400",
    "B25002_001E": "70000", "B25002_003E": "7000",
    "B08013_001E": "1500000", "B08012_001E": "75000",
    "B17001_001E": "160000", "B17001_002E": "24000",
    "B23025_001E": "130000", "B23025_002E": "84500",
}
EXPECTED = {
    "gross_rent": 950.0,
    "rent_burden": 8000 / 19600,
    "vacancy_rate": 0.1,
    "commute_minutes": 20.0,
    "poverty_rate": 0.15,
    "labor_force_rate": 0.65,
}


# one raw row tagged with its join code, with any variable overridden
def record(code, **overrides):
    row = dict(ABILENE)
    row.update(overrides)
    row["geo_code"] = code
    return row


def frame(*records):
    return pd.DataFrame(list(records))


# a fake requests response for the mocked fetch
def response(status, body=b"", content_type=""):
    fake = Mock()
    fake.status_code = status
    fake.content = body
    fake.text = body.decode()
    fake.headers = {"content-type": content_type}
    fake.json = lambda: json.loads(body)
    return fake


class TestMetricSpec(unittest.TestCase):
    def test_variables_are_the_fifteen_codes_once_each(self):
        self.assertEqual(len(acs.VARIABLES), 15)
        self.assertEqual(len(set(acs.VARIABLES)), 15)
        for spec in acs.METRICS.values():
            self.assertTrue(set(acs.metric_codes(spec)) <= set(acs.VARIABLES))

    # the builder refuses a metrics.csv that reuses a core field name
    def test_metric_names_are_snake_case_and_not_reserved(self):
        self.assertEqual(len(acs.METRICS), 6)
        self.assertFalse(set(acs.METRICS) & build_map_data.RESERVED)
        for name in acs.METRICS:
            self.assertRegex(name, r"^[a-z][a-z0-9_]*$")

    def test_geography_constants_are_the_pipelines(self):
        self.assertIs(acs.DIVISION_PARENTS, dc.DIVISION_PARENTS)
        self.assertIs(acs.DIVISION_CROSSWALK, dc.DIVISION_CROSSWALK)
        self.assertEqual(acs.MSA_COL, dc.MSA_COL)
        self.assertEqual(acs.DIV_COL, dc.DIV_COL)
        self.assertEqual(acs.VINTAGES, [2014, 2019, 2024])

    def test_available_metrics_drops_a_metric_missing_one_code(self):
        without = [code for code in acs.VARIABLES if code != "B25070_011E"]
        self.assertEqual(acs.available_metrics(without),
                         ["gross_rent", "vacancy_rate", "commute_minutes", "poverty_rate", "labor_force_rate"])
        self.assertEqual(acs.available_metrics(acs.VARIABLES), list(acs.METRICS))
        self.assertEqual(acs.available_metrics([]), [])

    def test_version_label(self):
        self.assertEqual(acs.version_label(), "ACS 5-year 2014, 2019, 2024")
        self.assertEqual(acs.version_label([2019]), "ACS 5-year 2019")

    def test_ascii_text_drops_accents_and_keeps_letters(self):
        self.assertEqual(acs.ascii_text("Mayag\u00fcez, PR Metro Area"), "Mayaguez, PR Metro Area")
        self.assertEqual(acs.ascii_text("San Juan-Bayam\u00f3n-Caguas, PR Metro Area"), "San Juan-Bayamon-Caguas, PR Metro Area")
        self.assertEqual(acs.ascii_text("Ca\u00f1on City, CO Micro Area"), "Canon City, CO Micro Area")
        self.assertEqual(acs.ascii_text("Abilene, TX Metro Area"), "Abilene, TX Metro Area")

    def test_redact_hides_the_key(self):
        self.assertEqual(acs.redact("bad url ?key=abc123 here", "abc123"), "bad url ?key=*** here")
        self.assertEqual(acs.redact("plain", ""), "plain")


class TestDerive(unittest.TestCase):
    def test_exact_numbers(self):
        out = acs.derive_metrics(frame(record("10180")))
        self.assertEqual(list(out.columns), list(acs.METRICS))
        for name, expected in EXPECTED.items():
            self.assertAlmostEqual(out[name].iloc[0], expected, places=9)

    def test_metric_rows_follow_the_contract(self):
        rows = acs.metric_rows(frame(record("10180")), 2014)
        self.assertEqual(list(rows.columns), acs.COLUMNS)
        self.assertEqual(len(rows), 6)
        self.assertEqual(set(rows.cbsa_code), {"10180"})
        self.assertEqual(set(rows.period), {"2014"})
        self.assertEqual(rows.value.dtype.kind, "f")
        self.assertEqual(rows.metric.tolist(), sorted(acs.METRICS))

    def test_metric_rows_round_to_six_places(self):
        rows = acs.metric_rows(frame(record("10180")), 2024)
        values = dict(zip(rows.metric, rows.value))
        self.assertEqual(values["rent_burden"], 0.408163)
        self.assertEqual(values["gross_rent"], 950.0)
        self.assertEqual(values["commute_minutes"], 20.0)

    def test_two_codes_keep_their_own_values(self):
        rows = acs.metric_rows(frame(record("10180"), record("16984", B25064_001E="1300")), 2019)
        rent = rows[rows.metric == "gross_rent"]
        self.assertEqual(dict(zip(rent.cbsa_code, rent.value)), {"10180": 950.0, "16984": 1300.0})
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows.cbsa_code.tolist(), ["10180"] * 6 + ["16984"] * 6)


class TestMissingValues(unittest.TestCase):
    def test_sentinel_is_missing_and_has_no_row(self):
        rows = acs.metric_rows(frame(record("10180", B25064_001E="-666666666")), 2014)
        self.assertNotIn("gross_rent", rows.metric.tolist())
        self.assertEqual(len(rows), 5)

    # the rule is anything at or below the sentinel
    def test_sentinel_boundary(self):
        at = acs.derive_metrics(frame(record("10180", B25064_001E="-666666")))
        above = acs.derive_metrics(frame(record("10180", B25064_001E="-666665")))
        self.assertTrue(pd.isna(at.gross_rent.iloc[0]))
        self.assertEqual(above.gross_rent.iloc[0], -666665.0)

    def test_one_missing_bucket_makes_the_whole_sum_missing(self):
        out = acs.derive_metrics(frame(record("10180", B25070_008E="-666666666")))
        self.assertTrue(pd.isna(out.rent_burden.iloc[0]))
        self.assertAlmostEqual(out.vacancy_rate.iloc[0], 0.1)

    def test_zero_denominator_is_missing(self):
        out = acs.derive_metrics(frame(record("10180", B25002_001E="0")))
        self.assertTrue(pd.isna(out.vacancy_rate.iloc[0]))

    # every renter household not computed leaves nothing to divide by
    def test_rent_burden_denominator_of_zero_after_subtraction(self):
        out = acs.derive_metrics(frame(record("10180", B25070_001E="400", B25070_011E="400")))
        self.assertTrue(pd.isna(out.rent_burden.iloc[0]))

    def test_blank_and_text_values_are_missing(self):
        rows = acs.metric_rows(frame(record("10180", B17001_002E="", B23025_002E="abc", B08012_001E=None)), 2014)
        self.assertEqual(rows.metric.tolist(), ["gross_rent", "rent_burden", "vacancy_rate"])

    def test_missing_denominator_is_missing(self):
        out = acs.derive_metrics(frame(record("10180", B17001_001E="-999999999")))
        self.assertTrue(pd.isna(out.poverty_rate.iloc[0]))


class TestEdges(unittest.TestCase):
    def test_empty_frame_gives_no_rows_with_the_contract_columns(self):
        empty = pd.DataFrame(columns=["NAME"] + acs.VARIABLES + ["geo_code"])
        rows = acs.metric_rows(empty, 2019)
        self.assertEqual(list(rows.columns), acs.COLUMNS)
        self.assertEqual(len(rows), 0)

    def test_frame_without_variable_columns_gives_no_rows(self):
        rows = acs.metric_rows(pd.DataFrame({"geo_code": ["10180"]}), 2019)
        self.assertEqual(len(rows), 0)

    # a vintage that lacks one code still yields the other five metrics
    def test_missing_code_column_leaves_that_metric_out(self):
        row = record("10180")
        del row["B25070_011E"]
        rows = acs.metric_rows(frame(row), 2014)
        self.assertNotIn("rent_burden", rows.metric.tolist())
        self.assertEqual(len(rows), 5)

    def test_leading_zero_code_is_kept_through_a_csv_round_trip(self):
        rows = acs.metric_rows(frame(record("01234")), 2014)
        self.assertEqual(set(rows.cbsa_code), {"01234"})
        text = rows.to_csv(index=False)
        self.assertIn("\n01234,gross_rent,2014,950.0\n", text)
        back = pd.read_csv(io.StringIO(text), dtype={"cbsa_code": str, "period": str})
        self.assertEqual(set(back.cbsa_code), {"01234"})

    def test_malformed_codes_are_dropped(self):
        rows = acs.metric_rows(frame(record(""), record("1234"), record(None), record(" 10180 ")), 2014)
        self.assertEqual(set(rows.cbsa_code), {"10180"})
        self.assertEqual(len(rows), 6)

    def test_duplicate_code_keeps_the_first_row(self):
        rows = acs.metric_rows(frame(record("10180", B25064_001E="900"), record("10180", B25064_001E="999")), 2014)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[rows.metric == "gross_rent"].value.iloc[0], 900.0)

    def test_a_year_with_no_data_has_no_period(self):
        empty = pd.DataFrame(columns=["NAME"] + acs.VARIABLES + ["geo_code"])
        out = acs.combine([acs.metric_rows(frame(record("10180")), 2014),
                           acs.metric_rows(empty, 2019),
                           acs.metric_rows(frame(record("10180")), 2024)])
        self.assertEqual(sorted(set(out.period)), ["2014", "2024"])
        self.assertEqual(len(out), 12)
        self.assertEqual(list(out.columns), acs.COLUMNS)

    def test_combine_sorts_and_dedupes_across_frames(self):
        one = acs.metric_rows(frame(record("16984"), record("10180")), 2019)
        out = acs.combine([one, one.copy()])
        self.assertEqual(len(out), 12)
        self.assertEqual(out.cbsa_code.tolist(), ["10180"] * 6 + ["16984"] * 6)

    def test_combine_nothing(self):
        out = acs.combine([])
        self.assertEqual(list(out.columns), acs.COLUMNS)
        self.assertEqual(len(out), 0)

    def test_parse_table_header_row_and_malformed_rows(self):
        df = acs.parse_table([["NAME", "B25064_001E", acs.MSA_COL],
                              ["Abilene, TX Metro Area", "950", "10180"],
                              ["short row", "1"],
                              ["Aberdeen, SD Micro Area", "700", "10100"]])
        self.assertEqual(list(df.columns), ["NAME", "B25064_001E", acs.MSA_COL])
        self.assertEqual(df[acs.MSA_COL].tolist(), ["10180", "10100"])

    def test_parse_table_empty_and_header_only(self):
        self.assertEqual(list(acs.parse_table([], ["a", "b"]).columns), ["a", "b"])
        self.assertEqual(len(acs.parse_table(None, ["a"])), 0)
        header_only = acs.parse_table([["NAME", acs.MSA_COL]])
        self.assertEqual(list(header_only.columns), ["NAME", acs.MSA_COL])
        self.assertEqual(len(header_only), 0)


class TestFetchVintage(unittest.TestCase):
    # msas come from one call, each split parent from its own. chicago's 2014
    # division code was 16974, the crosswalk brings it to 16984
    def fake_query(self, year, key, codes, geography, within=None):
        if within is None:
            row = [ABILENE[c] for c in ["NAME"] + codes] + ["10180"]
            row[0] = "Espa\u00f1ola, NM Micro Area"
            return pd.DataFrame([row], columns=["NAME"] + codes + [acs.MSA_COL])
        if within.endswith(":16980"):
            return pd.DataFrame([[ABILENE[c] for c in ["NAME"] + codes] + ["16980", "16974"],
                                 [ABILENE[c] for c in ["NAME"] + codes] + ["16980", "20994"]],
                                columns=["NAME"] + codes + [acs.MSA_COL, acs.DIV_COL])
        return pd.DataFrame(columns=["NAME"] + codes + [acs.MSA_COL, acs.DIV_COL])

    def test_tags_and_crosswalks(self):
        with patch.object(acs, "query", side_effect=self.fake_query) as mocked:
            df = acs.fetch_vintage(2014, "k", acs.VARIABLES)
        self.assertEqual(mocked.call_count, 1 + len(acs.DIVISION_PARENTS))
        self.assertEqual(df.geo_code.tolist(), ["10180", "16984", "20994"])
        self.assertEqual(df.NAME.iloc[0], "Espanola, NM Micro Area")
        self.assertEqual(df.geo_level.tolist(), ["msa", "division", "division"])
        self.assertEqual(df.parent_cbsa.tolist(), ["", "16980", "16980"])
        self.assertEqual(df[acs.DIV_COL].tolist()[1:], ["16974", "20994"])
        self.assertEqual(set(df.year), {2014})
        self.assertEqual(list(df.columns), ["NAME"] + acs.VARIABLES
                         + [acs.MSA_COL, acs.DIV_COL, "geo_level", "geo_code", "parent_cbsa", "year"])

    def test_division_rows_feed_metric_rows_under_the_current_code(self):
        with patch.object(acs, "query", side_effect=self.fake_query):
            rows = acs.metric_rows(acs.fetch_vintage(2014, "k", acs.VARIABLES), 2014)
        self.assertEqual(sorted(set(rows.cbsa_code)), ["10180", "16984", "20994"])
        self.assertNotIn("16974", set(rows.cbsa_code))


class TestQuery(unittest.TestCase):
    KEY = "secret-key-123"

    def test_request_shape(self):
        body = json.dumps([["NAME", "B25064_001E", acs.MSA_COL, acs.DIV_COL],
                           ["Elgin, IL Metro Division", "1100", "16980", "20994"]]).encode()
        with patch.object(acs, "fetch", return_value=response(200, body, "application/json")) as mocked:
            df = acs.query(2019, self.KEY, ["B25064_001E"], f"{acs.DIV_COL}:*", within=f"{acs.MSA_COL}:16980")
        self.assertEqual(mocked.call_args.args[0], "https://api.census.gov/data/2019/acs/acs5")
        params = mocked.call_args.kwargs["params"]
        self.assertEqual(params["get"], "NAME,B25064_001E")
        self.assertEqual(params["for"], "metropolitan division:*")
        self.assertEqual(params["in"], "metropolitan statistical area/micropolitan statistical area:16980")
        self.assertEqual(params["key"], self.KEY)
        self.assertEqual(df[acs.DIV_COL].tolist(), ["20994"])

    def test_msa_query_has_no_in_clause(self):
        body = json.dumps([["NAME", "B25064_001E", acs.MSA_COL]]).encode()
        with patch.object(acs, "fetch", return_value=response(200, body, "application/json")) as mocked:
            acs.query(2024, self.KEY, ["B25064_001E"], f"{acs.MSA_COL}:*")
        self.assertNotIn("in", mocked.call_args.kwargs["params"])

    # a parent with no divisions in that vintage
    def test_204_is_an_empty_frame_with_the_columns(self):
        with patch.object(acs, "fetch", return_value=response(204, b"")):
            df = acs.query(2014, self.KEY, ["B25064_001E"], f"{acs.DIV_COL}:*", within=f"{acs.MSA_COL}:12060")
        self.assertEqual(len(df), 0)
        self.assertEqual(list(df.columns), ["NAME", "B25064_001E", acs.MSA_COL, acs.DIV_COL])

    def test_blank_body_with_200_is_also_empty(self):
        with patch.object(acs, "fetch", return_value=response(200, b"  \n", "application/json")):
            self.assertEqual(len(acs.query(2014, self.KEY, ["B25064_001E"], "x")), 0)

    def test_html_with_200_raises_without_the_key(self):
        with patch.object(acs, "fetch", return_value=response(200, b"<html>invalid key</html>", "text/html")):
            with self.assertRaises(RuntimeError) as caught:
                acs.query(2014, self.KEY, ["B25064_001E"], "x")
        self.assertIn("CENSUS_API_KEY", str(caught.exception))
        self.assertNotIn(self.KEY, str(caught.exception))

    def test_400_raises_with_the_message_and_hides_the_key(self):
        body = f"error: unknown variable 'B25070_011E' for key={self.KEY}".encode()
        with patch.object(acs, "fetch", return_value=response(400, body, "text/plain")):
            with self.assertRaises(RuntimeError) as caught:
                acs.query(2014, self.KEY, ["B25070_011E"], "x")
        self.assertIn("unknown variable", str(caught.exception))
        self.assertNotIn(self.KEY, str(caught.exception))

    def test_present_variables_keeps_200_drops_404(self):
        def fake_fetch(url, params=None, **kwargs):
            return response(404, b"<html>", "text/html") if "B25070_011E" in url else response(200, b"{}", "application/json")
        with patch.object(acs, "fetch", side_effect=fake_fetch) as mocked:
            present = acs.present_variables(2014)
        self.assertEqual(present, [code for code in acs.VARIABLES if code != "B25070_011E"])
        self.assertEqual(mocked.call_count, len(acs.VARIABLES))
        self.assertEqual(mocked.call_args_list[0].args[0],
                         "https://api.census.gov/data/2014/acs/acs5/variables/B25064_001E.json")

    def test_present_variables_raises_on_other_status(self):
        with patch.object(acs, "fetch", return_value=response(503, b"")):
            with self.assertRaises(RuntimeError):
                acs.present_variables(2019, ["B25064_001E"])


# the whole collector offline: a fake api with two msas and one split parent,
# and a vintage that lacks one code
class TestCollect(unittest.TestCase):
    KEY = "secret-key-123"
    ABERDEEN = dict(ABILENE, NAME="Aberdeen, SD Micro Area", B25064_001E="-666666666")
    CHICAGO = dict(ABILENE, NAME="Chicago-Naperville-Schaumburg, IL Metro Division", B25064_001E="1300")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.tmp.name)
        self.patches = [
            patch.object(acs, "OUT_DIR", self.out_dir),
            patch.object(acs, "OUT_FILE", self.out_dir / "metrics.csv"),
            patch.object(acs, "fetch", side_effect=self.fake_fetch),
            patch.dict(os.environ, {"CENSUS_API_KEY": self.KEY}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def fake_fetch(self, url, params=None, **kwargs):
        year = url.split("/data/")[1].split("/")[0]
        if "/variables/" in url:
            code = url.rsplit("/", 1)[-1][:-len(".json")]
            if year == "2014" and code == "B25070_011E":
                return response(404, b"<html>not found</html>", "text/html")
            return response(200, b"{}", "application/json")
        self.assertEqual(params["key"], self.KEY)
        codes = params["get"].split(",")
        if "in" in params:
            parent = params["in"].rsplit(":", 1)[1]
            if parent != "16980":
                return response(204, b"")
            division = "16974" if year == "2014" else "16984"
            table = [codes + [acs.MSA_COL, acs.DIV_COL], [self.CHICAGO[c] for c in codes] + ["16980", division]]
        else:
            table = [codes + [acs.MSA_COL],
                     [ABILENE[c] for c in codes] + ["10180"],
                     [self.ABERDEEN[c] for c in codes] + ["10100"]]
        return response(200, json.dumps(table).encode(), "application/json")

    def run_collect(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            path = acs.collect()
        return path, out.getvalue()

    def test_missing_key_raises_before_any_request(self):
        with patch.dict(os.environ, {"CENSUS_API_KEY": "  "}):
            with self.assertRaises(RuntimeError) as caught:
                acs.collect()
        self.assertIn("CENSUS_API_KEY", str(caught.exception))
        self.assertEqual(acs.fetch.call_count, 0)

    def test_metrics_csv_matches_the_contract(self):
        path, printed = self.run_collect()
        self.assertEqual(path, self.out_dir / "metrics.csv")
        df = pd.read_csv(path, dtype={"cbsa_code": str, "period": str})
        self.assertEqual(list(df.columns), acs.COLUMNS)
        abilene = df[(df.cbsa_code == "10180") & (df.period == "2024")]
        self.assertEqual(dict(zip(abilene.metric, abilene.value)),
                         {"commute_minutes": 20.0, "gross_rent": 950.0, "labor_force_rate": 0.65,
                          "poverty_rate": 0.15, "rent_burden": 0.408163, "vacancy_rate": 0.1})
        # 2014 lacks B25070_011E in the fake api, so rent_burden is null there only
        burden = df[df.metric == "rent_burden"]
        self.assertEqual(sorted(set(burden.period)), ["2019", "2024"])
        self.assertEqual(df.groupby("cbsa_code").size().to_dict(), {"10100": 14, "10180": 17, "16984": 17})
        self.assertNotIn("16974", set(df.cbsa_code))
        self.assertEqual(sorted(set(df[df.cbsa_code == "16984"].period)), ["2014", "2019", "2024"])
        self.assertNotIn("gross_rent", set(df[df.cbsa_code == "10100"].metric))
        self.assertIn("acs_extra_2014.csv", printed)
        self.assertIn("rent_burden will be null", printed)

    def test_raw_files_and_manifest(self):
        self.run_collect()
        for year in acs.VINTAGES:
            raw = pd.read_csv(self.out_dir / f"acs_extra_{year}.csv", dtype=str)
            self.assertEqual(raw.geo_code.tolist(), ["10180", "10100", "16984"])
            self.assertEqual(raw.year.tolist(), [str(year)] * 3)
            self.assertEqual("B25070_011E" in raw.columns, year != 2014)
        entries = json.loads((self.out_dir / "download_manifest.json").read_text())
        self.assertEqual([e["filename"] for e in entries],
                         ["metrics.csv", "acs_extra_2014.csv", "acs_extra_2019.csv", "acs_extra_2024.csv"])
        self.assertEqual(entries[0]["version"], "ACS 5-year 2014, 2019, 2024")
        self.assertEqual(entries[0]["integrity"]["row_count"], 48)
        self.assertEqual(entries[0]["notes"]["absent_variables"], {"2014": ["B25070_011E"]})
        self.assertEqual(entries[1]["version"], "ACS 5-year 2014")
        self.assertEqual(entries[1]["source"]["access_method"], "REST API")
        self.assertEqual(entries[1]["integrity"]["row_count"], 3)

    def test_key_never_lands_on_disk(self):
        self.run_collect()
        for path in self.out_dir.iterdir():
            self.assertNotIn(self.KEY, path.read_text())

    def test_builder_accepts_the_output(self):
        path, _ = self.run_collect()
        source = build_map_data.load_enrichment(path)
        self.assertEqual(source["name"], self.out_dir.name)
        self.assertEqual(source["metrics"], sorted(acs.METRICS))
        self.assertEqual(sorted(source["groups"]), ["10100", "10180", "16984"])
        self.assertEqual(build_map_data.enrichment_version(self.out_dir), "ACS 5-year 2014, 2019, 2024")


if __name__ == "__main__":
    unittest.main()
