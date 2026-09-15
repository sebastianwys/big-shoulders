import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from bot import build_map_data as bm

MERGED_COLS = [
    "place_id", "place_name", "hpi_type", "hpi_flavor", "yr", "avg_index_nsa",
    "quarters_available", "NAME", "median_income", "total_pop", "median_age",
    "bachelors_count", "masters_count", "total_occupied_units", "owner_occupied_units",
    "median_home_value", "cbsa_code", "year", "homeownership_rate",
]


def merged_row(cbsa, name, year, hpi, income, pop, age, bach, mast, occ, own, hv, rate):
    return [cbsa, name, "traditional", "all-transactions", year, hpi, 4, f"{name} Metro Area",
            income, pop, age, bach, mast, occ, own, hv, cbsa, year, rate]


# abilene is the clean base case. chicago is missing 2014, has zero income in
# 2019, a census sentinel in 2024 and needs the first-city zillow fallback.
# springfield has no zillow row. nowhere has no centroid
MERGED = [
    merged_row("10180", "Abilene, TX", 2014, 100.0, 40000, 100000, 30.0, 10000, 2000, 50000, 30000, 80000, 0.6),
    merged_row("10180", "Abilene, TX", 2019, 125.0, 50000, 110000, 31.5, 12000, 3000, 52000, 31200, 110000, 0.6),
    merged_row("10180", "Abilene, TX", 2024, 150.0, 60000, 120000, 33.0, 15000, 3000, 55000, 34100, 150000, 0.62),
    merged_row("16980", "Chicago-Naperville-Elgin, IL-IN-WI", 2019, 140.0, 0, 9500000, 36.0, 1500000, 700000, 3500000, 2200000, 250000, ""),
    merged_row("16980", "Chicago-Naperville-Elgin, IL-IN-WI", 2024, 170.0, 80000, 9400000, -666666666, 1600000, 800000, 3600000, 2300000, 320000, 0.64),
    merged_row("44100", "Springfield, IL", 2014, 90.0, 50000, 200000, 38.0, 20000, 8000, 90000, 60000, 120000, 0.67),
    merged_row("44100", "Springfield, IL", 2019, 100.0, 55000, 205000, 39.0, 22000, 9000, 91000, 61000, 130000, 0.67),
    merged_row("44100", "Springfield, IL", 2024, 120.0, 60000, 208000, 40.0, 24000, 10000, 92000, 62000, 150000, 0.67),
    merged_row("99999", "Nowhere, ZZ", 2014, 100.0, 1, 1, 1, 1, 1, 1, 1, 1, 0.5),
]

CENTROIDS = pd.DataFrame({
    "cbsa_code": ["10180", "16980", "44100"],
    "name": ["Abilene, TX Metro Area", "Chicago-Naperville-Elgin, IL-IN-WI Metro Area", "Springfield, IL Metro Area"],
    "cbsa_type": [1, 1, 1],
    "land_sqmi": [2743.5, 7197.0, 868.0],
    "lat": [32.452022, 41.8, 39.8],
    "lon": [-99.718743, -87.9, -89.6],
})

ZILLOW_META = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName"]

ZHVI = pd.DataFrame(
    [[102001, 0, "United States", "country", None, 1, 1, 1, 1, 1, 1],
     [394297, 1, "Chicago, IL", "msa", "IL", 200000, 202000, 240000, 300000, None, 310000],
     [394299, 2, "Abilene, TX", "msa", "TX", 90000, 92000, 120000, 160000, None, 170000]],
    columns=ZILLOW_META + ["2014-01-31", "2014-02-28", "2019-01-31", "2024-01-31", "2024-02-29", "2026-07-31"],
)

ZORI = pd.DataFrame(
    [[102001, 0, "United States", "country", None, 1, 1, 1, 1],
     [394299, 2, "Abilene, TX", "msa", "TX", 1000, 1100, 1300, 1400]],
    columns=ZILLOW_META + ["2019-01-31", "2019-02-28", "2024-01-31", "2026-07-31"],
)

