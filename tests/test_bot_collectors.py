import unittest

import numpy as np
import pandas as pd

from bot.collectors import bls, fred, gazetteer

GAZ_TEXT = (
    "CSAFP\tGEOID\tNAME\tCBSA_TYPE\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG        \n"
    "101\t10180\tAbilene, TX Metro Area\t1\t7105669751\t36754978\t2743.515\t14.191\t32.452022\t-99.718743        \n"
    "\t10100\tAberdeen, SD Micro Area\t2\t1\t1\t1.0\t0.0\t45.5\t-98.5        \n"
)

# blank lines, a hyphenated multi-state name, puerto rico with no csa, all
# with the trailing spaces the real file carries
GAZ_EDGE_TEXT = (
    "CSAFP\tGEOID\tNAME\tCBSA_TYPE\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG        \n"
    "\n"
    "176\t16980\tChicago-Naperville-Elgin, IL-IN-WI Metro Area\t1\t1\t1\t1.0\t0.0\t41.8\t-87.9        \n"
    "   \n"
    "\t41980\tSan Juan-Bayamon-Caguas, PR Metro Area\t1\t1\t1\t1.0\t0.0\t18.3\t-66.1        \n"
    "\t10100\tAberdeen, SD Micro Area\t2\t1\t1\t1.0\t0.0\t45.5\t-98.5        \n"
)


class TestGazetteer(unittest.TestCase):
    # trailing spaces on every line are the trap in this file
    def test_parse_strips_and_types(self):
        df = gazetteer.parse_gazetteer(GAZ_TEXT)
        self.assertEqual(list(df.columns), ["cbsa_code", "name", "cbsa_type", "land_sqmi", "lat", "lon"])
        abilene = df[df.cbsa_code == "10180"].iloc[0]
        self.assertEqual(abilene["name"], "Abilene, TX Metro Area")
        self.assertAlmostEqual(abilene["lon"], -99.718743)
        self.assertEqual(int(abilene["cbsa_type"]), 1)

    def test_micro_areas_kept_with_type_two(self):
        df = gazetteer.parse_gazetteer(GAZ_TEXT)
        self.assertEqual(df[df.cbsa_code == "10100"].iloc[0]["cbsa_type"], 2)

    def test_header_trailing_whitespace_does_not_leak_into_columns(self):
        df = gazetteer.parse_gazetteer(GAZ_TEXT)
        self.assertFalse(any(c != c.strip() for c in df.columns))
        self.assertEqual(len(df), 2)

    def test_blank_lines_in_the_middle_are_skipped(self):
        df = gazetteer.parse_gazetteer(GAZ_EDGE_TEXT)
        self.assertEqual(df.cbsa_code.tolist(), ["16980", "41980", "10100"])

    def test_name_keeps_hyphens_and_comma(self):
        df = gazetteer.parse_gazetteer(GAZ_EDGE_TEXT)
        self.assertEqual(df[df.cbsa_code == "16980"].iloc[0]["name"],
                         "Chicago-Naperville-Elgin, IL-IN-WI Metro Area")

    def test_puerto_rico_row_without_csa(self):
        df = gazetteer.parse_gazetteer(GAZ_EDGE_TEXT)
        pr = df[df.cbsa_code == "41980"].iloc[0]
        self.assertEqual(pr["name"], "San Juan-Bayamon-Caguas, PR Metro Area")
        self.assertAlmostEqual(pr["lat"], 18.3)

    # every us metro is in the western hemisphere, and nothing is off the globe
    def test_longitudes_are_negative_and_on_the_globe(self):
        df = gazetteer.parse_gazetteer(GAZ_EDGE_TEXT)
        self.assertTrue((df.lon < 0).all())
        self.assertTrue(df.lon.between(-180, 180).all())
        self.assertTrue(df.lat.between(-90, 90).all())

    def test_cbsa_type_is_int_for_every_row(self):
        df = gazetteer.parse_gazetteer(GAZ_EDGE_TEXT)
        self.assertEqual(df.cbsa_type.dtype.kind, "i")
        for value in df.cbsa_type:
            self.assertIsInstance(value, (int, np.integer))