BLS = pd.DataFrame({
    "series_id": ["LAUMT481018000000003"] * 4,
    "cbsa_code": ["10180"] * 4,
    "year": [2019, 2024, 2025, 2025],
    "period": ["M13", "M13", "M03", "M02"],
    "value": [3.5, 3.4, 3.7, 3.9],
})

FRED = pd.DataFrame({
    "date": ["2014-01-02", "2014-01-09", "2019-01-03", "2024-01-04", "2024-01-11", "2026-09-10", "2026-09-17"],
    "value": [4.5, 4.3, 4.0, 6.6, 6.8, 6.76, None],
})


def write_fixtures(folder):
    folder = Path(folder)
    paths = {
        "merged": folder / "merged.csv",
        "centroids": folder / "centroids.csv",
        "zhvi": folder / "zhvi.csv",
        "zori": folder / "zori.csv",
        "bls": folder / "bls.csv",
        "fred": folder / "fred.csv",
    }
    pd.DataFrame(MERGED, columns=MERGED_COLS).to_csv(paths["merged"], index=False)
    CENTROIDS.to_csv(paths["centroids"], index=False)
    ZHVI.to_csv(paths["zhvi"], index=False)
    ZORI.to_csv(paths["zori"], index=False)
    BLS.to_csv(paths["bls"], index=False)
    FRED.to_csv(paths["fred"], index=False)
    return paths


class BuildCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = write_fixtures(self.tmp.name)

    def build(self, **overrides):
        paths = dict(self.paths)
        paths.update(overrides)
        out = bm.build(out_path=Path(self.tmp.name) / "metros.json", paths=paths)
        return json.loads(out.read_text())

    def metro(self, payload, cbsa):
        return next(m for m in payload["metros"] if m["cbsa"] == cbsa)


class TestBaseCases(BuildCase):
    def test_growth_ptir_and_degree_share_exact(self):
        abilene = self.metro(self.build(), "10180")
        self.assertEqual(abilene["growth"], {
            "hpi_14_19": 0.25, "hpi_19_24": 0.2, "income_14_24": 0.5,
            "pop_14_24": 0.2, "home_value_14_24": 0.875,
        })
        self.assertEqual(abilene["ptir"], {"2014": 2.0, "2019": 2.2, "2024": 2.5})
        self.assertEqual([abilene["years"][y]["degree_share"] for y in ("2014", "2019", "2024")], [0.12, 0.1364, 0.15])
        self.assertEqual(abilene["years"]["2024"]["own_rate"], 0.62)
        self.assertEqual(abilene["years"]["2014"]["pop"], 100000)
        self.assertEqual(abilene["lat"], 32.452022)

    def test_zillow_exact_match_and_annual_mean(self):
        abilene = self.metro(self.build(), "10180")
        self.assertEqual(abilene["years"]["2014"]["zhvi"], 91000.0)
        self.assertEqual(abilene["years"]["2019"]["zhvi"], 120000.0)
        # the null february month is skipped, not averaged as zero
        self.assertEqual(abilene["years"]["2024"]["zhvi"], 160000.0)
        self.assertEqual(abilene["latest"]["zhvi"], 170000.0)
        self.assertEqual(abilene["latest"]["zhvi_date"], "2026-07-31")
        # zori starts in 2015 so 2014 is null
        self.assertIsNone(abilene["years"]["2014"]["zori"])
        self.assertEqual(abilene["years"]["2019"]["zori"], 1050.0)

    def test_zillow_first_city_fallback(self):
        chicago = self.metro(self.build(), "16980")
        self.assertEqual(chicago["years"]["2014"]["zhvi"], 201000.0)
        self.assertEqual(chicago["latest"]["zhvi"], 310000.0)

    def test_bls_annual_versus_newest_month(self):
        abilene = self.metro(self.build(), "10180")
        self.assertIsNone(abilene["years"]["2014"]["unemp"])
        self.assertEqual(abilene["years"]["2019"]["unemp"], 3.5)
        self.assertEqual(abilene["years"]["2024"]["unemp"], 3.4)
        self.assertEqual(abilene["latest"]["unemp"], 3.7)
        self.assertEqual(abilene["latest"]["unemp_date"], "2025-03")

    def test_fred_annual_mean_and_latest(self):
        payload = self.build()
        self.assertEqual(payload["national"]["mortgage_rate"], {
            "2014": 4.4, "2019": 4.0, "2024": 6.7, "latest": 6.76, "latest_date": "2026-09-10",
        })
        self.assertEqual(payload["sources"], {
            "gazetteer": "2024 Gazetteer", "zillow": "through 2026-07-31",
            "bls": "2019 onward", "fred": "through 2026-09-10",
        })


class TestEdgeCases(BuildCase):
    def test_missing_optional_files_still_build(self):
        gone = Path(self.tmp.name) / "gone.csv"
        payload = self.build(zhvi=gone, zori=gone, bls=gone, fred=gone)
        abilene = self.metro(payload, "10180")
        self.assertIsNone(payload["national"])
        self.assertEqual(payload["sources"]["zillow"], None)
        self.assertEqual(payload["sources"]["bls"], None)
        self.assertEqual(payload["sources"]["fred"], None)
        self.assertIsNone(abilene["years"]["2019"]["zhvi"])
        self.assertIsNone(abilene["years"]["2019"]["unemp"])
        self.assertEqual(abilene["latest"], {"zhvi": None, "zhvi_date": None, "zori": None,
                                             "zori_date": None, "unemp": None, "unemp_date": None})
        # the required inputs still produce the census side
        self.assertEqual(abilene["ptir"]["2024"], 2.5)

    def test_metro_missing_a_year_gives_null_growth_for_that_pair(self):
        chicago = self.metro(self.build(), "16980")
        self.assertIsNone(chicago["growth"]["hpi_14_19"])
        self.assertIsNone(chicago["growth"]["income_14_24"])
        self.assertEqual(chicago["growth"]["hpi_19_24"], 0.2143)
        # the missing year is present with nulls, not absent
        self.assertIsNone(chicago["years"]["2014"]["hpi"])
        self.assertIn("2014", chicago["ptir"])

    def test_zero_income_gives_null_ptir(self):
        chicago = self.metro(self.build(), "16980")
        self.assertIsNone(chicago["ptir"]["2019"])
        self.assertEqual(chicago["ptir"]["2024"], 4.0)

    def test_census_sentinel_becomes_null(self):
        chicago = self.metro(self.build(), "16980")
        self.assertIsNone(chicago["years"]["2024"]["age"])
        self.assertEqual(chicago["years"]["2019"]["age"], 36.0)

    def test_blank_ownership_rate_falls_back_to_the_counts(self):
        chicago = self.metro(self.build(), "16980")
        self.assertEqual(chicago["years"]["2019"]["own_rate"], 0.6286)

    def test_all_null_zillow_months(self):
        row = pd.Series([None, None], index=["2024-01-31", "2024-02-29"], dtype="float64")
        self.assertIsNone(bm.zillow_annual(row, 2024))
        self.assertEqual(bm.zillow_latest(row), (None, None))

    def test_metro_without_centroid_is_dropped(self):
        payload = self.build()
        self.assertEqual([m["cbsa"] for m in payload["metros"]], ["10180", "16980", "44100"])

    def test_unmatched_zillow_name_gives_nulls(self):
        springfield = self.metro(self.build(), "44100")
        self.assertIsNone(springfield["years"]["2024"]["zhvi"])
        self.assertIsNone(springfield["latest"]["zhvi"])
        self.assertEqual(springfield["ptir"]["2024"], 2.5)

    def test_output_shape_and_sort_order(self):
        payload = self.build()
        self.assertEqual(list(payload), ["generated_at", "years", "sources", "national", "metros"])
        self.assertEqual(payload["years"], [2014, 2019, 2024])
        names = [m["name"] for m in payload["metros"]]
        self.assertEqual(names, sorted(names))
        metro = payload["metros"][0]
        self.assertEqual(list(metro), ["cbsa", "name", "level", "parent", "zillow_scope", "lat", "lon", "years", "latest", "growth", "ptir"])
        self.assertEqual(list(metro["years"]), ["2014", "2019", "2024"])
        self.assertEqual(list(metro["years"]["2014"]), ["hpi", "income", "pop", "age", "degree_share",
                                                        "own_rate", "home_value", "zhvi", "zori", "unemp"])
        self.assertEqual(list(metro["latest"]), ["zhvi", "zhvi_date", "zori", "zori_date", "unemp", "unemp_date"])
        self.assertEqual(list(metro["growth"]), ["hpi_14_19", "hpi_19_24", "income_14_24", "pop_14_24", "home_value_14_24"])
        self.assertEqual(list(metro["ptir"]), ["2014", "2019", "2024"])
        # the file is plain ascii json with no nan tokens
        text = (Path(self.tmp.name) / "metros.json").read_text()
        self.assertTrue(text.isascii())
        self.assertNotIn("NaN", text)