class TestBls(unittest.TestCase):
    # verified live: these three ids return data
    def test_series_id_matches_bls_scheme(self):
        self.assertEqual(bls.series_id("10180", "TX"), "LAUMT481018000000003")
        self.assertEqual(bls.series_id("16980", "IL"), "LAUMT171698000000003")
        self.assertEqual(bls.series_id("28140", "MO"), "LAUMT292814000000003")

    def test_series_id_is_always_twenty_chars(self):
        for code, state in (("10180", "TX"), ("16980", "IL"), ("41980", "PR"), ("10100", "SD")):
            self.assertEqual(len(bls.series_id(code, state)), 20)

    def test_series_id_zero_pads_state_fips(self):
        self.assertTrue(bls.series_id("10180", "AL").startswith("LAUMT01"))
        self.assertTrue(bls.series_id("10180", "AK").startswith("LAUMT02"))

    # an unknown abbreviation is a data problem, so a loud KeyError is intended
    def test_unknown_state_raises(self):
        with self.assertRaises(KeyError):
            bls.series_id("10180", "XX")

    def test_primary_state_is_the_first_listed(self):
        self.assertEqual(bls.primary_state("Chicago-Naperville-Elgin, IL-IN-WI Metro Area"), "IL")
        self.assertEqual(bls.primary_state("Abilene, TX Metro Area"), "TX")
        self.assertEqual(bls.primary_state("Washington-Arlington-Alexandria, DC-VA-MD-WV Metro Area"), "DC")

    def test_primary_state_puerto_rico_and_micro(self):
        self.assertEqual(bls.primary_state("San Juan-Bayamon-Caguas, PR Metro Area"), "PR")
        self.assertEqual(bls.primary_state("Aberdeen, SD Micro Area"), "SD")

    def test_parse_keeps_annual_and_newest_month(self):
        series = [{"seriesID": "LAUMT481018000000003", "data": [
            {"year": "2024", "period": "M13", "value": "3.4"},
            {"year": "2024", "period": "M12", "value": "3.1"},
            {"year": "2025", "period": "M03", "value": "3.7"},
            {"year": "2025", "period": "M02", "value": "3.9"},
        ]}]
        df = bls.parse_series(series)
        self.assertEqual(df.cbsa_code.tolist(), ["10180", "10180"])
        self.assertEqual(df[df.period == "M13"].value.iloc[0], 3.4)
        newest = df[df.period != "M13"].iloc[0]
        self.assertEqual((newest.year, newest.period, newest.value), (2025, "M03", 3.7))

    def test_parse_empty_series(self):
        df = bls.parse_series([{"seriesID": "LAUMT481018000000003", "data": []}])
        self.assertEqual(len(df), 0)

    # bls reports a suppressed value as a dash. it lands as a missing float
    def test_dash_value_is_missing(self):
        df = bls.parse_series([{"seriesID": "LAUMT481018000000003", "data": [
            {"year": "2024", "period": "M06", "value": "-"},
        ]}])
        self.assertEqual(len(df), 1)
        self.assertTrue(pd.isna(df.value.iloc[0]))

    def test_only_annual_rows_yield_no_newest_month(self):
        df = bls.parse_series([{"seriesID": "LAUMT481018000000003", "data": [
            {"year": "2023", "period": "M13", "value": "3.4"},
            {"year": "2024", "period": "M13", "value": "3.5"},
        ]}])
        self.assertEqual(df.period.tolist(), ["M13", "M13"])

    # the newest month can sit in the same year as the last annual average
    def test_newest_month_when_months_stop_mid_year(self):
        df = bls.parse_series([{"seriesID": "LAUMT481018000000003", "data": [
            {"year": "2024", "period": "M13", "value": "3.4"},
            {"year": "2024", "period": "M06", "value": "3.2"},
            {"year": "2024", "period": "M05", "value": "3.0"},
            {"year": "2023", "period": "M12", "value": "2.9"},
        ]}])
        newest = df[df.period != "M13"]
        self.assertEqual(len(newest), 1)
        self.assertEqual((newest.year.iloc[0], newest.period.iloc[0]), (2024, "M06"))

    def test_multiple_series_keep_their_own_cbsa_codes(self):
        df = bls.parse_series([
            {"seriesID": "LAUMT481018000000003", "data": [{"year": "2024", "period": "M13", "value": "3.4"}]},
            {"seriesID": "LAUMT171698000000003", "data": [{"year": "2024", "period": "M13", "value": "5.1"}]},
        ])
        self.assertEqual(dict(zip(df.cbsa_code, df.value)), {"10180": 3.4, "16980": 5.1})

    def test_empty_payload_has_the_documented_columns(self):
        df = bls.parse_series([])
        self.assertEqual(list(df.columns), ["series_id", "cbsa_code", "year", "period", "value"])
        self.assertEqual(len(df), 0)


class TestFred(unittest.TestCase):
    # fred marks missing weeks with a dot
    def test_dot_becomes_nan(self):
        df = fred.parse_observations([
            {"date": "2014-01-02", "value": "4.53"},
            {"date": "2014-01-09", "value": "."},
        ])
        self.assertEqual(df.value.iloc[0], 4.53)
        self.assertTrue(df.value.isna().iloc[1])

    def test_all_dots_gives_all_nan(self):
        df = fred.parse_observations([
            {"date": "2014-01-02", "value": "."},
            {"date": "2014-01-09", "value": "."},
        ])
        self.assertTrue(df.value.isna().all())
        self.assertEqual(len(df), 2)

    def test_values_are_numeric_dtype(self):
        df = fred.parse_observations([{"date": "2014-01-02", "value": "4.53"}])
        self.assertEqual(df.value.dtype.kind, "f")

    # an empty observation list currently raises KeyError inside the column
    # selection. documented here rather than fixed, see the report
    # an empty response still yields the two column frame, never a KeyError
    def test_empty_observations(self):
        df = fred.parse_observations([])
        self.assertEqual(list(df.columns), ["date", "value"])
        self.assertEqual(len(df), 0)


class TestZillowNewestMonth(unittest.TestCase):
    # zillow has no pure parser. this mirrors the header logic in collect()
    @staticmethod
    def newest_month(raw):
        header = raw.split(b"\n", 1)[0].decode()
        return header.rsplit(",", 1)[-1].strip(), raw.count(b"\n") - 1

    def test_newline_header(self):
        month, rows = self.newest_month(b"RegionID,RegionName,2026-06-30,2026-07-31\n10,x,1,2\n")
        self.assertEqual((month, rows), ("2026-07-31", 1))

    def test_carriage_return_header(self):
        month, rows = self.newest_month(b"RegionID,RegionName,2026-07-31\r\n10,x,1\r\n")
        self.assertEqual((month, rows), ("2026-07-31", 1))


if __name__ == "__main__":
    unittest.main()