class TestHelpers(unittest.TestCase):
    def test_zillow_candidates_order_and_dedupe(self):
        self.assertEqual(bm.zillow_candidates("Chicago-Naperville-Elgin, IL-IN-WI"),
                         ["Chicago-Naperville-Elgin, IL-IN-WI", "Chicago, IL",
                          "Chicago-Naperville, IL", "Naperville, IL", "Elgin, IL"])
        self.assertEqual(bm.zillow_candidates("Abilene, TX"), ["Abilene, TX"])
        self.assertEqual(bm.zillow_candidates("Winston-Salem, NC"),
                         ["Winston-Salem, NC", "Winston, NC", "Salem, NC"])

    # a slash separates city and county; zillow keeps only the city
    def test_zillow_candidates_slash_county(self):
        self.assertIn("Louisville, KY", bm.zillow_candidates("Louisville/Jefferson County, KY-IN"))

    # zillow can name the metro by a later city, tried after the first
    def test_zillow_candidates_later_city(self):
        cands = bm.zillow_candidates("Wildwood-The Villages, FL")
        self.assertIn("The Villages, FL", cands)
        self.assertLess(cands.index("Wildwood, FL"), cands.index("The Villages, FL"))

    def test_growth_and_ratio_guards(self):
        self.assertIsNone(bm.growth(10, 0))
        self.assertIsNone(bm.growth(None, 5))
        self.assertIsNone(bm.growth(float("nan"), 5))
        self.assertEqual(bm.growth(15, 10), 0.5)
        self.assertIsNone(bm.ratio(5, 0))
        self.assertEqual(bm.ratio(5, 2), 2.5)

    def test_bls_latest_orders_by_year_then_period(self):
        frame = pd.DataFrame({
            "series_id": ["x"] * 3, "cbsa_code": ["10180"] * 3,
            "year": [2025, 2024, 2025], "period": ["M02", "M12", "M03"], "value": [3.9, 3.1, 3.7],
        })
        self.assertEqual(bm.bls_latest(frame, "10180"), (3.7, "2025-03"))
        self.assertEqual(bm.bls_latest(frame, "00000"), (None, None))

    def test_fred_latest_skips_trailing_null(self):
        frame = pd.DataFrame({"date": ["2026-09-10", "2026-09-17"], "value": [6.76, None]})
        self.assertEqual(bm.fred_latest(frame), (6.76, "2026-09-10"))
        self.assertEqual(bm.fred_annual(frame, 2026), 6.76)
        self.assertIsNone(bm.fred_annual(frame, 2014))

    def test_rounding_helpers(self):
        self.assertIsNone(bm.rnd(None, 2))
        self.assertIsNone(bm.rnd(float("nan"), 2))
        self.assertEqual(bm.rnd(1.23456, 2), 1.23)
        self.assertEqual(bm.as_int(167171.0), 167171)


if __name__ == "__main__":
    unittest.main()


class TestDivisions(unittest.TestCase):
    def frames(self):
        merged = pd.DataFrame({
            "cbsa_code": ["16984", "16984", "10180"],
            "place_name": ["Chicago-Naperville-Schaumburg, IL (MSAD)"] * 2 + ["Abilene, TX"],
            "year": [2019, 2024, 2024],
            "avg_index_nsa": [200.0, 260.0, 335.5],
            "median_income": [80000, 90000, 50000],
            "total_pop": [7000000, 7100000, 170000],
            "median_home_value": [300000, 340000, 130000],
            "geo_level": ["division", "division", "msa"],
            "parent_cbsa": ["16980", "16980", None],
        })
        centroids = pd.DataFrame({
            "cbsa_code": ["16980", "16984", "10180"],
            "name": ["Chicago-Naperville-Elgin, IL-IN Metro Area", "Chicago-Naperville-Schaumburg, IL Metro Division", "Abilene, TX Metro Area"],
            "lat": [41.8, 41.85, 32.45], "lon": [-87.9, -87.95, -99.7],
        }).set_index("cbsa_code")
        zhvi = pd.DataFrame({"2024-06-30": [400000.0, 210000.0]}, index=pd.Index(["Chicago, IL", "Abilene, TX"], name="RegionName"))
        return merged, centroids, zhvi

    def test_division_carries_level_parent_and_clean_name(self):
        merged, centroids, zhvi = self.frames()
        metros, _, _ = bm.build_metros(merged, centroids, zhvi=zhvi)
        chi = next(m for m in metros if m["cbsa"] == "16984")
        self.assertEqual(chi["name"], "Chicago-Naperville-Schaumburg, IL")
        self.assertEqual(chi["level"], "division")
        self.assertEqual(chi["parent"], {"cbsa": "16980", "name": "Chicago-Naperville-Elgin, IL-IN"})

    # zillow has no divisions, so the parent metro's value is used and labeled
    def test_division_takes_zillow_from_parent(self):
        merged, centroids, zhvi = self.frames()
        metros, _, unmatched = bm.build_metros(merged, centroids, zhvi=zhvi)
        chi = next(m for m in metros if m["cbsa"] == "16984")
        self.assertEqual(chi["latest"]["zhvi"], 400000.0)
        self.assertEqual(chi["zillow_scope"], "parent metro")
        self.assertEqual(unmatched, 0)

    def test_msa_is_unchanged(self):
        merged, centroids, zhvi = self.frames()
        metros, _, _ = bm.build_metros(merged, centroids, zhvi=zhvi)
        abi = next(m for m in metros if m["cbsa"] == "10180")
        self.assertEqual((abi["level"], abi["parent"], abi["zillow_scope"]), ("msa", None, "metro"))

    # a division whose parent is unknown must not fall through to a metro with
    # the same name, so it gets no zillow values at all
    def test_division_without_parent_gets_no_zillow(self):
        merged, centroids, zhvi = self.frames()
        merged.loc[merged.cbsa_code == "16984", "parent_cbsa"] = "00000"
        metros, _, _ = bm.build_metros(merged, centroids, zhvi=zhvi)
        chi = next(m for m in metros if m["cbsa"] == "16984")
        self.assertIsNone(chi["parent"])
        self.assertIsNone(chi["latest"]["zhvi"])
        self.assertIsNone(chi["zillow_scope"])

    def test_display_name_strips_only_the_suffix(self):
        self.assertEqual(bm.display_name("Boston, MA (MSAD)"), "Boston, MA")
        self.assertEqual(bm.display_name("Abilene, TX"), "Abilene, TX")
